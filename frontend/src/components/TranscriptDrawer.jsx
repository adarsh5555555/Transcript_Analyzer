import { useEffect, useRef } from "react";

// Shows the full transcript with the cited line highlighted and the quoted
// words marked, so any claim can be checked against its source in one click.
function highlight(text, quote) {
  if (!quote) return text;
  const i = text.indexOf(quote);
  if (i < 0) return text;
  return (
    <>
      {text.slice(0, i)}
      <mark>{quote}</mark>
      {text.slice(i + quote.length)}
    </>
  );
}

export default function TranscriptDrawer({ transcript, focus, onClose }) {
  const focusRef = useRef(null);
  const closeRef = useRef(null);

  useEffect(() => {
    closeRef.current?.focus();
    focusRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [transcript, focus, onClose]);

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-h"
             onClick={(e) => e.stopPropagation()}>
        <header className="drawer-head">
          <div>
            <p className="eyebrow">{transcript.filename}</p>
            <h2 id="drawer-h">{transcript.expert_name}</h2>
            <p className="muted">{[transcript.role, transcript.market].filter(Boolean).join(" · ")}</p>
          </div>
          <button ref={closeRef} className="btn btn-ghost" onClick={onClose}>Close</button>
        </header>
        <ol className="lines">
          {transcript.segments.map((s) => {
            const on = focus?.segment_id === s.id;
            return (
              <li key={s.id} ref={on ? focusRef : null}
                  className={`line ${s.is_expert ? "is-expert" : "is-interviewer"} ${on ? "on" : ""}`}>
                <span className="line-ts">{s.timestamp}</span>
                <div>
                  <span className="line-who">{s.speaker}</span>
                  <p>{on ? highlight(s.text, focus.text) : s.text}</p>
                </div>
                <span className="line-id">{s.id}</span>
              </li>
            );
          })}
        </ol>
      </aside>
    </div>
  );
}
