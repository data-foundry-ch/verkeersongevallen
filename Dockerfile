# DataFoundry showcase — monolith: Vite frontend + FastAPI + DuckDB
# One Render service per showcase → custom subdomain (e.g. ongevallen.datafoundry.ch)

# --- Frontend (same-origin API at /api) ---
FROM node:20-bookworm-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_API_BASE=/api
ENV VITE_MARKETING_URL=https://datafoundry.ch
RUN npm run build

# --- API + static dist ---
FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY backend ./backend
COPY config ./config
COPY deploy/fetch_duckdb.sh /tmp/fetch_duckdb.sh
COPY deploy/docker-entrypoint.sh /tmp/docker-entrypoint.sh

RUN pip install --no-cache-dir .

COPY --from=frontend /fe/dist ./frontend/dist

RUN mkdir -p data/processed

ENV DATABASE_PATH=/app/data/processed/accidents_deploy.duckdb
ENV PYTHONUNBUFFERED=1

# Pre-install spatial (DB is downloaded at container start — Render env vars are runtime-only).
RUN python -c "import duckdb; c=duckdb.connect(); c.execute('INSTALL spatial;'); c.execute('LOAD spatial;')"

EXPOSE 8000

# Strip Windows CRLF if present; invoke via sh so a bad shebang cannot kill the container silently.
RUN sed -i 's/\r$//' /tmp/fetch_duckdb.sh /tmp/docker-entrypoint.sh \
    && chmod +x /tmp/fetch_duckdb.sh /tmp/docker-entrypoint.sh

CMD ["/bin/sh", "/tmp/docker-entrypoint.sh"]
