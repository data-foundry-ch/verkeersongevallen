#!/bin/sh
# Start API after ensuring deploy DuckDB exists (Render provides DUCKDB_DOWNLOAD_URL at runtime).
set -eu

export DATABASE_PATH="${DATABASE_PATH:-/app/data/processed/accidents_deploy.duckdb}"

echo "Entrypoint: DATABASE_PATH=$DATABASE_PATH"

FETCH_SCRIPT="/app/deploy/fetch_duckdb.sh"
if [ ! -x "$FETCH_SCRIPT" ]; then
  echo "ERROR: $FETCH_SCRIPT is missing or not executable"
  exit 1
fi

"$FETCH_SCRIPT"

echo "Starting uvicorn on port ${PORT:-8000}..."
exec uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
