# met-weather-pipeline  
  
[![CI](https://github.com/eckballtor/met-weather-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/eckballtor/met-weather-pipeline/actions/workflows/ci.yml)  
[![Nightly snapshot](https://github.com/eckballtor/met-weather-pipeline/actions/workflows/nightly-snapshot.yml/badge.svg)](https://github.com/eckballtor/met-weather-pipeline/actions/workflows/nightly-snapshot.yml)  
  
**Live API:** https://met-weather-pipeline.onrender.com *(free tier — cold start after ~15 min idle, first hit may take ~30–60 s)*  
  
A small end-to-end data pipeline built to establish the tooling: periodic snapshots  
of met.no's public weather forecasts are stored as Parquet, modeled into a DuckDB  
warehouse via dbt (with data-quality tests as first-class citizens), and served as  
JSON by a read-only FastAPI — containerized and deployed from the repo.  
  
## What it produces  
  
Every run captures **what the forecast looked like at a point in time**. A forecast  
is not data — it is a claim that changes. Stacking these snapshots turns the API's  
"current forecast" into a **forecast-history warehouse**, from which the pipeline  
derives its centerpiece: the **revision fact** — how predictions for the same  
(location, hour) were corrected between consecutive snapshots.  
  
Found in the first two snapshots alone: the same evening hour's forecast was revised  
by **−1.8 °C within one day** (at a 212-hour lead time), with the largest corrections  
concentrated at multi-day leads. Larger snapshot sets grow this analysis  
automatically — no code change, the data just deepens.  
  
## Architecture
mermaid  
flowchart LR  
A[met.no Locationforecast API] --> B[ingest: one Parquet snapshot per run]  
B --> C[data/snapshots/ — version-controlled history]  
C --> D[dbt: staging view → marts]  
D --> DQ{16 data tests + duplicate check}  
DQ --> E[(warehouse.duckdb)]  
E --> F[FastAPI: read-only JSON API]  
F --> G[Render: live at /docs]  
H[GitHub Actions nightly] --> B  
H --> I[commit + push new snapshot]  
I --> J[auto-redeploy on Render]  
K[GitHub Actions CI] --> DQ  
K --> F
- **Ingestion** (`ingest/ingest.py`) — met.no Locationforecast 2.0 compact; free,  
no API key (terms require an identifying User-Agent, which the script provides  
honestly). Writes one Parquet snapshot per run, stamped with `ingested_at`.  
- **dbt warehouse** (`models/`) — `stg_forecast` view tidies all snapshots via glob;  
marts materialize the serving fact (`fct_forecast_history`, incl.  
`lead_time_hours`) and the `lag()`-windowed drift fact (`fct_forecast_revisions`).  
12 generic tests + 1 custom singular test = **16 quality gates**.  
- **API** (`api/main.py`) — short-lived read-only DuckDB connections; endpoints:  
`/` (menu) · `/health` · `/locations` · `/forecasts/{location}/latest` ·  
`/revisions/{location}` · interactive docs at `/docs`.  
- **Automation** (`.github/workflows/`) — CI on every push (dbt build + API smoke  
test); nightly cron ingests a fresh snapshot, **validates it with all 16 tests,  
then commits and pushes** — only test-passing snapshots enter history, and each  
push auto-redeploys Render.  
  
## Design decisions  
  
- **DuckDB as the warehouse** — a real analytical engine in a single file: no  
server, no credentials, reproducible anywhere. Same model code would port to  
Postgres/Snowflake adapters unchanged.  
- **Versioned snapshot history** — the temporal state lives in git (KB-scale  
Parquet), not on a server. Lesson learned live: each container build is  
stateless, and a stateless build can only ever bake *one* snapshot — so  
accumulation was moved into the repo, which every build extends.  
- **The image build is a pipeline run** — the Dockerfile ingests and dbt-builds at  
image creation, so `docker run` serves a warehouse with data-as-of-build-time;  
rebuild = refresh.  
- **Tests as deploy gates** — dbt tests run locally, in CI, in every nightly run,  
and inside every Docker build. A snapshot that breaks a contract never reaches  
the warehouse or the live service.  
  
## Quickstart
bash  
uv sync --frozen  
uv run python -m ingest.ingest # add a fresh snapshot  
uv run dbt build --profiles-dir . # warehouse + 16 tests  
uv run uvicorn api.main:app --port 8000
Or the whole thing in one image:
bash  
docker build -t met-weather-pipeline . && docker run -p 8000:8000 met-weather-pipeline
