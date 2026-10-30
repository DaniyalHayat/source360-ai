# Metric dictionary

All USD values are nominal synthetic amounts. PO spend excludes tax; invoice totals include a synthetic 7% tax. Never sum the two.

| Metric | Definition and scope |
|---|---|
| Governed spend | Sum(quantity x local unit price x fixed FX) for valid, resolved PO lines, Nov 2023-Oct 2026 |
| Annual spend | Same definition with order_date >= 2025-11-01 within the snapshot |
| Off-contract exposure | Governed spend with blank contract ID; review population, not assumed savings |
| Price anomaly exposure | Spend where absolute robust z > 3.5; item median and MAD; overlaps off-contract exposure |
| Robust z | 0.6745 x (unit USD price - item median) / item MAD; zero MAD is not flagged |
| On-time delivery | Observed delivered_date <= promised_date count / rows with both dates observed |
| Defect rate | Defective units / purchased units; quantity-weighted |
| Supplier concentration | Supplier spend / its category spend |
| Risk score | 100 x weighted sum of bounded [0,1] components; policy weights below |
| Landed award cash cost | Awarded quantity x (normalized bid USD/EA + logistics USD/EA x multiplier), plus selected supplier fixed costs |
| RFQ baseline cost | Scenario demand x synthetic reference USD/EA, excluding additional fixed/logistics charges; assumed all-in incumbent reference |
| Simulated cash savings | Baseline cost - landed cash cost; no realized impact |
| Optimization objective | Landed cash cost + risk_penalty_USD_per_risk_unit_per_EA x sum(award units x risk_score/100) |
| Qualified allocation | Award share assigned to explicitly qualified operational suppliers; no protected-attribute policy |
| Reconciliation delta | Absolute(raw signed USD PO total - quarantined signed USD total - published total) |
| Forecast WAPE | Sum(abs(actual - predicted)) / sum(abs(actual)), six expanding one-step test origins |

Risk components: late fraction (30%); min(defect_rate/.05,1) (20%); min(price CV/.25,1) (15%); assumed 72% capacity utilization (15%); mean clipped response SLA excess (10%); category concentration (10%). Not an industry-standard score or a default probability. All utilization values are deliberately synthetic assumptions.

FX schedule: USD 1, EUR 1.08, GBP 1.27 USD per local unit. BOX10 means 10 EA. No live market FX is represented. No scoring bonus based on nationality or protected attributes exists.
