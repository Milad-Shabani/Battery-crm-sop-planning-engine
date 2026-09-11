"""Dynamics-365-style CRM entity generator: Accounts, Contacts, Leads,
Opportunities (with a real sales-stage funnel), Activities, and Cases.

The design choice that makes this useful for forecasting rather than just
decorative: an opportunity's `estimated_close_date` can fall *after* the
end of the historical data window. Those opportunities are left genuinely
OPEN (no actual_close_date, no final Won/Lost status) with a current stage
and probability — exactly the open pipeline a real sales team would be
carrying into the next quarter, and exactly what
`forecasting.pipeline_signal` uses as a leading indicator for the forecast
horizon.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from faker import Faker

STAGES = ["1-Qualify", "2-Develop", "3-Propose", "4-Close"]
STAGE_PROBABILITY = {"1-Qualify": 0.15, "2-Develop": 0.35, "3-Propose": 0.65, "4-Close": 0.90}

LEAD_SOURCES = ["Web Inquiry", "Trade Show", "Referral", "Cold Outreach", "Partner Channel"]
DISQUALIFY_REASONS = [
    "No Budget",
    "No Longer Interested",
    "Wrong Fit",
    "Went With Competitor",
    "Unresponsive",
]
LOSE_REASONS = [
    "Price",
    "Lost to Competitor",
    "No Budget",
    "Timing / Postponed",
    "Went With In-house Supply",
]
CASE_CATEGORIES = [
    "Warranty Claim",
    "Technical Support",
    "Billing Inquiry",
    "Delivery Complaint",
    "Product Defect",
]
CASE_PRIORITIES = ["Low", "Medium", "High", "Critical"]

ACCOUNT_NAME_SUFFIXES = [
    "Trading Co.",
    "Auto Parts",
    "Distribution Group",
    "Battery Center",
    "Fleet Services",
    "Import & Export Co.",
    "Industrial Supply",
]


def generate_accounts(regions: pd.DataFrame, n_accounts: int, seed: int) -> pd.DataFrame:
    fake = Faker()
    Faker.seed(seed)
    rng = np.random.default_rng(seed)

    rows = []
    for i in range(1, n_accounts + 1):
        region = regions.iloc[rng.integers(0, len(regions))]
        customer_type = region["customer_type"]
        annual_revenue = int(
            rng.lognormal(mean=16.5 if customer_type != "OEM / Fleet" else 17.3, sigma=0.7)
        )
        company_name = fake.company().split(",")[0]
        rows.append(
            {
                "account_id": f"ACC{i:04d}",
                "account_name": f"{company_name} {rng.choice(ACCOUNT_NAME_SUFFIXES)}",
                "account_type": customer_type,
                "region_id": region["region_id"],
                "annual_revenue_estimate_irr": annual_revenue,
                "credit_limit_irr": int(annual_revenue * rng.uniform(0.05, 0.15)),
                "created_date": fake.date_between(start_date="-6y", end_date="-90d"),
            }
        )
    return pd.DataFrame(rows)


def generate_contacts(accounts: pd.DataFrame, seed: int) -> pd.DataFrame:
    fake = Faker()
    Faker.seed(seed + 1)
    rng = np.random.default_rng(seed + 1)
    titles = [
        "Procurement Manager",
        "Fleet Manager",
        "Owner",
        "Purchasing Officer",
        "Operations Manager",
        "General Manager",
    ]

    rows = []
    cid = 1
    for _, acc in accounts.iterrows():
        n_contacts = rng.integers(1, 4)
        for _ in range(n_contacts):
            name = fake.name()
            rows.append(
                {
                    "contact_id": f"CON{cid:05d}",
                    "account_id": acc["account_id"],
                    "full_name": name,
                    "title": rng.choice(titles),
                    "email": name.lower().replace(" ", ".").replace("'", "") + "@example.com",
                    "phone": fake.phone_number(),
                }
            )
            cid += 1
    return pd.DataFrame(rows)


def _assign_open_stage(created_date, estimated_close_date, as_of_date, rng) -> tuple[str, float]:
    total = (estimated_close_date - created_date).days
    elapsed = (as_of_date - created_date).days
    frac = np.clip(elapsed / total if total > 0 else 1.0, 0, 1)
    idx = min(int(frac * len(STAGES)), len(STAGES) - 1)
    stage = STAGES[idx]
    prob = np.clip(STAGE_PROBABILITY[stage] + rng.normal(0, 0.05), 0.05, 0.95)
    return stage, round(float(prob), 2)


def generate_leads_and_opportunities(
    accounts: pd.DataFrame,
    products: pd.DataFrame,
    sales_reps: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    n_leads: int,
    n_direct_opportunities: int,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Leads feed a fraction of opportunities (new-business); the rest are
    created directly against existing accounts (expansion/repeat business),
    which is how most CRM pipelines actually split in practice.
    """
    Faker.seed(seed + 2)
    rng = np.random.default_rng(seed + 2)

    rep_ids = sales_reps["employee_id"].tolist()
    product_ids = products["product_id"].tolist()
    product_price = dict(zip(products["product_id"], products["unit_price_irr"]))
    account_ids = accounts["account_id"].tolist()
    account_type = dict(zip(accounts["account_id"], accounts["account_type"]))

    lead_days = rng.integers(0, (end_date - start_date).days, size=n_leads)
    lead_rows = []
    converted_lead_ids = []
    for i in range(n_leads):
        created = start_date + pd.Timedelta(days=int(lead_days[i]))
        lead_id = f"LEAD{i + 1:05d}"
        # Younger leads (created near end_date) may still be genuinely open.
        days_since = (end_date - created).days
        will_resolve = days_since > 21 or rng.random() < 0.3
        if not will_resolve:
            status, qualified_date, converts = "Open", None, False
        else:
            converts = rng.random() < 0.38
            status = "Qualified" if converts else "Disqualified"
            qualified_date = created + pd.Timedelta(days=int(rng.integers(2, 21)))
            qualified_date = min(qualified_date, end_date)

        lead_rows.append(
            {
                "lead_id": lead_id,
                "created_date": created.date(),
                "source": rng.choice(LEAD_SOURCES),
                "owner": rng.choice(rep_ids),
                "status": status,
                "qualified_date": qualified_date.date() if qualified_date is not None else None,
                "disqualify_reason": (
                    None if converts or status == "Open" else rng.choice(DISQUALIFY_REASONS)
                ),
            }
        )
        if converts:
            converted_lead_ids.append((lead_id, qualified_date, rng.choice(account_ids)))

    leads = pd.DataFrame(lead_rows)

    # --- Opportunities: converted-from-lead + directly-created ---
    opp_rows = []
    opp_counter = 1

    def _make_opportunity(created, source_account, lead_id):
        nonlocal opp_counter
        acc_type = account_type[source_account]
        cycle_days = {
            "Distributor": rng.integers(20, 60),
            "Retailer": rng.integers(15, 40),
            "OEM / Fleet": rng.integers(45, 150),
            "Export": rng.integers(60, 180),
        }[acc_type]
        estimated_close = created + pd.Timedelta(days=int(cycle_days))
        product_id = rng.choice(product_ids)
        qty = max(int(rng.lognormal(mean=3.2, sigma=0.9)), 1)
        estimated_value = int(qty * product_price[product_id] * rng.uniform(0.95, 1.1))

        row = {
            "opportunity_id": f"OPP{opp_counter:05d}",
            "account_id": source_account,
            "lead_id": lead_id,
            "owner": rng.choice(rep_ids),
            "product_id": product_id,
            "estimated_quantity": qty,
            "created_date": created.date(),
            "estimated_close_date": estimated_close.date(),
        }
        opp_counter += 1

        if estimated_close <= end_date:
            slip_days = max(int(rng.normal(4, 6)), -10)
            actual_close = min(estimated_close + pd.Timedelta(days=slip_days), end_date)
            win_rate = {"Distributor": 0.42, "Retailer": 0.5, "OEM / Fleet": 0.3, "Export": 0.25}[
                acc_type
            ]
            won = rng.random() < win_rate
            row.update(
                {
                    "stage": "4-Close",
                    "probability_pct": 1.0 if won else 0.0,
                    "status": "Won" if won else "Lost",
                    "actual_close_date": actual_close.date(),
                    "actual_value_irr": (
                        int(estimated_value * rng.uniform(0.9, 1.05)) if won else None
                    ),
                    "lose_reason": None if won else rng.choice(LOSE_REASONS),
                }
            )
        else:
            stage, prob = _assign_open_stage(created, estimated_close, end_date, rng)
            row.update(
                {
                    "stage": stage,
                    "probability_pct": prob,
                    "status": "Open",
                    "actual_close_date": None,
                    "actual_value_irr": None,
                    "lose_reason": None,
                }
            )
        row["estimated_value_irr"] = estimated_value
        return row

    for lead_id, qualified_date, source_account in converted_lead_ids:
        created = qualified_date + pd.Timedelta(days=int(rng.integers(1, 5)))
        if created > end_date:
            continue
        opp_rows.append(_make_opportunity(created, source_account, lead_id))

    direct_days = rng.integers(0, (end_date - start_date).days, size=n_direct_opportunities)
    for i in range(n_direct_opportunities):
        created = start_date + pd.Timedelta(days=int(direct_days[i]))
        source_account = rng.choice(account_ids)
        opp_rows.append(_make_opportunity(created, source_account, None))

    opportunities = pd.DataFrame(opp_rows)
    return leads, opportunities


