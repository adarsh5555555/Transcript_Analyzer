"""Prompts. Rules the verifier also enforces in code are stated here too, so the
model gets them right first time; the verifier is the backstop, not the plan."""

CITATION_RULES = """\
Citation rules (enforced by code; violations are discarded):
- Cite by segment ID, e.g. "FR-06". Only cite segments marked EXPERT, never Interviewer lines.
- "quote" must be copied character-for-character from that one segment: a contiguous span,
  no paraphrasing, no "...", no joining text from two segments. Prefer one full clause or sentence.
- Never state a fact, number or opinion that is not in the cited quotes.
"""

EXTRACT_INSTRUCTIONS = f"""\
You analyse one expert-call transcript for a market research firm.
For EVERY question in the interview guide, report what this expert said.

Decide the status honestly:
- "answered": the expert directly and substantively answered this question.
- "partially_addressed": the question was not asked directly (or only part of it was covered),
  but the expert said something relevant elsewhere in the call.
- "not_addressed": nothing in the transcript speaks to it.
Set asked_directly=true only if the interviewer actually asked this question (or a close variant).
If a multi-part question (e.g. "training and clinical outcomes") was only partly covered,
use "partially_addressed" and say in the answer which part is missing.

The "answer" is 1-3 plain sentences in the expert's terms. Keep scope qualifiers
exactly ("in some of the stronger centres", "across the whole market", "if funding is available").
For partially/not addressed questions, start the answer with "Not directly asked." or
"Not addressed." and then give the closest related point, if any, with its citation.
Give 1-3 citations per question (0 only for "not_addressed" with nothing related).

{CITATION_RULES}"""

SYNTHESIS_INSTRUCTIONS = f"""\
You compare several expert interviews from one market research project.
You get each expert's full transcript and their per-question answers.

Return:
- agreements: themes most or all experts share (3-5).
- disagreements: points where experts genuinely differ (3-6).

For each finding give a short topic, a 1-2 sentence summary, and one position per relevant
expert (transcript_id + their stance in a sentence + 1-2 citations from THAT expert's transcript).
Use "nuance" for anything that stops a naive comparison: especially numbers with different scopes
or conditions (e.g. "15-20% in some stronger centres" vs "high single digits across the whole
market" are not directly comparable), or conditional statements ("6-9 months if funding is available").
Do not call something a disagreement if the difference is only in scope; explain the scope instead.
Set nuance to null when there is none.

{CITATION_RULES}"""

HOT_QUESTIONS_INSTRUCTIONS = f"""\
You read a set of expert-call / discussion transcripts from one project and flag the 2-3
"hot" questions a decision-maker should look at first: where the money, risk, a key
decision, or a clear disagreement between speakers sits. Prefer questions that more than one
transcript speaks to. Do not flag questions the transcripts cannot answer.

For each: a short question (max ~15 words), why_flagged in one sentence, an answer of 2-4
sentences that names who said what and keeps disagreements and scope qualifiers visible,
and 2-5 citations spread across the relevant transcripts.

{CITATION_RULES}"""

ASK_INSTRUCTIONS = f"""\
You answer a user's question using ONLY the expert-call transcripts provided.
- If the transcripts support an answer, set answerable=true, answer in 2-5 sentences naming
  which expert said what, and cite every claim.
- If they do not (the topic never comes up), set answerable=false, answer with one sentence saying
  it is not covered in the transcripts, and give no citations. Do not use outside knowledge.
- If only partly covered, answer the covered part and say plainly what is not covered.
- Earlier chat turns may be included so you can resolve follow-ups ("what about him?").
  They are context only, never evidence: every claim must still be cited from the transcripts.

{CITATION_RULES}"""


def render_transcript(t) -> str:
    head = f"=== Transcript {t.id}: {t.expert_name}"
    if t.role:
        head += f", {t.role}"
    if t.market:
        head += f" ({t.market})"
    lines = [head + " ==="]
    for s in t.segments:
        who = "EXPERT" if s.is_expert else "Interviewer"
        lines.append(f"[{s.id}] {s.timestamp} {who} {s.speaker}: {s.text}")
    return "\n".join(lines)


def render_guide(guide) -> str:
    return "\n".join(f"{q.id}. {q.text}" for q in guide.questions)
