# MBclaw-Lite — Hermes-Agent long-term memory system
FROM python:3.13-slim

WORKDIR /app

# System deps for ChromaDB (sqlite3 vec extension)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir chromadb

COPY app/ ./app/

ENV DATA_DIR=/data
RUN mkdir -p /data

EXPOSE 8011

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8011/ || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8011"]
