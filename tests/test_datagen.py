import pandas as pd

from crm_sop_planning.datagen import crm, dimensions, facts
from crm_sop_planning.datagen.bom import generate_bom


def test_generate_employees_includes_sales_and_service_reps():
    employees = dimensions.generate_employees(engine_seed=1, n_employees=100)
    assert (employees["role"] == "Sales Representative").sum() > 0
    assert (employees["role"] == "Service Representative").sum() > 0
    assert employees["employee_id"].is_unique


def test_products_reference_valid_lines():
    products = dimensions.generate_products()
    lines = dimensions.generate_production_lines()
    assert set(products["primary_line_id"]).issubset(set(lines["line_id"]))


def test_bom_scales_with_capacity_ah():
    products = dimensions.generate_products()
    raw_materials = dimensions.generate_raw_materials()
    bom = generate_bom(products, raw_materials)

    lead_material_id = raw_materials.loc[
        raw_materials["material_name"] == "Lead Ingot", "material_id"
    ].iloc[0]
    small = products[products["product_name"] == "SLI 45Ah 12V Compact"]["product_id"].iloc[0]
    large = products[products["product_name"] == "SLI 100Ah 12V Heavy Duty"]["product_id"].iloc[0]

    small_qty = bom[(bom.product_id == small) & (bom.material_id == lead_material_id)][
        "qty_per_unit"
    ].iloc[0]
    large_qty = bom[(bom.product_id == large) & (bom.material_id == lead_material_id)][
        "qty_per_unit"
    ].iloc[0]
    assert large_qty > small_qty


def test_accounts_and_contacts_are_linked():
    regions = dimensions.generate_regions()
    accounts = crm.generate_accounts(regions, n_accounts=20, seed=1)
    contacts = crm.generate_contacts(accounts, seed=1)

    assert set(contacts["account_id"]).issubset(set(accounts["account_id"]))
    assert accounts["account_id"].is_unique
    assert contacts["contact_id"].is_unique


def test_open_opportunities_have_no_final_outcome_yet():
    regions = dimensions.generate_regions()
    products = dimensions.generate_products()
    employees = dimensions.generate_employees(engine_seed=2, n_employees=60)
    sales_reps = employees[employees["role"] == "Sales Representative"]
    accounts = crm.generate_accounts(regions, n_accounts=15, seed=2)

    start, end = pd.Timestamp("2024-01-01"), pd.Timestamp("2025-12-31")
    _, opportunities = crm.generate_leads_and_opportunities(
        accounts, products, sales_reps, start, end, n_leads=200, n_direct_opportunities=60, seed=2
    )

    open_opps = opportunities[opportunities["status"] == "Open"]
    assert (pd.to_datetime(open_opps["estimated_close_date"]) > end).all()
    assert open_opps["actual_close_date"].isna().all()
    assert open_opps["actual_value_irr"].isna().all()

    resolved = opportunities[opportunities["status"] != "Open"]
    assert (pd.to_datetime(resolved["estimated_close_date"]) <= end).all()
    assert resolved["actual_close_date"].notna().all()


def test_production_log_respects_line_capacity():
    lines = dimensions.generate_production_lines()
    products = dimensions.generate_products()
    orders = pd.DataFrame(
        [
            {
                "order_id": "O1",
                "order_source": "Repeat",
                "account_id": "A1",
                "product_id": products["product_id"].iloc[0],
                "order_date": "2024-01-05",
                "quantity": 5,
                "unit_price_irr": 1,
                "revenue_irr": 5,
            },
        ]
    )
    production = facts.generate_production_log(orders, products, lines, seed=1)
    capacity = dict(zip(lines["line_id"], lines["capacity_units_per_hour"]))
    shifts = dict(zip(lines["line_id"], lines["shifts_per_day"]))

    for _, row in production.iterrows():
        max_possible = capacity[row["line_id"]] * shifts[row["line_id"]] * 8 * 0.6
        assert row["planned_units"] <= max_possible + 1
