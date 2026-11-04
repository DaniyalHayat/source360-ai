import json
import numpy as np
import pandas as pd
import pytest
from source360.forecast import forecast
from source360.portfolio import evaluate_portfolio
from unittest.mock import patch


@pytest.mark.parametrize("length", [24, 25, 36])
def test_minimum_history_has_finite_horizon_errors(length):
    frame = pd.DataFrame(dict(month=pd.date_range("2020-01-01", periods=length, freq="MS"),
                              spend_usd=100 + np.arange(length) * 3 + np.sin(np.arange(length)) * 5))
    result = forecast(frame)
    assert result["backtest"]["origins"] == 6
    assert all(c["observations"] and np.isfinite(c["errors"]).all() for c in result["calibration"])
    json.dumps(result, allow_nan=False)


def test_duplicate_events_and_missing_capacity_cannot_inflate_savings():
    rfq = dict(rfq_id="one", demand=10, baseline_unit_price=20)
    bids = [dict(supplier_id=i, canonical_name=str(i), unit_price_usd=2, logistics_unit_usd=0,
                 fixed_cost=0, risk_score=0, capacity=10, qualified=True, source_ref="fixture") for i in [1,2]]
    with pytest.raises(ValueError):
        evaluate_portfolio([rfq, rfq], {"one":bids})
    assert evaluate_portfolio([rfq], {"one":bids})["modeled_savings"] is None
    assert evaluate_portfolio([rfq], {"one":bids}, {"1":0,"2":0})["status"] == "blocked"
    result = evaluate_portfolio([rfq], {"one":bids}, {"1":10,"2":10})
    assert result["modeled_savings"] == pytest.approx(180)


def test_api_cache_is_invalidated_by_input_snapshot():
    from source360.api import table, cached_table
    cached_table.cache_clear()
    with patch('source360.api.latest_run', return_value={'input_snapshot_id':'first'}), patch('source360.api.read', return_value='old'):
        assert table('dim_supplier') == 'old'
    with patch('source360.api.latest_run', return_value={'input_snapshot_id':'second'}), patch('source360.api.read', return_value='new'):
        assert table('dim_supplier') == 'new'
    cached_table.cache_clear()
