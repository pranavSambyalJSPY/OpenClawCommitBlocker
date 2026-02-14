"""Output formatting for machine and human consumers."""

from __future__ import annotations

import json
from textwrap import shorten

from .signals import Signal


def to_json(repo_path: str, final_score: float, signals: list[Signal]) -> str:
    payload = {
        "repo_path": repo_path,
        "score": round(final_score, 3),
        "signals": [
            {"name": s.name, "score": round(s.score, 3), "evidence": s.evidence}
            for s in signals
        ],
    }
    return json.dumps(payload, indent=2)


def to_table(repo_path: str, final_score: float, signals: list[Signal]) -> str:
    header = f"Commit Blocker scan: {repo_path}\nLikely agent-generated score: {final_score:.3f}\n"
    cols = "| Signal | Score | Evidence |\n|---|---:|---|"
    rows = "\n".join(
        f"| {s.name} | {s.score:.3f} | {shorten(s.evidence, width=60, placeholder='…')} |"
        for s in signals
    )
    return f"{header}\n{cols}\n{rows}" if rows else f"{header}\n{cols}"
