import hashlib
import json
import math
import time
from collections import defaultdict

import pulp


def joint_award(rfqs, bid_sets, capacities, *, risk_penalty=100., max_share=.6,
                min_suppliers=2, max_suppliers=3, qualified_share=.3,
                capacity_factor=1., logistics_factor=1., snapshot='unknown', **unused):
    started = time.perf_counter()
    if not rfqs or len({r['rfq_id'] for r in rfqs}) != len(rfqs):
        raise ValueError('Supply at least one uniquely identified RFQ')
    values = [risk_penalty, max_share, qualified_share, capacity_factor, logistics_factor]
    if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in values):
        raise ValueError('Allocation parameters must be finite numbers')
    if risk_penalty < 0 or not 0 < max_share <= 1 or not 0 <= qualified_share <= 1 or capacity_factor < 0 or logistics_factor < 0:
        raise ValueError('Invalid allocation bounds')
    if not all(isinstance(n, int) for n in [min_suppliers, max_suppliers]) or not 1 <= min_suppliers <= max_suppliers <= 20:
        raise ValueError('Invalid supplier count bounds')
    periods = {r['rfq_id']: (str(r.get('capacity_period', 'unspecified')), r.get('unit', 'EA')) for r in rfqs}
    pairs, budgets, supplier_dimensions = {}, {}, defaultdict(set)
    for r in rfqs:
        demand = r['demand']
        if not isinstance(demand, (int, float)) or not math.isfinite(demand) or demand <= 0 or not math.isfinite(r['baseline_unit_price']):
            raise ValueError('Demand and baseline must be finite and demand positive')
        for b in bid_sets[r['rfq_id']]:
            key = (r['rfq_id'], int(b['supplier_id']))
            if key in pairs:
                raise ValueError('Duplicate supplier bid within an RFQ')
            if any(not isinstance(b[k], (int, float)) or not math.isfinite(b[k]) or b[k] < 0 for k in ['capacity', 'unit_price_usd', 'logistics_unit_usd', 'fixed_cost', 'risk_score']):
                raise ValueError('Bid values must be finite and nonnegative')
            pairs[key] = b
            supplier_dimensions[key[1]].add(periods[key[0]])
    if isinstance(capacities, dict):
        if any(len(dims) != 1 for dims in supplier_dimensions.values()):
            raise ValueError('Capacity records must specify period and unit when a supplier spans dimensions')
        for sid, dims in supplier_dimensions.items():
            budgets[(sid, *next(iter(dims)))] = capacities.get(str(sid), capacities.get(sid, 0))
    else:
        for c in capacities:
            key = (int(c['supplier_id']), str(c['capacity_period']), c['unit'])
            if key in budgets:
                raise ValueError('Duplicate supplier-period-unit capacity record')
            budgets[key] = c['capacity']
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in budgets.values()):
        raise ValueError('Shared capacities must be finite and nonnegative')
    model = pulp.LpProblem('joint_sourcing_portfolio', pulp.LpMinimize)
    x = {k: pulp.LpVariable(f'quantity_{i}', lowBound=0) for i, k in enumerate(pairs)}
    y = {k: pulp.LpVariable(f'selected_{i}', cat='Binary') for i, k in enumerate(pairs)}
    prices = {k: b['unit_price_usd'] + b['logistics_unit_usd'] * logistics_factor for k, b in pairs.items()}
    model += pulp.lpSum((prices[k] + risk_penalty * b['risk_score'] / 100) * x[k] + b['fixed_cost'] * y[k] for k, b in pairs.items())
    for r in rfqs:
        keys = [k for k in pairs if k[0] == r['rfq_id']]
        model += pulp.lpSum(x[k] for k in keys) == r['demand']
        model += pulp.lpSum(y[k] for k in keys) >= min_suppliers
        model += pulp.lpSum(y[k] for k in keys) <= max_suppliers
        model += pulp.lpSum(x[k] for k in keys if pairs[k]['qualified']) >= qualified_share * r['demand']
        for k in keys:
            model += x[k] <= pairs[k]['capacity'] * y[k]
            model += x[k] <= max_share * r['demand']
            model += x[k] >= .01 * r['demand'] * y[k]
    capacity_keys = {(sid, *periods[rid]) for rid, sid in pairs}
    for sid, period, unit in capacity_keys:
        model += pulp.lpSum(x[k] for k in pairs if k[1] == sid and periods[k[0]] == (period, unit)) <= budgets.get((sid, period, unit), 0) * capacity_factor
    model.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=12, gapRel=0))
    optimal = model.status == pulp.LpStatusOptimal and model.sol_status == pulp.LpSolutionOptimal
    payload = dict(rfqs=rfqs, bids=bid_sets, capacities=capacities, snapshot=snapshot,
                   risk_penalty=risk_penalty, max_share=max_share, qualified_share=qualified_share,
                   min_suppliers=min_suppliers, max_suppliers=max_suppliers, capacity_factor=capacity_factor, logistics_factor=logistics_factor)
    result = dict(events=len(rfqs), synthetic=True, realized_savings=False, status='feasible' if optimal else 'blocked',
                  solver_status=pulp.LpStatus[model.status], solver='PuLP/CBC joint mixed-integer program',
                  input_hash=hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(), input_snapshot_id=snapshot,
                  scope='Joint awards across all events with shared supplier-period-unit capacity constraints.',
                  capacity_basis='Capacity is supplied independently of bids and awards; annual throughput proxy is a declared synthetic planning assumption.',
                  portfolio_capacity_verified=optimal, baseline_cost=None, landed_cost=None, modeled_savings=None,
                  savings_pct=None, optimal_events=len(rfqs) if optimal else 0, results=[], supplier_capacity=[], capacity_breaches=[])
    if optimal:
        for r in rfqs:
            allocations = [dict(supplier_id=k[1], name=b['canonical_name'], quantity=float(x[k].value()),
                                unit_landed_cost=prices[k], cost=float(x[k].value()) * prices[k] + b['fixed_cost'],
                                risk_score=b['risk_score']) for k, b in pairs.items() if k[0] == r['rfq_id'] and x[k].value() > 1e-5]
            result['results'].append(dict(rfq_id=r['rfq_id'], status='Optimal', demand=r['demand'],
                                         allocations=allocations, baseline_cost=r['demand'] * r['baseline_unit_price'],
                                         landed_cost=sum(a['cost'] for a in allocations)))
        for sid, period, unit in sorted(capacity_keys):
            used = sum(float(x[k].value()) for k in pairs if k[1] == sid and periods[k[0]] == (period, unit))
            cap = budgets.get((sid, period, unit), 0) * capacity_factor
            result['supplier_capacity'].append(dict(supplier_id=sid, capacity_period=period, unit=unit,
                                                    capacity=cap, used=used, slack=cap-used, binding=abs(cap-used) < .01))
        result['supplier_usage'] = {str(sid): sum(c['used'] for c in result['supplier_capacity'] if c['supplier_id'] == sid) for sid in supplier_dimensions}
        result['baseline_cost'] = sum(r['baseline_cost'] for r in result['results'])
        result['landed_cost'] = sum(r['landed_cost'] for r in result['results'])
        result['modeled_savings'] = result['baseline_cost'] - result['landed_cost']
        result['savings_pct'] = result['modeled_savings'] / result['baseline_cost'] if result['baseline_cost'] else None
        result['risk_adjusted_objective'] = pulp.value(model.objective)
    result['solve_ms'] = round((time.perf_counter() - started) * 1000, 3)
    return result
