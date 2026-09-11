import pandas as pd

from crm_sop_planning.config import QualityThresholds
from crm_sop_planning.quality.checks import run_quality_checks


def test_quality_passes_within_thresholds():
    monthly_summary = pd.DataFrame({"period_start": ["2026-01-01"], "fill_rate": [0.95]})
    accuracy = pd.DataFrame([{"line_id": "__OVERALL__", "mape": None, "wape": 0.5, "n_months": 4}])
    thresholds = QualityThresholds(min_fill_rate=0.75, max_backtest_wape=0.65)

    report = run_quality_checks(monthly_summary, accuracy, thresholds)
    assert report.passed


def test_quality_fails_when_fill_rate_too_low():
    monthly_summary = pd.DataFrame({"period_start": ["2026-01-01"], "fill_rate": [0.5]})
    accuracy = pd.DataFrame([{"line_id": "__OVERALL__", "mape": None, "wape": 0.5, "n_months": 4}])
    thresholds = QualityThresholds(min_fill_rate=0.75, max_backtest_wape=0.65)

    report = run_quality_checks(monthly_summary, accuracy, thresholds)
    assert not report.passed
    assert any("fill rate" in f for f in report.failures)


def test_quality_fails_when_backtest_wape_too_high():
    monthly_summary = pd.DataFrame({"period_start": ["2026-01-01"], "fill_rate": [1.0]})
    accuracy = pd.DataFrame([{"line_id": "__OVERALL__", "mape": None, "wape": 0.9, "n_months": 4}])
    thresholds = QualityThresholds(min_fill_rate=0.75, max_backtest_wape=0.65)

    report = run_quality_checks(monthly_summary, accuracy, thresholds)
    assert not report.passed
    assert any("WAPE" in f for f in report.failures)
