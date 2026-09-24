// A deployed instance may require a shared passcode (APP_PASSCODE on the server).
// It is kept per browser; locally there is none and nothing is ever prompted.
const PASSCODE_KEY = "ta_passcode";

export function getPasscode() {
  try {
    return localStorage.getItem(PASSCODE_KEY) || "";
  } catch {
    return "";
  }
}

export function setPasscode(value) {
  try {
    localStorage.setItem(PASSCODE_KEY, value);
  } catch {
    /* private window: the passcode just will not be remembered */
  }
}

function authHeaders(extra = {}) {
  const code = getPasscode();
  return code ? { ...extra, "X-Passcode": code } : extra;
}

async function request(url, options) {
  const res = await fetch(url, options);
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    const message = typeof detail === "string" ? detail
      : Array.isArray(detail) ? detail.map((d) => d.msg).join("; ")
      : `Request failed (${res.status})`;
    throw new Error(message);
  }
  return body;
}

export function analyze({ files, guide, useSamples, refresh }) {
  const form = new FormData();
  if (useSamples) form.append("use_samples", "true");
  for (const f of files || []) form.append("files", f);
  if (guide) form.append("guide", guide);
  if (refresh) form.append("refresh", "true");
  return request("/api/analyze", { method: "POST", body: form, headers: authHeaders() });
}

export function ask(analysisId, question, history = [], transcripts = null) {
  return request("/api/ask", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    // transcripts travel with the question so the API needs no server-side state
    body: JSON.stringify({ analysis_id: analysisId, question, history, transcripts }),
  });
}

export async function needsPasscode() {
  try {
    const r = await fetch("/api/health");
    const body = await r.json();
    return Boolean(body.passcode_required);
  } catch {
    return false;
  }
}
