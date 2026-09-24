import { useEffect, useRef, useState } from "react";
import { ask } from "../api.js";
import Quote from "./Quote.jsx";
import StatusBadge from "./StatusBadge.jsx";

const STATUS_NOTES = {
  not_in_transcripts: "The transcripts do not cover this, so no answer is given.",
  unverified: "None of the quotes behind this answer could be verified. Treat it with caution.",
};

// Chat over all transcripts. Earlier turns are sent as context for follow-ups,
// but every answer is still backed only by verified, timestamped quotes.
export default function AskSection({ number, analysisId, transcripts, experts, onOpen, suggestions }) {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState([]);   // {question, result?, error?}
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    if (turns.length) endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  async function submit(q) {
    const text = (q ?? question).trim();
    if (!text || loading) return;
    const history = turns
      .filter((t) => t.result)
      .map((t) => ({ question: t.question, answer: t.result.answer }));
    setTurns((ts) => [...ts, { question: text }]);
    setQuestion("");
    setLoading(true);
    try {
      const result = await ask(analysisId, text, history, transcripts);
      setTurns((ts) => ts.map((t, i) => (i === ts.length - 1 ? { ...t, result } : t)));
    } catch (e) {
      setTurns((ts) => ts.map((t, i) => (i === ts.length - 1 ? { ...t, error: e.message } : t)));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="section" aria-labelledby="ask-h">
      <header className="section-head">
        <p className="eyebrow">{number}</p>
        <h2 id="ask-h">Ask the transcripts</h2>
        <p className="guide-line">Answers cite timestamped quotes</p>
      </header>

      <div className="panel chat">
        {turns.length === 0 ? (
          <div className="chat-empty">
            <p className="muted">Ask anything about these calls. Follow-up questions work too.</p>
            <div className="suggestions">
              {suggestions.map((s) => (
                <button key={s} className="chip" disabled={loading} onClick={() => submit(s)}>{s}</button>
              ))}
            </div>
          </div>
        ) : (
          <ol className="thread" aria-live="polite">
            {turns.map((t, i) => (
              <li key={i} className="turn">
                <p className="bubble user">{t.question}</p>
                {!t.result && !t.error && (
                  <div className="bubble bot thinking"><span className="spinner" aria-hidden="true" />Reading the transcripts…</div>
                )}
                {t.error && <p className="bubble bot error" role="alert">{t.error}</p>}
                {t.result && (
                  <div className="bubble bot">
                    <div className="bot-head"><StatusBadge status={t.result.status} /></div>
                    <p className="answer">{t.result.answer}</p>
                    {STATUS_NOTES[t.result.status] && <p className="nuance">{STATUS_NOTES[t.result.status]}</p>}
                    {t.result.quotes.map((q, j) => (
                      <Quote key={j} quote={q} expert={experts[q.transcript_id]} onOpen={onOpen} />
                    ))}
                    {t.result.dropped_quotes > 0 && (
                      <p className="dropped">{t.result.dropped_quotes} quote(s) removed: not found in the transcript</p>
                    )}
                  </div>
                )}
              </li>
            ))}
            <li ref={endRef} aria-hidden="true" />
          </ol>
        )}

        <form className="ask-form" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <input value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={1000}
                 placeholder="Ask a question about the transcripts…" aria-label="Your question"
                 disabled={loading} />
          <button className="btn" disabled={loading || !question.trim()}>
            {loading ? "Thinking…" : "Ask"}
          </button>
        </form>
      </div>
    </section>
  );
}
