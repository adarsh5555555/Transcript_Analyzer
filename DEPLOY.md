# Deploying (free, public link)

The whole app is one container: FastAPI serves the API **and** the built React page, so there is
nothing to split across two hosts. See `Dockerfile`.

## Before you deploy

1. **Push to GitHub** (both hosts deploy from a repo):

   ```bash
   git init && git add -A && git commit -m "Transcript analyzer"
   gh repo create hasamex-transcript-analyzer --private --source=. --push
   ```

   `.env` and `.cache/` are gitignored, so no key and no transcript ever leaves your machine.

2. **Set a spending cap** on the OpenAI dashboard (Billing → limits). A public URL runs on
   your credits.

3. **Pick a passcode.** With `APP_PASSCODE` set, the API refuses anything without it and the
   page asks for it once. Send the passcode alongside the link.

---

> **Hugging Face Docker Spaces now need a PRO account** (changed in 2026; free accounts get
> static and ZeroGPU-Gradio Spaces only). So Option A below is the free route, and it needs no
> Docker at all — locally or remotely.

## Option A: Vercel, free, no card, no sleeping (recommended)

Vercel serves the built React app as static files and runs FastAPI as a serverless function
(`api/index.py`, ASGI). `vercel.json` wires it up, with `maxDuration: 300` because a full
analysis takes about a minute.

Serverless gives no shared memory between requests, so `/api/ask` accepts the transcripts inline:
the browser already has them from `/api/analyze`, and the verifier checks quotes against exactly
those. The analysis is a pure function of its inputs, so instances need no shared state.

```bash
npm i -g vercel
cd /Users/adarsh/Downloads/hasamex-transcript-analyzer
vercel            # first run: log in, accept the defaults, it deploys a preview
vercel --prod     # the public link
```

### Database (needed on serverless)

Serverless instances share no memory or disk, so analyses must live in Postgres or an analysis
cannot be reopened by the next request. [Neon](https://neon.tech) has a free tier with no card:
create a project, copy the **pooled** connection string (it contains `-pooler`), and set it as
`DATABASE_URL`. The table is created automatically on first use.

Without it the app still works: the browser resends the transcripts it already has, so questions
are answered, but refreshing the page loses the analysis and nothing is cached between users.

### Environment variables (dashboard → Settings → Environment Variables)

```
OPENAI_API_KEY = sk-proj-...
DATABASE_URL   = postgresql://...-pooler.../neondb?sslmode=require
APP_PASSCODE   = pick-something
CACHE_DIR      = /tmp/cache        # only used when DATABASE_URL is empty
```

Re-deploy after setting them (`vercel --prod`). Importing the GitHub repo in the Vercel dashboard
works the same way and redeploys on every push.

Sample transcripts answer instantly on a fresh deploy: that analysis ships in `.cache/` and is
read from there, while new analyses write to `/tmp`.

## Option B: Render, free, no card, no Docker

`render.yaml` describes it: Render installs the Python deps and runs uvicorn. The React app is
built on your machine and committed, so the server needs no Node.

1. Push this repo to GitHub.
2. [render.com](https://render.com) → New → **Web Service** → connect the repo →
   runtime **Python** → plan **Free**.
3. Environment → add `OPENAI_API_KEY` and `APP_PASSCODE`.
4. Your link: `https://<name>.onrender.com`

After any frontend change: `cd frontend && npm run build && cd .. && git add -f frontend/dist &&
git commit -m "rebuild ui" && git push`.

Notes: free instances **sleep after 15 minutes idle** and take ~1 minute to wake, so open the link
a couple of minutes before a demo. 750 instance-hours per month, no credit card.

The bundled sample analysis is committed under `.cache/`, so "Use the 3 sample transcripts" on a
fresh deploy answers instantly and costs nothing.

## Option B (needs HF PRO): Hugging Face Spaces

1. Create a Space → **Docker** → blank template → public.
2. Push this repo to the Space remote (or connect the GitHub repo).
3. Add a `README.md` header at the top of the Space's README so it knows the port:

   ```yaml
   ---
   title: Transcript Analyzer
   sdk: docker
   app_port: 7860
   ---
   ```

4. Settings → **Variables and secrets** → add `OPENAI_API_KEY` and `APP_PASSCODE` as *secrets*.
5. Your link: `https://huggingface.co/spaces/<user>/<space>`

Notes: free CPU tier, sleeps after a couple of days idle and wakes on the next visit.

## Option C: your own EC2 + nginx

Same container, no sleeping, custom domain, but not free.

```bash
docker build -t transcript-analyzer .
docker run -d -p 8010:7860 --env-file .env --name analyzer transcript-analyzer
```

Put nginx in front for TLS.

---

## What the deploy changes about behaviour

| | Local | Deployed |
|---|---|---|
| Passcode | none | required if `APP_PASSCODE` is set |
| Rate limit | 12 analyses + 80 questions per hour per IP | same, tune with `ANALYSES_PER_HOUR` / `QUESTIONS_PER_HOUR` |
| Cache | `.cache/` on disk | ephemeral on free tiers: a restart clears it, analyses just re-run |
| Transcripts | your machine | the container's disk **and** the OpenAI API. Say this out loud in the interview. |

## Environment variables

| Name | Required | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | yes | your key |
| `APP_PASSCODE` | no | shared passcode; unset means open access |
| `OPENAI_MODEL` | no | defaults to `gpt-5.5` |
| `ANALYSES_PER_HOUR` | no | per-IP cap on full analyses (default 12) |
| `QUESTIONS_PER_HOUR` | no | per-IP cap on chat questions (default 80) |
| `PORT` | no | injected by the host; defaults to 7860 |
