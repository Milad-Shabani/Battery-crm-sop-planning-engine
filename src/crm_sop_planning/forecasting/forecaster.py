"""Line-level monthly demand forecasting.

Two grain decisions, both driven by what the data actually looks like:

- **Line, not SKU.** B2B order data is lumpy at the SKU level — most weeks
  have zero orders for any single battery model (see
  docs/ARCHITECTURE.md). Aggregating to the 4 production lines gives a
  series with real volume to forecast. SKU-level detail is reconstructed
  afterward in `pipeline_signal.py`.
- **Monthly, not weekly.** Individual B2B orders are large relative to a
  week's total, so weekly demand is extremely spiky (coefficient of
  variation ~0.6-1.0). Monthly aggregation roughly halves that (~0.4-0.6)
  while still matching how an industrial manufacturer actually runs its
  S&OP cycle — monthly, not daily. This is also an intentional part of the
  project's point: even monthly, pure history-based forecasting is only
  moderately accurate on lumpy B2B demand (see the backtest results in
  README.md) — which is the motivation for `pipeline_signal.py`.
"""

from __future__ import annotations

import logging
import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

logger = logging.getLogger(__name__)

MIN_MONTHS_FOR_SEASONAL_FIT = 24


def monthly_line_demand(sales_orders: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    """Aggregate order-level demand to (line_id, period_start), zero-filling
    months with no orders so the series is continuous."""
    df = sales_orders.merge(products[["product_id", "primary_line_id"]], on="product_id")
    df["order_date"] = pd.to_datetime(df["order_date"])
    df["period_start"] = df["order_date"].dt.to_period("M").dt.to_timestamp()

    monthly = df.groupby(["primary_line_id", "period_start"], as_index=False)["quantity"].sum()
    monthly = monthly.rename(columns={"quantity": "demand_units", "primary_line_id": "line_id"})

    all_months = pd.date_range(
        monthly["period_start"].min(), monthly["period_start"].max(), freq="MS"
    )
    filled = []
    for line_id, group in monthly.groupby("line_id"):
        series = group.set_index("period_start")["demand_units"].reindex(all_months, fill_value=0)
        filled.append(
            pd.DataFrame(
                {"line_id": line_id, "period_start": all_months, "demand_units": series.values}
            )
        )
    return pd.concat(filled, ignore_index=True)


def _forecast_one_series(series: pd.Series, horizon_months: int) -> np.ndarray:
    series = series.astype(float)
    if len(series) >= MIN_MONTHS_FOR_SEASONAL_FIT and series.sum() > 0:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = ExponentialSmoothing(
                    series,
                    trend="add",
                    seasonal="add",
                    seasonal_periods=12,
                    initialization_method="estimated",
                ).fit(optimized=True)
            forecast = model.forecast(horizon_months)
            return np.clip(forecast.values, 0, None)
        except Exception as exc:  # noqa: BLE001 - fall back rather than crash the whole run
            logger.warning("Holt-Winters failed (%s); falling back to seasonal-naive.", exc)

    return _seasonal_naive(series, horizon_months)


def _seasonal_naive(series: pd.Series, horizon_months: int) -> np.ndarray:
    """Repeat the same calendar month from a year ago, scaled by the ratio
    of recent trailing demand to the same trailing window a year ago — a
    robust fallback when there isn't enough history for a full seasonal fit."""
    if len(series) >= 12:
        last_year = series.values[-12:]
        recent = series.tail(3).mean()
        year_ago_same_period = (
            series.values[-15:-12].mean() if len(series) >= 15 else last_year.mean()
        )
        trend_ratio = (recent / year_ago_same_period) if year_ago_same_period > 0 else 1.0
        trend_ratio = np.clip(trend_ratio, 0.5, 2.0)
        reps = int(np.ceil(horizon_months / 12))
        return np.tile(last_year, reps)[:horizon_months] * trend_ratio
    return np.full(horizon_months, max(series.tail(3).mean(), 0.0))


def forecast_all_lines(monthly: pd.DataFrame, horizon_months: int = 3) -> pd.DataFrame:
    results = []
    for line_id, group in monthly.groupby("line_id"):
        group = group.sort_values("period_start")
        series = group.set_index("period_start")["demand_units"]
        last_period = series.index.max()

        values = _forecast_one_series(series, horizon_months)
        future_periods = [
            last_period + pd.DateOffset(months=i) for i in range(1, horizon_months + 1)
        ]

        for period, val in zip(future_periods, values):
            results.append(
                {
                    "line_id": line_id,
                    "period_start": period,
                    "statistical_forecast_units": max(round(val), 0),
                }
            )

    return pd.DataFrame(results)
