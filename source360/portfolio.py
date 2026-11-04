"""Aggregate RFQ scenarios with an explicit shared supplier-capacity budget."""
import json
from pathlib import Path

from source360.database import read, records
from source360.optimization import optimize


def evaluate_portfolio(rfqs, bid_sets, capacity_budgets=None, **params):
    ids = [r["rfq_id"] for r in rfqs]
    if len(ids) != len(set(ids)):
        raise ValueError("RFQ IDs must be unique")
    results = [optimize(r, bid_sets[r["rfq_id"]], **params) for r in rfqs]
    usage = {}
    for result in results:
        for award in result.get("allocations", []):
            sid = str(award["supplier_id"])
            usage[sid] = usage.get(sid, 0) + award["quantity"]
    breaches = []
    if capacity_budgets is not None:
        for sid, quantity in usage.items():
            if sid not in capacity_budgets or quantity > capacity_budgets[sid] + .01:
                breaches.append(dict(supplier_id=sid, quantity=quantity, budget=capacity_budgets.get(sid)))
    feasible = all(r["status"] == "Optimal" for r in results) and not breaches
    baseline = sum(r["baseline_cost"] for r in results if r["status"] == "Optimal")
    landed = sum(r["landed_cost"] for r in results if r["status"] == "Optimal")
    return dict(
        events=len(rfqs), optimal_events=sum(r["status"] == "Optimal" for r in results),
        synthetic=True, realized_savings=False,
        scope="Sum of independent event awards; not a joint portfolio optimum. Repeated supplier capacity must be budgeted separately.",
        portfolio_capacity_verified=capacity_budgets is not None and not breaches,
        status="feasible" if feasible and capacity_budgets is not None else "capacity_unverified" if feasible else "blocked",
        baseline_cost=baseline if feasible else None, landed_cost=landed if feasible else None,
        modeled_savings=baseline-landed if feasible and capacity_budgets is not None else None,
        savings_pct=(baseline-landed)/baseline if feasible and capacity_budgets is not None and baseline else None,
        supplier_usage=usage, capacity_breaches=breaches, results=results,
    )


def main():
    rfqs = records(read("rfq_events"))
    suppliers = records(read("supplier_metrics"))
    lookup = {s["supplier_id"]: s for s in suppliers}
    bids = records(read("rfq_bids"))
    sets = {r["rfq_id"]: [{**b, "canonical_name": lookup[b["supplier_id"]]["canonical_name"],
                              "risk_score": lookup[b["supplier_id"]]["risk_score"]}
                             for b in bids if b["rfq_id"] == r["rfq_id"]] for r in rfqs}
    budgets = {}
    for b in bids:
        sid = str(b["supplier_id"])
        budgets[sid] = budgets.get(sid, 0) + b["capacity"]
    result = evaluate_portfolio(rfqs, sets, budgets, draws=1000)
    result["capacity_basis"] = "Synthetic assumption: event capacities are incremental and additive. Not independently confirmed supplier-wide capacity."
    path = Path("docs/portfolio-evaluation.json")
    path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("results", "supplier_usage")}))


if __name__ == "__main__":
    main()
