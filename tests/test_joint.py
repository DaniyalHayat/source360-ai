import pytest
from source360.joint import joint_award


def fixture():
    rfqs = [dict(rfq_id=str(i), demand=10, baseline_unit_price=20, unit='kg', capacity_period='2027') for i in range(2)]
    bids = {r['rfq_id']: [dict(supplier_id=s, canonical_name=str(s), unit_price_usd=p, logistics_unit_usd=0,
                             fixed_cost=0, risk_score=0, capacity=10, qualified=True) for s, p in [(1,2),(2,5),(3,8)]] for r in rfqs}
    return rfqs, bids


def test_joint_solver_reallocates_instead_of_double_counting_capacity():
    rfqs, bids = fixture()
    result = joint_award(rfqs, bids, {'1':5, '2':10, '3':10}, min_suppliers=1, max_suppliers=3, max_share=1)
    assert result['status'] == 'feasible'
    assert result['supplier_usage']['1'] == pytest.approx(5)
    assert result['landed_cost'] == pytest.approx(100)
    assert sum(c['binding'] for c in result['supplier_capacity']) == 2
    assert all(sum(a['quantity'] for a in r['allocations']) == pytest.approx(10) for r in result['results'])


def test_infeasible_shared_capacity_never_returns_savings():
    rfqs, bids = fixture()
    result = joint_award(rfqs, bids, {'1':1,'2':1,'3':1})
    assert result['status'] == 'blocked'
    assert result['modeled_savings'] is None
    assert not result['results']


def test_period_and_unit_boundaries_are_not_fungible():
    rfqs, bids = fixture()
    rfqs[1]['unit'] = 'hour'
    with pytest.raises(ValueError, match='dimensions'):
        joint_award(rfqs, bids, {'1':100,'2':100,'3':100})
    caps = [dict(supplier_id=s, capacity_period='2027', unit='kg', capacity=100) for s in [1,2,3]]
    assert joint_award(rfqs, bids, caps)['status'] == 'blocked'


def test_duplicate_and_nonfinite_capacity_rejected():
    rfqs, bids = fixture()
    with pytest.raises(ValueError):
        joint_award(rfqs, bids, {'1':float('nan')})
    caps = [dict(supplier_id=1,capacity_period='2027',unit='kg',capacity=10)] * 2
    with pytest.raises(ValueError, match='Duplicate'):
        joint_award(rfqs, bids, caps)


def test_live_portfolio_inputs_match_the_current_published_snapshot(client):
    response = client.get('/api/v1/portfolio/inputs')
    assert response.status_code == 200
    data = response.json()
    assert data['snapshot'] == client.get('/api/v1/data-quality/status').json()['run']['input_snapshot_id']
    assert len(data['rfqs']) == 25 and set(data['bids']) == {r['rfq_id'] for r in data['rfqs']}
    assert data['warehouse']['receipt']['input_snapshot_id'] == data['snapshot']
