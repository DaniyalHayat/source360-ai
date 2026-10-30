select p.*,
    quantity * unit_price_usd as extended_spend_usd,
    to_char(order_date, 'YYYY-MM') || '-01' as month,
    case when promised_date <> '' and delivered_date <> '' then 1 else 0 end as delivery_observed,
    case when promised_date <> '' and delivered_date <> '' and cast(delivered_date as date) <= cast(promised_date as date)
        then 1 else 0 end as on_time,
    case when abs(0.6745 * (unit_price_usd - item_median) / nullif(item_mad, 0)) > 3.5 then 1 else 0 end as price_anomaly
from {{ ref('stg_purchase_order_lines') }} p
join (
    select item_id, percentile_cont(0.5) within group (order by unit_price_usd) as item_median
    from {{ ref('stg_purchase_order_lines') }} group by item_id
) med using (item_id)
join (
    select b.item_id, percentile_cont(0.5) within group (order by abs(b.unit_price_usd - m.item_median)) as item_mad
    from {{ ref('stg_purchase_order_lines') }} b
    join (
        select item_id, percentile_cont(0.5) within group (order by unit_price_usd) as item_median
        from {{ ref('stg_purchase_order_lines') }} group by item_id
    ) m using (item_id)
    group by b.item_id
) mad using (item_id)
