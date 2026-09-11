"""Pipeline orchestration: load data -> forecast (statistical + CRM
pipeline overlay) -> capacity LP -> MRP -> CRM analytics -> quality gate ->
publish (SQLite + Parquet + Excel workbook).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import pandas as pd

from .config import PlanningSettings, load_settings
from .crm_analytics.funnel import (
    at_risk_accounts,
    lead_funnel,
    lose_reason_breakdown,
    opportunity_funnel,
    rep_leaderboard,
    win_rate_by_segment,
)
from .forecasting.backtest import accuracy_summary, backtest
from .forecasting.forecaster import forecast_all_lines, monthly_line_demand
from .forecasting.pipeline_signal import build_sku_forecast
from .io_utils import load_raw_tables
from .load.excel_export import build_workbook
from .load.outputs import write_outputs
from .planning.capacity_lp import build_production_plan
from .planning.mrp import (
    explode_requirements,
    latest_on_hand,
    net_requirements_and_recommend_orders,
)
from .planning.sop_report import build_monthly_summary
from .quality.checks import QualityReport, run_quality_checks

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    months_forecasted: int
    total_forecast_units: int
    total_allocated_units: int
    quality: QualityReport
    duration_seconds: float


def run_pipeline(
    config_path: str = "config/config.yaml", fail_on_quality: bool = True
) -> PipelineResult:
    started = time.monotonic()
    settings: PlanningSettings = load_settings(config_path)

    logger.info("Loading raw tables from %s", settings.raw_dir)
    tables = load_raw_tables(settings.raw_dir)

    logger.info("Aggregating order history to monthly line-level demand...")
    monthly = monthly_line_demand(tables["fact_sales_orders"], tables["dim_product"])

    logger.info(
        "Backtesting the statistical forecast component (last %d months)...",
        settings.backtest_months,
    )
    bt = backtest(monthly, test_months=settings.backtest_months)
    accuracy = accuracy_summary(bt)

    logger.info("Forecasting %d months ahead, per line...", settings.horizon_months)
    line_forecast = forecast_all_lines(monthly, horizon_months=settings.horizon_months)

    logger.info("Blending in the open CRM pipeline and reconstructing SKU-level forecast...")
    sku_forecast = build_sku_forecast(
        line_forecast,
        tables["dim_product"],
        tables["fact_sales_orders"],
        tables["fact_opportunities"],
    )

    logger.info("Solving the production capacity LP for every line/month...")
    production_plan = build_production_plan(
        sku_forecast.rename(columns={"forecast_units": "forecast_units"}),
        tables["dim_product"],
        tables["dim_production_line"],
        tables["fact_workforce_availability"],
        operators_per_running_hour=settings.operators_per_running_hour,
        hours_per_shift=settings.hours_per_shift,
        oee=settings.oee,
    )

    logger.info("Running MRP: exploding the plan through the BOM and netting against inventory...")
    requirements = explode_requirements(production_plan, tables["bom"])
    on_hand = latest_on_hand(tables["fact_inventory_transactions"])
    mrp = net_requirements_and_recommend_orders(requirements, tables["dim_raw_material"], on_hand)

    monthly_summary = build_monthly_summary(production_plan, tables["dim_product"], mrp)

    logger.info("Computing CRM funnel and account-health analytics...")
    lead_funnel_df = lead_funnel(tables["fact_leads"])
    opportunity_funnel_df = opportunity_funnel(tables["fact_opportunities"])
    win_rate_df = win_rate_by_segment(tables["fact_opportunities"], tables["dim_account"])
    rep_leaderboard_df = rep_leaderboard(tables["fact_opportunities"], tables["dim_employee"])
    lose_reasons_df = lose_reason_breakdown(tables["fact_opportunities"])
    as_of = pd.to_datetime(tables["fact_sales_orders"]["order_date"]).max()
    at_risk_df = at_risk_accounts(
        tables["dim_account"],
        tables["fact_cases"],
        tables["fact_activities"],
        tables["fact_sales_orders"],
        as_of,
    )

    quality = run_quality_checks(monthly_summary, accuracy, settings.quality)
    if not quality.passed and fail_on_quality:
        raise RuntimeError(f"Quality gate failed: {'; '.join(quality.failures)}")

    write_outputs(
        {
            "forecast": sku_forecast,
            "production_plan": production_plan,
            "material_requirements": mrp,
            "monthly_summary": monthly_summary,
            "backtest_accuracy": accuracy,
            "lead_funnel": lead_funnel_df,
            "win_rate_by_segment": win_rate_df,
            "rep_leaderboard": rep_leaderboard_df,
            "at_risk_accounts": at_risk_df,
        },
        settings.processed_dir,
        settings.parquet_dir,
    )

    logger.info("Building the Excel workbook...")
    build_workbook(
        monthly_summary,
        sku_forecast,
        production_plan,
        mrp,
        accuracy,
        lead_funnel_df,
        opportunity_funnel_df,
        win_rate_df,
        rep_leaderboard_df,
        lose_reasons_df,
        at_risk_df,
        tables["dim_product"],
        settings.excel_path,
    )

    duration = time.monotonic() - started
    logger.info("Pipeline completed in %.2fs", duration)

    return PipelineResult(
        months_forecasted=settings.horizon_months,
        total_forecast_units=int(sku_forecast["forecast_units"].sum()),
        total_allocated_units=int(production_plan["allocated_units"].sum()),
        quality=quality,
        duration_seconds=duration,
    )
