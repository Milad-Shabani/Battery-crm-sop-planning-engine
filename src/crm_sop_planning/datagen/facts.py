"""Operations fact tables: sales orders (repeat B2B business + CRM-won
deals), production log, material consumption, purchase orders + inventory
ledger, and daily workforce availability.

`fact_sales_orders` deliberately blends two sources, tagged by
`order_source`, because that's how B2B demand actually shows up: most
revenue is recurring/repeat business from existing accounts placing
periodic reorders, and a smaller but meaningful slice is new/incremental
business that came through the CRM pipeline (a won opportunity).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .seasonality import seasonal_multiplier, weekday_multiplier

# Baseline order frequency (orders per account per year) and typical order
# size (units), by account type — distributors reorder often in modest
# quantities, OEM/Fleet accounts order rarely but in bulk.
ACCOUNT_ORDER_PROFILE = {
    "Distributor": {"orders_per_year": 14, "qty_mean": 3.4, "qty_sigma": 0.6},
    "Retailer": {"orders_per_year": 10, "qty_mean": 2.6, "qty_sigma": 0.5},
    "OEM / Fleet": {"orders_per_year": 5, "qty_mean": 4.6, "qty_sigma": 0.8},
    "Export": {"orders_per_year": 4, "qty_mean": 4.2, "qty_sigma": 0.7},
}


def generate_date_range(start: str = "2024-01-01", end: str = "2025-12-31") -> pd.DatetimeIndex:
    return pd.date_range(start=start, end=end, freq="D")


def generate_repeat_orders(
    accounts: pd.DataFrame, products: pd.DataFrame, dates: pd.DatetimeIndex, seed: int
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    weekday_mult = weekday_multiplier(dates)
    n_days = len(dates)

    # Each product gets its own seasonal curve; precompute once.
    product_seasonal = {
        row["product_id"]: seasonal_multiplier(
            dates, row["seasonal_peak"] if row["is_seasonal"] else None, rng
        )
        for _, row in products.iterrows()
    }
    product_price = dict(zip(products["product_id"], products["unit_price_irr"]))
    product_ids = products["product_id"].tolist()

    rows = []
    order_counter = 1
    for _, acc in accounts.iterrows():
        profile = ACCOUNT_ORDER_PROFILE[acc["account_type"]]
        n_orders = max(int(rng.poisson(profile["orders_per_year"] * (n_days / 365))), 1)

        # An account leans toward 1-2 preferred product lines rather than
        # ordering uniformly across the whole catalog.
        preferred_products = rng.choice(product_ids, size=min(3, len(product_ids)), replace=False)

        order_day_idx = rng.integers(0, n_days, size=n_orders)
        for day_idx in sorted(order_day_idx):
            d = dates[day_idx]
            # weight by that day's combined weekday x seasonal signal for
            # whichever product ends up chosen, approximated via a random
            # pick among preferred products then a rejection check.
            product_id = rng.choice(preferred_products)
            day_weight = weekday_mult[day_idx] * product_seasonal[product_id][day_idx]
            if rng.random() > np.clip(day_weight / 3.0, 0.05, 1.0):
                continue  # thin out orders on low-weight days (weekends, off-season)

            qty = max(int(round(rng.lognormal(profile["qty_mean"], profile["qty_sigma"]))), 1)
            unit_price = product_price[product_id] * rng.uniform(0.95, 1.03)
            rows.append(
                {
                    "order_id": f"ORD{order_counter:06d}",
                    "order_source": "Repeat",
                    "account_id": acc["account_id"],
                    "product_id": product_id,
                    "order_date": d.date(),
                    "quantity": qty,
                    "unit_price_irr": int(unit_price),
                    "revenue_irr": int(qty * unit_price),
                }
            )
            order_counter += 1

    return pd.DataFrame(rows)


def generate_crm_orders(opportunities: pd.DataFrame, start_counter: int) -> pd.DataFrame:
    won = opportunities[opportunities["status"] == "Won"].copy()
    if won.empty:
        return pd.DataFrame(
            columns=[
                "order_id",
                "order_source",
                "account_id",
                "product_id",
                "order_date",
                "quantity",
                "unit_price_irr",
                "revenue_irr",
            ]
        )

    won["unit_price_irr"] = (
        (won["actual_value_irr"] / won["estimated_quantity"]).round().astype(int)
    )
    rows = []
    for i, (_, opp) in enumerate(won.iterrows()):
        rows.append(
            {
                "order_id": f"ORD{start_counter + i:06d}",
                "order_source": "CRM Won",
                "account_id": opp["account_id"],
                "product_id": opp["product_id"],
                "order_date": opp["actual_close_date"],
                "quantity": int(opp["estimated_quantity"]),
                "unit_price_irr": int(opp["unit_price_irr"]),
                "revenue_irr": int(opp["actual_value_irr"]),
            }
        )
    return pd.DataFrame(rows)


def generate_production_log(
    sales_orders: pd.DataFrame, products: pd.DataFrame, lines: pd.DataFrame, seed: int
) -> pd.DataFrame:
    """Derive a daily production log from combined order demand, applying
    a small forward buffer and realistic line-capacity limits, downtime,
    and scrap — same pattern as consumer-goods production, just B2B-sourced
    demand instead of retail."""
    rng = np.random.default_rng(seed)
    line_capacity = dict(zip(lines["line_id"], lines["capacity_units_per_hour"]))
    line_shifts = dict(zip(lines["line_id"], lines["shifts_per_day"]))
    line_for_product = dict(zip(products["product_id"], products["primary_line_id"]))

    demand = sales_orders.groupby(["order_date", "product_id"], as_index=False)["quantity"].sum()
    demand = demand.rename(columns={"order_date": "date", "quantity": "units_sold"})
    demand["planned_units"] = np.ceil(demand["units_sold"] * 1.08).astype(int)
    demand["line_id"] = demand["product_id"].map(line_for_product)

    rows = []
    for _, r in demand.iterrows():
        hours_available = line_shifts[r["line_id"]] * 8
        max_capacity = int(line_capacity[r["line_id"]] * hours_available * 0.6)
        planned = min(r["planned_units"], max(max_capacity, 1))

        downtime_minutes = int(max(rng.normal(25, 18), 0))
        scrap_rate = np.clip(rng.normal(0.02, 0.008), 0, 0.09)
        produced = int(round(planned * (1 - downtime_minutes / (hours_available * 60) * 0.5)))
        scrap = int(round(produced * scrap_rate))

        rows.append(
            {
                "date": r["date"],
                "line_id": r["line_id"],
                "product_id": r["product_id"],
                "planned_units": int(planned),
                "produced_units": max(produced - scrap, 0),
                "scrap_units": scrap,
                "downtime_minutes": downtime_minutes,
            }
        )
    return pd.DataFrame(rows)


def generate_material_consumption(production: pd.DataFrame, bom: pd.DataFrame) -> pd.DataFrame:
    merged = production.merge(bom, on="product_id", how="left")
    merged["quantity"] = merged["produced_units"] * merged["qty_per_unit"]
    consumption = merged.groupby(["date", "material_id"], as_index=False)["quantity"].sum()
    consumption["transaction_type"] = "Consumption"
    return consumption[["date", "material_id", "transaction_type", "quantity"]]


def mat_reliability(
    raw_materials: pd.DataFrame, material_id: str, supplier_reliability: dict
) -> float:
    supplier_id = raw_materials.loc[
        raw_materials["material_id"] == material_id, "default_supplier_id"
    ].iloc[0]
    return supplier_reliability.get(supplier_id, 0.95)


def generate_purchase_orders_and_inventory(
    consumption: pd.DataFrame,
    raw_materials: pd.DataFrame,
    suppliers: pd.DataFrame,
    dates: pd.DatetimeIndex,
    seed: int,
    starting_stock_days: float = 15.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    supplier_reliability = dict(zip(suppliers["supplier_id"], suppliers["reliability_score"]))
    po_rows, inv_rows = [], []
    po_counter = 1

    for _, mat in raw_materials.iterrows():
        mat_id = mat["material_id"]
        daily_use = consumption.loc[consumption["material_id"] == mat_id].set_index("date")[
            "quantity"
        ]
        daily_use = daily_use.reindex([d.date() for d in dates], fill_value=0.0)
        avg_daily_use = max(daily_use.mean(), 0.01)

        on_hand = avg_daily_use * starting_stock_days
        reorder_point = avg_daily_use * (mat["lead_time_days"] + mat["safety_stock_days"])
        order_qty = avg_daily_use * (mat["lead_time_days"] + mat["safety_stock_days"]) * 1.5
        pending_deliveries: dict = {}

        for d in dates:
            dd = d.date()
            delivered_today = pending_deliveries.pop(dd, 0.0)
            if delivered_today:
                on_hand += delivered_today
                inv_rows.append(
                    {
                        "date": dd,
                        "material_id": mat_id,
                        "transaction_type": "Receipt",
                        "quantity": round(delivered_today, 2),
                    }
                )

            used_today = daily_use.get(dd, 0.0)
            on_hand -= used_today
            if used_today:
                inv_rows.append(
                    {
                        "date": dd,
                        "material_id": mat_id,
                        "transaction_type": "Consumption",
                        "quantity": -round(used_today, 2),
                    }
                )

            if on_hand < reorder_point and not pending_deliveries:
                lead = int(max(mat["lead_time_days"] + rng.normal(0, 1.5), 1))
                late_chance = 1 - mat_reliability(raw_materials, mat_id, supplier_reliability)
                if rng.random() < late_chance:
                    lead += int(rng.integers(2, 7))
                delivery_date = (pd.Timestamp(dd) + pd.Timedelta(days=lead)).date()
                pending_deliveries[delivery_date] = (
                    pending_deliveries.get(delivery_date, 0.0) + order_qty
                )

                po_rows.append(
                    {
                        "po_id": f"PO{po_counter:05d}",
                        "material_id": mat_id,
                        "supplier_id": mat["default_supplier_id"],
                        "order_date": dd,
                        "expected_delivery_date": (
                            pd.Timestamp(dd) + pd.Timedelta(days=int(mat["lead_time_days"]))
                        ).date(),
                        "actual_delivery_date": delivery_date,
                        "quantity": round(order_qty, 2),
                        "unit_cost_irr": mat["unit_cost_irr"],
                        "status": "Delivered",
                    }
                )
                po_counter += 1

            inv_rows.append(
                {
                    "date": dd,
                    "material_id": mat_id,
                    "transaction_type": "OnHandSnapshot",
                    "quantity": round(on_hand, 2),
                }
            )

    return pd.DataFrame(po_rows), pd.DataFrame(inv_rows)


def generate_workforce_availability(
    employees: pd.DataFrame, lines: pd.DataFrame, dates: pd.DatetimeIndex, seed: int
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    production_roles = ("Production Operator", "Line Supervisor", "QC / Battery Test Technician")
    prod_employees = employees[
        employees["role"].isin(production_roles) & employees["production_line_id"].notna()
    ]

    rows = []
    for line_id in lines["line_id"]:
        line_staff = prod_employees[prod_employees["production_line_id"] == line_id]
        for shift in sorted(line_staff["shift"].unique().tolist()):
            scheduled = int((line_staff["shift"] == shift).sum())
            if scheduled == 0:
                continue
            for d in dates:
                present = int(np.clip(rng.binomial(scheduled, 0.93), 0, scheduled))
                rows.append(
                    {
                        "date": d.date(),
                        "line_id": line_id,
                        "shift": shift,
                        "scheduled_headcount": scheduled,
                        "present_headcount": present,
                    }
                )
    return pd.DataFrame(rows)
