"""CLI entrypoint for commit-blocker."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .eval import evaluate, load_eval_config, load_examples, regression_status
from .model import DEFAULT_MODEL_ID, analyze_with_model
from .report import to_json, to_table
from .scorer import load_weights, risk_band, score
from .signals import extract_signals

DEFAULT_WEIGHTS_CONFIG = Path("config/default_weights.json")


def _blend_scores(heuristic_score: float, model_score: float, model_weight: float) -> float:
    model_weight = max(0.0, min(1.0, model_weight))
    return (1.0 - model_weight) * heuristic_score + model_weight * model_score


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
    scan.add_argument(
        "--use-model",
        action="store_true",
        help="blend heuristic score with LLM analysis (LiquidAI/LFM2.5-1.2B-Instruct by default)",
    )
    scan.add_argument(
        "--model-id",
        default=DEFAULT_MODEL_ID,
        help="Hugging Face model id for optional LLM analysis",
    )
    scan.add_argument(
        "--model-weight",
        type=float,
        default=0.3,
        help="blend weight for model score in final decision [0.0-1.0]",
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
    evaluate_parser.add_argument("--use-model", action="store_true", help="enable optional LLM signal during evaluation")
    evaluate_parser.add_argument("--model-id", default=DEFAULT_MODEL_ID, help="Hugging Face model id for optional LLM analysis")
    evaluate_parser.add_argument("--model-weight", type=float, default=0.3, help="blend weight for model score in final score")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "scan":
        signals = extract_signals(args.repo_path, max_commits=args.max_commits)
        weights = load_weights(args.weights_file) if args.weights_file else load_weights(None)
        heuristic_score = score(signals, weights=weights)

        analysis: dict[str, object] | None = None
        final_score = heuristic_score
        if args.use_model:
            model_result = analyze_with_model(args.repo_path, max_commits=args.max_commits, model_id=args.model_id)
            if model_result.available:
                final_score = _blend_scores(heuristic_score, model_result.score, args.model_weight)
            analysis = {
                "heuristic_score": round(heuristic_score, 3),
                "model_score": round(model_result.score, 3),
                "model_weight": round(max(0.0, min(1.0, args.model_weight)), 3),
                "final_score": round(final_score, 3),
                "model_available": model_result.available,
                "model_id": model_result.model_id,
                "model_evidence": model_result.evidence,
            }

        band = risk_band(final_score)
        output = (
            to_json(args.repo_path, final_score, band, signals, weights, analysis=analysis)
            if args.format == "json"
            else to_table(args.repo_path, final_score, band, signals, weights, analysis=analysis)
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
            use_model=args.use_model,
            model_id=args.model_id,
            model_weight=args.model_weight,
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
