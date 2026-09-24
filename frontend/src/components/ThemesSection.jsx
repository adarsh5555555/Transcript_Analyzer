import Quote from "./Quote.jsx";

function FindingCard({ finding, experts, onOpen }) {
  return (
    <article className="panel finding">
      <h3>{finding.topic}</h3>
      <p className="answer">{finding.summary}</p>
      {finding.nuance && (
        <p className="nuance"><strong>Read carefully:</strong> {finding.nuance}</p>
      )}
      <ul className="positions">
        {finding.positions.map((p) => (
          <li key={p.transcript_id}>
            <div className="cell-head">
              <span className="expert-tag">{p.transcript_id}</span>
              <span className="cell-name">{experts[p.transcript_id]?.speaker_label}</span>
            </div>
            <p className="position">{p.position}</p>
            {p.quotes.map((q, i) => (
              <Quote key={i} quote={q} expert={experts[p.transcript_id]} onOpen={onOpen} />
            ))}
          </li>
        ))}
      </ul>
    </article>
  );
}

export default function ThemesSection({ number, synthesis, experts, onOpen }) {
  return (
    <section className="section" aria-labelledby="themes-h">
      <header className="section-head">
        <p className="eyebrow">{number}</p>
        <h2 id="themes-h">Themes &amp; disagreements</h2>
      </header>
      <div className="themes">
        <div>
          <h3 className="col-title"><span className="dot dot-agree" />Where they agree</h3>
          {synthesis.agreements.map((f, i) => (
            <FindingCard key={i} finding={f} experts={experts} onOpen={onOpen} />
          ))}
        </div>
        <div>
          <h3 className="col-title"><span className="dot dot-differ" />Where they differ</h3>
          {synthesis.disagreements.map((f, i) => (
            <FindingCard key={i} finding={f} experts={experts} onOpen={onOpen} />
          ))}
        </div>
      </div>
    </section>
  );
}
