"""Weighted scoring for residue signals."""

from __future__ import annotations

import json
from pathlib import Path

from .signals import Signal

DEFAULT_WEIGHTS = {
    "automation_marker": 0.4,
    "templated_pr_style": 0.6,
}


def load_weights(config_path: str | Path | None = None) -> dict[str, float]:
    """Load weights from a JSON config file.

    Expected shape:
    {
      "weights": {
        "signal_name": 0.5
      }
    }
    """

    if config_path is None:
        return DEFAULT_WEIGHTS.copy()

    path = Path(config_path)
    payload = json.loads(path.read_text())
    weights = payload.get("weights", {})
    return {str(k): float(v) for k, v in weights.items()}


def score(signals: list[Signal], weights: dict[str, float] | None = None) -> float:
    """Return weighted aggregate score in the [0.0, 1.0] range."""

    active_weights = weights or DEFAULT_WEIGHTS
    total_weight = 0.0
    weighted_sum = 0.0

    for signal in signals:
        weight = active_weights.get(signal.name, 0.0)
        weighted_sum += signal.score * weight
        total_weight += weight

    if total_weight == 0.0:
        return 0.0

    return max(0.0, min(1.0, weighted_sum / total_weight))