def generate_activities(
    opportunities: pd.DataFrame, cases: pd.DataFrame, seed: int
) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 3)
    types = ["Call", "Email", "Meeting", "Task"]
    rows = []
    aid = 1

    def _emit(regarding_type, regarding_id, owner, window_start, window_end, n):
        nonlocal aid
        span = max((window_end - window_start).days, 1)
        for _ in range(n):
            d = window_start + pd.Timedelta(days=int(rng.integers(0, span + 1)))
            atype = rng.choice(types, p=[0.4, 0.35, 0.15, 0.1])
            rows.append(
                {
                    "activity_id": f"ACT{aid:06d}",
                    "type": atype,
                    "regarding_type": regarding_type,
                    "regarding_id": regarding_id,
                    "owner": owner,
                    "activity_date": d.date(),
                    "duration_minutes": (
                        int(rng.integers(5, 45)) if atype in ("Call", "Meeting") else None
                    ),
                }
            )
            aid += 1

    for _, opp in opportunities.iterrows():
        start = pd.Timestamp(opp["created_date"])
        end = (
            pd.Timestamp(opp["actual_close_date"])
            if pd.notna(opp["actual_close_date"])
            else start + pd.Timedelta(days=30)
        )
        n = int(rng.integers(2, 9))
        _emit("Opportunity", opp["opportunity_id"], opp["owner"], start, end, n)

    for _, case in cases.iterrows():
        start = pd.Timestamp(case["created_date"])
        end = (
            pd.Timestamp(case["resolved_date"])
            if pd.notna(case["resolved_date"])
            else start + pd.Timedelta(days=10)
        )
        n = int(rng.integers(1, 6))
        _emit("Case", case["case_id"], case["owner"], start, end, n)

    return pd.DataFrame(rows)


