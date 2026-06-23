# Dutch Road Accident Map (A2 MVP)

Local-first web app to explore traffic accident density on the Dutch **A2** motorway using BRON accident data and NWB/RWS road network data.

Inspired conceptually by Norwegian road accident density maps, but built from first principles with Dutch datasets — not a copy of external source code.

## A2-first MVP

The first complete version focuses **only on the A2**. The profiler and ingestion handle all raw files, but bin generation, API endpoints, and the map are A2-specific until the vertical slice works end-to-end.

## Data setup

Place your files as follows:

```
data/raw/nwb/          ← NWB network (wegvakken, shapefile, puntlocaties, …)
data/raw/bron/         ← BRON ongevallen.txt (and optional reference files)
```

This repository includes a copy of sample data under those paths if you cloned with data.

## Quick start

### Windows (PowerShell) — recommended

`make` is usually **not** installed on Windows. Use `make.ps1` instead:

```powershell
cd dutch-road-accident-map
python -m venv .venv
.\.venv\Scripts\Activate.ps1
.\make.ps1 install

.\make.ps1 profile
.\make.ps1 pipeline          # or run ingest / normalize / bins / validate separately

# Two terminals:
.\make.ps1 backend           # http://localhost:8000
.\make.ps1 frontend          # http://localhost:5173
```

CMD: `tasks.cmd profile`  
Git Bash: `./tasks.sh profile` (activate with `source .venv/Scripts/activate`)

### Linux / macOS / WSL (with GNU make)

```bash
cd dutch-road-accident-map
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

make profile
make pipeline

make backend    # http://localhost:8001
make frontend   # http://localhost:5173
```

## Commands

| Command | Description |
|---------|-------------|
| `make profile` / `.\make.ps1 profile` / `./tasks.sh profile` | Profile raw files → `data/processed/profile_report.md` |
| `make ingest` / `.\make.ps1 ingest` | Load raw tables into `data/processed/accidents.duckdb` |
| `make normalize` / `.\make.ps1 normalize` | Build `roads_a2_norm`, `accidents_a2_norm`, … |
| `make bins` / `.\make.ps1 bins` | Build A2 distance bins and accident counts |
| `make validate` / `.\make.ps1 validate` | Write `data/processed/validation_report_a2.md` |
| `make backend` / `.\make.ps1 backend` | FastAPI on port 8000 |
| `make frontend` / `.\make.ps1 frontend` | Vite dev server on port 5173 |
| `make dev` / `.\make.ps1 dev` | Prints instructions for concurrent run |
| `make pipeline` / `.\make.ps1 pipeline` | Run profile → ingest → normalize → bins → validate |

## API (A2)

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Health + DuckDB status |
| `GET /api/meta` | A2 counts, year range, severities |
| `GET /api/roads?q=A2` | Road list (A2 implemented; others marked not_implemented_yet) |
| `GET /api/road/A2/bins` | GeoJSON bins (`bin_size_km`, year, severity filters) |
| `GET /api/road/A2/accidents` | GeoJSON accident points |
| `GET /api/road/A2/stats` | Summary statistics |

Non-A2 roads return **501 Not Implemented**.

## Editing `config/column_map.yml`

After `make profile`:

1. Open `data/processed/profile_report.md` → section **A2 detection candidates**
2. Compare with `config/column_map.generated.yml`
3. Set column names in `config/column_map.yml` (especially if your BRON/NWB export version differs)
4. Re-run `make ingest normalize bins validate`

### A2 detection

Road numbers are normalized to a canonical form (`A2`). Detection uses:

- Primary: `WEGNR_HMP = 'A2'` in NWB wegvakken
- Fallbacks: route letter/number, road type + number (`R` + `002`), configurable allowed values in `config/column_map.yml` under `a2:`

Accidents are linked to A2 when their `WVK_ID` matches an A2 wegvak segment.

### Accident location hierarchy

1. Direct X/Y coordinates (RD)
2. Puntlocatie / hectopunt reference
3. Wegvak + hectometer interpolation
4. Wegvak midpoint fallback
5. Unresolved (kept in database, never dropped)

## Known limitations

- Column names depend on BRON/NWB export version — use profiler + `column_map.yml`
- Bin geometry may be **approximate** (`approximate_segment_collect`) in MVP
- Road direction / carriageway handling is basic
- Historical (expired) wegvakken are retained but chainage ordering is segment-order based
- **Only A2** is implemented in the map/API MVP

## Stack

- **Analytics:** DuckDB + spatial extension
- **Backend:** FastAPI, Pydantic, Uvicorn
- **Frontend:** Vite, React, TypeScript, MapLibre GL, TanStack Query

## Production deploy (DataFoundry showcases)

Each showcase is **one Render service** (map + API + DuckDB) on a subdomain, e.g. `ongevallen.datafoundry.ch`. Marketing stays on Lovable at `datafoundry.ch`.

See **[DEPLOY.md](DEPLOY.md)** for DNS, Render, and the multi-showcase pattern.

## Next improvements

See [roadmap.md](roadmap.md) for generalization to all A/N roads, vector tiles, and richer filters.
