with resolved as (
    select p.*, s.supplier_id as resolved_supplier_id,
        case p.currency when 'USD' then 1.0 when 'EUR' then 1.08 when 'GBP' then 1.27 end as resolved_fx
    from {{ source('landing', 'source_po') }} p
    left join {{ source('landing', 'dim_supplier') }} s
        on lower(trim(p.supplier_raw)) = lower(trim(s.canonical_name))
        or lower(trim(p.supplier_raw)) = lower(trim(s.alias))
)
select po_line_id, po_id, resolved_supplier_id as supplier_id, item_id, category_id,
    cast(order_date as date) as order_date, quantity, unit_price_local,
    currency, resolved_fx as fx_rate_usd,
    unit_price_local * resolved_fx as unit_price_usd,
    contract_id, promised_date, delivered_date, defective_units,
    case when contract_id is null or contract_id = '' then 1 else 0 end as off_contract_flag,
    source_system
from resolved
where quantity > 0 and unit_price_local > 0 and resolved_supplier_id is not null and resolved_fx is not null
