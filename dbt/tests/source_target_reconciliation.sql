with raw as (
    select sum(extended_spend_usd) as total from {{ source('landing', 'source_po') }}
), quarantine as (
    select coalesce(sum(extended_spend_usd), 0) as total from public.quarantine
), published as (
    select sum(extended_spend_usd) as total from {{ ref('fct_spend') }}
)
select raw.total - quarantine.total - published.total as unexplained
from raw, quarantine, published
where abs(raw.total - quarantine.total - published.total) > 0.01
