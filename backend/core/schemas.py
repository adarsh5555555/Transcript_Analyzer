"""Data shapes shared by the parser, verifier, analyzer and API.

Two families live here:
- Domain / API models (Segment, Transcript, ExpertAnswer, ...): what the app returns.
- LLM output models (the *Out classes): what the model is forced to return via
  structured outputs. They only carry segment IDs and quote text; timestamps,
  speakers and verification status are added afterwards in code.
"""

from typing import Literal

from pydantic import BaseModel

Status = Literal["answered", "partially_addressed", "not_addressed"]


# ---------- parsed input ----------

class Segment(BaseModel):
    id: str               # e.g. "FR-05", stable and unique across the analysis
    transcript_id: str    # e.g. "FR"
    index: int            # 1-based position inside the transcript
    timestamp: str        # exactly as written in the file, e.g. "02:18"
    seconds: int
    speaker: str          # as written, e.g. "Dr. Martin" or "Interviewer"
    is_expert: bool
    text: str


class Transcript(BaseModel):
    id: str
    filename: str
    expert_name: str
    role: str | None
    market: str | None
    speaker_label: str | None   # how the expert is labelled in the body
    segments: list[Segment]


class Question(BaseModel):
    id: int
    text: str


class Guide(BaseModel):
    title: str
    questions: list[Question]
    filename: str = ""


# ---------- verified output ----------

class Quote(BaseModel):
    segment_id: str
    transcript_id: str
    timestamp: str
    speaker: str
    text: str             # the exact span as it appears in the transcript


class ExpertAnswer(BaseModel):
    question_id: int
    transcript_id: str
    status: Status
    asked_directly: bool
    answer: str
    quotes: list[Quote]
    dropped_quotes: int   # citations the model gave that failed verification
    unverified: bool      # claims an answer but no quote survived verification


class Position(BaseModel):
    transcript_id: str
    position: str
    quotes: list[Quote]
    dropped_quotes: int


class Finding(BaseModel):
    topic: str
    summary: str
    nuance: str | None
    positions: list[Position]


class Synthesis(BaseModel):
    agreements: list[Finding]
    disagreements: list[Finding]


class VerificationStats(BaseModel):
    cited: int
    verified: int
    dropped: int


class HotQuestion(BaseModel):
    question: str
    why_flagged: str
    answer: str
    quotes: list[Quote]
    dropped_quotes: int


class AnalysisResult(BaseModel):
    analysis_id: str
    model: str
    guide: Guide | None          # None: no guide uploaded, so no per-question table
    transcripts: list[Transcript]
    hot_questions: list[HotQuestion]
    answers: list[ExpertAnswer]
    synthesis: Synthesis
    stats: VerificationStats


class ChatTurn(BaseModel):
    question: str
    answer: str


class AskRequest(BaseModel):
    analysis_id: str
    question: str
    history: list[ChatTurn] = []
    # Serverless hosts give no shared memory between requests, so the client may
    # send the transcripts it already has instead of relying on a server lookup.
    transcripts: list[Transcript] | None = None


class AskResult(BaseModel):
    question: str
    status: Literal["answered", "not_in_transcripts", "unverified"]
    answer: str
    quotes: list[Quote]
    dropped_quotes: int


# ---------- LLM output (structured outputs) ----------

class CitationOut(BaseModel):
    segment_id: str
    quote: str


class AnswerOut(BaseModel):
    question_id: int
    asked_directly: bool
    status: Status
    answer: str
    citations: list[CitationOut]


class ExtractionOut(BaseModel):
    answers: list[AnswerOut]


class PositionOut(BaseModel):
    transcript_id: str
    position: str
    citations: list[CitationOut]


class FindingOut(BaseModel):
    topic: str
    summary: str
    nuance: str | None
    positions: list[PositionOut]


class SynthesisOut(BaseModel):
    agreements: list[FindingOut]
    disagreements: list[FindingOut]


class HotQuestionOut(BaseModel):
    question: str
    why_flagged: str
    answer: str
    citations: list[CitationOut]


class HotQuestionsOut(BaseModel):
    questions: list[HotQuestionOut]


class AskOut(BaseModel):
    answerable: bool
    answer: str
    citations: list[CitationOut]
