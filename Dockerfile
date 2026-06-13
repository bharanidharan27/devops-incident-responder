FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    ENV=prod \
    DB_FILE=/data/dev.db \
    RAG_PERSIST_DIR=/data/rag_index \
    LOGS_MODE=local \
    API_HOST=127.0.0.1 \
    API_PORT=8000 \
    API_BASE_URL=http://127.0.0.1:8000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data \
    && useradd --create-home --shell /bin/bash appuser \
    && sed -i 's/\r$//' scripts/*.sh \
    && chmod +x scripts/start_streamlit.sh scripts/start_api.sh \
    && chown -R appuser:appuser /app /data

USER appuser

EXPOSE 8000 8501

CMD ["scripts/start_streamlit.sh"]
