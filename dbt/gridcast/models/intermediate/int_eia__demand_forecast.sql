with staging as (

    select *
    from {{ ref('stg_eia__region_data') }}

),

-- Pivot D/DF out of series_type into their own columns so downstream marts
-- can build lag/rolling features on demand without unstacking per row.
pivoted as (

    select
        demand_hour_utc,
        respondent,
        max(case when series_type = 'D' then value end)  as demand_mwh,
        max(case when series_type = 'DF' then value end) as forecast_mwh
    from staging
    group by demand_hour_utc, respondent

)

select
    demand_hour_utc,
    respondent,
    demand_mwh,
    forecast_mwh
from pivoted
