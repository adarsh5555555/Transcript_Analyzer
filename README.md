---
title: Transcript Analyzer
emoji: 🎙️
colorFrom: purple
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: Answers from call transcripts, with verified quotes and timestamps
---

# Transcript Analyzer

Upload expert-call transcripts. The app flags the 2–3 questions that matter most, answers each interview-guide question per expert with exact quotes and timestamps, shows where the experts agree and disagree, and lets you chat with the transcripts. Every quote, in every section, is checked in code against the transcript before it is shown.

The interview guide is optional. Without one you get flagged questions, themes and chat; with one you also get the per-question table. The bundled sample guide is only used with the bundled sample transcripts.

## Run it locally

Requirements: Python 3.11+, Node 18+, an OpenAI API key.

```bash
# 1. key
cp .env.example .env            # then set OPENAI_API_KEY=...

# 2. backend (http://localhost:8010)
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/uvicorn backend.api:app --port 8010

# 3. frontend (http://localhost:5180), in a second terminal
cd frontend && npm install && npm run dev
```

Open http://localhost:5180 and click **Use the 3 sample transcripts**, or upload your own `.txt` files.

The bundled sample set (`data/`) is synthetic: three fictional interviews about European electric-bus
adoption, written to contain the cases that matter — a guide question that was never directly asked,
growth figures quoted at different scopes, and genuine disagreements between the speakers.

Single-server option: `cd frontend && npm run build`, then open http://localhost:8010. FastAPI serves the built app.

Optional: `OPENAI_MODEL=...` in `.env` to switch models (default `gpt-5.5`).

## Tests and CI

```bash
.venv/bin/python -m pytest backend/tests        # parser + verifier, no API calls
.venv/bin/python -m evals.trap_checks           # the data's traps, against the real model
```

GitHub Actions (`.github/workflows/`):

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | every push and PR | backend tests + import check, frontend `npm ci && build`, then **deploy to Vercel only if both pass and the branch is `main`**, finishing with a health-check smoke test against the deployed URL |
| `evals.yml` | manual + weekly | runs the trap checks against the live model; kept off the push path because each run costs API credits |

Deployment is driven by Actions rather than Vercel's git integration (disabled in `vercel.json`), so
there is exactly one path to production and it runs behind the tests.

`trap_checks` asserts, among other things: 100% of quotes verify; 2–3 flagged questions are produced, each with verified quotes; Poland and Spain are *not* marked as fully answering "driver training and reliability" (neither was asked both parts); the synthesis explains that the growth figures have different scopes (larger city fleets vs the whole national fleet); the cost-vs-policy and barrier disagreements cite the right lines; the chat declines a question the transcripts don't cover. Current result: 12/12.

## Architecture

```
                        ┌► FLAG HOT QUESTIONS (1 call) ─────────────────────┐
.txt files ──► PARSE ───┤                                                   ├► VERIFY ──┐
              (code)    └► EXTRACT per guide question (1 call/transcript) ──┘  (code)   │
                           (only when a guide is given; all calls run in parallel)       ▼
                                                        SYNTHESISE (1 call) ──► VERIFY ──► UI
Chat question (+ last 6 turns as context) ─────────►   ASK (1 call) ───────► VERIFY ──► UI
```

| Path | Role |
|---|---|
| `backend/core/parser.py` | Splits each transcript into segments with stable IDs (`PL-06`), speaker and timestamp. No LLM. |
| `backend/core/verifier.py` | Accepts a citation only if the quote is a verbatim substring of the cited segment, spoken by the right expert. |
| `backend/core/analyzer.py` | Flag hot questions + extract → verify → synthesise → verify; chat. |
| `backend/core/prompts.py`, `llm.py` | Prompts and a thin OpenAI structured-output wrapper. |
| `backend/api.py` | `GET /api/health`, `GET /api/samples`, `POST /api/analyze`, `POST /api/ask`. Validation and caching only. |
| `frontend/` | React (Vite). One page: flagged questions, answers per expert, themes and disagreements, chat, transcript viewer. |

The core has no FastAPI imports, so it's usable from the eval script, a CLI or a queue worker unchanged.

## Design choices

**No RAG at this size.** The three sample transcripts are about 6 KB together, so every call sees the full text. Retrieval would only add a way to miss context. See scaling below for when that changes.

**Model: `gpt-5.5` with structured outputs.** Responses are constrained to a Pydantic schema, so there is no free-text parsing. The model is set in config; the verifier makes quality measurable if a cheaper model is tried.

**Citations and timestamps.** The model never writes a timestamp. It cites a segment ID and a quote; the timestamp, speaker and exact text shown in the UI come from the parser. Clicking any timestamp opens the transcript at that line with the quote highlighted.

**Reducing hallucinations**
1. *Checked in code, not trusted from the prompt.* A quote is kept only if it appears verbatim (whitespace, case and curly-quote tolerant) in the cited segment, that segment is the expert's (not the interviewer's), and it belongs to the expert the claim is about. Failed quotes are removed and counted; the UI shows the verified/total ratio.
2. *Explicit coverage.* Each question × expert gets `answered`, `partially_addressed` or `not_addressed`, plus whether it was asked directly, so a missing topic is shown as missing instead of filled in.
3. *An answer with no verified quote is flagged `unverified`.* A synthesis position with no verified quote is dropped.
4. *Scope-aware synthesis.* The prompt requires a `nuance` field for numbers or conditions that aren't directly comparable, e.g. "20 to 25 percent … in the larger city fleets" vs "high single digits … across the whole national fleet".
5. *Chat can say no.* When the transcripts don't cover a question, the answer is "not in the transcripts" with no citations. Earlier chat turns are sent only to resolve follow-ups ("what about Anil?") and are marked as context, not evidence: each answer still needs its own verified quotes.
6. *Flagged questions need evidence.* A flagged question with no verifiable quote is not shown.

## Scaling from 3 to 30+ transcripts

- **Map step already scales.** Extraction is one call per transcript, run concurrently. Today the whole analysis is cached by content hash (`.cache/`); next step is caching each transcript's extraction by its own hash, so adding transcript 31 costs one call, not 31. At volume: a job queue with rate limiting and retries instead of `asyncio.gather`.
- **Reduce step.** Synthesis reads the per-question answers, not full transcripts, once the full text no longer fits. For hundreds: synthesise per question (6 small calls), or hierarchically by market.
- **Q&A.** Once all transcripts no longer fit in one call, embed segments and retrieve the top-k (with the question × expert answer table as a second index), then run the same cite → verify step. Retrieval changes what the model sees, not how its output is checked.
- **Storage.** Swap the in-memory/JSON cache for Postgres (segments, answers, citations) and pgvector for embeddings.
- **Evaluation.** The trap checks become a regression suite; the verified-quote ratio is tracked per model and prompt version.

## Limits

- `.txt` only: `MM:SS` on its own line followed by `Speaker: text`, or `[HH:MM:SS] Speaker: text` on one line. The interviewer is recognised by labels such as `Interviewer`, `You`, `Moderator`, `Host`. PDF/DOCX/audio would need a converter in front of the parser.
- The app assumes all uploaded transcripts belong to one project. An off-topic file is not detected; nothing is invented, but the themes section will compare unrelated calls.
- Verification proves a quote exists and belongs to the right expert. It does not prove the summary sentence around it is a fair reading; that is what the visible quotes and the transcript viewer are for.
- The cache is a local folder and analyses live in process memory; fine for a demo, not for multiple instances.
