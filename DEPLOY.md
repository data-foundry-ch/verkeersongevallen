# Deploy: DataFoundry showcases

Each **showcase** (like this accident map) is a **single deploy**: React UI + FastAPI + DuckDB in one Docker container on Render. Your **marketing site stays on Lovable** at `datafoundry.ch`; each showcase gets its own **subdomain**.

```
datafoundry.ch              →  Lovable (marketing, portfolio, links)
ongevallen.datafoundry.ch   →  Render (this repo — map + API)
future-showcase.datafoundry.ch →  another repo / another Render service
```

This repo’s metadata: `deploy/showcase.yml` (`subdomain: ongevallen`).

---

## Architecture

| URL | What runs there |
|-----|-----------------|
| `https://datafoundry.ch` | Lovable marketing app |
| `https://ongevallen.datafoundry.ch` | Full monolith from **this repo** |
| `https://ongevallen.datafoundry.ch/api/*` | Same host — no CORS issues for the map |
| `https://ongevallen.datafoundry.ch/docs` | FastAPI OpenAPI (optional) |

The browser loads the map from `/` and calls `/api/meta`, `/api/road/A2/bins`, etc. on the **same origin**.

**Marketing integration:** add a button on Lovable:

```html
<a href="https://ongevallen.datafoundry.ch">Verkeersongevallen kaart</a>
```

No need to copy map code into Lovable.

---

## 1. Prepare data locally

```powershell
cd dutch-road-accident-map
.\make.ps1 pipeline
```

### Split for deployment (required before Render)

The full `accidents.duckdb` can be several GB. Production uses a **slim deploy file** only.

```powershell
.\make.ps1 split-raw        # Step 1 → accidents_raw.duckdb (raw_* + staging)
.\make.ps1 export-deploy    # Step 2 → accidents_deploy.duckdb (API tables only)
# or both:
.\make.ps1 split-db
```

| File | Purpose | Upload to Render? |
|------|---------|-------------------|
| `accidents.duckdb` | Full local dev | No |
| `accidents_raw.duckdb` | Raw archive / re-normalize | No |
| `accidents_deploy.duckdb` | Map + `/api` | **Yes** |

Upload **`accidents_deploy.duckdb`** to GitHub Release / R2 (must be &lt; 2 GB for GitHub).

Deploy DB contains only: `roads_norm`, `accidents_norm`, `raw_nwb_hectointervallen` (trimmed), `accidents_staging` (fatal/injury), filtered to `implemented_roads` in `config/app.yml`.

---

## 2. Deploy to Render (one service per showcase)

1. Push this repo to GitHub.
2. Render → **New Blueprint** → connect repo (`render.yaml` → service `showcase-ongevallen`, Starter, Frankfurt).
3. Set **Environment**:
   | Variable | Required | Example |
   |----------|----------|---------|
   | `DUCKDB_DOWNLOAD_URL` | Yes | `https://.../accidents_deploy.duckdb` |
   | `CORS_ORIGINS` | No* | `https://datafoundry.ch` |

   \*Only if the marketing site fetches this API from the browser. A normal link to the subdomain does **not** need CORS.

4. Deploy. Verify:
   - `https://showcase-ongevallen.onrender.com/api/health` → `ok`
   - `https://showcase-ongevallen.onrender.com/` → map UI (not JSON)

---

## 3. Custom subdomain (`ongevallen.datafoundry.ch`)

### A. Render

1. Service → **Settings** → **Custom Domains** → Add `ongevallen.datafoundry.ch`.
2. Render shows a **CNAME target** (e.g. `showcase-ongevallen.onrender.com`).

### B. DNS (Cloudflare / your registrar)

| Type | Name | Target |
|------|------|--------|
| CNAME | `ongevallen` | `showcase-ongevallen.onrender.com` |

Enable proxy (orange cloud) on Cloudflare if you use it — Render supports this.

### C. Verify

- `https://ongevallen.datafoundry.ch/` — map
- `https://ongevallen.datafoundry.ch/api/health` — API

Update `deploy/showcase.yml` `public_url` if you use a different hostname.

---

## 4. Marketing site (Lovable)

Keep building **only** the marketing site on Lovable at `datafoundry.ch`.

**Do not** embed this map in Lovable unless you want a duplicate integration. Instead:

- **Showcases** section on the homepage listing cards linking to subdomains.
- Each future showcase = new repo → new Render service → new subdomain (`xyz.datafoundry.ch`).

Example showcases config you might track in Notion or a small YAML in the marketing repo:

```yaml
showcases:
  - title: Verkeersongevallen
    url: https://ongevallen.datafoundry.ch
    description: NWB hectometer-km dichtheidskaart
```

---

## 5. Adding the next showcase

Copy this pattern per project:

1. New git repo (or template from this one).
2. Edit `deploy/showcase.yml` (`subdomain`, `public_url`).
3. New Render service (or duplicate Blueprint with new `name` in `render.yaml`).
4. New CNAME: `newname.datafoundry.ch` → that Render hostname.
5. Link from Lovable marketing.

**Cost:** ~$7/mo Render Starter **per** always-on showcase.

---

## 6. Local development (unchanged)

```powershell
.\make.ps1 backend    # API :8001
.\make.ps1 frontend   # Vite :5173, proxies /api
```

Production Docker builds the frontend with `VITE_API_BASE=/api` and serves `frontend/dist` from FastAPI.

### Test monolith locally

```powershell
cd frontend
npm run build
cd ..
.\.venv\Scripts\uvicorn.exe backend.app.main:app --host 127.0.0.1 --port 8001
```

Open `http://127.0.0.1:8001/` — map + API on one port.

### Test Docker

```powershell
docker build -t showcase-ongevallen .
docker run --rm -p 8000:8000 showcase-ongevallen
# http://localhost:8000/
```

With remote DB:

```powershell
docker build --build-arg DUCKDB_DOWNLOAD_URL="https://..." -t showcase-ongevallen .
```

---

## 7. Updating data

1. Re-run pipeline locally.
2. `.\make.ps1 export-deploy`
3. Upload new `accidents_deploy.duckdb`.
3. **Manual Deploy** on Render (rebuild re-downloads the DB).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `/` returns JSON only | `frontend/dist` missing in image — check Docker frontend build stage logs |
| Build: no DuckDB | Set `DUCKDB_DOWNLOAD_URL` |
| Map loads, API 404 | Wrong `VITE_API_BASE` — production must be `/api` |
| SSL on subdomain | Wait for Render + DNS; check CNAME |
| Marketing CORS error | Set `CORS_ORIGINS` to `https://datafoundry.ch` |

---

## File reference

| File | Role |
|------|------|
| `Dockerfile` | Multi-stage: `npm build` + Python API + static dist |
| `render.yaml` | Render Blueprint |
| `deploy/showcase.yml` | Subdomain + public URL for this showcase |
| `deploy/fetch_duckdb.sh` | Download DB at image build |
| `backend/app/static_files.py` | Serves SPA from `frontend/dist` |
