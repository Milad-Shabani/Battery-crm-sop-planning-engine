"""Command-line entry point.

python -m crm_sop_planning.cli generate-data --seed 42
python -m crm_sop_planning.cli run
"""

from __future__ import annotations

import argparse
import sys

from .datagen.build_dataset import build_dataset
from .logging_config import setup_logging
from .pipeline import run_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="crm-sop-planning")
    sub = parser.add_subparsers(dest="command", required=True)

    gen_parser = sub.add_parser(
        "generate-data", help="Generate the synthetic CRM + operations dataset."
    )
    gen_parser.add_argument("--out-dir", default="data/raw")
    gen_parser.add_argument("--seed", type=int, default=42)
    gen_parser.add_argument("--employees", type=int, default=180)
    gen_parser.add_argument("--accounts", type=int, default=70)
    gen_parser.add_argument("--leads", type=int, default=1800)
    gen_parser.add_argument("--direct-opportunities", type=int, default=320)
    gen_parser.add_argument("--cases", type=int, default=450)
    gen_parser.add_argument("--start", default="2024-01-01")
    gen_parser.add_argument("--end", default="2025-12-31")
    gen_parser.add_argument("--log-level", default="INFO")

    run_parser = sub.add_parser(
        "run", help="Run forecast -> capacity plan -> MRP -> CRM analytics -> publish."
    )
    run_parser.add_argument("--config", default="config/config.yaml")
    run_parser.add_argument("--log-level", default="INFO")
    run_parser.add_argument("--no-fail-on-quality", action="store_true")

    args = parser.parse_args(argv)
    setup_logging(args.log_level)

    if args.command == "generate-data":
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
        print(
            f"\nGenerated {len(counts)} tables, {sum(counts.values()):,} total rows, "
            f"in {args.out_dir}"
        )
        return 0

    if args.command == "run":
        result = run_pipeline(config_path=args.config, fail_on_quality=not args.no_fail_on_quality)
        print(
            f"\nForecasted {result.months_forecasted} months ahead: "
            f"{result.total_forecast_units:,} units demanded (incl. CRM pipeline overlay), "
            f"{result.total_allocated_units:,} units planned "
            f"({result.total_allocated_units / max(result.total_forecast_units, 1):.1%} fill rate) "
            f"in {result.duration_seconds:.2f}s "
            f"(quality {'PASSED' if result.quality.passed else 'FAILED'})"
        )
        return 0 if result.quality.passed else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
