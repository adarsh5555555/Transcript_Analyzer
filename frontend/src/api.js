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

export async function ask(analysisId, question, history = [], transcripts = null) {
  const send = (body) =>
    request("/api/ask", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });

  try {
    // Normal path: the server looks the analysis up in its store.
    return await send({ analysis_id: analysisId, question, history });
  } catch (e) {
    // No shared store (serverless without a database): resend the transcripts
    // this browser already has, so the question can still be answered.
    if (transcripts && /unknown analysis_id/i.test(e.message)) {
      return send({ analysis_id: analysisId, question, history, transcripts });
    }
    throw e;
  }
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
