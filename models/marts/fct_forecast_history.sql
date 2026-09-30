{{ config(materialized='table') }}

-- Serving fact: every forecast claim ever ingested.
-- one row per (snapshot, location, forecast hour).
select
    ingested_at,
    location,
    forecast_time,
    air_temperature,
    wind_speed_ms,
    precipitation_next_1h,
    symbol_next_1h,
    date_diff('hour', ingested_at, forecast_time) as lead_time_hours
from {{ ref('stg_forecast') }}
