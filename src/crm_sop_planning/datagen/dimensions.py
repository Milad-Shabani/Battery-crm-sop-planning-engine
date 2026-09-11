"""Operations-side dimension tables: employees, production lines, products,
raw materials, suppliers, and sales regions for a fictional battery
manufacturer ("Pars Voltage Battery Industries Co.").
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from faker import Faker

ROLES = [
    ("Production Operator", 0.35),
    ("Line Supervisor", 0.03),
    ("QC / Battery Test Technician", 0.07),
    ("Warehouse Staff", 0.09),
    ("Forklift Operator", 0.03),
    ("Maintenance Technician", 0.05),
    ("Logistics Coordinator", 0.04),
    ("Sales Representative", 0.11),
    ("Service Representative", 0.06),
    ("Procurement Officer", 0.03),
    ("Finance / Admin", 0.06),
    ("Plant Management", 0.02),
    ("HR / Support", 0.03),
    ("CRM / IT Administrator", 0.03),
]

SHIFTS = ["Morning (06:00-14:00)", "Evening (14:00-22:00)", "Night (22:00-06:00)"]

PRODUCTION_LINES = [
    # Capacity is deliberately modest in "units/hour" terms: lead-acid
    # battery manufacturing includes a formation/initial-charge step that
    # takes hours per batch, not a fast assembly-line throughput — so a
    # line's real monthly output is much lower relative to nameplate
    # "parts per hour" than, say, a bakery line.
    {
        "line_id": "L1",
        "line_name": "Automotive SLI Battery Line",
        "capacity_units_per_hour": 2.2,
        "shifts_per_day": 3,
        "changeover_minutes": 30,
        "commissioned_date": "2014-04-01",
    },
    {
        "line_id": "L2",
        "line_name": "Motorcycle Battery Line",
        "capacity_units_per_hour": 1.6,
        "shifts_per_day": 2,
        "changeover_minutes": 20,
        "commissioned_date": "2016-09-10",
    },
    {
        "line_id": "L3",
        "line_name": "Industrial / UPS Battery Line",
        "capacity_units_per_hour": 3.0,
        "shifts_per_day": 2,
        "changeover_minutes": 40,
        "commissioned_date": "2018-02-15",
    },
    {
        "line_id": "L4",
        "line_name": "Deep-Cycle & Solar Battery Line",
        "capacity_units_per_hour": 2.5,
        "shifts_per_day": 2,
        "changeover_minutes": 35,
        "commissioned_date": "2020-06-01",
    },
]

# (product_name, category, primary_line_id, capacity_ah, voltage, warranty_months,
#  unit_price_irr, is_seasonal, seasonal_peak)
PRODUCTS = [
    ("SLI 45Ah 12V Compact", "Automotive SLI", "L1", 45, 12, 18, 4_200_000, True, "WinterColdSnap"),
    (
        "SLI 60Ah 12V Standard",
        "Automotive SLI",
        "L1",
        60,
        12,
        18,
        5_100_000,
        True,
        "WinterColdSnap",
    ),
    (
        "SLI 70Ah 12V Standard",
        "Automotive SLI",
        "L1",
        70,
        12,
        24,
        5_900_000,
        True,
        "WinterColdSnap",
    ),
    (
        "SLI 88Ah 12V Heavy Duty",
        "Automotive SLI",
        "L1",
        88,
        12,
        24,
        7_400_000,
        True,
        "WinterColdSnap",
    ),
    (
        "SLI 100Ah 12V Heavy Duty",
        "Automotive SLI",
        "L1",
        100,
        12,
        24,
        8_600_000,
        True,
        "WinterColdSnap",
    ),
    ("MC 5Ah 12V Compact", "Motorcycle", "L2", 5, 12, 12, 1_450_000, True, "WinterColdSnap"),
    ("MC 9Ah 12V Standard", "Motorcycle", "L2", 9, 12, 12, 1_950_000, True, "WinterColdSnap"),
    ("MC 12Ah 12V Standard", "Motorcycle", "L2", 12, 12, 12, 2_350_000, True, "WinterColdSnap"),
    ("UPS 7Ah 12V", "Industrial / UPS", "L3", 7, 12, 24, 1_650_000, False, None),
    ("UPS 18Ah 12V", "Industrial / UPS", "L3", 18, 12, 24, 2_950_000, False, None),
    ("UPS 100Ah 12V Industrial", "Industrial / UPS", "L3", 100, 12, 36, 9_800_000, False, None),
    ("Telecom 200Ah 2V Cell", "Industrial / UPS", "L3", 200, 2, 60, 3_200_000, False, None),
    (
        "Solar 100Ah 12V Deep-Cycle",
        "Deep-Cycle / Solar",
        "L4",
        100,
        12,
        24,
        9_200_000,
        False,
        "PreNowruzTravel",
    ),
    (
        "Solar 150Ah 12V Deep-Cycle",
        "Deep-Cycle / Solar",
        "L4",
        150,
        12,
        24,
        12_500_000,
        False,
        "PreNowruzTravel",
    ),
    (
        "Solar 200Ah 12V Deep-Cycle AGM",
        "Deep-Cycle / Solar",
        "L4",
        200,
        12,
        36,
        18_400_000,
        False,
        None,
    ),
    (
        "Marine 100Ah 12V Dual-Purpose",
        "Deep-Cycle / Solar",
        "L4",
        100,
        12,
        24,
        10_100_000,
        False,
        "PreNowruzTravel",
    ),
    (
        "Golf-Cart 220Ah 6V Deep-Cycle",
        "Deep-Cycle / Solar",
        "L4",
        220,
        6,
        24,
        11_300_000,
        False,
        None,
    ),
]

SUPPLIERS = [
    # (supplier_id, supplier_name, material_categories, avg_lead_time_days,
    #  reliability_score, payment_terms_days)
    ("SUP01", "Alborz Lead Smelting Co.", "Lead Ingot, Lead Oxide", 10, 0.95, 40),
    ("SUP02", "Pars Sulfuric Acid Industries", "Sulfuric Acid, Acid Additives", 6, 0.97, 30),
    (
        "SUP03",
        "Tehran Polymer & Plastics Co.",
        "Polypropylene Resin, Separator Sheets",
        8,
        0.96,
        35,
    ),
    ("SUP04", "Isfahan Alloy & Casting Works", "Terminal Posts, Calcium Alloy Grids", 12, 0.92, 45),
    ("SUP05", "Shargh AGM Materials Co.", "AGM Glass Mat", 15, 0.90, 45),
    (
        "SUP06",
        "National Packaging Industries",
        "Cartons, Packaging Film, Warning Labels",
        6,
        0.96,
        40,
    ),
]

RAW_MATERIALS = [
    # (material_name, unit, unit_cost_irr, default_supplier_id, lead_time_days, safety_stock_days)
    ("Lead Ingot", "kg", 620_000, "SUP01", 10, 15),
    ("Lead Oxide", "kg", 580_000, "SUP01", 10, 12),
    ("Sulfuric Acid", "L", 42_000, "SUP02", 6, 10),
    ("Acid Additives", "L", 95_000, "SUP02", 6, 12),
    ("Polypropylene Resin", "kg", 118_000, "SUP03", 8, 12),
    ("Separator Sheets", "unit", 8_500, "SUP03", 8, 10),
    ("Terminal Posts (Lead Alloy)", "unit", 24_000, "SUP04", 12, 15),
    ("Calcium Alloy Grids", "kg", 690_000, "SUP04", 12, 15),
    ("AGM Glass Mat", "unit", 32_000, "SUP05", 15, 18),
    ("Cartons", "unit", 5_200, "SUP06", 6, 10),
    ("Packaging Film", "unit", 2_100, "SUP06", 6, 10),
    ("Warning Labels", "unit", 900, "SUP06", 6, 10),
]

REGIONS = [
    # (region_id, region_name, customer_type, payment_terms_days)
    ("R01", "Tehran Metro", "Distributor", 45),
    ("R02", "Alborz (Karaj)", "Distributor", 45),
    ("R03", "Isfahan", "OEM / Fleet", 55),
    ("R04", "Fars (Shiraz)", "Retailer", 35),
    ("R05", "Khorasan Razavi (Mashhad)", "Distributor", 50),
    ("R06", "East Azerbaijan (Tabriz)", "Retailer", 35),
    ("R07", "National Export", "Export", 100),
]


def generate_employees(engine_seed: int, n_employees: int = 180) -> pd.DataFrame:
    fake = Faker()
    Faker.seed(engine_seed)
    rng = np.random.default_rng(engine_seed)

    role_names = [r[0] for r in ROLES]
    role_weights = np.array([r[1] for r in ROLES])
    role_weights = role_weights / role_weights.sum()
    lines = [p["line_id"] for p in PRODUCTION_LINES]

    non_shift_roles = (
        "Plant Management",
        "Finance / Admin",
        "HR / Support",
        "CRM / IT Administrator",
    )
    production_roles = ("Production Operator", "Line Supervisor", "QC / Battery Test Technician")
    base_wage_by_role = {
        "Production Operator": 1.0,
        "Line Supervisor": 1.65,
        "QC / Battery Test Technician": 1.4,
        "Warehouse Staff": 0.95,
        "Forklift Operator": 1.05,
        "Maintenance Technician": 1.45,
        "Logistics Coordinator": 1.25,
        "Sales Representative": 1.35,
        "Service Representative": 1.15,
        "Procurement Officer": 1.35,
        "Finance / Admin": 1.3,
        "Plant Management": 2.5,
        "HR / Support": 1.1,
        "CRM / IT Administrator": 1.4,
    }

    rows = []
    for i in range(1, n_employees + 1):
        role = rng.choice(role_names, p=role_weights)
        is_production = role in production_roles
        line_id = rng.choice(lines) if is_production else None
        shift = rng.choice(SHIFTS) if role not in non_shift_roles else "Day Office"
        hire_date = fake.date_between(start_date="-9y", end_date="-30d")
        employment_type = rng.choice(
            ["Full-time", "Full-time", "Full-time", "Part-time", "Seasonal"],
            p=[0.6, 0.15, 0.1, 0.1, 0.05],
        )
        monthly_wage_irr = int(rng.normal(base_wage_by_role[role] * 58_000_000, 4_000_000))

        if role == "Sales Representative":
            department = "Sales / CRM"
        elif role == "Service Representative":
            department = "Customer Service"
        elif is_production:
            department = "Production"
        elif role in ("Warehouse Staff", "Forklift Operator", "Logistics Coordinator"):
            department = "Warehouse & Logistics"
        else:
            department = "Corporate"

        rows.append(
            {
                "employee_id": f"E{i:04d}",
                "full_name": fake.name(),
                "role": role,
                "department": department,
                "production_line_id": line_id,
                "shift": shift,
                "employment_type": employment_type,
                "hire_date": hire_date,
                "monthly_wage_irr": max(monthly_wage_irr, 42_000_000),
            }
        )
    return pd.DataFrame(rows)


def generate_production_lines() -> pd.DataFrame:
    return pd.DataFrame(PRODUCTION_LINES)


def generate_products() -> pd.DataFrame:
    cols = [
        "product_name",
        "category",
        "primary_line_id",
        "capacity_ah",
        "voltage",
        "warranty_months",
        "unit_price_irr",
        "is_seasonal",
        "seasonal_peak",
    ]
    df = pd.DataFrame(PRODUCTS, columns=cols)
    df.insert(0, "product_id", [f"P{i:03d}" for i in range(1, len(df) + 1)])
    return df


def generate_suppliers() -> pd.DataFrame:
    cols = [
        "supplier_id",
        "supplier_name",
        "material_categories",
        "avg_lead_time_days",
        "reliability_score",
        "payment_terms_days",
    ]
    return pd.DataFrame(SUPPLIERS, columns=cols)


def generate_raw_materials() -> pd.DataFrame:
    cols = [
        "material_name",
        "unit_of_measure",
        "unit_cost_irr",
        "default_supplier_id",
        "lead_time_days",
        "safety_stock_days",
    ]
    df = pd.DataFrame(RAW_MATERIALS, columns=cols)
    df.insert(0, "material_id", [f"M{i:02d}" for i in range(1, len(df) + 1)])
    return df


def generate_regions() -> pd.DataFrame:
    cols = ["region_id", "region_name", "customer_type", "payment_terms_days"]
    return pd.DataFrame(REGIONS, columns=cols)
