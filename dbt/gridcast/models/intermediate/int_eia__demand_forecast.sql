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
        max(case when series_type = 'D' then value end)  as demand_mwh_raw,
        max(case when series_type = 'DF' then value end) as forecast_mwh
    from staging
    group by demand_hour_utc, respondent

),

-- EIA's feed occasionally emits garbage demand readings -- negative values,
-- or sentinel/overflow values orders of magnitude above anything physically
-- possible for a single respondent (seen: ~2^31 for PJM against a normal
-- range of ~80k-150k). This has to be filtered here, before fct_demand_features
-- builds lag/rolling windows over demand_mwh -- once a bad reading is inside
-- a window function it poisons every lag/rolling value that looks back across
-- it, and no amount of cleaning downstream in the DVC pipeline can undo that.
bounded as (

    select
        *,
        median(demand_mwh_raw) over (partition by respondent) as respondent_median_demand
    from pivoted

)

select
    demand_hour_utc,
    respondent,
    case
        when demand_mwh_raw < 0 then null
        when demand_mwh_raw > 10 * respondent_median_demand then null
        else demand_mwh_raw
    end as demand_mwh,
    forecast_mwh
from bounded
