"""CLI entrypoint for commit-blocker."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .eval import evaluate, load_eval_config, load_examples, regression_status
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

    evaluate_parser = subcommands.add_parser("eval", help="evaluate detector on labeled examples")
    evaluate_parser.add_argument(
        "examples_file",
        help="JSONL examples with id, repo_path, repo_type, subject_type, and agent_generated",
    )
    evaluate_parser.add_argument(
        "--config",
        default="eval/config.json",
        help="evaluation config path (thresholds, regression budget, launch gate)",
    )
    evaluate_parser.add_argument(
        "--weights-file",
        default=str(DEFAULT_WEIGHTS_CONFIG) if DEFAULT_WEIGHTS_CONFIG.exists() else None,
        help="optional JSON file with {\"weights\": {signal: value}}",
    )
    evaluate_parser.add_argument(
        "--output",
        default="eval/report.json",
        help="path for machine-readable evaluation report",
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

    if args.command == "eval":
        examples = load_examples(args.examples_file)
        config = load_eval_config(args.config)
        report = evaluate(
            examples=examples,
            threshold=float(config["threshold"]),
            thresholds=[float(v) for v in config["threshold_sweep"]],
            weights_file=args.weights_file,
        )
        regression = regression_status(config, float(report["metrics"]["precision"]))
        launch_gate = config["launch_gate"]
        launch_gate_passed = (
            float(report["metrics"]["precision"]) >= float(launch_gate["min_precision"])
        )

        payload = {
            "report": report,
            "regression_check": regression,
            "launch_gate": {
                **launch_gate,
                "passed": launch_gate_passed,
                "observed_precision": report["metrics"]["precision"],
            },
        }
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2) + "\n")

        print(json.dumps(payload, indent=2))
        return 1 if (not regression["passed"] or not launch_gate_passed) else 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
