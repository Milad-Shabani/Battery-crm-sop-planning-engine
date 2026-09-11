import numpy as np
import pandas as pd

from crm_sop_planning.forecasting.backtest import accuracy_summary, backtest
from crm_sop_planning.forecasting.forecaster import forecast_all_lines, monthly_line_demand
from crm_sop_planning.forecasting.pipeline_signal import (
    build_sku_forecast,
    pipeline_units_by_sku_month,
)


def _synthetic_monthly(n_months: int = 30, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    months = pd.date_range("2023-01-01", periods=n_months, freq="MS")
    seasonal = 200 + 80 * np.sin(2 * np.pi * np.arange(n_months) / 12)
    noise = rng.normal(0, 15, n_months)
    demand = np.clip(seasonal + noise, 0, None)
    return pd.DataFrame({"line_id": "L_TEST", "period_start": months, "demand_units": demand})


def test_monthly_line_demand_zero_fills_missing_months():
    orders = pd.DataFrame(
        [
            {"order_date": "2024-01-05", "product_id": "P1", "quantity": 10},
            {"order_date": "2024-03-10", "product_id": "P1", "quantity": 20},
        ]
    )
    products = pd.DataFrame([{"product_id": "P1", "primary_line_id": "L1"}])
    monthly = monthly_line_demand(orders, products)

    assert len(monthly) == 3  # Jan, Feb (zero), Mar
    feb = monthly[monthly["period_start"] == pd.Timestamp("2024-02-01")]
    assert feb["demand_units"].iloc[0] == 0


def test_forecast_all_lines_returns_requested_horizon():
    monthly = _synthetic_monthly()
    forecast = forecast_all_lines(monthly, horizon_months=3)

    assert len(forecast) == 3
    assert forecast["period_start"].is_monotonic_increasing
    assert (forecast["statistical_forecast_units"] >= 0).all()


def test_backtest_and_accuracy_summary_shape():
    monthly = _synthetic_monthly()
    bt = backtest(monthly, test_months=2)
    acc = accuracy_summary(bt)

    assert len(bt) == 2
    overall = acc[acc["line_id"] == "__OVERALL__"]
    assert not overall.empty
    assert 0 <= overall["wape"].iloc[0] < 2.0


def test_pipeline_units_only_counts_open_opportunities():
    opps = pd.DataFrame(
        [
            {
                "opportunity_id": "O1",
                "product_id": "P1",
                "status": "Open",
                "estimated_close_date": "2026-02-15",
                "estimated_quantity": 100,
                "probability_pct": 0.5,
            },
            {
                "opportunity_id": "O2",
                "product_id": "P1",
                "status": "Won",
                "estimated_close_date": "2025-01-01",
                "estimated_quantity": 999,
                "probability_pct": 1.0,
            },
        ]
    )
    products = pd.DataFrame([{"product_id": "P1", "primary_line_id": "L1"}])
    result = pipeline_units_by_sku_month(opps, products)

    assert len(result) == 1
    assert result["pipeline_units"].iloc[0] == 50.0  # 100 * 0.5, Won opp excluded


def test_build_sku_forecast_adds_pipeline_on_top_of_baseline():
    line_forecast = pd.DataFrame(
        [
            {
                "line_id": "L1",
                "period_start": pd.Timestamp("2026-02-01"),
                "statistical_forecast_units": 100,
            }
        ]
    )
    products = pd.DataFrame(
        [
            {"product_id": "P1", "primary_line_id": "L1"},
            {"product_id": "P2", "primary_line_id": "L1"},
        ]
    )
    orders = pd.DataFrame(
        [
            {"order_date": "2025-12-01", "product_id": "P1", "quantity": 50},
            {"order_date": "2025-12-01", "product_id": "P2", "quantity": 50},
        ]
    )
    opps = pd.DataFrame(
        [
            {
                "opportunity_id": "O1",
                "product_id": "P1",
                "status": "Open",
                "estimated_close_date": "2026-02-10",
                "estimated_quantity": 40,
                "probability_pct": 0.5,
            }
        ]
    )

    sku_fc = build_sku_forecast(line_forecast, products, orders, opps).set_index("product_id")

    assert sku_fc.loc["P1", "pipeline_units"] == 20.0  # 40 * 0.5
    assert sku_fc.loc["P1", "forecast_units"] > sku_fc.loc["P2", "forecast_units"]
    # baseline should split ~50/50 given equal recent order history
    assert abs(sku_fc.loc["P1", "baseline_units"] - sku_fc.loc["P2", "baseline_units"]) < 1
