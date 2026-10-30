import hashlib
import json
from datetime import datetime, timezone

import numpy as np
import pulp


def optimize(
    rfq,
    bids,
    *,
    demand=None,
    risk_penalty=100.0,
    max_share=0.6,
    min_suppliers=2,
    max_suppliers=3,
    qualified_share=0.3,
    capacity_factor=1.0,
    logistics_factor=1.0,
    seed=360,
    draws=5000,
    snapshot="unknown",
):
    demand = float(demand if demand is not None else rfq["demand"])
    inputs = dict(
        rfq=rfq,
        bids=bids,
        demand=demand,
        risk_penalty=risk_penalty,
        max_share=max_share,
        min_suppliers=min_suppliers,
        max_suppliers=max_suppliers,
        qualified_share=qualified_share,
        capacity_factor=capacity_factor,
        logistics_factor=logistics_factor,
        seed=seed,
        draws=draws,
        snapshot=snapshot,
    )
    input_hash = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    result = dict(
        scenario_id=input_hash[:24],
        rfq_id=rfq["rfq_id"],
        input_hash=input_hash,
        input_snapshot_id=snapshot,
        timestamp=datetime.now(timezone.utc).isoformat(),
        solver="PuLP / CBC",
        synthetic=True,
        approval_status="human_review_required",
        assumptions=inputs,
    )
    if demand <= 0 or not 0 < max_share <= 1 or not 0 <= qualified_share <= 1:
        raise ValueError("Invalid demand or allocation shares")
    model = pulp.LpProblem("supplier_award", pulp.LpMinimize)
    ids = [int(b["supplier_id"]) for b in bids]
    x = pulp.LpVariable.dicts("units", ids, lowBound=0)
    y = pulp.LpVariable.dicts("selected", ids, cat="Binary")
    prices = {
        int(b["supplier_id"]): b["unit_price_usd"] + b["logistics_unit_usd"] * logistics_factor for b in bids
    }
    model += pulp.lpSum(
        (prices[s] + risk_penalty * b["risk_score"] / 100) * x[s] + b["fixed_cost"] * y[s]
        for s, b in zip(ids, bids)
    )
    model += pulp.lpSum(x.values()) == demand
    model += pulp.lpSum(y.values()) >= min_suppliers
    model += pulp.lpSum(y.values()) <= max_suppliers
    for s, b in zip(ids, bids):
        model += x[s] <= b["capacity"] * capacity_factor * y[s]
        model += x[s] <= max_share * demand
        model += x[s] >= 0.01 * demand * y[s]
    model += pulp.lpSum(x[int(b["supplier_id"])] for b in bids if b["qualified"]) >= qualified_share * demand
    model.solve(pulp.PULP_CBC_CMD(msg=False, threads=1, timeLimit=20))
    result["status"] = pulp.LpStatus[model.status]
    if result["status"] != "Optimal":
        result["allocations"] = []
        result["message"] = (
            "No optimal award. Review demand, capacity, concentration and qualified-source requirements."
        )
        return result
    allocations = []
    for s, b in zip(ids, bids):
        qty = float(x[s].value() or 0)
        if qty > 1e-4:
            allocations.append(
                dict(
                    supplier_id=s,
                    name=b["canonical_name"],
                    quantity=qty,
                    share=qty / demand,
                    unit_landed_cost=prices[s],
                    cost=qty * prices[s] + b["fixed_cost"],
                    risk_score=b["risk_score"],
                    capacity=b["capacity"] * capacity_factor,
                    qualified=bool(b["qualified"]),
                    source_ref=b["source_ref"],
                )
            )
    purchase = sum(
        a["quantity"] * next(b["unit_price_usd"] for b in bids if b["supplier_id"] == a["supplier_id"])
        for a in allocations
    )
    logistics = sum(
        a["quantity"]
        * next(b["logistics_unit_usd"] for b in bids if b["supplier_id"] == a["supplier_id"])
        * logistics_factor
        for a in allocations
    )
    fixed = sum(
        next(b["fixed_cost"] for b in bids if b["supplier_id"] == a["supplier_id"]) for a in allocations
    )
    risk = sum(a["quantity"] * a["risk_score"] / 100 * risk_penalty for a in allocations)
    landed = purchase + logistics + fixed
    baseline = demand * rfq["baseline_unit_price"]
    rng = np.random.default_rng(seed)
    demand_shock = rng.triangular(0.9, 1.0, 1.15, draws)
    common_price = rng.triangular(0.94, 1, 1.12, draws)
    variable = np.zeros(draws)
    for a in allocations:
        variable += (
            a["quantity"] * a["unit_landed_cost"] * common_price * rng.triangular(0.97, 1, 1.04, draws)
        )
    cost_draws = variable * demand_shock + fixed
    savings_draws = baseline * demand_shock - cost_draws
    hist, edges = np.histogram(cost_draws, bins=28)
    result.update(
        allocations=allocations,
        baseline_cost=baseline,
        landed_cost=landed,
        objective_value=landed + risk,
        objective_components=dict(purchase=purchase, logistics=logistics, fixed=fixed, risk_penalty=risk),
        savings=baseline - landed,
        savings_pct=(baseline - landed) / baseline,
        weighted_risk=sum(a["share"] * a["risk_score"] for a in allocations),
        constraint_checks=dict(
            demand_met=abs(sum(a["quantity"] for a in allocations) - demand) < 0.01,
            capacity_respected=all(a["quantity"] <= a["capacity"] + 0.01 for a in allocations),
            concentration_respected=all(a["share"] <= max_share + 1e-6 for a in allocations),
            source_count_respected=min_suppliers <= len(allocations) <= max_suppliers,
            qualified_share_respected=sum(a["share"] for a in allocations if a["qualified"]) + 1e-6
            >= qualified_share,
        ),
        uncertainty=dict(
            draws=draws,
            seed=seed,
            cost_p10=float(np.quantile(cost_draws, 0.1)),
            cost_p50=float(np.quantile(cost_draws, 0.5)),
            cost_p90=float(np.quantile(cost_draws, 0.9)),
            savings_p10=float(np.quantile(savings_draws, 0.1)),
            savings_p90=float(np.quantile(savings_draws, 0.9)),
            histogram=[
                dict(cost=float((edges[i] + edges[i + 1]) / 2), count=int(h)) for i, h in enumerate(hist)
            ],
            method="Fixed award mix; correlated triangular prices and demand. Stress costs only; does not assert stressed capacity feasibility.",
        ),
    )
    return result
