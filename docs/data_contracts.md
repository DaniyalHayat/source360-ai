# Data contracts

Snapshot: 2026-10-30. Seed: 360. All files are generated, not client extracts. Raw manifest stores SHA-256 per file. Source files must be regenerated with a new manifest after intentional changes.

| Source | Grain | Primary checks |
|---|---|---|
| erp_purchase_orders.csv | One PO line | Positive quantity/price, explicit currency, supplier resolution, unique PO line ID |
| supplier_portal.csv | Supplier | Unique supplier ID, canonical and alias mapping |
| ap_invoices.csv | Invoice line plus injected duplicate IDs | Deduplicate invoice ID; synthetic tax included; not part of spend baseline |
| rfq_events.csv | Single-item RFQ | Positive demand, USD incumbent reference, each-unit convention |
| rfq_bids.csv | RFQ x supplier | Supported currency/UOM, capacity, fixed cost, source reference |
| contracts.json | Contract excerpt | Source ID and untrusted plain-text excerpt |
| communications.csv | Supplier response event | Response hours assessed against stated 48h SLA |
| market_indices.csv | Category x month | Sixty synthetic observations, separate from forecast features |

Source systems are SQL Server-style ERP and MySQL-style supplier portal simulations plus CSV/JSON feeds. No live SQL Server/MySQL integration is claimed. PO invalid values remain in quarantine with explicit reasons. Missing promised dates are excluded from delivery denominators instead of silently imputed. Finance uses PO line spend, not invoice totals; the AP source currently demonstrates ID deduplication, not a complete AP matching/three-way-control system.

Pipeline publication blocks on failed financial bridge, row bridge, uniqueness, referential validity, deduplication or promised-date-completeness checks. Historical snapshot age is explicitly distinct from current live-feed freshness. Freshness policy is demonstrated relative to the fixed synthetic as-of date only.
