import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from source360.settings import DATA

CATEGORIES = [
    "IT Hardware",
    "Packaging",
    "Logistics",
    "MRO",
    "Professional Services",
    "Electronics",
    "Facilities",
    "Raw Materials",
    "Office Supplies",
    "Telecom",
]
BASE_PRICES = [920, 18, 145, 62, 210, 88, 115, 45, 24, 170]
FX = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27}


def generate(rows=100_000, seed=360, root=DATA):
    if rows < 1000:
        raise ValueError("Use at least 1,000 PO lines")
    raw = Path(root) / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    names = ["Aster", "Meridian", "Northstar", "Vertex", "Cobalt", "Summit"]
    suppliers = []
    for i in range(60):
        category = i // 6
        name = f"{names[i % 6]} {CATEGORIES[category]}"
        suppliers.append(
            dict(
                supplier_id=i + 1,
                canonical_name=name,
                alias=f"S{i + 1:03d} LTD",
                category_id=category + 1,
                country=["US", "DE", "GB", "CA", "MX", "US"][i % 6],
                qualified=i % 6 in (0, 1, 4),
                updated_at="2026-10-30",
            )
        )
    sm = pd.DataFrame(suppliers)
    sm.to_csv(raw / "supplier_portal.csv", index=False)
    category = rng.integers(0, 10, rows)
    supplier = category * 6 + rng.integers(0, 6, rows) + 1
    quantity = rng.integers(1, 28, rows)
    month = rng.integers(0, 36, rows)
    dates = pd.to_datetime("2023-11-01") + pd.to_timedelta(month * 30 + rng.integers(0, 28, rows), unit="D")
    currency = rng.choice(["USD", "EUR", "GBP"], rows, p=[0.7, 0.2, 0.1])
    fx = np.array([FX[c] for c in currency])
    usd = np.array(BASE_PRICES)[category] * (1 + month * 0.002) * rng.lognormal(0, 0.06, rows)
    usd[::137] *= 1.7
    promised = dates + pd.to_timedelta(rng.integers(10, 35, rows), unit="D")
    delivered = promised + pd.to_timedelta(rng.integers(-5, 6, rows) + (supplier % 6 == 4) * 3, unit="D")
    po = pd.DataFrame(
        dict(
            po_line_id=np.arange(1, rows + 1),
            po_id=[f"PO-{i // 3:07}" for i in range(rows)],
            supplier_raw=[
                sm.iloc[s - 1]["alias" if i % 4 == 0 else "canonical_name"] for i, s in enumerate(supplier)
            ],
            item_id=[f"SKU-{c + 1:02}-01" for c in category],
            category_id=category + 1,
            quantity=quantity,
            unit_price_local=np.round(usd / fx, 4),
            currency=currency,
            order_date=dates.strftime("%Y-%m-%d"),
            promised_date=promised.strftime("%Y-%m-%d"),
            delivered_date=delivered.strftime("%Y-%m-%d"),
            defective_units=rng.binomial(quantity, 0.005 + (supplier % 6) * 0.003),
            contract_id=[f"CTR-{s:03}-1" if i % 5 else "" for i, s in enumerate(supplier)],
            source_system="sqlserver_erp_extract",
        )
    )
    po.loc[po.index[::997], "quantity"] = -1
    po.loc[po.index[::1201], "supplier_raw"] = "UNMAPPED SUPPLIER"
    po.loc[po.index[::311], "promised_date"] = ""
    po.to_csv(raw / "erp_purchase_orders.csv", index=False)
    invoices = po.iloc[: int(rows * 0.85)][["po_line_id", "supplier_raw"]].copy()
    invoices["invoice_id"] = [f"INV-{i:08}" for i in range(len(invoices))]
    invoices["invoice_total_local"] = np.round(
        po.quantity.iloc[: len(invoices)].to_numpy()
        * po.unit_price_local.iloc[: len(invoices)].to_numpy()
        * 1.07,
        2,
    )
    invoices["currency"] = currency[: len(invoices)]
    invoices["tax_rate"] = 0.07
    invoices["paid_date"] = "2026-10-20"
    pd.concat([invoices, invoices.iloc[::200]], ignore_index=True).to_csv(
        raw / "ap_invoices.csv", index=False
    )
    rfqs, bids = [], []
    for i in range(25):
        c = i % 10
        demand = [8000, 120000, 24000, 36000, 16000, 42000, 18000, 80000, 60000, 24000][c]
        rid = f"RFQ-{i + 1:03}"
        rfqs.append(
            dict(
                rfq_id=rid,
                category_id=c + 1,
                title=f"{CATEGORIES[c]} annual sourcing",
                demand=demand,
                baseline_unit_price=round(BASE_PRICES[c] * 1.07, 4),
                issue_date="2026-10-01",
                close_date="2026-11-15",
                unit="EA",
            )
        )
        for j in range(4):
            sid = c * 6 + j + 1
            factor = [0.86, 0.90, 0.82, 0.95][j]
            price = round(BASE_PRICES[c] * factor, 4)
            curr = ["USD", "EUR", "USD", "GBP"][j]
            uom = "BOX10" if j == 1 else "EA"
            bid_price = price / FX[curr] * (10 if uom == "BOX10" else 1)
            bids.append(
                dict(
                    rfq_id=rid,
                    supplier_id=sid,
                    quoted_price=round(bid_price, 4),
                    currency=curr,
                    uom=uom,
                    logistics_unit_usd=BASE_PRICES[c] * [0.025, 0.04, 0.06, 0.015][j],
                    capacity=int(demand * [0.55, 0.65, 0.75, 0.40][j]),
                    lead_time_days=[18, 24, 32, 14][j],
                    fixed_cost=[1200, 1800, 950, 2200][j],
                    qualified=j in (0, 1),
                    contract_id=f"CTR-{sid:03}-1",
                    source_ref=f"synthetic-bid:{rid}:{sid}",
                )
            )
    pd.DataFrame(rfqs).to_csv(raw / "rfq_events.csv", index=False)
    pd.DataFrame(bids).to_csv(raw / "rfq_bids.csv", index=False)
    contracts = []
    for s in suppliers:
        for v in (1, 2):
            cid = f"CTR-{s['supplier_id']:03}-{v}"
            contracts.append(
                dict(
                    document_id=cid,
                    supplier_id=s["supplier_id"],
                    text=f"Contract {cid}. Supplier: {s['canonical_name']}. "
                    f"Payment terms: {30 if v == 1 else 45} days. Lead time: {14 + v * 7} days. "
                    "Currency: USD. Incoterm: DAP. Service level: 98%. "
                    "Valid from 2026-01-01 to 2027-12-31. Human review required.",
                )
            )
    (raw / "contracts.json").write_text(json.dumps(contracts, indent=2), encoding="utf-8")
    comm = pd.DataFrame(
        dict(
            event_id=range(1, 3001),
            supplier_id=rng.integers(1, 61, 3000),
            response_hours=np.round(rng.gamma(2, 10, 3000), 2),
            requested_sla_hours=48,
            channel="email",
            sent_at="2026-10-01T09:00:00Z",
        )
    )
    comm.to_csv(raw / "communications.csv", index=False)
    market = []
    for c in range(10):
        for m, date in enumerate(pd.date_range("2021-11-01", periods=60, freq="MS")):
            market.append(
                dict(
                    category_id=c + 1,
                    month=date.strftime("%Y-%m-%d"),
                    commodity_index=round(100 + m * 0.3 + 3 * np.sin(m * np.pi / 6) + rng.normal(0, 1), 3),
                    freight_index=round(100 + m * 0.08 + rng.normal(0, 0.8), 3),
                )
            )
    pd.DataFrame(market).to_csv(raw / "market_indices.csv", index=False)
    files = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(raw.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    manifest = dict(seed=seed, po_lines=rows, snapshot_date="2026-10-30", synthetic=True, files=files)
    (raw / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=360)
    args = parser.parse_args()
    print(json.dumps(generate(args.rows, args.seed), indent=2))
