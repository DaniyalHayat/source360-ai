select coalesce(a.po_line_id,b.po_line_id) as po_line_id
from {{ ref('fct_spend') }} a
full outer join public.fct_spend b using (po_line_id)
where a.po_line_id is null or b.po_line_id is null
    or abs(a.extended_spend_usd-b.extended_spend_usd) > 0.001
    or a.off_contract_flag <> b.off_contract_flag
    or a.on_time <> b.on_time
    or a.price_anomaly <> b.price_anomaly
