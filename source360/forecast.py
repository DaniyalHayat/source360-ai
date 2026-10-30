import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing


def ets_predict(values, horizon):
    scale = max(float(np.mean(values)), 1)
    fitted = ExponentialSmoothing(
        np.asarray(values) / scale, trend="add", seasonal=None, initialization_method="estimated"
    ).fit(method="least_squares")
    if not fitted.mle_retvals.success:
        raise ValueError("ETS fitting did not converge; do not publish this forecast")
    return fitted.forecast(horizon) * scale


def forecast(monthly, horizon=6):
    series = (
        monthly.set_index(pd.to_datetime(monthly.month)).spend_usd.sort_index().asfreq("MS", fill_value=0)
    )
    if len(series) < 24:
        raise ValueError("At least 24 monthly observations are required")
    actual, naive, ets = [], [], []
    for origin in range(max(24, len(series) - 6), len(series)):
        train = series.iloc[:origin].to_numpy(dtype=float)
        actual.append(float(series.iloc[origin]))
        naive.append(float(train[-12]))
        ets.append(float(ets_predict(train, 1)[0]))
    denominator = max(sum(abs(v) for v in actual), 1)
    naive_wape = sum(abs(a - p) for a, p in zip(actual, naive)) / denominator
    ets_wape = sum(abs(a - p) for a, p in zip(actual, ets)) / denominator
    selected = "ETS additive trend" if ets_wape < naive_wape else "Seasonal naive (12 months)"
    predictions = (
        ets_predict(series.to_numpy(dtype=float), horizon)
        if ets_wape < naive_wape
        else np.resize(series.iloc[-12:].to_numpy(), horizon)
    )
    errors = np.array(actual) - np.array(ets if ets_wape < naive_wape else naive)
    sigma = max(float(np.sqrt(np.mean(errors**2))), float(series.mean()) * 0.02)
    future = pd.date_range(series.index[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
    return dict(
        model=selected,
        metric="monthly nominal USD spend",
        backtest=dict(
            origins=len(actual),
            naive_wape=naive_wape,
            ets_wape=ets_wape,
            actual=actual,
            seasonal_naive=naive,
            ets=ets,
        ),
        history=[dict(month=str(d.date()), spend=float(v)) for d, v in series.items()],
        forecast=[
            dict(
                month=str(d.date()),
                spend=max(0, float(p)),
                low=max(0, float(p) - 1.645 * sigma * np.sqrt(i + 1)),
                high=float(p) + 1.645 * sigma * np.sqrt(i + 1),
            )
            for i, (d, p) in enumerate(zip(future, predictions))
        ],
        limitations="Illustrative 90% normal-error prediction bands from six one-step origins; uncalibrated for multi-step coverage. Synthetic data; no causal market inference.",
    )
