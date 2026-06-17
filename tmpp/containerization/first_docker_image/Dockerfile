
# A "best practices" single-stage Dockerfile for a Python AI service.
FROM python:3.12-slim

# Stream logs immediately; don't write .pyc files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# System libs some ML wheels need (kept minimal, cleaned in same layer)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Deps first for caching
COPY artefacts/requirements.txt .
RUN pip install -r requirements.txt

# App code
COPY hello.py classifier.pkl .

# Create a non-root user and hand over ownership, then switch to it
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Liveness probe (uses Python, which exists in the image — curl does NOT)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

#CMD ["python -m", "hello:pancakes", "--host", "0.0.0.0", "--port", "8000"]

CMD ["python", "-m", "flask", "--app", "hello.py", "run", "--host=0.0.0.0", "--port=9000"]