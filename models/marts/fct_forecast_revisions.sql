{{ config(materialized='table') }}

-- Drift fact: how the forecast for the same (location, hour) was revised
-- between consecutive snapshots.
with forecast_series as (
    select
        location,
        forecast_time,
        ingested_at,
        air_temperature,
        lag(ingested_at) over w as prev_ingested_at,
        lag(air_temperature) over w as prev_air_temperature
    from {{ ref('stg_forecast') }}
    window w as (partition by location, forecast_time order by ingested_at)
)
select
    location,
    forecast_time,
    prev_ingested_at as snapshot_before,
    ingested_at as snapshot_after,
    date_diff('hour', prev_ingested_at, forecast_time) as lead_time_hours_before,
    date_diff('hour', ingested_at, forecast_time) as lead_time_hours_after,
    prev_air_temperature as temperature_before,
    air_temperature as temperature_after,
    round(air_temperature - prev_air_temperature, 2) as temperature_revision
from forecast_series
where prev_ingested_at is not null
