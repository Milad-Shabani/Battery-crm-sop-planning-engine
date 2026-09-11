import pandas as pd

from crm_sop_planning.crm_analytics.funnel import (
    at_risk_accounts,
    lead_funnel,
    lose_reason_breakdown,
    sales_cycle_length,
    win_rate_by_segment,
)


def _opps():
    return pd.DataFrame(
        [
            {
                "opportunity_id": "O1",
                "account_id": "A1",
                "status": "Won",
                "actual_value_irr": 100,
                "created_date": "2025-01-01",
                "actual_close_date": "2025-02-01",
                "lose_reason": None,
            },
            {
                "opportunity_id": "O2",
                "account_id": "A2",
                "status": "Lost",
                "actual_value_irr": None,
                "created_date": "2025-01-01",
                "actual_close_date": "2025-03-01",
                "lose_reason": "Price",
            },
            {
                "opportunity_id": "O3",
                "account_id": "A1",
                "status": "Open",
                "actual_value_irr": None,
                "created_date": "2025-06-01",
                "actual_close_date": None,
                "lose_reason": None,
            },
        ]
    )


def test_lead_funnel_conversion_rate():
    leads = pd.DataFrame(
        [
            {"source": "Web", "status": "Qualified"},
            {"source": "Web", "status": "Disqualified"},
            {"source": "Web", "status": "Qualified"},
            {"source": "Referral", "status": "Qualified"},
        ]
    )
    result = lead_funnel(leads).set_index("source")
    assert abs(result.loc["Web", "conversion_rate"] - 2 / 3) < 0.001


def test_win_rate_by_segment_excludes_open_opportunities():
    accounts = pd.DataFrame(
        [
            {"account_id": "A1", "account_type": "Distributor"},
            {"account_id": "A2", "account_type": "Retailer"},
        ]
    )
    result = win_rate_by_segment(_opps(), accounts)
    assert result["opportunities"].sum() == 2  # only Won + Lost, not the Open one


def test_lose_reason_breakdown_only_counts_lost():
    result = lose_reason_breakdown(_opps())
    assert len(result) == 1
    assert result.iloc[0]["lose_reason"] == "Price"


def test_sales_cycle_length_won_vs_lost():
    result = sales_cycle_length(_opps()).set_index("status")
    assert result.loc["Won", "mean"] == 31.0  # Jan 1 -> Feb 1
    assert result.loc["Lost", "mean"] == 59.0  # Jan 1 -> Mar 1


def test_at_risk_flags_open_case_and_quiet_account():
    accounts = pd.DataFrame(
        [{"account_id": "A1", "account_name": "Acme", "account_type": "Distributor"}]
    )
    cases = pd.DataFrame([{"account_id": "A1", "status": "Open"}])
    orders = pd.DataFrame([{"account_id": "A1", "order_date": "2024-01-01"}])
    activities = pd.DataFrame(columns=["account_id"])

    result = at_risk_accounts(
        accounts, cases, activities, orders, as_of=pd.Timestamp("2025-06-01"), quiet_days=90
    )
    assert result.iloc[0]["at_risk"]


def test_at_risk_false_when_account_ordered_recently():
    accounts = pd.DataFrame(
        [{"account_id": "A1", "account_name": "Acme", "account_type": "Distributor"}]
    )
    cases = pd.DataFrame([{"account_id": "A1", "status": "Open"}])
    orders = pd.DataFrame([{"account_id": "A1", "order_date": "2025-05-20"}])
    activities = pd.DataFrame(columns=["account_id"])

    result = at_risk_accounts(
        accounts, cases, activities, orders, as_of=pd.Timestamp("2025-06-01"), quiet_days=90
    )
    assert not result.iloc[0]["at_risk"]
