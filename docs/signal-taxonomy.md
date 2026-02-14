# Signal taxonomy

This taxonomy defines the baseline residue signal families used by `commit-blocker`.

## Current baseline signals

| Signal key | Family | What it captures | Current extractor |
|---|---|---|---|
| `automation_marker` | Repository residue | Markers suggesting generated/automated workflow artifacts in commit or repository context | placeholder baseline in `extract_signals` |
| `templated_pr_style` | PR residue | Repetitive/template-like phrasing common in generated PR descriptions | placeholder baseline in `extract_signals` |

## Scoring model

- Signals emit normalized per-signal scores in `[0.0, 1.0]`.
- Global risk score is a weighted average using `config/default_weights.json`.
- Unknown signal names default to zero weight unless overridden by an explicit config.

## Extension guidance

When extending detection quality, add signals by:

1. Defining signal metadata and extraction logic in `signals.py`.
2. Assigning/adjusting weights in `config/default_weights.json`.
3. Updating sample outputs and docs so clients can track payload stability.
