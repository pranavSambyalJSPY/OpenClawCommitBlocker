"""Evaluation workflow for labeled commit/PR examples."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .model import analyze_with_model
from .scorer import load_weights, score
from .signals import extract_signals


@dataclass(frozen=True)
class LabeledExample:
    """A labeled example used for detector evaluation."""

    example_id: str
    subject_type: str
    repo_path: str
    repo_type: str
    agent_generated: bool
    max_commits: int = 60


def load_examples(examples_path: str | Path) -> list[LabeledExample]:
    """Load JSONL examples with `agent_generated` labels."""

    examples: list[LabeledExample] = []
    for idx, line in enumerate(Path(examples_path).read_text().splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        examples.append(
            LabeledExample(
                example_id=str(payload.get("id", f"example-{idx}")),
                subject_type=str(payload.get("subject_type", "repo")),
                repo_path=str(payload["repo_path"]),
                repo_type=str(payload.get("repo_type", "unknown")),
                agent_generated=bool(payload["agent_generated"]),
                max_commits=int(payload.get("max_commits", 60)),
            )
        )
    return examples


def _classification_counts(labels: list[bool], scores: list[float], threshold: float) -> dict[str, int]:
    tp = fp = tn = fn = 0
    for label, value in zip(labels, scores):
        predicted = value >= threshold
        if predicted and label:
            tp += 1
        elif predicted and not label:
            fp += 1
        elif not predicted and not label:
            tn += 1
        else:
            fn += 1
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}


def _metrics_from_counts(counts: dict[str, int]) -> dict[str, float]:
    tp = counts["tp"]
    fp = counts["fp"]
    tn = counts["tn"]
    fn = counts["fn"]

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": fpr,
    }


def _fpr_by_repo_type(examples: list[LabeledExample], scores: list[float], threshold: float) -> dict[str, float]:
    negatives_by_type: dict[str, int] = defaultdict(int)
    fp_by_type: dict[str, int] = defaultdict(int)

    for example, value in zip(examples, scores):
        if example.agent_generated:
            continue
        negatives_by_type[example.repo_type] += 1
        if value >= threshold:
            fp_by_type[example.repo_type] += 1

    return {
        repo_type: (fp_by_type[repo_type] / count if count else 0.0)
        for repo_type, count in negatives_by_type.items()
    }


def evaluate(
    examples: list[LabeledExample],
    threshold: float,
    thresholds: list[float],
    weights_file: str | Path | None,
    use_model: bool = False,
    model_id: str = "LiquidAI/LFM2.5-1.2B-Instruct",
    model_weight: float = 0.3,
) -> dict[str, object]:
    """Run detector for each example and produce evaluation reports."""

    model_weight = max(0.0, min(1.0, model_weight))
    weights = load_weights(weights_file) if weights_file else load_weights(None)
    labels = [item.agent_generated for item in examples]
    sample_scores: list[float] = []
    sample_results: list[dict[str, object]] = []

    for item in examples:
        signals = extract_signals(item.repo_path, max_commits=item.max_commits)
        heuristic_score = score(signals, weights)
        model_score = 0.0
        model_available = False
        model_evidence = "disabled"

        final_score = heuristic_score
        if use_model:
            model = analyze_with_model(item.repo_path, max_commits=item.max_commits, model_id=model_id)
            model_available = model.available
            model_score = model.score
            model_evidence = model.evidence
            if model_available:
                final_score = (1.0 - model_weight) * heuristic_score + model_weight * model_score

        sample_scores.append(final_score)
        sample_results.append(
            {
                "id": item.example_id,
                "subject_type": item.subject_type,
                "repo_path": item.repo_path,
                "repo_type": item.repo_type,
                "agent_generated": item.agent_generated,
                "score": final_score,
                "heuristic_score": heuristic_score,
                "model_score": model_score,
                "model_available": model_available,
                "model_evidence": model_evidence,
                "predicted_agent_generated": final_score >= threshold,
            }
        )

    counts = _classification_counts(labels, sample_scores, threshold)
    metrics = _metrics_from_counts(counts)

    sweep: list[dict[str, object]] = []
    for item in thresholds:
        item_counts = _classification_counts(labels, sample_scores, item)
        item_metrics = _metrics_from_counts(item_counts)
        sweep.append(
            {
                "threshold": item,
                "confusion_matrix": item_counts,
                "metrics": item_metrics,
                "false_positive_rate_by_repo_type": _fpr_by_repo_type(examples, sample_scores, item),
            }
        )

    return {
        "example_count": len(examples),
        "threshold": threshold,
        "use_model": use_model,
        "model_id": model_id,
        "model_weight": model_weight,
        "confusion_matrix": counts,
        "metrics": metrics,
        "false_positive_rate_by_repo_type": _fpr_by_repo_type(examples, sample_scores, threshold),
        "threshold_sweep": sweep,
        "samples": sample_results,
    }


def load_eval_config(path: str | Path) -> dict[str, object]:
    """Load evaluation config JSON for thresholds and regression budget."""

    config = json.loads(Path(path).read_text())
    threshold = float(config.get("threshold", 0.5))
    sweep = [float(v) for v in config.get("threshold_sweep", [0.1, 0.3, 0.5, 0.7, 0.9])]
    regression = config.get("regression", {})
    launch_gate = config.get("launch_gate", {})

    return {
        "threshold": threshold,
        "threshold_sweep": sweep,
        "regression": {
            "baseline_precision": float(regression.get("baseline_precision", 0.0)),
            "precision_degradation_budget": float(regression.get("precision_degradation_budget", 0.0)),
        },
        "launch_gate": {
            "name": str(launch_gate.get("name", "default")),
            "min_precision": float(launch_gate.get("min_precision", 0.9)),
            "threshold_label": str(launch_gate.get("threshold_label", "medium")),
        },
    }


def regression_status(config: dict[str, object], precision: float) -> dict[str, object]:
    """Return regression-check verdict based on precision degradation budget."""

    regression = config["regression"]
    baseline_precision = float(regression["baseline_precision"])
    budget = float(regression["precision_degradation_budget"])
    min_allowed_precision = baseline_precision - budget
    passed = precision >= min_allowed_precision

    return {
        "passed": passed,
        "baseline_precision": baseline_precision,
        "precision_degradation_budget": budget,
        "min_allowed_precision": min_allowed_precision,
        "observed_precision": precision,
    }
