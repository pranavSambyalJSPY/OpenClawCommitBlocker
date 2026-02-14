# commit-blocker

`commit-blocker` is a minimal Python scaffold for detecting likely agent-generated pull requests based on commit/PR residue signals.

## Purpose

The project provides a starting point for:

- extracting residue-style signals from a repository/PR (`signals.py`),
- combining those signals into a weighted risk score (`scorer.py`), and
- producing output consumable by machines and humans (`report.py`).

## Project layout

- `src/commit_blocker/signals.py`: signal data model and baseline extractors.
- `src/commit_blocker/scorer.py`: weighted score aggregation and weight loading.
- `src/commit_blocker/report.py`: JSON + table rendering.
- `docs/signal-taxonomy.md`: baseline signal taxonomy and extension guidance.
- `config/default_weights.json`: default scoring weights.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
commit-blocker scan .
commit-blocker scan . --format json
```

## CLI

```bash
commit-blocker scan <repo_path> [--format table|json] [--weights-file path/to/weights.json]
```

If `config/default_weights.json` exists in the current working directory, the CLI uses it automatically.

## Sample output

### JSON

```json
{
  "repo_path": ".",
  "score": 0.29,
  "signals": [
    {
      "name": "automation_marker",
      "score": 0.2,
      "evidence": "repo_path_status=existing-path"
    },
    {
      "name": "templated_pr_style",
      "score": 0.35,
      "evidence": "placeholder residue model"
    }
  ]
}
```

### Human-readable table

```text
Commit Blocker scan: .
Likely agent-generated score: 0.290

| Signal | Score | Evidence |
|---|---:|---|
| automation_marker | 0.200 | repo_path_status=existing-path |
| templated_pr_style | 0.350 | placeholder residue model |
```

## Notes

This is intentionally minimal. Replace placeholder heuristics with real commit metadata, PR text parsing, and richer calibration as you evolve detection quality.
