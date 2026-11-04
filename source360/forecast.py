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
    if horizon < 1 or horizon > 12:
        raise ValueError("Forecast horizon must be between 1 and 12 months")
    if not np.isfinite(series.to_numpy()).all() or (series < 0).any():
        raise ValueError("Spend must contain finite nonnegative observations")
    if len(series) < 24:
        raise ValueError("At least 24 monthly observations are required")
    actual, naive, ets = [], [], []
    for origin in range(len(series) - 6, len(series)):
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
    calibration = []
    for step in range(1, horizon + 1):
        errors = []
        for origin in range(max(12, len(series) - 12), len(series) - step + 1):
            train = series.iloc[:origin].to_numpy(dtype=float)
            prediction = ets_predict(train, step)[-1] if ets_wape < naive_wape else train[(step - 1) % 12 - 12]
            errors.append(float(series.iloc[origin + step - 1]) - float(prediction))
        radius = float(np.quantile(np.abs(errors), min(1, np.ceil((len(errors) + 1) * .9) / len(errors)), method="higher"))
        calibration.append(dict(horizon=step, errors=errors, observations=len(errors), radius=radius))
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
                low=max(0, float(p) - calibration[i]["radius"]),
                high=max(0, float(p)) + calibration[i]["radius"],
            )
            for i, (d, p) in enumerate(zip(future, predictions))
        ],
        calibration=calibration,
        limitations="Empirical horizon-specific absolute-error bands on synthetic observations. Model selection and residual assessment share history; nominal 90% coverage is not guaranteed out of sample. Synthetic data; no causal market inference.",
    )
