import Quote from "./Quote.jsx";

// The 2-3 questions the model flags as most decision-relevant, each answered
// only with quotes that passed verification.
export default function HotQuestionsSection({ number, hotQuestions, experts, onOpen }) {
  return (
    <section className="section" aria-labelledby="hot-h">
      <header className="section-head">
        <p className="eyebrow">{number}</p>
        <h2 id="hot-h">Flagged questions</h2>
        <p className="guide-line">Picked by the AI from the transcripts</p>
      </header>

      {hotQuestions.length === 0 ? (
        <p className="panel empty">No question could be flagged with verifiable evidence.</p>
      ) : (
        <div className="hot-grid">
          {hotQuestions.map((h, i) => (
            <article className="panel hot" key={i}>
              <p className="hot-flag"><span aria-hidden="true">🔥</span> Flag {i + 1}</p>
              <h3>{h.question}</h3>
              <p className="why"><strong>Why it matters:</strong> {h.why_flagged}</p>
              <p className="answer">{h.answer}</p>
              {h.quotes.map((q, j) => (
                <Quote key={j} quote={q} expert={experts[q.transcript_id]} onOpen={onOpen} />
              ))}
              {h.dropped_quotes > 0 && (
                <p className="dropped">{h.dropped_quotes} quote(s) removed: not found in the transcript</p>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
