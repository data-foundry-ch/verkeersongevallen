#!/bin/sh
# Start API after ensuring deploy DuckDB exists (Render provides DUCKDB_DOWNLOAD_URL at runtime).
set -eu

export DATABASE_PATH="${DATABASE_PATH:-/app/data/processed/accidents_deploy.duckdb}"

echo "Entrypoint: DATABASE_PATH=$DATABASE_PATH"

if [ ! -x /tmp/fetch_duckdb.sh ]; then
  echo "ERROR: /tmp/fetch_duckdb.sh is missing or not executable"
  exit 1
fi

/tmp/fetch_duckdb.sh

echo "Starting uvicorn on port ${PORT:-8000}..."
exec uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
