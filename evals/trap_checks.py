"""Checks the hard cases in the sample data against a real model run.

    .venv/bin/python -m evals.trap_checks            # fresh model run (~1 min)
    .venv/bin/python -m evals.trap_checks --cached   # reuse the last saved analysis

Exits non-zero if any check fails.
"""

import asyncio
import sys

from backend import config
from backend.core import analyzer
from backend.core.llm import LLM
from backend.core.parser import parse_guide, parse_transcripts
from backend.core.schemas import AnalysisResult


def load_inputs():
    texts = [(n, (config.DATA_DIR / n).read_text(encoding="utf-8")) for n in config.SAMPLE_TRANSCRIPTS]
    guide = parse_guide((config.DATA_DIR / config.SAMPLE_GUIDE).read_text(encoding="utf-8"))
    return parse_transcripts(texts), guide


def latest_cached() -> AnalysisResult | None:
    files = sorted(config.CACHE_DIR.glob("analysis_*.json"), key=lambda p: p.stat().st_mtime)
    return AnalysisResult.model_validate_json(files[-1].read_text()) if files else None


async def main(cached: bool) -> int:
    llm = LLM(config.OPENAI_MODEL)
    transcripts, guide = load_inputs()
    if cached and (r := latest_cached()):
        hot, answers, synthesis, stats = r.hot_questions, r.answers, r.synthesis, r.stats
        print("using cached analysis")
    else:
        hot, answers, synthesis, stats = await analyzer.analyse(llm, transcripts, guide)

    ans = {(a.transcript_id, a.question_id): a for a in answers}
    findings = synthesis.agreements + synthesis.disagreements
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = ""):
        results.append((name, ok, detail))

    # Every quote the model gave is found verbatim in the cited expert line.
    check("all quotes verify", stats.dropped == 0, f"{stats.verified}/{stats.cited} verified")

    check("2-3 flagged questions, each with verified quotes",
          2 <= len(hot) <= 3 and all(h.quotes for h in hot), f"{len(hot)} flagged")

    # Case 1: Q4 asks about training AND reliability. Spain was never asked either
    # directly, and Poland was asked only about training, so neither is a full answer.
    for tid in ("PL", "ES"):
        a = ans[(tid, 4)]
        check(f"{tid} x Q4 (training & reliability) is not a full answer",
              a.status != "answered", a.status)

    # Case 2: growth numbers have different scopes; the synthesis must say so.
    text = " ".join(f"{f.summary} {f.nuance or ''}" for f in findings).lower()
    check("growth scopes explained",
          ("city fleet" in text or "larger city" in text) and "national fleet" in text)

    # Case 3: real disagreements are found and cite the right lines.
    dis_segments = {q.segment_id for f in synthesis.disagreements for p in f.positions for q in p.quotes}
    check("cost-vs-policy disagreement cites ES 03:13 ('not financial case alone')", "ES-08" in dis_segments)
    check("barrier disagreement cites ES 01:09 (depot readiness)", "ES-04" in dis_segments)

    expected_timeline = {"NL": "06:12", "PL": "06:09", "ES": "05:12"}
    for tid, ts in expected_timeline.items():
        got = [q.timestamp for q in ans[(tid, 6)].quotes]
        check(f"{tid} timeline quote at {ts}", ts in got, str(got))

    # Q&A: supported vs unsupported questions.
    supported = await analyzer.ask(llm, transcripts, "How long does a fleet purchase decision take?")
    check("Q&A answers a covered question with quotes",
          supported.status == "answered" and len(supported.quotes) >= 3, supported.status)
    unsupported = await analyzer.ask(llm, transcripts, "What did the experts say about hydrogen fuel cell buses?")
    check("Q&A refuses an uncovered question", unsupported.status == "not_in_transcripts",
          unsupported.status)

    width = max(len(n) for n, _, _ in results)
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
    failed = sum(not ok for _, ok, _ in results)
    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(cached="--cached" in sys.argv)))
