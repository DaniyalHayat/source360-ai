# Power BI authoring kit

This directory contains import queries, measures and a theme, not a native PBIX. The user selected a runnable Figma/recruiter app as the primary UX. Open Power BI Desktop to create a native report if required; native Power BI authoring and rendering have not been verified here.

Import the CSV tables in `data/processed/` with the supplied `load_table.pq` function and a folder parameter. Join dim_category[category_id] 1:* fct_spend[category_id], dim_supplier[supplier_id] 1:* fct_spend[supplier_id]. Use single-direction filters and matching numeric types. Keep rfq_bids as a separate RFQ-grain fact; never join it directly to spend at row level. Import `theme.json` and the measures from `measures.dax`.

Suggested pages: Executive (spend, off-contract exposure, observed on-time rate, category bar, risk scatter), Sourcing (export a scenario receipt; use allocations and objective components as separate tables), Controls (receipt, quarantines, checks). Label all outcomes synthetic. The web screenshot in docs/screenshots is a web-cockpit screenshot, not Power BI evidence.
