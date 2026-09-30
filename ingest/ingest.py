"""Ingestion stage: fetch one Locationforecast snapshot from met.no and store as Parquet.

Each run captures what the forecast looked like at a point in time;
the sequence of snapshots forms a forecast-history dataset,
modeled downstream with dbt.
"""
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import httpx
import pandas as pd

# met.no terms of use require an identifying User-Agent.
USER_AGENT = "met-weather-pipeline/0.1 github.com/eckballtor/met-weather-pipeline"

BASE_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
LOCATIONS = {
    "oslo": (59.9139, 10.7522),
    "bergen": (60.3913, 5.3221),
}
RAW_DIR = Path("data/snapshots")
# No API key. The met.no module is credential-free.


def fetch_snapshot(name: str, lat: float, lon: float) -> pd.DataFrame:
    """Fetch one forecast and flatten the timeseries to tidy rows."""
    resp = httpx.get(
        BASE_URL,
        params={"lat": lat, "lon": lon},
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    resp.raise_for_status()
    payload = resp.json()

    rows = []
    for entry in payload["properties"]["timeseries"]:
        details = entry["data"]["instant"]["details"]
        next_1h = entry["data"].get("next_1_hours") or {}
        rows.append(
            {
                "location": name,
                "forecast_time": entry["time"],
                "air_temperature": details.get("air_temperature"),
                "wind_speed_ms": details.get("wind_speed"),
                "precipitation_next_1h": (next_1h.get("details") or {}).get(
                    "precipitation_amount"
                ),
                "symbol_next_1h": (next_1h.get("summary") or {}).get("symbol_code"),
            }
        )

    df = pd.DataFrame(rows)
    df["forecast_time"] = pd.to_datetime(df["forecast_time"])
    return df


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ingested_at = datetime.now(timezone.utc)  # one timestamp for the whole run

    # loop through cities and stack results into table
    df = pd.concat(
        [fetch_snapshot(name, lat, lon) for name, (lat, lon) in LOCATIONS.items()],
        ignore_index=True,
    )
    df["ingested_at"] = ingested_at

    out = RAW_DIR / f"forecasts_{ingested_at:%Y%m%dT%H%M%SZ}.parquet"
    duckdb.sql(f"COPY df TO '{out}' (FORMAT PARQUET)")
    print(f"wrote {len(df)} rows -> {out}")
    print(df.head(4).to_string(index=False))


if __name__ == "__main__":
    main()
