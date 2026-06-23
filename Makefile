.PHONY: profile ingest normalize bins validate backend frontend dev install

PYTHON ?= python
ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

profile:
	$(PYTHON) scripts/00_profile_raw_data.py

ingest:
	$(PYTHON) scripts/01_ingest_to_duckdb.py

normalize:
	$(PYTHON) scripts/02_build_normalized_tables.py

bins:
	$(PYTHON) scripts/03_build_a2_bins.py

validate:
	$(PYTHON) scripts/04_validate_a2_outputs.py

backend:
	cd $(ROOT) && uvicorn backend.app.main:app --reload --reload-dir backend/app --host 127.0.0.1 --port 8001

frontend:
	cd frontend && npm run dev

install:
	$(PYTHON) -m pip install -e ".[dev]"
	cd frontend && npm install

dev:
	@echo "Run in two terminals:"
	@echo "  make backend"
	@echo "  make frontend"

pipeline: profile ingest normalize bins validate
	@echo "Full A2 pipeline complete."
