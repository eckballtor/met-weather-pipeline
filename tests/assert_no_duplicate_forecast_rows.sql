-- Fails if the same (snapshot, location, forecast hour) appears twice.
select
    ingested_at,
    location,
    forecast_time,
    count(*) as duplicate_rows
from {{ ref('fct_forecast_history') }}
group by all
having count(*) > 1
