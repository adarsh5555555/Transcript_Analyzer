"""Where analyses live.

Two backends behind one interface:

- Postgres (when DATABASE_URL is set): the real one. Works on serverless, where
  each request may hit a different instance with no shared memory, and survives
  restarts so a link can be reopened later.
- JSON files (otherwise): zero-setup local development and the sample analysis
  that ships with the repo.

The row is keyed by the analysis id, which is a hash of the inputs, so the store
doubles as the cache: the same files never cost a second model run. `owner_id` is
where per-user scoping plugs in once there is auth; it is unused for now.
"""

import json
import logging
from pathlib import Path

from .schemas import AnalysisResult

log = logging.getLogger("uvicorn.error")

SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    id          text PRIMARY KEY,
    model       text NOT NULL,
    owner_id    text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    payload     jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS analyses_created_at_idx ON analyses (created_at DESC);
"""


class Store:
    async def get(self, analysis_id: str) -> AnalysisResult | None: ...
    async def put(self, result: AnalysisResult) -> None: ...
    async def close(self) -> None: ...

    @property
    def kind(self) -> str: ...


class FileStore(Store):
    """Local development: one JSON file per analysis, plus a read-only seed dir."""

    def __init__(self, cache_dir: Path, seed_dir: Path):
        self.cache_dir = cache_dir
        self.seed_dir = seed_dir
        self._memory: dict[str, AnalysisResult] = {}

    @property
    def kind(self) -> str:
        return "files"

    def _paths(self, analysis_id: str) -> list[Path]:
        name = f"analysis_{analysis_id}.json"
        return [self.cache_dir / name, self.seed_dir / name]

    async def get(self, analysis_id: str) -> AnalysisResult | None:
        if analysis_id in self._memory:
            return self._memory[analysis_id]
        for path in self._paths(analysis_id):
            if path.exists():
                self._memory[analysis_id] = AnalysisResult.model_validate_json(path.read_text())
                return self._memory[analysis_id]
        return None

    async def put(self, result: AnalysisResult) -> None:
        self._memory[result.analysis_id] = result
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._paths(result.analysis_id)[0].write_text(result.model_dump_json())
        except OSError as e:   # read-only filesystem: caching is an optimisation, not a requirement
            log.warning("could not write cache file: %s", e)

    async def close(self) -> None:
        pass


class PostgresStore(Store):
    """Production: a row per analysis. Pool kept small because serverless instances
    are many and short-lived; point DATABASE_URL at a pooled endpoint."""

    def __init__(self, dsn: str, min_size: int = 0, max_size: int = 4):
        self.dsn = dsn
        self._pool = None
        self._min, self._max = min_size, max_size

    @property
    def kind(self) -> str:
        return "postgres"

    async def _get_pool(self):
        if self._pool is None:
            import asyncpg
            self._pool = await asyncpg.create_pool(self.dsn, min_size=self._min, max_size=self._max)
            async with self._pool.acquire() as conn:
                await conn.execute(SCHEMA)
        return self._pool

    async def get(self, analysis_id: str) -> AnalysisResult | None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchval("SELECT payload FROM analyses WHERE id = $1", analysis_id)
        return AnalysisResult.model_validate_json(row) if row else None

    async def put(self, result: AnalysisResult) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO analyses (id, model, payload) VALUES ($1, $2, $3::jsonb)
                   ON CONFLICT (id) DO UPDATE SET payload = EXCLUDED.payload, model = EXCLUDED.model""",
                result.analysis_id, result.model, result.model_dump_json())

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


def build_store(database_url: str, cache_dir: Path, seed_dir: Path) -> Store:
    if database_url:
        return PostgresStore(database_url)
    return FileStore(cache_dir, seed_dir)
