#!/bin/sh
# Fetch or verify accidents.duckdb for Docker / Render builds.
# Set DUCKDB_DOWNLOAD_URL (https://...) when the file is not in the build context.
set -eu

DB_PATH="${DATABASE_PATH:-data/processed/accidents_deploy.duckdb}"
mkdir -p "$(dirname "$DB_PATH")"

if [ -f "$DB_PATH" ] && [ -s "$DB_PATH" ]; then
  echo "DuckDB present: $DB_PATH ($(wc -c < "$DB_PATH") bytes)"
  exit 0
fi

if [ -n "${DUCKDB_DOWNLOAD_URL:-}" ]; then
  echo "Downloading DuckDB from DUCKDB_DOWNLOAD_URL..."
  curl -fsSL "$DUCKDB_DOWNLOAD_URL" -o "$DB_PATH"
  echo "Downloaded: $DB_PATH ($(wc -c < "$DB_PATH") bytes)"
  exit 0
fi

echo "ERROR: No DuckDB at $DB_PATH and DUCKDB_DOWNLOAD_URL is not set."
echo "  Local: run split-db deploy so data/processed/accidents_deploy.duckdb exists."
echo "  Render: set DUCKDB_DOWNLOAD_URL to a public/signed URL (GitHub Release, R2, etc.)."
exit 1
