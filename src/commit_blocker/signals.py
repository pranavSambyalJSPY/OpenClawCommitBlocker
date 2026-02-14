"""Signal extraction helpers for commit/PR residue analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Signal:
    """A single residue signal and its normalized score."""

    name: str
    score: float
    evidence: str


def extract_signals(repo_path: str | Path) -> list[Signal]:
    """Return a small baseline set of heuristic signals.

    This scaffold intentionally ships with a tiny, deterministic extractor so
    clients can swap in richer repository/PR parsing logic later.
    """

    path = Path(repo_path)
    path_hint = "missing-path" if not path.exists() else "existing-path"

    return [
        Signal(
            name="automation_marker",
            score=0.2,
            evidence=f"repo_path_status={path_hint}",
        ),
        Signal(
            name="templated_pr_style",
            score=0.35,
            evidence="placeholder residue model",
        ),
    ]
