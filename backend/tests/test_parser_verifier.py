import pytest

from backend.config import DATA_DIR, SAMPLE_GUIDE, SAMPLE_TRANSCRIPTS
from backend.core.parser import ParseError, parse_guide, parse_transcript, parse_transcripts
from backend.core.schemas import CitationOut
from backend.core.verifier import Verifier, find_span


@pytest.fixture(scope="module")
def transcripts():
    files = [(f, (DATA_DIR / f).read_text(encoding="utf-8")) for f in SAMPLE_TRANSCRIPTS]
    return parse_transcripts(files)


def test_headers_and_ids(transcripts):
    nl, pl, es = transcripts
    assert [t.id for t in transcripts] == ["NL", "PL", "ES"]
    assert nl.expert_name == "Sanne de Vries" and nl.market == "Netherlands"
    assert nl.speaker_label == "Sanne de Vries"
    assert pl.expert_name == "Marek Kowalski"
    assert pl.role == "Former Procurement Director, Municipal Transport Authority"
    assert es.speaker_label == "Elena Navarro" and es.market == "Spain"


def test_segments_keep_source_timestamps(transcripts):
    nl = transcripts[0]
    seg = {s.timestamp: s for s in nl.segments}
    assert seg["05:09"].text.startswith("I expect continued growth")
    assert seg["05:09"].is_expert and seg["05:01"].speaker == "Interviewer"
    assert nl.segments[0].id == "NL-01" and nl.segments[1].seconds == 21
    assert all(len(t.segments) >= 12 for t in transcripts)


def test_guide_has_six_questions():
    guide = parse_guide((DATA_DIR / SAMPLE_GUIDE).read_text(encoding="utf-8"))
    assert [q.id for q in guide.questions] == [1, 2, 3, 4, 5, 6]
    assert "reliability" in guide.questions[3].text


def test_crlf_bom_and_same_line_speaker():
    raw = "﻿Expert 1 - Jo\r\nMarket: Spain\r\n\r\n[00:05] Interviewer: Hi?\r\n00:09\r\nJo: Fine,\r\nthanks.\r\n"
    t = parse_transcript(raw, "x.txt", "E1")
    assert t.id == "ES" and [s.id for s in t.segments] == ["ES-01", "ES-02"]
    assert t.segments[1].text == "Fine, thanks."


def test_bad_files_raise_clear_errors():
    with pytest.raises(ParseError, match="no timestamps"):
        parse_transcript("just some text", "notes.txt", "E1")
    with pytest.raises(ParseError, match="line 1"):
        parse_transcript("00:01\nno speaker here", "bad.txt", "E1")


def test_duplicate_markets_get_unique_ids():
    raw = "Market: France\n00:00\nDr. A: hello there everyone"
    a, b = parse_transcripts([("a.txt", raw), ("b.txt", raw)])
    assert a.id != b.id and b.segments[0].id.startswith(b.id)


def test_find_span_is_tolerant_but_exact():
    text = "Purchase price is the first barrier. These are large capital items."
    assert find_span("purchase price is the  first barrier.", text) == "Purchase price is the first barrier"
    assert find_span("“Purchase price is the first barrier”", text) == "Purchase price is the first barrier"
    assert find_span("Purchase price is the main barrier", text) is None   # paraphrase
    assert find_span("Purchase price ... items", text) is None             # stitched
    assert find_span("Price", text) is None                                # too short


def test_verifier_rules(transcripts):
    v = Verifier([s for t in transcripts for s in t.segments])
    good = CitationOut(segment_id="PL-06", quote="the financial case decides whether it gets approved")
    q = v.check(good)
    assert q and q.timestamp == "02:12" and q.speaker == "Marek Kowalski"
    # right words, wrong expert's segment
    assert v.check(good, allowed_transcripts={"NL"}) is None
    # interviewer lines are never quotable as expert evidence
    assert v.check(CitationOut(segment_id="PL-05", quote="What does procurement actually look at")) is None
    # invented segment / invented words
    assert v.check(CitationOut(segment_id="PL-99", quote="the financial case decides")) is None
    assert v.check(CitationOut(segment_id="PL-06", quote="air quality alone decides everything")) is None
    quotes, dropped = v.check_all([good, good, CitationOut(segment_id="X-1", quote="nothing at all")])
    assert len(quotes) == 1 and dropped == 1


@pytest.mark.parametrize("text", [
    "My guide\n1. First?\n2. Second?",
    "My guide\nQ1: First?\nQ2: Second?",
    "My guide\nQuestion 1 - First?\nQuestion 2 - Second?",
    "My guide\n1) First?\n2) Second?",
    "My guide\n- First?\n- Second?",
])
def test_guide_formats(text):
    g = parse_guide(text, "mine.txt")
    assert [q.text for q in g.questions] == ["First?", "Second?"] and g.filename == "mine.txt"


def test_guide_without_questions_is_an_error():
    with pytest.raises(ParseError, match="no questions found"):
        parse_guide("just a title\nsome notes", "notes.txt")


def test_you_is_the_interviewer_and_inline_hms_timestamps():
    raw = ("TRANSCRIPTION — DISCUSSION WITH MR. AMIT\nTopic: showroom\n\n"
           "[00:00:07] Amit: Let's discuss the showroom.\n"
           "[00:00:20] You: Sure. What's the current thinking?\n"
           "[00:01:17] Amit: I'm considering the ring road site.\n")
    t = parse_transcript(raw, "Mr_Amit.txt", "E1")
    assert [s.is_expert for s in t.segments] == [True, False, True]
    assert t.speaker_label == "Amit" and t.expert_name == "Amit"
    assert t.segments[2].timestamp == "00:01:17" and t.segments[2].seconds == 77
