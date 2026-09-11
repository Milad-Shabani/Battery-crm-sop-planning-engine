"""Material Requirements Planning (MRP), monthly grain.

Explodes the production plan through the BOM into monthly raw-material
requirements, nets that against current on-hand inventory, and recommends
purchase orders — sized and timed so they land before stock would run out,
given each material's supplier lead time and safety-stock policy.
"""

from __future__ import annotations

import pandas as pd


def latest_on_hand(inventory: pd.DataFrame) -> pd.Series:
    snapshots = inventory[inventory["transaction_type"] == "OnHandSnapshot"].copy()
    snapshots["date"] = pd.to_datetime(snapshots["date"])
    latest = snapshots.sort_values("date").groupby("material_id").tail(1)
    return latest.set_index("material_id")["quantity"]


def explode_requirements(production_plan: pd.DataFrame, bom: pd.DataFrame) -> pd.DataFrame:
    merged = production_plan.merge(bom, on="product_id", how="left")
    merged["required_quantity"] = merged["allocated_units"] * merged["qty_per_unit"]
    requirements = merged.groupby(["period_start", "material_id"], as_index=False)[
        "required_quantity"
    ].sum()
    return requirements.sort_values(["material_id", "period_start"])


def net_requirements_and_recommend_orders(
    requirements: pd.DataFrame, raw_materials: pd.DataFrame, starting_on_hand: pd.Series
) -> pd.DataFrame:
    """Walk each material forward month by month, netting requirements
    against a running projected on-hand balance, and recommend a purchase
    order whenever projected stock would fall below the safety-stock
    target before an order placed today could arrive. Recommended orders
    are assumed placed and received on time — scheduled as a future
    delivery `lead_months` out and credited back to `on_hand` — so the
    projection reflects a functioning reorder policy, not a purely
    depleting balance."""
    rows = []
    materials = raw_materials.set_index("material_id")

    for material_id, group in requirements.groupby("material_id"):
        group = group.reset_index(drop=True).sort_values("period_start").reset_index(drop=True)
        n_periods = len(group)
        lead_months = max(round(materials.loc[material_id, "lead_time_days"] / 30), 1)
        safety_stock = (
            materials.loc[material_id, "safety_stock_days"] / 30 * group["required_quantity"].mean()
        )

        on_hand = float(starting_on_hand.get(material_id, 0.0))
        pending_deliveries: dict[int, float] = {}
        order_open_until: int = -1

        for i, r in group.iterrows():
            delivered_this_period = pending_deliveries.pop(i, 0.0)
            on_hand += delivered_this_period

            future_need = group["required_quantity"].iloc[i : i + lead_months].sum()
            will_breach_safety_stock = (on_hand - future_need) < safety_stock

            recommended_order_qty = 0.0
            has_open_order = order_open_until >= i
            if will_breach_safety_stock and not has_open_order:
                recommended_order_qty = max(future_need + safety_stock - on_hand, 0.0)
                arrival_period = i + lead_months
                if arrival_period < n_periods:
                    pending_deliveries[arrival_period] = (
                        pending_deliveries.get(arrival_period, 0.0) + recommended_order_qty
                    )
                    order_open_until = arrival_period

            projected_end = on_hand - r["required_quantity"]

            rows.append(
                {
                    "period_start": r["period_start"],
                    "material_id": material_id,
                    "required_quantity": round(r["required_quantity"], 2),
                    "projected_on_hand_start": round(on_hand, 2),
                    "projected_on_hand_end": round(projected_end, 2),
                    "below_safety_stock": bool(on_hand < safety_stock),
                    "recommended_order_qty": round(recommended_order_qty, 2),
                }
            )
            on_hand = projected_end

    return pd.DataFrame(rows)
