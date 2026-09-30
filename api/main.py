"""Serving layer: read-only HTTP API over the dbt-built DuckDB warehouse."""
from datetime import datetime, timezone
from pathlib import Path

import duckdb
from fastapi import FastAPI, HTTPException, Query

WAREHOUSE = Path(__file__).resolve().parent.parent / "warehouse.duckdb"

app = FastAPI(
    title="met-weather-pipeline",
    description="Forecast history and revision analytics from met.no snapshots, "
    "served from a dbt/DuckDB warehouse.",
    version="0.1.0",
)


@app.get("/")
def index() -> dict:
    """Friendly landing: what this service is and what to click."""
    return {
        "service": "met-weather-pipeline",
        "description": "Forecast history and revision analytics from met.no "
        "snapshots, served from a dbt/DuckDB warehouse.",
        "endpoints": {
            "health": "/health",
            "locations": "/locations",
            "latest_forecast": "/forecasts/{location}/latest?limit=24",
            "revisions": "/revisions/{location}?limit=10",
            "interactive_docs": "/docs",
        },
    }


def _warehouse() -> duckdb.DuckDBPyConnection:
    if not WAREHOUSE.exists():
        raise HTTPException(
            status_code=503,
            detail="warehouse.duckdb not found — run ingestion and dbt build first",
        )
    return duckdb.connect(str(WAREHOUSE), read_only=True)


def _rows(sql: str, params: list | None = None) -> list[dict]:
    con = _warehouse()
    try:
        df = con.sql(sql, params=params or None).df()
    finally:
        con.close()
    return df.where(df.notna(), None).to_dict(orient="records")


@app.get("/health")
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok", "time": datetime.now(timezone.utc)}


@app.get("/locations")
def locations() -> dict:
    """Locations present in the warehouse."""
    return {
        "locations": [
            r["location"]
            for r in _rows(
                "select distinct location from fct_forecast_history order by 1"
            )
        ]
    }


@app.get("/forecasts/{location}/latest")
def latest_forecast(location: str, limit: int = Query(default=24, ge=1, le=200)) -> dict:
    """The most recent snapshot's forecast rows for one location."""
    rows = _rows(
        """
        select ingested_at, location, forecast_time, air_temperature,
               wind_speed_ms, precipitation_next_1h, symbol_next_1h, lead_time_hours
        from fct_forecast_history
        where location = ?
          and ingested_at = (select max(ingested_at) from fct_forecast_history
                             where location = ?)
        order by forecast_time
        limit ?
        """,
        [location, location, limit],
    )
    if not rows:
        raise HTTPException(404, f"unknown location: {location!r}")
    return {
        "location": location,
        "snapshot": rows[0]["ingested_at"],
        "n_rows": len(rows),
        "rows": rows,
    }


@app.get("/revisions/{location}")
def revisions(location: str, limit: int = Query(default=10, ge=1, le=100)) -> dict:
    """Largest forecast revisions (same hour, consecutive snapshots) for one location."""
    rows = _rows(
        """
        select location, forecast_time, snapshot_before, snapshot_after,
               temperature_before, temperature_after, temperature_revision,
               lead_time_hours_after
        from fct_forecast_revisions
        where location = ?
        order by abs(temperature_revision) desc
        limit ?
        """,
        [location, limit],
    )
    if not rows:
        raise HTTPException(404, f"no revisions found for location: {location!r}")
    return {"location": location, "n_rows": len(rows), "rows": rows}
