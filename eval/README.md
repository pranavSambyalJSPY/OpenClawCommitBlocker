# Evaluation workflow

This directory contains a reproducible evaluation workflow for labeled commit/PR examples.

## 1) Prepare labeled data

Create a JSONL file where each line has:

- `id`: unique identifier
- `subject_type`: `commit` or `pr`
- `repo_path`: local path to a git repository sample
- `repo_type`: grouping label for FPR analysis (for example `application`, `library`, `infra`)
- `agent_generated`: `true` or `false`
- `max_commits` (optional): commit history depth used for detection

Use `eval/examples.template.jsonl` as a schema template.

## 2) Run evaluation

```bash
commit-blocker eval eval/examples.jsonl --config eval/config.json --output eval/report.json --use-model --model-id LiquidAI/LFM2.5-1.2B-Instruct --model-weight 0.3
```

The command runs the detector for every example, then computes:

- precision
- recall
- F1
- false-positive rate (overall and by `repo_type`)
- confusion matrix at the configured threshold
- threshold sweep report (metrics and confusion matrix for each threshold)

The report is written to `eval/report.json`.
Model-assisted evaluation blends heuristic score with the LiquidAI model output using `model_weight` (default 0.3).


## 3) Regression check

Regression safety is configured in `eval/config.json`:

- `regression.baseline_precision`
- `regression.precision_degradation_budget`

Evaluation fails if:

`observed_precision < baseline_precision - precision_degradation_budget`

This prevents rule updates from degrading precision beyond the configured budget.

## 4) Launch gate target

`launch_gate` in `eval/config.json` sets launch criteria. Current target:

- **precision >= 0.9 at medium threshold** (`threshold_label: "medium"`)

The eval command returns non-zero if launch gate fails.


## 5) Incorporate PR reaction feedback

When using the PR workflows, treat adjudication reactions as labels:

- no reaction: keep classification as likely correct
- `👍`: confirmed correct
- `👎` or `😕`: likely incorrect, add that PR/repo sample to your labeled dataset and rerun eval

Use this loop to adjust threshold/weights while preserving the precision regression budget.
