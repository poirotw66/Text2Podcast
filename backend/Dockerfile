# Python 3.13 slim is viable here specifically because pydub (which imported the
# stdlib `audioop` module -- removed outright in 3.13) was replaced with direct
# ffmpeg subprocess calls (see app/services/audio_service.py). Don't downgrade
# this base image without re-checking that removal still holds.
FROM python:3.13-slim

# ffmpeg: audio_service.py shells out to the `ffmpeg` binary directly to merge
# synthesized segments -- it must be on PATH, there is no Python fallback.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies are installed from the pinned requirements.txt in their own
# layer, before the source is copied in, so an app-code-only change doesn't
# invalidate the (slow) dependency-install layer's build cache.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Non-root user. Owns /app so it can write outputs/ and uploads/ at runtime
# (see OUTPUTS_DIR / UPLOADS_DIR in app/api/routes.py).
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/outputs /app/uploads \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

# IMPORTANT: exactly one uvicorn worker, always. TaskManager
# (app/services/task_manager.py) keeps all task state in an in-memory dict
# inside this single process -- it is not shared across processes. Running
# with --workers > 1 (or scaling this container to multiple replicas behind a
# naive load balancer) silently breaks task status lookups and SSE progress
# streaming: a request can land on a worker that never saw the task get
# created. See backend/README.md ("Deployment constraint: single process
# only") before changing this. If you need horizontal scaling, TaskManager
# must first be swapped for a shared store (Redis/SQLite) -- it already
# exposes a TaskStore interface for that, but no implementation exists yet.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
