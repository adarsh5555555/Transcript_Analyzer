"""Checks every quote the model gives against the transcript, in code.

A citation passes only if:
1. the segment ID exists,
2. the segment belongs to an allowed transcript and is spoken by the expert
   (never the interviewer),
3. the quote is a contiguous substring of that segment after normalising
   whitespace, case, curly quotes and dashes.

The returned Quote carries the exact span from the transcript (not the model's
spelling of it) and the parser's timestamp.
"""

import unicodedata

from .schemas import CitationOut, Quote, Segment

_CHAR_MAP = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "...", " ": " ",
}
_STRIP = " \t\n\"'.,;:!?…“”‘’"
MIN_QUOTE_CHARS = 8


def _normalise_with_map(text: str) -> tuple[str, list[int]]:
    """Normalised text plus, for each normalised char, its index in the original."""
    out: list[str] = []
    index: list[int] = []
    prev_space = True
    for i, ch in enumerate(unicodedata.normalize("NFC", text)):
        rep = _CHAR_MAP.get(ch, ch)
        for c in rep:
            if c.isspace():
                if prev_space:
                    continue
                c, prev_space = " ", True
            else:
                prev_space = False
            out.append(c.lower())
            index.append(i)
    while out and out[-1] == " ":
        out.pop()
        index.pop()
    return "".join(out), index


def normalise(text: str) -> str:
    return _normalise_with_map(text)[0]


def find_span(quote: str, segment_text: str) -> str | None:
    """Return the exact span of segment_text matching quote, or None."""
    needle = normalise(quote.strip(_STRIP))
    if len(needle) < MIN_QUOTE_CHARS:
        return None
    source = unicodedata.normalize("NFC", segment_text)
    hay, index = _normalise_with_map(source)
    pos = hay.find(needle)
    if pos < 0:
        return None
    start, end = index[pos], index[pos + len(needle) - 1] + 1
    return source[start:end]


class Verifier:
    def __init__(self, segments: list[Segment]):
        self.by_id = {s.id: s for s in segments}

    def check(self, citation: CitationOut, allowed_transcripts: set[str] | None = None) -> Quote | None:
        seg = self.by_id.get(citation.segment_id.strip().upper())
        if seg is None or not seg.is_expert:
            return None
        if allowed_transcripts is not None and seg.transcript_id not in allowed_transcripts:
            return None
        span = find_span(citation.quote, seg.text)
        if span is None:
            return None
        return Quote(segment_id=seg.id, transcript_id=seg.transcript_id,
                     timestamp=seg.timestamp, speaker=seg.speaker, text=span)

    def check_all(self, citations: list[CitationOut],
                  allowed_transcripts: set[str] | None = None) -> tuple[list[Quote], int]:
        """Verified, de-duplicated quotes plus the number dropped."""
        quotes: list[Quote] = []
        seen: set[tuple[str, str]] = set()
        dropped = 0
        for c in citations:
            q = self.check(c, allowed_transcripts)
            if q is None:
                dropped += 1
            elif (q.segment_id, q.text) not in seen:
                seen.add((q.segment_id, q.text))
                quotes.append(q)
        return quotes, dropped
