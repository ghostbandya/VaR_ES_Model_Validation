"""
Orchestrates the full VaR/ES model validation pipeline:
fetch_data -> engine -> analysis -> brief -> build_dashboard -> build_report.
"""
import argparse
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC_DIR))

import fetch_data
import engine
import analysis
import brief
import build_dashboard
import build_report
from config import load_config, DEFAULT_CONFIG_PATH


def parse_args():
    parser = argparse.ArgumentParser(description="Run the VaR/ES model validation pipeline.")
    parser.add_argument("--skip-fetch", action="store_true",
                         help="Skip fetching fresh prices; reuse output/prices.csv as-is.")
    parser.add_argument("--no-brief", action="store_true",
                         help="Skip the Anthropic API daily brief step.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH),
                         help="Path to config.yaml (default: repo root config.yaml).")
    return parser.parse_args()


def print_summary(data):
    print("\n" + "=" * 60)
    print("PIPELINE SUMMARY")
    print("=" * 60)
    for k, name in data["models"].items():
        zone = data["current_zone"][k]
        kt = data["overall_backtest"][k]["kupiec"]
        print(f"  {name:28s} zone={zone['zone'].upper():6s} "
              f"exceptions/250d={zone['breach_count_250d']:<3d} "
              f"total_exceptions={kt['exceptions']}/{kt['n_obs']}")
    print("=" * 60)


def main():
    args = parse_args()
    cfg = load_config(args.config)

    if args.skip_fetch:
        print("Skipping fetch step (--skip-fetch); reusing existing output/prices.csv")
    else:
        fetch_data.main(cfg)

    engine.main(cfg)
    data = analysis.main(cfg)

    brief_text = None
    if args.no_brief:
        print("Skipping daily brief step (--no-brief)")
    else:
        brief_text = brief.main(cfg)

    build_dashboard.main(cfg)
    build_report.main(cfg)

    print_summary(data)
    print(f"Daily brief generated: {'yes' if brief_text else 'no'}")


if __name__ == "__main__":
    main()
