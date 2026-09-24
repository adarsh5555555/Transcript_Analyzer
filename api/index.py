"""Vercel entry point: the same FastAPI app, exposed as a serverless function.

Vercel's Python runtime serves any ASGI app named `app` from this file. The
frontend is served by Vercel as static files, so only /api/* reaches here.
"""

from backend.api import app  # noqa: F401  (Vercel looks for `app`)
