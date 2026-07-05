with source as (

    select *
    from {{ source('eia', 'region_data') }}

),

flattened as (

    select
        f.value:period::timestamp_ntz as demand_hour_utc,
        f.value:respondent::string    as respondent,
        f.value:type::string          as series_type,
        f.value:value::float          as value,
        source.source_file,
        source.loaded_at
    from source,
    lateral flatten(input => source.payload:response:data) f

)

select
    demand_hour_utc,
    respondent,
    series_type,
    value,
    source_file,
    loaded_at
from flattened
