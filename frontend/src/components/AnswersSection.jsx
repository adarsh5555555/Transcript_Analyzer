import Quote from "./Quote.jsx";
import StatusBadge from "./StatusBadge.jsx";

function AnswerCell({ answer, expert, onOpen }) {
  return (
    <div className="cell">
      <div className="cell-head">
        <span className="expert-tag">{expert.id}</span>
        <span className="cell-name">{expert.speaker_label}</span>
        <StatusBadge status={answer.unverified ? "unverified" : answer.status} />
      </div>
      {!answer.asked_directly && answer.status !== "answered" && (
        <p className="asked-note">Not asked directly in this interview</p>
      )}
      <p className="answer">{answer.answer}</p>
      {answer.quotes.map((q, i) => (
        <Quote key={i} quote={q} expert={expert} onOpen={onOpen} />
      ))}
      {answer.dropped_quotes > 0 && (
        <p className="dropped">{answer.dropped_quotes} quote(s) removed: not found in the transcript</p>
      )}
    </div>
  );
}

export default function AnswersSection({ number, result, experts, onOpen }) {
  const byKey = new Map(result.answers.map((a) => [`${a.transcript_id}:${a.question_id}`, a]));

  return (
    <section className="section" aria-labelledby="answers-h">
      <header className="section-head">
        <p className="eyebrow">{number}</p>
        <h2 id="answers-h">Answers per expert</h2>
        <p className="guide-line">
          Guide: {result.guide.filename} · {result.guide.questions.length} questions
        </p>
        <nav className="qnav" aria-label="Jump to question">
          {result.guide.questions.map((q) => (
            <a key={q.id} href={`#q${q.id}`}>Q{q.id}</a>
          ))}
        </nav>
      </header>

      {result.guide.questions.map((q) => (
        <article className="panel question" id={`q${q.id}`} key={q.id}>
          <h3><span className="qnum">Q{q.id}</span>{q.text}</h3>
          <div className="grid" style={{ "--cols": result.transcripts.length }}>
            {result.transcripts.map((t) => {
              const a = byKey.get(`${t.id}:${q.id}`);
              return a ? <AnswerCell key={t.id} answer={a} expert={experts[t.id]} onOpen={onOpen} /> : null;
            })}
          </div>
        </article>
      ))}
    </section>
  );
}
