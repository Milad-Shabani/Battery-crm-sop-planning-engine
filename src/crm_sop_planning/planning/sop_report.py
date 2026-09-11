"""Consolidated monthly S&OP summary."""

from __future__ import annotations

import pandas as pd


def build_monthly_summary(
    production_plan: pd.DataFrame, products: pd.DataFrame, mrp: pd.DataFrame
) -> pd.DataFrame:
    prices = products.set_index("product_id")["unit_price_irr"]

    plan = production_plan.copy()
    plan["revenue_captured_irr"] = plan["allocated_units"] * plan["product_id"].map(prices)
    plan["revenue_lost_irr"] = plan["unmet_units"] * plan["product_id"].map(prices)

    monthly = (
        plan.groupby("period_start")
        .agg(
            forecast_units=("forecast_units", "sum"),
            allocated_units=("allocated_units", "sum"),
            unmet_units=("unmet_units", "sum"),
            revenue_captured_irr=("revenue_captured_irr", "sum"),
            revenue_lost_irr=("revenue_lost_irr", "sum"),
        )
        .reset_index()
    )
    monthly["fill_rate"] = (monthly["allocated_units"] / monthly["forecast_units"]).round(4)

    if not mrp.empty:
        shortage = (
            mrp[mrp["below_safety_stock"]]
            .groupby("period_start")["material_id"]
            .nunique()
            .rename("materials_below_safety_stock")
        )
        monthly = monthly.merge(shortage, on="period_start", how="left")
        monthly["materials_below_safety_stock"] = (
            monthly["materials_below_safety_stock"].fillna(0).astype(int)
        )
    else:
        monthly["materials_below_safety_stock"] = 0

    return monthly.sort_values("period_start").reset_index(drop=True)
