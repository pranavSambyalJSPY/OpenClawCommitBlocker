"""CLI entrypoint for commit-blocker."""

from __future__ import annotations

import argparse
from pathlib import Path

from .report import to_json, to_table
from .scorer import load_weights, risk_band, score
from .signals import extract_signals

DEFAULT_WEIGHTS_CONFIG = Path("config/default_weights.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="commit-blocker")
    subcommands = parser.add_subparsers(dest="command", required=True)

    scan = subcommands.add_parser("scan", help="scan a repository path")
    scan.add_argument("repo_path", help="path to target repository")
    scan.add_argument(
        "--format",
        choices=("json", "table"),
        default="table",
        help="output format",
    )
    scan.add_argument(
        "--max-commits",
        type=int,
        default=60,
        help="number of recent commits to inspect",
    )
    scan.add_argument(
        "--weights-file",
        default=str(DEFAULT_WEIGHTS_CONFIG) if DEFAULT_WEIGHTS_CONFIG.exists() else None,
        help="optional JSON file with {\"weights\": {signal: value}}",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "scan":
        signals = extract_signals(args.repo_path, max_commits=args.max_commits)
        weights = load_weights(args.weights_file) if args.weights_file else load_weights(None)
        final_score = score(signals, weights=weights)
        band = risk_band(final_score)
        output = (
            to_json(args.repo_path, final_score, band, signals, weights)
            if args.format == "json"
            else to_table(args.repo_path, final_score, band, signals, weights)
        )
        print(output)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
