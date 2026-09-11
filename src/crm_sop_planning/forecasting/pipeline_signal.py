"""Turn the open CRM opportunity pipeline into a forecast overlay.

This is the module that makes a CRM system worth having connected to the
planning engine at all: a statistical time-series model has no way to know
that a specific 400-unit deal is sitting in "3-Propose" with a contractual
expected close date next month — but the CRM does, and that's concrete,
probability-weighted evidence a pure history-based forecast should not
ignore.

Two things happen here:

1. **Pipeline units, by SKU and month**: every *open* opportunity's
   `estimated_quantity x probability_pct` is placed in the month bucket
   matching its `estimated_close_date`.
2. **SKU-level reconstruction**: the line-level statistical forecast (the
   grain that's actually reliable — see forecaster.py) is split down to
   SKUs using each SKU's trailing historical share of its line, and then
   any SKU-specific pipeline units for that month are added on top — a
   known, probability-weighted deal is treated as incremental evidence
   beyond the general historical pattern, not merely folded into it.
"""

from __future__ import annotations

import pandas as pd


def pipeline_units_by_sku_month(
    opportunities: pd.DataFrame, products: pd.DataFrame
) -> pd.DataFrame:
    open_opps = opportunities[opportunities["status"] == "Open"].copy()
    if open_opps.empty:
        return pd.DataFrame(columns=["product_id", "line_id", "period_start", "pipeline_units"])

    open_opps["estimated_close_date"] = pd.to_datetime(open_opps["estimated_close_date"])
    open_opps["period_start"] = (
        open_opps["estimated_close_date"].dt.to_period("M").dt.to_timestamp()
    )
    open_opps["pipeline_units"] = open_opps["estimated_quantity"] * open_opps["probability_pct"]

    result = open_opps.groupby(["product_id", "period_start"], as_index=False)[
        "pipeline_units"
    ].sum()
    return result.merge(products[["product_id", "primary_line_id"]], on="product_id").rename(
        columns={"primary_line_id": "line_id"}
    )


def trailing_sku_shares(
    sales_orders: pd.DataFrame, products: pd.DataFrame, trailing_months: int = 6
) -> pd.DataFrame:
    """Each SKU's share of its line's unit volume, over the most recent
    `trailing_months` of order history. Falls back to an equal split across
    a line's SKUs if there's no recent history for it (a brand-new SKU)."""
    df = sales_orders.merge(products[["product_id", "primary_line_id"]], on="product_id")
    df["order_date"] = pd.to_datetime(df["order_date"])
    cutoff = df["order_date"].max() - pd.DateOffset(months=trailing_months)
    recent = df[df["order_date"] >= cutoff]

    sku_units = recent.groupby("product_id")["quantity"].sum()
    line_units = recent.groupby("primary_line_id")["quantity"].sum()

    rows = []
    for _, p in products.iterrows():
        line_total = line_units.get(p["primary_line_id"], 0)
        sku_total = sku_units.get(p["product_id"], 0)
        n_skus_on_line = (products["primary_line_id"] == p["primary_line_id"]).sum()
        share = (sku_total / line_total) if line_total > 0 else (1.0 / n_skus_on_line)
        rows.append(
            {"product_id": p["product_id"], "primary_line_id": p["primary_line_id"], "share": share}
        )

    shares = pd.DataFrame(rows)
    shares["share"] = shares.groupby("primary_line_id")["share"].transform(lambda s: s / s.sum())
    return shares


def build_sku_forecast(
    line_forecast: pd.DataFrame,
    products: pd.DataFrame,
    sales_orders: pd.DataFrame,
    opportunities: pd.DataFrame,
) -> pd.DataFrame:
    """Combine the line-level statistical forecast with SKU shares and the
    pipeline overlay into a final per-SKU, per-month forecast."""
    shares = trailing_sku_shares(sales_orders, products)
    pipeline = pipeline_units_by_sku_month(opportunities, products)

    rows = []
    for _, lf in line_forecast.iterrows():
        line_skus = shares[shares["primary_line_id"] == lf["line_id"]]
        for _, sku in line_skus.iterrows():
            baseline = lf["statistical_forecast_units"] * sku["share"]
            pipe_match = pipeline[
                (pipeline["product_id"] == sku["product_id"])
                & (pipeline["period_start"] == lf["period_start"])
            ]
            pipeline_units = (
                float(pipe_match["pipeline_units"].iloc[0]) if not pipe_match.empty else 0.0
            )
            rows.append(
                {
                    "product_id": sku["product_id"],
                    "line_id": lf["line_id"],
                    "period_start": lf["period_start"],
                    "baseline_units": round(baseline, 1),
                    "pipeline_units": round(pipeline_units, 1),
                    "forecast_units": max(round(baseline + pipeline_units), 0),
                }
            )
    return pd.DataFrame(rows)
