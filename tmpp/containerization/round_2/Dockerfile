# syntax=docker/dockerfile:1
# ============ STAGE 1: builder ============
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1
WORKDIR /app

# Build tools live ONLY in this stage and are never shipped to the runtime image.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Isolated virtualenv we copy out wholesale into the runtime stage.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ============ STAGE 2: runtime ============
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app

# Copy ONLY the finished virtualenv from the builder — no compilers, no caches.
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# App code (app.py, ingest.py, templates/), owned by the non-root user.
COPY --chown=appuser:appuser . .
USER appuser

EXPOSE 8000
# Liveness probe via Python (curl isn't in slim images).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Production WSGI server. ONE worker keeps a single Prometheus metrics registry;
# threads give cheap concurrency for I/O-bound requests (each /ask waits on OpenAI
# + Chroma). Scale out with more workers + multiprocess metrics in production.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "8", "--timeout", "120", "app:app"]
