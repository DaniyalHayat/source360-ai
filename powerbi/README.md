# Native Power BI report

Open `Source360/Source360.pbix` for the portable report, or `Source360/Source360.pbip` for the editable project. Both were authored in Power BI Desktop; the PBIX contains its imported data model and all five report pages. The project embeds its synthetic analytical tables as Power Query data, so it has no personal file-path or cloud-credential dependency. Refresh the PBIP on first open. The executive and sourcing pages were visually verified; screenshots are in `docs/screenshots/powerbi-*.png`.

Rebuild from the local Source360 dataset with `python -m powerbi.build_project` from the repository root. Pages cover executive spend, supplier performance, the modeled IT Hardware award with P10/P90 cost estimates, illustrative forecast bands and financial controls. Forecast coverage is uncalibrated; modeled savings are not realized impact.

Import the CSV tables in `data/processed/` with the supplied `load_table.pq` function and a folder parameter. Join dim_category[category_id] 1:* fct_spend[category_id], dim_supplier[supplier_id] 1:* fct_spend[supplier_id]. Use single-direction filters and matching numeric types. Keep rfq_bids as a separate RFQ-grain fact; never join it directly to spend at row level. Import `theme.json` and the measures from `measures.dax`.

Suggested pages: Executive (spend, off-contract exposure, observed on-time rate, category bar, risk scatter), Sourcing (export a scenario receipt; use allocations and objective components as separate tables), Controls (receipt, quarantines, checks). Label all outcomes synthetic. The web screenshot in docs/screenshots is a web-cockpit screenshot, not Power BI evidence.
