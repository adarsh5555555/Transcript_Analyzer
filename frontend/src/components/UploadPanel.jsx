import { useState } from "react";

export default function UploadPanel({ loading, onAnalyze }) {
  const [files, setFiles] = useState([]);
  const [guide, setGuide] = useState(null);

  return (
    <section className="panel upload" aria-labelledby="upload-h">
      <div className="upload-copy">
        <p className="eyebrow">Start here</p>
        <h2 id="upload-h">Load the transcripts</h2>
        <p className="muted">
          Plain-text <code>.txt</code> files: a header, then <code>MM:SS</code> lines each followed
          by <code>Speaker: text</code> (or <code>[00:01:17] Name: text</code>). Add an interview
          guide to get a per-question table; without one you still get flagged questions, themes
          and chat.
        </p>
      </div>

      <div className="upload-controls">
        <label className="file">
          <span className="file-label">Transcripts</span>
          <input type="file" accept=".txt,text/plain" multiple disabled={loading}
                 onChange={(e) => setFiles([...e.target.files])} />
          <span className="file-names">
            {files.length ? files.map((f) => f.name).join(", ") : "Choose one or more .txt files"}
          </span>
        </label>
        <label className="file">
          <span className="file-label">Interview guide (optional)</span>
          <input type="file" accept=".txt,text/plain" disabled={loading}
                 onChange={(e) => setGuide(e.target.files[0] || null)} />
          <span className="file-names">
            {guide ? guide.name : "None: flagged questions, themes and chat only (samples use their own guide)"}
          </span>
        </label>

        <div className="actions">
          <button className="btn" disabled={loading || !files.length}
                  onClick={() => onAnalyze({ files, guide })}>
            Analyze uploads
          </button>
          <button className="btn btn-ghost" disabled={loading}
                  onClick={() => onAnalyze({ useSamples: true, guide })}>
            Use the 3 sample transcripts
          </button>
        </div>
      </div>
    </section>
  );
}
