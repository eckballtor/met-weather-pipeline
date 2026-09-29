{{ config(materialized='view') }}

-- Tidy pass over all raw snapshots: one row per (snapshot, location, forecast hour).
select
    location,
    cast(forecast_time as timestamp) as forecast_time,
    cast(air_temperature as double) as air_temperature,
    cast(wind_speed_ms as double) as wind_speed_ms,
    cast(precipitation_next_1h as double) as precipitation_next_1h,
    symbol_next_1h,
    cast(ingested_at as timestamp) as ingested_at
from read_parquet('data/snapshots/forecasts_*.parquet')
