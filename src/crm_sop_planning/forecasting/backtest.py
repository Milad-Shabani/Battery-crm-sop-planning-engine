"""Rolling backtest of the statistical (line-level, monthly) forecast.

Deliberately scoped to the statistical baseline only, not the CRM pipeline
overlay: reproducing what the open pipeline looked like *as of* each
historical cutoff would need point-in-time CRM snapshots this dataset
doesn't carry (opportunities are generated with their final/current state,
not a full change history). Backtesting only the statistical component is
the honest thing to do — see docs/ARCHITECTURE.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .forecaster import forecast_all_lines


def backtest(monthly: pd.DataFrame, test_months: int = 2) -> pd.DataFrame:
    rows = []
    for line_id, group in monthly.groupby("line_id"):
        group = group.sort_values("period_start")
        if len(group) <= test_months + 6:
            continue

        train = group.iloc[:-test_months]
        actual = group.iloc[-test_months:]

        forecast = forecast_all_lines(train.assign(line_id=line_id), horizon_months=test_months)
        merged = forecast.merge(
            actual[["period_start", "demand_units"]], on="period_start", how="inner"
        )
        merged["line_id"] = line_id
        rows.append(merged)

    if not rows:
        return pd.DataFrame(
            columns=["line_id", "period_start", "statistical_forecast_units", "demand_units"]
        )
    return pd.concat(rows, ignore_index=True)


def accuracy_summary(backtest_df: pd.DataFrame) -> pd.DataFrame:
    if backtest_df.empty:
        return pd.DataFrame(columns=["line_id", "mape", "wape", "n_months"])

    def _wape(g: pd.DataFrame) -> float:
        denom = g["demand_units"].sum()
        return (
            float(np.abs(g["statistical_forecast_units"] - g["demand_units"]).sum() / denom)
            if denom
            else np.nan
        )

    def _mape(g: pd.DataFrame) -> float:
        nonzero = g[g["demand_units"] > 0]
        if nonzero.empty:
            return np.nan
        return float(
            (
                np.abs(nonzero["statistical_forecast_units"] - nonzero["demand_units"])
                / nonzero["demand_units"]
            ).mean()
        )

    per_line = (
        backtest_df.groupby("line_id")
        .apply(lambda g: pd.Series({"mape": _mape(g), "wape": _wape(g), "n_months": len(g)}))
        .reset_index()
    )
    overall_wape = _wape(backtest_df)
    overall = pd.DataFrame(
        [
            {
                "line_id": "__OVERALL__",
                "mape": np.nan,
                "wape": overall_wape,
                "n_months": len(backtest_df),
            }
        ]
    )
    return pd.concat([per_line, overall], ignore_index=True)
