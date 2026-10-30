select category_id, month, sum(extended_spend_usd) as spend_usd, sum(quantity) as units
from {{ ref('fct_spend') }}
group by category_id, month
