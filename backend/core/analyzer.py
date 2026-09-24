"""The pipeline: flag hot questions + extract per guide question (map, one call per
transcript), all in parallel -> verify -> synthesise (reduce, one call) -> verify.
Plus free-form chat. Every citation from every step goes through the same Verifier."""

import asyncio

from . import prompts
from .llm import LLM
from .schemas import (AnswerOut, AskOut, AskResult, ChatTurn, ExpertAnswer, ExtractionOut,
                      Finding, Guide, HotQuestion, HotQuestionsOut, Position, Synthesis,
                      SynthesisOut, Transcript, VerificationStats)
from .verifier import Verifier


class Stats:
    def __init__(self):
        self.verified = 0
        self.dropped = 0

    def add(self, verified: int, dropped: int):
        self.verified += verified
        self.dropped += dropped

    def result(self) -> VerificationStats:
        return VerificationStats(cited=self.verified + self.dropped,
                                 verified=self.verified, dropped=self.dropped)


async def extract(llm: LLM, t: Transcript, guide: Guide, verifier: Verifier,
                  stats: Stats) -> list[ExpertAnswer]:
    user = (f"Interview guide:\n{prompts.render_guide(guide)}\n\n"
            f"Transcript:\n{prompts.render_transcript(t)}")
    out = await llm.structured(prompts.EXTRACT_INSTRUCTIONS, user, ExtractionOut)
    by_q: dict[int, AnswerOut] = {a.question_id: a for a in out.answers}

    answers = []
    for q in guide.questions:
        a = by_q.get(q.id)
        if a is None:   # model skipped a question: say so rather than guess
            answers.append(ExpertAnswer(
                question_id=q.id, transcript_id=t.id, status="not_addressed", asked_directly=False,
                answer="Not addressed.", quotes=[], dropped_quotes=0, unverified=False))
            continue
        quotes, dropped = verifier.check_all(a.citations, {t.id})
        stats.add(len(quotes), dropped)
        answers.append(ExpertAnswer(
            question_id=q.id, transcript_id=t.id, status=a.status, asked_directly=a.asked_directly,
            answer=a.answer, quotes=quotes, dropped_quotes=dropped,
            unverified=a.status != "not_addressed" and not quotes))
    return answers


def _all_transcripts(transcripts: list[Transcript]) -> str:
    return "Transcripts:\n\n" + "\n\n".join(prompts.render_transcript(t) for t in transcripts)


async def flag_hot_questions(llm: LLM, transcripts: list[Transcript], verifier: Verifier,
                             stats: Stats) -> list[HotQuestion]:
    out = await llm.structured(prompts.HOT_QUESTIONS_INSTRUCTIONS, _all_transcripts(transcripts),
                               HotQuestionsOut)
    result = []
    for h in out.questions[:3]:
        quotes, dropped = verifier.check_all(h.citations)
        stats.add(len(quotes), dropped)
        if quotes:   # a flagged question with no verifiable evidence is not shown
            result.append(HotQuestion(question=h.question, why_flagged=h.why_flagged,
                                      answer=h.answer, quotes=quotes, dropped_quotes=dropped))
    return result


async def synthesise(llm: LLM, transcripts: list[Transcript], guide: Guide | None,
                     answers: list[ExpertAnswer], verifier: Verifier, stats: Stats) -> Synthesis:
    user = _all_transcripts(transcripts)
    if guide and answers:
        questions = {q.id: q.text for q in guide.questions}
        summary = "\n".join(
            f"- {a.transcript_id} | Q{a.question_id} ({questions[a.question_id]}) | {a.status}: {a.answer}"
            for a in answers)
        user += f"\n\nPer-question answers (already extracted):\n{summary}"
    out = await llm.structured(prompts.SYNTHESIS_INSTRUCTIONS, user, SynthesisOut)

    known = {t.id for t in transcripts}

    def build(findings) -> list[Finding]:
        result = []
        for f in findings:
            positions = []
            for p in f.positions:
                tid = p.transcript_id.strip().upper()
                if tid not in known:
                    stats.add(0, len(p.citations))
                    continue
                quotes, dropped = verifier.check_all(p.citations, {tid})
                stats.add(len(quotes), dropped)
                if quotes:   # a position with no verifiable quote is not shown
                    positions.append(Position(transcript_id=tid, position=p.position,
                                              quotes=quotes, dropped_quotes=dropped))
            if positions:
                result.append(Finding(topic=f.topic, summary=f.summary, nuance=f.nuance,
                                      positions=positions))
        return result

    return Synthesis(agreements=build(out.agreements), disagreements=build(out.disagreements))


async def analyse(llm: LLM, transcripts: list[Transcript], guide: Guide | None):
    verifier = Verifier([s for t in transcripts for s in t.segments])
    stats = Stats()
    extractions = [extract(llm, t, guide, verifier, stats) for t in transcripts] if guide else []
    hot, *per_transcript = await asyncio.gather(
        flag_hot_questions(llm, transcripts, verifier, stats), *extractions)
    answers = [a for group in per_transcript for a in group]
    synthesis = await synthesise(llm, transcripts, guide, answers, verifier, stats)
    return hot, answers, synthesis, stats.result()


async def ask(llm: LLM, transcripts: list[Transcript], question: str,
              history: list[ChatTurn] | None = None) -> AskResult:
    verifier = Verifier([s for t in transcripts for s in t.segments])
    user = _all_transcripts(transcripts)
    if history:
        turns = "\n".join(f"User: {h.question}\nAssistant: {h.answer}" for h in history[-6:])
        user += f"\n\nEarlier chat (context only, not evidence):\n{turns}"
    user += f"\n\nQuestion: {question}"
    out = await llm.structured(prompts.ASK_INSTRUCTIONS, user, AskOut)
    quotes, dropped = verifier.check_all(out.citations)

    if not out.answerable:
        status = "not_in_transcripts"
    elif quotes:
        status = "answered"
    else:
        status = "unverified"
    return AskResult(question=question, status=status, answer=out.answer,
                     quotes=quotes, dropped_quotes=dropped)
