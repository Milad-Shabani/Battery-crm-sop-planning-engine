import pandas as pd

from crm_sop_planning.planning.capacity_lp import build_labor_hours_per_unit, plan_line_month
from crm_sop_planning.planning.mrp import (
    explode_requirements,
    net_requirements_and_recommend_orders,
)


def _products_on_line():
    return pd.DataFrame(
        [
            {"product_id": "P1", "unit_price_irr": 100000, "primary_line_id": "L1"},
            {"product_id": "P2", "unit_price_irr": 300000, "primary_line_id": "L1"},
        ]
    )


def test_plan_line_month_prioritizes_higher_revenue_product_when_capacity_binds():
    products = _products_on_line()
    forecast = {"P1": 1000, "P2": 1000}
    labor_hours_per_unit = {"P1": 0.01, "P2": 0.01}

    plan = plan_line_month(
        products,
        forecast,
        capacity_units_per_hour=100,
        machine_hours_available=10,  # only enough for 1000 units total, demand is 2000
        labor_hours_available=1000,
        labor_hours_per_unit=labor_hours_per_unit,
    ).set_index("product_id")

    assert plan.loc["P2", "allocated_units"] == plan.loc["P2", "forecast_units"]
    assert plan.loc["P1", "allocated_units"] < plan.loc["P1", "forecast_units"]


def test_plan_line_month_never_exceeds_forecast_or_capacity():
    products = _products_on_line()
    forecast = {"P1": 500, "P2": 500}
    labor_hours_per_unit = {"P1": 0.02, "P2": 0.02}

    plan = plan_line_month(
        products,
        forecast,
        capacity_units_per_hour=50,
        machine_hours_available=8,
        labor_hours_available=1000,
        labor_hours_per_unit=labor_hours_per_unit,
    )
    assert (plan["allocated_units"] <= plan["forecast_units"]).all()
    assert plan["allocated_units"].sum() <= 400 + 1  # 50*8


def test_build_labor_hours_per_unit_matches_expected_ratio():
    products = pd.DataFrame([{"product_id": "P1", "primary_line_id": "L1"}])
    lines = pd.DataFrame([{"line_id": "L1", "capacity_units_per_hour": 2.0}])
    result = build_labor_hours_per_unit(products, lines, operators_per_running_hour={"L1": 6})
    assert result["P1"] == 6 / 2.0


def test_explode_requirements_sums_across_products_sharing_a_material():
    plan = pd.DataFrame(
        [
            {"product_id": "P1", "period_start": "2026-01-01", "allocated_units": 100},
            {"product_id": "P2", "period_start": "2026-01-01", "allocated_units": 50},
        ]
    )
    bom = pd.DataFrame(
        [
            {"product_id": "P1", "material_id": "M1", "qty_per_unit": 0.1},
            {"product_id": "P2", "material_id": "M1", "qty_per_unit": 0.2},
        ]
    )
    req = explode_requirements(plan, bom)
    assert req["required_quantity"].iloc[0] == 100 * 0.1 + 50 * 0.2


def test_mrp_recommends_and_replenishes_when_stock_would_run_out():
    requirements = pd.DataFrame(
        [
            {
                "period_start": pd.Timestamp("2026-01-01"),
                "material_id": "M1",
                "required_quantity": 100,
            },
            {
                "period_start": pd.Timestamp("2026-02-01"),
                "material_id": "M1",
                "required_quantity": 100,
            },
            {
                "period_start": pd.Timestamp("2026-03-01"),
                "material_id": "M1",
                "required_quantity": 100,
            },
            {
                "period_start": pd.Timestamp("2026-04-01"),
                "material_id": "M1",
                "required_quantity": 100,
            },
        ]
    )
    raw_materials = pd.DataFrame(
        [{"material_id": "M1", "lead_time_days": 30, "safety_stock_days": 15}]
    )
    starting_on_hand = pd.Series({"M1": 120})

    result = net_requirements_and_recommend_orders(requirements, raw_materials, starting_on_hand)

    assert result["recommended_order_qty"].sum() > 0
    assert result["projected_on_hand_end"].iloc[-1] > result["projected_on_hand_end"].min()
