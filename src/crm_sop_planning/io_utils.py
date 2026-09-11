"""Load the raw CSV tables (produced by `datagen.build_dataset`) into memory."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

TABLE_NAMES = [
    "dim_employee",
    "dim_production_line",
    "dim_product",
    "dim_supplier",
    "dim_raw_material",
    "dim_region",
    "bom",
    "dim_account",
    "dim_contact",
    "fact_leads",
    "fact_opportunities",
    "fact_cases",
    "fact_activities",
    "fact_sales_orders",
    "fact_production_log",
    "fact_inventory_transactions",
    "fact_purchase_orders",
    "fact_workforce_availability",
]


def load_raw_tables(raw_dir: str) -> dict[str, pd.DataFrame]:
    raw_path = Path(raw_dir)
    tables = {}
    for name in TABLE_NAMES:
        path = raw_path / f"{name}.csv"
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found — run `python -m crm_sop_planning.cli generate-data` first."
            )
        tables[name] = pd.read_csv(path)
    return tables
