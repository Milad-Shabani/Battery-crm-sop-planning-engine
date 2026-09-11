"""Production capacity planning as a linear program (monthly grain).

Each production line is shared across several battery models, and both
machine time and labor are finite. When forecasted demand for a month
exceeds what a line can actually produce, the question this module answers
is: which products should be prioritized to capture the most revenue,
given both constraints?

For each (line, month):

    maximize      sum_p  unit_price[p] * units[p]
    subject to    0 <= units[p] <= forecast[p]                    for every product p on the line
                  sum_p  units[p] / capacity_units_per_hour   <= machine_hours_available
                  sum_p  units[p] * labor_hours_per_unit[p]   <= labor_hours_available

`labor_hours_available` comes from the actual simulated workforce
attendance for that line/month; `labor_hours_per_unit` is derived from a
per-line "operators needed to run one hour at full capacity" assumption in
`config.yaml`.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy.optimize import linprog

logger = logging.getLogger(__name__)


def build_labor_hours_per_unit(
    products: pd.DataFrame, lines: pd.DataFrame, operators_per_running_hour: dict[str, float]
) -> dict[str, float]:
    capacity_by_line = dict(zip(lines["line_id"], lines["capacity_units_per_hour"]))
    result = {}
    for _, p in products.iterrows():
        line_id = p["primary_line_id"]
        result[p["product_id"]] = operators_per_running_hour[line_id] / capacity_by_line[line_id]
    return result


def plan_line_month(
    products_on_line: pd.DataFrame,
    forecast_by_product: dict[str, float],
    capacity_units_per_hour: float,
    machine_hours_available: float,
    labor_hours_available: float,
    labor_hours_per_unit: dict[str, float],
) -> pd.DataFrame:
    product_ids = products_on_line["product_id"].tolist()
    n = len(product_ids)
    if n == 0:
        return pd.DataFrame(columns=["product_id", "allocated_units", "forecast_units"])

    prices = products_on_line.set_index("product_id")["unit_price_irr"].reindex(product_ids).values
    forecasts = np.array([forecast_by_product.get(pid, 0.0) for pid in product_ids])

    c = -prices
    machine_row = np.array([1.0 / capacity_units_per_hour] * n)
    labor_row = np.array([labor_hours_per_unit[pid] for pid in product_ids])
    A_ub = np.vstack([machine_row, labor_row])
    b_ub = np.array([machine_hours_available, labor_hours_available])
    bounds = [(0, f) for f in forecasts]

    if forecasts.sum() == 0:
        allocated = np.zeros(n)
    else:
        result = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")
        if not result.success:
            logger.warning(
                "LP did not converge for line month (products=%s); falling back to 0 allocation.",
                product_ids,
            )
            allocated = np.zeros(n)
        else:
            allocated = np.clip(np.round(result.x), 0, forecasts)

    return pd.DataFrame(
        {
            "product_id": product_ids,
            "allocated_units": allocated.astype(int),
            "forecast_units": forecasts.astype(int),
        }
    )


def build_production_plan(
    forecast: pd.DataFrame,
    products: pd.DataFrame,
    lines: pd.DataFrame,
    workforce: pd.DataFrame,
    operators_per_running_hour: dict[str, float],
    hours_per_shift: float = 8.0,
    oee: float = 1.0,
) -> pd.DataFrame:
    labor_hours_per_unit = build_labor_hours_per_unit(products, lines, operators_per_running_hour)
    capacity_by_line = dict(zip(lines["line_id"], lines["capacity_units_per_hour"]))
    shifts_by_line = dict(zip(lines["line_id"], lines["shifts_per_day"]))

    workforce = workforce.copy()
    workforce["date"] = pd.to_datetime(workforce["date"])
    workforce["period_start"] = workforce["date"].dt.to_period("M").dt.to_timestamp()
    workforce["days_in_month"] = workforce["date"].dt.days_in_month
    monthly_labor_hours = (
        workforce.groupby(["line_id", "period_start"])["present_headcount"].sum() * hours_per_shift
    )
    avg_labor_hours_by_line = monthly_labor_hours.groupby(level=0).mean()

    plans = []
    for period_start in sorted(forecast["period_start"].unique()):
        period_forecast = forecast[forecast["period_start"] == period_start]
        forecast_by_product = dict(
            zip(period_forecast["product_id"], period_forecast["forecast_units"])
        )
        days_in_month = pd.Timestamp(period_start).days_in_month

        for line_id in lines["line_id"]:
            line_products = products[products["primary_line_id"] == line_id]
            machine_hours = shifts_by_line[line_id] * hours_per_shift * days_in_month * oee
            labor_hours = monthly_labor_hours.get(
                (line_id, period_start), avg_labor_hours_by_line.get(line_id, machine_hours)
            )

            plan = plan_line_month(
                line_products,
                forecast_by_product,
                capacity_units_per_hour=capacity_by_line[line_id],
                machine_hours_available=machine_hours,
                labor_hours_available=labor_hours,
                labor_hours_per_unit=labor_hours_per_unit,
            )
            plan["line_id"] = line_id
            plan["period_start"] = period_start
            plans.append(plan)

    result = pd.concat(plans, ignore_index=True) if plans else pd.DataFrame()
    if not result.empty:
        result["unmet_units"] = result["forecast_units"] - result["allocated_units"]
    return result
