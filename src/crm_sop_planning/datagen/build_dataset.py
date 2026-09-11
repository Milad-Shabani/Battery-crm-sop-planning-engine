"""Entry point that generates the full synthetic dataset (operations + CRM)
and writes it to `data/raw/` as CSVs.

    python -m crm_sop_planning.datagen.build_dataset --out-dir data/raw --seed 42
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from . import crm, dimensions, facts
from .bom import generate_bom

logger = logging.getLogger(__name__)


def build_dataset(
    out_dir: str,
    seed: int = 42,
    n_employees: int = 180,
    n_accounts: int = 70,
    n_leads: int = 1800,
    n_direct_opportunities: int = 320,
    n_cases: int = 450,
    start: str = "2024-01-01",
    end: str = "2025-12-31",
) -> dict[str, int]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    logger.info("Generating operations dimension tables...")
    employees = dimensions.generate_employees(seed, n_employees=n_employees)
    lines = dimensions.generate_production_lines()
    products = dimensions.generate_products()
    suppliers = dimensions.generate_suppliers()
    raw_materials = dimensions.generate_raw_materials()
    regions = dimensions.generate_regions()
    bom = generate_bom(products, raw_materials)

    logger.info("Generating CRM entities: accounts, contacts...")
    accounts = crm.generate_accounts(regions, n_accounts=n_accounts, seed=seed)
    contacts = crm.generate_contacts(accounts, seed=seed)

    sales_reps = employees[employees["role"] == "Sales Representative"]
    service_reps = employees[employees["role"] == "Service Representative"]

    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)

    logger.info("Generating leads and the opportunity pipeline...")
    leads, opportunities = crm.generate_leads_and_opportunities(
        accounts,
        products,
        sales_reps,
        start_ts,
        end_ts,
        n_leads=n_leads,
        n_direct_opportunities=n_direct_opportunities,
        seed=seed,
    )

    logger.info("Generating service cases and activities...")
    cases = crm.generate_cases(
        accounts, contacts, products, service_reps, start_ts, end_ts, n_cases=n_cases, seed=seed
    )
    activities = crm.generate_activities(opportunities, cases, seed=seed)

    dates = facts.generate_date_range(start, end)

    logger.info("Generating repeat B2B order history (%d accounts)...", len(accounts))
    repeat_orders = facts.generate_repeat_orders(accounts, products, dates, seed=seed + 1)
    crm_orders = facts.generate_crm_orders(opportunities, start_counter=len(repeat_orders) + 1)
    sales_orders = (
        pd.concat([repeat_orders, crm_orders], ignore_index=True)
        .sort_values("order_date")
        .reset_index(drop=True)
    )

    logger.info("Deriving production log from combined order demand...")
    production = facts.generate_production_log(sales_orders, products, lines, seed=seed + 2)

    logger.info("Exploding production through the BOM into material consumption...")
    consumption = facts.generate_material_consumption(production, bom)

    logger.info("Simulating purchasing policy and inventory ledger...")
    purchase_orders, inventory = facts.generate_purchase_orders_and_inventory(
        consumption, raw_materials, suppliers, dates, seed=seed + 3
    )

    logger.info("Simulating daily workforce availability...")
    workforce = facts.generate_workforce_availability(employees, lines, dates, seed=seed + 4)

    tables = {
        "dim_employee.csv": employees,
        "dim_production_line.csv": lines,
        "dim_product.csv": products,
        "dim_supplier.csv": suppliers,
        "dim_raw_material.csv": raw_materials,
        "dim_region.csv": regions,
        "bom.csv": bom,
        "dim_account.csv": accounts,
        "dim_contact.csv": contacts,
        "fact_leads.csv": leads,
        "fact_opportunities.csv": opportunities,
        "fact_cases.csv": cases,
        "fact_activities.csv": activities,
        "fact_sales_orders.csv": sales_orders,
        "fact_production_log.csv": production,
        "fact_inventory_transactions.csv": inventory,
        "fact_purchase_orders.csv": purchase_orders,
        "fact_workforce_availability.csv": workforce,
    }

    row_counts = {}
    for filename, df in tables.items():
        df.to_csv(out_path / filename, index=False)
        row_counts[filename] = len(df)
        logger.info("Wrote %s (%d rows)", filename, len(df))

    return row_counts


def main() -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s | %(levelname)-8s | %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="data/raw")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--employees", type=int, default=180)
    parser.add_argument("--accounts", type=int, default=70)
    parser.add_argument("--leads", type=int, default=1800)
    parser.add_argument("--direct-opportunities", type=int, default=320)
    parser.add_argument("--cases", type=int, default=450)
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2025-12-31")
    args = parser.parse_args()

    counts = build_dataset(
        args.out_dir,
        seed=args.seed,
        n_employees=args.employees,
        n_accounts=args.accounts,
        n_leads=args.leads,
        n_direct_opportunities=args.direct_opportunities,
        n_cases=args.cases,
        start=args.start,
        end=args.end,
    )
    total = sum(counts.values())
    print(f"\nGenerated {len(counts)} tables, {total:,} total rows, in {args.out_dir}")


if __name__ == "__main__":
    main()
