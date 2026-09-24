import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { analyze, getPasscode, needsPasscode, setPasscode } from "./api.js";
import Background from "./components/Background.jsx";
import UploadPanel from "./components/UploadPanel.jsx";
import HotQuestionsSection from "./components/HotQuestionsSection.jsx";
import AnswersSection from "./components/AnswersSection.jsx";
import ThemesSection from "./components/ThemesSection.jsx";
import AskSection from "./components/AskSection.jsx";
import TranscriptDrawer from "./components/TranscriptDrawer.jsx";

const CHAT_SUGGESTIONS = [
  "Where do the speakers disagree the most?",
  "What numbers or figures were mentioned, and by whom?",
  "What next steps were agreed?",
];

const pad = (n) => String(n).padStart(2, "0");

export default function App() {
  const [result, setResult] = useState(null);
  const [lastRequest, setLastRequest] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [focus, setFocus] = useState(null);   // the quote whose transcript is open
  const resultsRef = useRef(null);
  const [askPasscode, setAskPasscode] = useState(false);   // only on deploys that set one
  const [passcodeInput, setPasscodeInput] = useState("");

  useEffect(() => {
    needsPasscode().then((needed) => setAskPasscode(needed && !getPasscode()));
  }, []);

  const experts = useMemo(
    () => Object.fromEntries((result?.transcripts || []).map((t) => [t.id, t])),
    [result]
  );

  async function run(request) {
    setLoading(true);
    setError(null);
    setResult(null);   // never leave an old analysis on screen under a new request
    setFocus(null);
    try {
      setResult(await analyze(request));
      setLastRequest(request);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (result) resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [result]);

  const openQuote = useCallback((quote) => setFocus(quote), []);
  const closeDrawer = useCallback(() => setFocus(null), []);

  return (
    <>
      <Background />
      <div className="page">
        <header className="topbar">
          <span className="brand">Transcript<em>Analyzer</em></span>
          {result && (
            <div className="topbar-right">
              <span className="stat" title="Every quote is checked in code against the transcript">
                <strong>{result.stats.verified}/{result.stats.cited}</strong> quotes verified · {result.model}
              </span>
              <button className="btn btn-ghost btn-sm" disabled={loading}
                      title="Ignore the cache and ask the model again"
                      onClick={() => run({ ...lastRequest, refresh: true })}>
                Re-run
              </button>
            </div>
          )}
        </header>

        <section className="hero">
          <p className="eyebrow">Expert-call analysis</p>
          <h1>Every answer, <em>with its source.</em></h1>
          <p className="lead">
            Flags the questions that matter most, answers your interview guide per expert, maps
            where the experts agree and differ, and lets you chat with the transcripts. Every quote is checked word for word against the
            transcript, and every timestamp comes from the file, not the model.
          </p>
        </section>

        {askPasscode ? (
          <form className="panel upload passcode" onSubmit={(e) => {
                  e.preventDefault();
                  setPasscode(passcodeInput.trim());
                  setAskPasscode(false);
                }}>
            <div className="upload-copy">
              <p className="eyebrow">Access</p>
              <h2>Enter the passcode</h2>
              <p className="muted">This shared demo needs a passcode before it will analyse transcripts.</p>
            </div>
            <div className="ask-form">
              <input value={passcodeInput} onChange={(e) => setPasscodeInput(e.target.value)}
                     type="password" placeholder="Passcode" aria-label="Passcode" />
              <button className="btn" disabled={!passcodeInput.trim()}>Continue</button>
            </div>
          </form>
        ) : (
          <UploadPanel loading={loading} onAnalyze={run} />
        )}

        {loading && (
          <div className="panel status" role="status">
            <span className="spinner" aria-hidden="true" />
            Reading the transcripts and verifying every quote. The first run takes about a minute.
          </div>
        )}
        {error && (
          <div className="panel error" role="alert">
            <p>{error}</p>
            {/passcode/i.test(error) && (
              <button className="btn btn-ghost btn-sm" onClick={() => setAskPasscode(true)}>
                Enter passcode
              </button>
            )}
          </div>
        )}

        {result && !loading && (
          <>
            <section className="experts" aria-label="Experts" ref={resultsRef}>
              {result.transcripts.map((t) => (
                <button key={t.id} className="panel expert"
                        onClick={() => setFocus({ transcript_id: t.id, segment_id: null })}>
                  <span className="expert-tag">{t.id}</span>
                  <span className="expert-name">{t.expert_name}</span>
                  <span className="muted">{[t.role, t.market].filter(Boolean).join(" · ")}</span>
                  <span className="link">View transcript →</span>
                </button>
              ))}
            </section>

            <HotQuestionsSection number="01" hotQuestions={result.hot_questions}
                                 experts={experts} onOpen={openQuote} />
            {result.guide && (
              <AnswersSection number="02" result={result} experts={experts} onOpen={openQuote} />
            )}
            <ThemesSection number={pad(result.guide ? 3 : 2)} synthesis={result.synthesis}
                           experts={experts} onOpen={openQuote} />
            <AskSection key={result.analysis_id} number={pad(result.guide ? 4 : 3)}
                        analysisId={result.analysis_id} transcripts={result.transcripts}
                        experts={experts} onOpen={openQuote}
                        suggestions={CHAT_SUGGESTIONS} />
          </>
        )}

        <footer className="footer muted">
          Quotes that cannot be found word for word in the cited transcript line are removed before
          anything is shown.
        </footer>
      </div>

      {focus && experts[focus.transcript_id] && (
        <TranscriptDrawer transcript={experts[focus.transcript_id]} focus={focus} onClose={closeDrawer} />
      )}
    </>
  );
}
