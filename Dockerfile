# 1. build the React app
FROM node:20-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# 2. run FastAPI, which also serves the built app (one service, one port)
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt
COPY backend/ backend/
COPY data/ data/
COPY evals/ evals/
COPY --from=ui /ui/dist frontend/dist

# Hugging Face Spaces runs containers as uid 1000, so the app dir and the cache
# directory must be owned by that user or writes fail at runtime.
RUN useradd -m -u 1000 appuser && mkdir -p /app/.cache && chown -R appuser /app
USER appuser
ENV CACHE_DIR=/app/.cache

# hosts inject $PORT (Render, Fly, Cloud Run); Hugging Face Spaces expects 7860
ENV PORT=7860
EXPOSE 7860
CMD ["sh", "-c", "uvicorn backend.api:app --host 0.0.0.0 --port ${PORT:-7860}"]
