#!/bin/sh
set -eu

PORT="${PORT:-8501}"

exec streamlit run ui/streamlit_app.py \
    --server.address=0.0.0.0 \
    --server.port="${PORT}" \
    --server.headless=true \
    --server.fileWatcherType=none \
    --browser.gatherUsageStats=false
