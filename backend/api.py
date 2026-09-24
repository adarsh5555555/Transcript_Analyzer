"""FastAPI routes. A thin layer: validation, caching and HTTP; the logic is in core/."""

import hashlib
import logging
import re
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .core import analyzer
from .core.llm import LLM
from .core.parser import ParseError, parse_guide, parse_transcripts
from .core.schemas import AnalysisResult, AskRequest, AskResult

log = logging.getLogger("uvicorn.error")

app = FastAPI(title="Hasamex Transcript Analyzer")
app.add_middleware(CORSMiddleware, allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
                   allow_methods=["*"], allow_headers=["*"])

llm = LLM(config.OPENAI_MODEL)
# analysis_id -> result. Results are also written to .cache/ so a restart (or
# re-uploading the same files) costs nothing. At 30+ transcripts: Redis/Postgres.
analyses: dict[str, AnalysisResult] = {}

# --- protection for public deploys -------------------------------------------
# A shared passcode plus a per-IP hourly cap: the model calls cost real money, so
# a public URL should not be an open tap. Both are off unless configured.
_hits: dict[str, deque[float]] = defaultdict(deque)


def check_passcode(x_passcode: str | None = Header(default=None)):
    if config.APP_PASSCODE and not secrets.compare_digest(x_passcode or "", config.APP_PASSCODE):
        raise HTTPException(401, "wrong or missing passcode")


def rate_limit(request: Request, bucket: str, per_hour: int):
    key = f"{bucket}:{request.client.host if request.client else 'unknown'}"
    now = time.time()
    hits = _hits[key]
    while hits and now - hits[0] > 3600:
        hits.popleft()
    if len(hits) >= per_hour:
        raise HTTPException(429, f"rate limit reached ({per_hour}/hour); try again later")
    hits.append(now)


def _read_sample(name: str) -> str:
    return (config.DATA_DIR / name).read_text(encoding="utf-8")


async def _read_upload(f: UploadFile) -> str:
    name = f.filename or "upload"
    if not name.lower().endswith(".txt"):
        raise HTTPException(422, f"{name}: only .txt files are supported")
    raw = await f.read(config.MAX_FILE_BYTES + 1)
    if len(raw) > config.MAX_FILE_BYTES:
        raise HTTPException(422, f"{name}: larger than {config.MAX_FILE_BYTES // 1000} KB")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(422, f"{name}: not UTF-8 text")


def _analysis_id(guide_text: str, files: list[tuple[str, str]]) -> str:
    h = hashlib.sha256(f"{config.PIPELINE_VERSION}|{config.OPENAI_MODEL}".encode())
    h.update(guide_text.encode())
    for name, text in files:
        h.update(name.encode() + b"\0" + text.encode() + b"\0")
    return h.hexdigest()[:16]


def _cache_path(analysis_id: str) -> Path:
    return config.CACHE_DIR / f"analysis_{analysis_id}.json"


def _load(analysis_id: str) -> AnalysisResult | None:
    if not re.fullmatch(r"[0-9a-f]{16}", analysis_id):   # it becomes a file path
        return None
    if analysis_id in analyses:
        return analyses[analysis_id]
    for path in (_cache_path(analysis_id), config.SEED_CACHE_DIR / f"analysis_{analysis_id}.json"):
        if path.exists():
            analyses[analysis_id] = AnalysisResult.model_validate_json(path.read_text())
            return analyses[analysis_id]
    return None


@app.get("/api/health")
def health():
    return {"status": "ok", "model": config.OPENAI_MODEL,
            "passcode_required": bool(config.APP_PASSCODE)}


@app.get("/api/samples")
def samples():
    return {
        "guide": {"filename": config.SAMPLE_GUIDE, "text": _read_sample(config.SAMPLE_GUIDE)},
        "transcripts": [{"filename": n, "text": _read_sample(n)} for n in config.SAMPLE_TRANSCRIPTS],
    }


@app.post("/api/analyze", response_model=AnalysisResult)
async def analyze(
    request: Request,
    files: list[UploadFile] = File(default=[]),
    guide: UploadFile | None = File(default=None),
    use_samples: bool = Form(default=False),
    refresh: bool = Form(default=False),
    x_passcode: str | None = Header(default=None),
):
    check_passcode(x_passcode)
    rate_limit(request, "analyze", config.ANALYSES_PER_HOUR)
    if use_samples:
        texts = [(n, _read_sample(n)) for n in config.SAMPLE_TRANSCRIPTS]
    else:
        if not files:
            raise HTTPException(422, "upload at least one transcript (.txt) or use the samples")
        if len(files) > config.MAX_FILES:
            raise HTTPException(422, f"at most {config.MAX_FILES} transcripts per analysis")
        texts = [(f.filename or f"transcript_{i}.txt", await _read_upload(f))
                 for i, f in enumerate(files, start=1)]
    # The sample guide belongs to the sample transcripts only. Own transcripts without a
    # guide get flagged questions, themes and chat, but no per-question table.
    if guide:
        guide_text, guide_name = await _read_upload(guide), guide.filename or "guide.txt"
    elif use_samples:
        guide_text, guide_name = _read_sample(config.SAMPLE_GUIDE), config.SAMPLE_GUIDE
    else:
        guide_text, guide_name = "", None

    try:
        transcripts = parse_transcripts(texts)
        parsed_guide = parse_guide(guide_text, guide_name) if guide_name else None
    except ParseError as e:
        raise HTTPException(422, str(e))

    analysis_id = _analysis_id(guide_text, texts)
    cached = None if refresh else _load(analysis_id)
    log.info("analyze %s: transcripts=%s guide=%s (%d questions) %s", analysis_id,
             [n for n, _ in texts], guide_name, len(parsed_guide.questions) if parsed_guide else 0,
             "cache hit" if cached else "running model")
    if cached:
        return cached

    try:
        hot, answers, synthesis, stats = await analyzer.analyse(llm, transcripts, parsed_guide)
    except Exception as e:
        raise HTTPException(502, f"model call failed: {e}")

    result = AnalysisResult(
        analysis_id=analysis_id, model=config.OPENAI_MODEL, guide=parsed_guide,
        transcripts=transcripts, hot_questions=hot, answers=answers, synthesis=synthesis,
        stats=stats)
    analyses[analysis_id] = result
    try:
        config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(analysis_id).write_text(result.model_dump_json())
    except OSError as e:          # read-only filesystem on some hosts: caching is optional
        log.warning("could not write cache: %s", e)
    return result


@app.post("/api/ask", response_model=AskResult)
async def ask(req: AskRequest, request: Request, x_passcode: str | None = Header(default=None)):
    check_passcode(x_passcode)
    rate_limit(request, "ask", config.QUESTIONS_PER_HOUR)
    question = req.question.strip()
    if not question:
        raise HTTPException(422, "question is empty")
    if len(question) > 1000:
        raise HTTPException(422, "question is too long (max 1000 characters)")
    if req.transcripts:              # stateless path (serverless)
        transcripts = req.transcripts
    else:                            # stateful path (long-running server)
        result = _load(req.analysis_id)
        if result is None:
            raise HTTPException(404, "unknown analysis_id; run /api/analyze first")
        transcripts = result.transcripts
    try:
        return await analyzer.ask(llm, transcripts, question, req.history)
    except Exception as e:
        raise HTTPException(502, f"model call failed: {e}")


# Serve the built React app from the same server when it exists (npm run build).
if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        return FileResponse(config.FRONTEND_DIST / "index.html")
