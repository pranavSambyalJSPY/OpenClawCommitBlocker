"""Handle reaction feedback for commit-blocker assessment comments."""

from __future__ import annotations

import json
import os
import urllib.request

ASSESSMENT_MARKER = "<!-- commit-blocker:pr-ai-assessment -->"
FEEDBACK_MARKER = "<!-- commit-blocker:reaction-feedback -->"


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


def main() -> int:
    event = json.loads(open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8").read())
    reaction = str(event.get("reaction", {}).get("content", ""))
    comment = event.get("comment", {})

    if ASSESSMENT_MARKER not in str(comment.get("body", "")):
        return 0

    issue = event.get("issue", {})
    repo = os.environ["GITHUB_REPOSITORY"]
    api = os.getenv("GITHUB_API_URL", "https://api.github.com")
    token = os.environ["GITHUB_TOKEN"]
    issue_number = int(issue["number"])

    if reaction in {"-1", "confused"}:
        verdict = "misclassified"
        guidance = (
            "Negative adjudication received. Please add this PR example to `eval/examples.jsonl` and rerun "
            "`commit-blocker eval ...` to retune threshold/weights."
        )
    elif reaction == "+1":
        verdict = "correct"
        guidance = "Positive adjudication received. Current classification appears correct."
    else:
        verdict = "neutral"
        guidance = "Reaction recorded (neutral)."

    body = (
        f"{FEEDBACK_MARKER}\n"
        f"Reaction feedback captured: **{reaction}** → **{verdict}**.\n\n"
        f"{guidance}"
    )

    comments_url = f"{api}/repos/{repo}/issues/{issue_number}/comments"
    comments = _request("GET", comments_url, token)
    existing = None
    for item in comments:
        if FEEDBACK_MARKER in str(item.get("body", "")):
            existing = item
            break

    if existing:
        _request("PATCH", f"{api}/repos/{repo}/issues/comments/{existing['id']}", token, {"body": body})
    else:
        _request("POST", comments_url, token, {"body": body})

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
