#!/bin/sh
# Start API after ensuring deploy DuckDB exists (Render provides DUCKDB_DOWNLOAD_URL at runtime).
set -eu

export DATABASE_PATH="${DATABASE_PATH:-/app/data/processed/accidents_deploy.duckdb}"

if [ -x /tmp/fetch_duckdb.sh ]; then
  /tmp/fetch_duckdb.sh
fi

exec uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
