with demand_forecast as (

    select *
    from {{ ref('int_eia__demand_forecast') }}

),

-- Lag and rolling features are windowed per respondent, ordered by hour.
-- Rolling windows deliberately exclude the current row (N PRECEDING AND
-- 1 PRECEDING) so a feature never peeks at the value it's trying to help
-- predict — the same point-in-time-correctness rule as the time-based
-- train/test split downstream.
windowed as (

    select
        demand_hour_utc,
        respondent,
        demand_mwh,
        forecast_mwh,

        lag(demand_mwh, 1)   over (partition by respondent order by demand_hour_utc) as demand_lag_1h,
        lag(demand_mwh, 24)  over (partition by respondent order by demand_hour_utc) as demand_lag_24h,
        lag(demand_mwh, 168) over (partition by respondent order by demand_hour_utc) as demand_lag_168h,

        avg(demand_mwh)    over (
            partition by respondent order by demand_hour_utc
            rows between 24 preceding and 1 preceding
        ) as demand_rolling_mean_24h,
        stddev(demand_mwh) over (
            partition by respondent order by demand_hour_utc
            rows between 24 preceding and 1 preceding
        ) as demand_rolling_std_24h,

        avg(demand_mwh)    over (
            partition by respondent order by demand_hour_utc
            rows between 168 preceding and 1 preceding
        ) as demand_rolling_mean_168h,
        stddev(demand_mwh) over (
            partition by respondent order by demand_hour_utc
            rows between 168 preceding and 1 preceding
        ) as demand_rolling_std_168h

    from demand_forecast

),

calendar as (

    select
        *,
        hour(demand_hour_utc)          as hour_of_day,
        dayofweekiso(demand_hour_utc)  as day_of_week,      -- 1=Mon ... 7=Sun
        month(demand_hour_utc)         as month,
        dayofweekiso(demand_hour_utc) in (6, 7) as is_weekend
    from windowed

),

holiday_flagged as (

    select
        calendar.*,
        holidays.holiday_date is not null as is_holiday
    from calendar
    left join {{ ref('us_federal_holidays') }} as holidays
        on to_date(calendar.demand_hour_utc) = holidays.holiday_date

)

select
    demand_hour_utc,
    respondent,
    demand_mwh,
    forecast_mwh,
    demand_lag_1h,
    demand_lag_24h,
    demand_lag_168h,
    demand_rolling_mean_24h,
    demand_rolling_std_24h,
    demand_rolling_mean_168h,
    demand_rolling_std_168h,
    hour_of_day,
    day_of_week,
    month,
    is_weekend,
    is_holiday
from holiday_flagged
