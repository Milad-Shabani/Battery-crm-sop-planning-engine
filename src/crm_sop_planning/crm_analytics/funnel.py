"""CRM funnel and pipeline health analytics — the reporting a sales
manager actually wants alongside the S&OP numbers: where deals fall out of
the funnel, who's winning, how long deals take, which lead sources are
worth the spend, and which accounts have gone quiet.
"""

from __future__ import annotations

import pandas as pd


def lead_funnel(leads: pd.DataFrame) -> pd.DataFrame:
    """Lead outcome counts and conversion rate, by source."""
    summary = leads.groupby("source")["status"].value_counts().unstack(fill_value=0)
    for col in ("Open", "Qualified", "Disqualified"):
        if col not in summary.columns:
            summary[col] = 0
    summary["total"] = summary[["Open", "Qualified", "Disqualified"]].sum(axis=1)
    summary["conversion_rate"] = (summary["Qualified"] / summary["total"]).round(3)
    return summary.reset_index().sort_values("conversion_rate", ascending=False)


def opportunity_funnel(opportunities: pd.DataFrame) -> pd.DataFrame:
    """Resolved-opportunity counts by stage-at-close-equivalent status."""
    resolved = opportunities[opportunities["status"].isin(["Won", "Lost"])]
    total = len(resolved)
    won = (resolved["status"] == "Won").sum()
    return pd.DataFrame(
        [
            {"stage": "Created", "count": len(opportunities)},
            {"stage": "Resolved (Won or Lost)", "count": total},
            {"stage": "Won", "count": int(won)},
        ]
    ).assign(win_rate=lambda d: round(won / total, 3) if total else None)


def win_rate_by_segment(
    opportunities: pd.DataFrame, accounts: pd.DataFrame, segment_col: str = "account_type"
) -> pd.DataFrame:
    df = opportunities[opportunities["status"].isin(["Won", "Lost"])].merge(
        accounts[["account_id", segment_col]], on="account_id"
    )
    summary = df.groupby(segment_col).agg(
        opportunities=("opportunity_id", "count"),
        won=("status", lambda s: (s == "Won").sum()),
        won_value_irr=("actual_value_irr", "sum"),
    )
    summary["win_rate"] = (summary["won"] / summary["opportunities"]).round(3)
    return summary.reset_index().sort_values("win_rate", ascending=False)


def rep_leaderboard(opportunities: pd.DataFrame, employees: pd.DataFrame) -> pd.DataFrame:
    df = opportunities[opportunities["status"].isin(["Won", "Lost"])].copy()
    summary = df.groupby("owner").agg(
        opportunities=("opportunity_id", "count"),
        won=("status", lambda s: (s == "Won").sum()),
        won_value_irr=("actual_value_irr", "sum"),
    )
    summary["win_rate"] = (summary["won"] / summary["opportunities"]).round(3)
    summary = summary.reset_index().rename(columns={"owner": "employee_id"})
    summary = summary.merge(employees[["employee_id", "full_name"]], on="employee_id", how="left")
    return summary.sort_values("won_value_irr", ascending=False)


def sales_cycle_length(opportunities: pd.DataFrame) -> pd.DataFrame:
    resolved = opportunities[opportunities["status"].isin(["Won", "Lost"])].copy()
    resolved["created_date"] = pd.to_datetime(resolved["created_date"])
    resolved["actual_close_date"] = pd.to_datetime(resolved["actual_close_date"])
    resolved["cycle_days"] = (resolved["actual_close_date"] - resolved["created_date"]).dt.days

    return (
        resolved.groupby("status")["cycle_days"]
        .agg(["mean", "median", "count"])
        .round(1)
        .reset_index()
    )


def lose_reason_breakdown(opportunities: pd.DataFrame) -> pd.DataFrame:
    lost = opportunities[opportunities["status"] == "Lost"]
    counts = lost["lose_reason"].value_counts().reset_index()
    counts.columns = ["lose_reason", "count"]
    counts["share"] = (counts["count"] / counts["count"].sum()).round(3)
    return counts


def at_risk_accounts(
    accounts: pd.DataFrame,
    cases: pd.DataFrame,
    activities: pd.DataFrame,
    sales_orders: pd.DataFrame,
    as_of: pd.Timestamp,
    quiet_days: int = 90,
) -> pd.DataFrame:
    """Accounts with an open case AND no recent sales/activity — a simple,
    explainable churn-risk flag rather than a black-box score."""
    open_cases = cases[cases["status"] == "Open"].groupby("account_id").size().rename("open_cases")

    last_order = sales_orders.copy()
    last_order["order_date"] = pd.to_datetime(last_order["order_date"])
    last_order_by_account = (
        last_order.groupby("account_id")["order_date"].max().rename("last_order_date")
    )

    result = accounts[["account_id", "account_name", "account_type"]].merge(
        open_cases, on="account_id", how="left"
    )
    result = result.merge(last_order_by_account, on="account_id", how="left")
    result["open_cases"] = result["open_cases"].fillna(0).astype(int)
    result["days_since_last_order"] = (as_of - result["last_order_date"]).dt.days
    result["days_since_last_order"] = result["days_since_last_order"].fillna(9999).astype(int)

    result["at_risk"] = (result["open_cases"] > 0) & (result["days_since_last_order"] > quiet_days)
    return result.sort_values(["at_risk", "days_since_last_order"], ascending=[False, False])
