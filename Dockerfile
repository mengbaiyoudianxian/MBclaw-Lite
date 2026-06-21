FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

RUN mkdir -p data/transcripts data/archive
ENV MBCLAW_DB_PATH=/app/data/mbclaw.db
ENV MBCLAW_LLM_MOCK=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
