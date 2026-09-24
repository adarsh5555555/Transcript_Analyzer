"""FastAPI routes. A thin layer: validation, caching and HTTP; the logic is in core/."""

import hashlib
import logging
import re
import secrets
import time
from collections import defaultdict, deque
from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .core import analyzer
from .core.llm import LLM
from .core.parser import ParseError, parse_guide, parse_transcripts
from .core.schemas import AnalysisResult, AskRequest, AskResult
from .core.store import build_store

log = logging.getLogger("uvicorn.error")

app = FastAPI(title="Hasamex Transcript Analyzer")
app.add_middleware(CORSMiddleware, allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
                   allow_methods=["*"], allow_headers=["*"])

llm = LLM(config.OPENAI_MODEL)
# Postgres when DATABASE_URL is set, JSON files otherwise. Keyed by the content
# hash, so the store is also the cache: the same files never cost a second run.
store = build_store(config.DATABASE_URL, config.CACHE_DIR, config.SEED_CACHE_DIR)


@app.on_event("shutdown")
async def _close_store():
    await store.close()

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


async def _load(analysis_id: str) -> AnalysisResult | None:
    if not re.fullmatch(r"[0-9a-f]{16}", analysis_id):   # it can become a file path
        return None
    return await store.get(analysis_id)


@app.get("/api/health")
def health():
    return {"status": "ok", "model": config.OPENAI_MODEL, "store": store.kind,
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
    cached = None if refresh else await _load(analysis_id)
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
    await store.put(result)
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
    result = await _load(req.analysis_id)
    if result is not None:
        transcripts = result.transcripts
    elif req.transcripts:            # fallback when no shared store is configured
        transcripts = req.transcripts
    else:
        raise HTTPException(404, "unknown analysis_id; run /api/analyze first")
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
