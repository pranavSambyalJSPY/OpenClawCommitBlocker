"""Output formatting for machine and human consumers."""

from __future__ import annotations

import json
from textwrap import shorten

from .signals import Signal


def _contributions(signals: list[Signal], weights: dict[str, float]) -> list[dict[str, float | str]]:
    rows = []
    for s in signals:
        w = weights.get(s.name, 0.0)
        rows.append(
            {
                "name": s.name,
                "signal_score": round(s.score, 3),
                "weight": round(w, 3),
                "contribution": round(s.score * w, 3),
                "evidence": s.evidence,
            }
        )
    return sorted(rows, key=lambda r: float(r["contribution"]), reverse=True)


def to_json(
    repo_path: str,
    final_score: float,
    band: str,
    signals: list[Signal],
    weights: dict[str, float],
    analysis: dict[str, object] | None = None,
) -> str:
    payload = {
        "repo_path": repo_path,
        "score": round(final_score, 3),
        "score_100": round(final_score * 100, 1),
        "risk_band": band,
        "signals": _contributions(signals, weights),
    }
    if analysis:
        payload["analysis"] = analysis
    return json.dumps(payload, indent=2)


def to_table(
    repo_path: str,
    final_score: float,
    band: str,
    signals: list[Signal],
    weights: dict[str, float],
    analysis: dict[str, object] | None = None,
) -> str:
    header = (
        f"Commit Blocker scan: {repo_path}\n"
        f"Likely agent-generated score: {final_score:.3f} ({final_score*100:.1f}/100, {band})\n"
    )
    if analysis:
        header += (
            f"Model blend: heuristic={analysis.get('heuristic_score', 0.0):.3f}, "
            f"model={analysis.get('model_score', 0.0):.3f}, "
            f"final={analysis.get('final_score', final_score):.3f}, "
            f"model_available={analysis.get('model_available', False)}\n"
        )
    cols = "| Signal | Score | Weight | Contribution | Evidence |\n|---|---:|---:|---:|---|"
    rows = "\n".join(
        f"| {r['name']} | {r['signal_score']:.3f} | {r['weight']:.3f} | {r['contribution']:.3f} | {shorten(str(r['evidence']), width=58, placeholder='…')} |"
        for r in _contributions(signals, weights)
    )
    return f"{header}\n{cols}\n{rows}" if rows else f"{header}\n{cols}"