def generate_cases(
    accounts: pd.DataFrame,
    contacts: pd.DataFrame,
    products: pd.DataFrame,
    service_reps: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    n_cases: int,
    seed: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 4)
    contacts_by_account = contacts.groupby("account_id")["contact_id"].apply(list).to_dict()
    account_ids = accounts["account_id"].tolist()
    product_ids = products["product_id"].tolist()
    rep_ids = service_reps["employee_id"].tolist()

    days = rng.integers(0, (end_date - start_date).days, size=n_cases)
    rows = []
    for i in range(n_cases):
        created = start_date + pd.Timedelta(days=int(days[i]))
        account_id = rng.choice(account_ids)
        contacts_here = contacts_by_account.get(account_id, [None])
        resolve_days = int(rng.lognormal(mean=1.6, sigma=0.8))
        resolved = created + pd.Timedelta(days=resolve_days)
        still_open = resolved > end_date
        rows.append(
            {
                "case_id": f"CASE{i + 1:05d}",
                "account_id": account_id,
                "contact_id": rng.choice(contacts_here),
                "product_id": rng.choice(product_ids),
                "owner": rng.choice(rep_ids),
                "priority": rng.choice(CASE_PRIORITIES, p=[0.35, 0.4, 0.2, 0.05]),
                "category": rng.choice(CASE_CATEGORIES),
                "created_date": created.date(),
                "resolved_date": None if still_open else resolved.date(),
                "status": "Open" if still_open else "Resolved",
            }
        )
    return pd.DataFrame(rows)
