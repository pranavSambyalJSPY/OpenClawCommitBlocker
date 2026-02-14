"""Render and upsert a PR comment for AI-likelihood scoring."""

from __future__ import annotations

import json
import os
import urllib.request

MARKER = "<!-- commit-blocker:pr-ai-assessment -->"


def _request(method: str, url: str, token: str, payload: dict | None = None) -> dict | list:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, method=method, headers=headers, data=data)
    with urllib.request.urlopen(req) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8") or "{}")


def _label(score: float) -> str:
    if score >= 0.7:
        return "high"
    if score >= 0.3:
        return "medium"
    return "low"


def _feedback_status(existing_comment: dict | None) -> str:
    if not existing_comment:
        return "No feedback yet (first assessment)."

    reactions = existing_comment.get("reactions", {})
    positive = int(reactions.get("+1", 0))
    negative = int(reactions.get("-1", 0)) + int(reactions.get("confused", 0))

    if positive == 0 and negative == 0:
        return "No reaction received yet → treated as likely correct classification."
    if negative > 0:
        return (
            f"Negative feedback detected ({negative} signal(s)) → treat this as misclassification and retune thresholds/weights."
        )
    return f"Positive feedback detected ({positive} 👍) → classification appears correct."


def _build_comment(scan: dict, pr_number: int, feedback_status: str) -> str:
    score = float(scan.get("score", 0.0))
    score_100 = float(scan.get("score_100", round(score * 100, 1)))
    band = str(scan.get("risk_band", _label(score)))
    top = sorted(scan.get("signals", []), key=lambda item: float(item.get("contribution", 0.0)), reverse=True)[:3]
    analysis = scan.get("analysis", {})

    top_lines = "\n".join(
        f"- `{item.get('name')}` contribution={item.get('contribution')} evidence={item.get('evidence')}"
        for item in top
    ) or "- No signals were produced."

    return (
        f"{MARKER}\n"
        f"## 🤖 Commit-Blocker AI-likelihood assessment\n"
        f"PR #{pr_number} appears **{band}** likelihood for agent-generated residue.\n\n"
        f"- Score: **{score:.3f}** ({score_100:.1f}/100)\n"
        f"- Risk band: **{band}**\n"
        f"- Decision threshold reference: medium≈0.5 (configurable in `eval/config.json`)\n"
        f"- Model used: **{analysis.get('model_id', 'heuristics-only')}** (available={analysis.get('model_available', False)})\n"
        f"- Blend: heuristic={analysis.get('heuristic_score', score):.3f}, model={analysis.get('model_score', 0.0):.3f}, weight={analysis.get('model_weight', 0.0)}\n\n"
        f"### Top contributing signals\n{top_lines}\n\n"
        f"### Current adjudication state\n{feedback_status}\n\n"
        "### Feedback loop\n"
        "React on this comment:\n"
        "- 👍 = classification correct\n"
        "- 👎 or 😕 = classification wrong (use this to retune params)\n"
    )


def main() -> int:
    scan = json.loads(open(os.environ["SCAN_JSON_PATH"], encoding="utf-8").read())
    event = json.loads(open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8").read())

    token = os.environ["GITHUB_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]
    api = os.getenv("GITHUB_API_URL", "https://api.github.com")
    pr_number = int(event["pull_request"]["number"])

    comments_url = f"{api}/repos/{repo}/issues/{pr_number}/comments"
    comments = _request("GET", comments_url, token)

    existing = None
    for comment in comments:
        if MARKER in str(comment.get("body", "")):
            existing = comment
            break

    body = _build_comment(scan, pr_number, _feedback_status(existing))
    if existing:
        _request("PATCH", f"{api}/repos/{repo}/issues/comments/{existing['id']}", token, {"body": body})
    else:
        _request("POST", comments_url, token, {"body": body})

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
