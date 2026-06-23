#!/usr/bin/env bash
# Git Bash / Linux task runner when `make` is not installed.
# Usage: ./tasks.sh profile

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/Scripts/python.exe" ]]; then
  PYTHON="$ROOT/.venv/Scripts/python.exe"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON="python"
fi

API_PORT="${API_PORT:-8001}"

run_pipeline() {
  "$PYTHON" scripts/00_profile_raw_data.py
  "$PYTHON" scripts/01_ingest_to_duckdb.py
  "$PYTHON" scripts/02_build_normalized_tables.py
  "$PYTHON" scripts/03_build_a2_bins.py
  "$PYTHON" scripts/04_validate_a2_outputs.py
  echo "Full A2 pipeline complete."
}

TARGET="${1:-help}"

case "$TARGET" in
  profile)   "$PYTHON" scripts/00_profile_raw_data.py ;;
  ingest)    "$PYTHON" scripts/01_ingest_to_duckdb.py ;;
  normalize) "$PYTHON" scripts/02_build_normalized_tables.py ;;
  bins)      "$PYTHON" scripts/03_build_a2_bins.py ;;
  validate)  "$PYTHON" scripts/04_validate_a2_outputs.py ;;
  split-raw) "$PYTHON" scripts/05_split_databases.py raw ;;
  export-deploy) "$PYTHON" scripts/05_split_databases.py deploy ;;
  split-db)  "$PYTHON" scripts/05_split_databases.py all ;;
  pipeline)  run_pipeline ;;
  backend)
    if [[ -x "$ROOT/.venv/Scripts/uvicorn.exe" ]]; then
      UVICORN="$ROOT/.venv/Scripts/uvicorn.exe"
    else
      UVICORN="uvicorn"
    fi
    if [[ "${DEV_RELOAD:-}" == "1" ]]; then
      "$UVICORN" backend.app.main:app --reload --reload-dir backend/app --host 127.0.0.1 --port "$API_PORT"
    else
      "$UVICORN" backend.app.main:app --host 127.0.0.1 --port "$API_PORT"
    fi
    ;;
  frontend)
    cd frontend && npm run dev
    ;;
  install)
    "$PYTHON" -m pip install -e ".[dev]"
    (cd frontend && npm install)
    ;;
  dev)
    echo "Run in two terminals:"
    echo "  ./tasks.sh backend"
    echo "  ./tasks.sh frontend"
    ;;
  help|*)
    cat <<'EOF'
Dutch Road Accident Map — tasks

  ./tasks.sh install     Install dependencies
  ./tasks.sh profile     Profile raw data
  ./tasks.sh ingest      Ingest into DuckDB
  ./tasks.sh normalize   Build normalized tables
  ./tasks.sh bins        Build A2 bins
  ./tasks.sh validate    Validation report
  ./tasks.sh split-raw   Export raw_* to accidents_raw.duckdb
  ./tasks.sh export-deploy  Slim API DB to accidents_deploy.duckdb
  ./tasks.sh split-db    Both split steps
  ./tasks.sh pipeline    Run profile → validate
  ./tasks.sh backend     FastAPI on http://localhost:8001
  ./tasks.sh frontend    Vite on http://localhost:5173

Activate venv (Git Bash):  source .venv/Scripts/activate
PowerShell:                .\.venv\Scripts\Activate.ps1
EOF
    ;;
esac
