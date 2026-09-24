"""Deterministic transcript and guide parsing. No LLM involved.

Transcript format:

    Expert 1 – Dr. Jean Martin
    Role: Head of Urology
    Market: France

    00:18
    Dr. Martin: Adoption is growing, ...

Each timestamp + "Speaker: text" block becomes one Segment with a stable ID
such as "FR-02". These IDs are what the model cites, and the timestamps shown
in the UI always come from here, never from the model.
"""

import re

from .schemas import Guide, Question, Segment, Transcript


class ParseError(ValueError):
    def __init__(self, filename: str, message: str, line: int | None = None):
        where = f"{filename}, line {line}" if line else filename
        super().__init__(f"{where}: {message}")


HEADER_RE = re.compile(r"^Expert\s*(\d+)?\s*[–—:-]\s*(.+)$", re.IGNORECASE)
FIELD_RE = re.compile(r"^(Role|Market)\s*:\s*(.+)$", re.IGNORECASE)
# "02:18", "1:02:18", "[02:18]", optionally followed by "Speaker: text" on the same line
TIMESTAMP_RE = re.compile(r"^\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?\s*(.*)$")
SPEAKER_RE = re.compile(r"^([^:]{1,60}?)\s*:\s*(.+)$")
# Speaker labels that mean "the person asking", whatever the transcript calls them.
INTERVIEWER_LABELS = {"interviewer", "you", "me", "moderator", "host", "analyst", "q",
                      "question", "consultant", "caller", "researcher"}
# "1. ...", "1) ...", "1: ...", "Q1. ...", "Q1: ...", "Question 1 - ..."
QUESTION_RE = re.compile(r"^\s*(?:Q(?:uestion)?\s*)?(\d+)\s*[.):\-–]\s*(.+)$", re.IGNORECASE)
BULLET_RE = re.compile(r"^\s*[-*•]\s+(.+\?)\s*$")

MARKET_CODES = {
    "france": "FR", "germany": "DE", "united kingdom": "UK", "uk": "UK",
    "england": "UK", "spain": "ES", "italy": "IT", "netherlands": "NL",
    "belgium": "BE", "switzerland": "CH", "austria": "AT", "sweden": "SE",
    "norway": "NO", "denmark": "DK", "finland": "FI", "poland": "PL",
    "portugal": "PT", "ireland": "IE", "united states": "US", "usa": "US",
}


def normalise_text(raw: str) -> str:
    return raw.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")


def to_seconds(ts: str) -> int:
    parts = [int(p) for p in ts.split(":")]
    seconds = 0
    for p in parts:
        seconds = seconds * 60 + p
    return seconds


def market_code(market: str | None, fallback: str) -> str:
    if not market:
        return fallback
    return MARKET_CODES.get(market.strip().lower(), fallback)


def parse_transcript(raw: str, filename: str, fallback_id: str) -> Transcript:
    lines = normalise_text(raw).split("\n")

    expert_name = role = market = None
    blocks: list[tuple[str, int, list[str]]] = []   # (timestamp, line_no, body lines)

    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        ts = TIMESTAMP_RE.match(stripped)
        if ts:
            blocks.append((ts.group(1), line_no, [ts.group(2)] if ts.group(2) else []))
            continue
        if not blocks:
            # still in the header
            if m := FIELD_RE.match(stripped):
                if m.group(1).lower() == "role":
                    role = m.group(2).strip()
                else:
                    market = m.group(2).strip()
            elif m := HEADER_RE.match(stripped):
                expert_name = m.group(2).strip()
            continue
        blocks[-1][2].append(stripped)

    if not blocks:
        raise ParseError(filename, "no timestamps found (expected lines like '02:18')")

    tid = market_code(market, fallback_id)
    segments: list[Segment] = []
    expert_speakers: dict[str, int] = {}

    for i, (timestamp, line_no, body) in enumerate(blocks, start=1):
        text = " ".join(body).strip()
        m = SPEAKER_RE.match(text)
        if not m:
            raise ParseError(filename, f"expected 'Speaker: text' after timestamp {timestamp}", line_no)
        speaker, said = m.group(1).strip(), m.group(2).strip()
        is_expert = speaker.lower().rstrip(".") not in INTERVIEWER_LABELS
        if is_expert:
            expert_speakers[speaker] = expert_speakers.get(speaker, 0) + 1
        segments.append(Segment(
            id=f"{tid}-{i:02d}", transcript_id=tid, index=i, timestamp=timestamp,
            seconds=to_seconds(timestamp), speaker=speaker, is_expert=is_expert, text=said,
        ))

    speaker_label = max(expert_speakers, key=expert_speakers.get) if expert_speakers else None
    if not expert_speakers:
        raise ParseError(filename, "no expert lines found (every speaker is 'Interviewer')")

    return Transcript(
        id=tid, filename=filename, expert_name=expert_name or speaker_label,
        role=role, market=market, speaker_label=speaker_label, segments=segments,
    )


def parse_transcripts(files: list[tuple[str, str]]) -> list[Transcript]:
    """Parse (filename, text) pairs, guaranteeing unique transcript IDs."""
    transcripts: list[Transcript] = []
    seen: set[str] = set()
    for n, (filename, text) in enumerate(files, start=1):
        t = parse_transcript(text, filename, fallback_id=f"E{n}")
        if t.id in seen:
            new_id = f"{t.id}{n}"
            for s in t.segments:
                s.transcript_id = new_id
                s.id = f"{new_id}-{s.index:02d}"
            t.id = new_id
        seen.add(t.id)
        transcripts.append(t)
    return transcripts


def parse_guide(raw: str, filename: str = "guide") -> Guide:
    lines = [l.strip() for l in normalise_text(raw).split("\n") if l.strip()]
    questions = [
        Question(id=int(m.group(1)), text=m.group(2).strip())
        for l in lines if (m := QUESTION_RE.match(l))
    ]
    if not questions:   # fall back to a bulleted list of questions
        questions = [Question(id=i, text=m.group(1).strip())
                     for i, m in enumerate(filter(None, map(BULLET_RE.match, lines)), start=1)]
    if not questions:
        raise ParseError(filename, "no questions found (expected numbered lines like '1. ...' or 'Q1: ...')")
    if len({q.id for q in questions}) != len(questions):   # e.g. two lists both starting at 1
        questions = [Question(id=i, text=q.text) for i, q in enumerate(questions, start=1)]
    return Guide(title=lines[0] if lines else "Interview guide", questions=questions, filename=filename)
