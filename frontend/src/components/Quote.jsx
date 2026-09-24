// One verified quote: the exact transcript text plus a clickable timestamp
// that opens the transcript at that line.
export default function Quote({ quote, expert, onOpen }) {
  return (
    <figure className="quote">
      <blockquote>“{quote.text}”</blockquote>
      <figcaption>
        <button className="ts" onClick={() => onOpen(quote)} title="Open the transcript at this line">
          <span aria-hidden="true">⏱</span> {quote.timestamp}
        </button>
        <span className="who">{expert ? expert.speaker_label : quote.speaker}</span>
        <span className="seg">{quote.segment_id}</span>
      </figcaption>
    </figure>
  );
}
