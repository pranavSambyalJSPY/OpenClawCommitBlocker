"""Optional lightweight LLM analysis for AI-generated residue scoring."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .signals import _extract_commit_messages, _git_available

DEFAULT_MODEL_ID = "LiquidAI/LFM2.5-1.2B-Instruct"


@dataclass(slots=True)
class ModelAnalysis:
    """Model-based estimate for AI-generated likelihood."""

    available: bool
    score: float
    evidence: str
    model_id: str


def _sample_repo_text(repo: Path, max_files: int = 8, max_chars: int = 7000) -> str:
    snippets: list[str] = []
    total = 0
    for path in repo.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".lock"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            continue
        piece = f"\n# file: {path.relative_to(repo)}\n{text[:800]}\n"
        if total + len(piece) > max_chars:
            break
        snippets.append(piece)
        total += len(piece)
        if len(snippets) >= max_files:
            break
    return "\n".join(snippets)


def _build_prompt(repo: Path, max_commits: int) -> str:
    messages = _extract_commit_messages(repo, max_commits=max_commits)[:20]
    commit_block = "\n".join(f"- {m[:180]}" for m in messages)
    content_block = _sample_repo_text(repo)

    return (
        "You are a strict classifier for whether a pull request/commit history appears AI-generated.\n"
        "Return JSON only with keys: score (0.0-1.0 float), rationale (short string).\n"
        "Higher score means more likely AI-generated residue.\n\n"
        "Signals to consider: templated commit messages, repetitive automation language, low-human-context prose,"
        " and machine-like change organization.\n\n"
        f"Repository: {repo}\n"
        f"Recent commit messages:\n{commit_block or '- none'}\n\n"
        f"Sample repository text:\n{content_block or '(empty)'}\n"
    )


def analyze_with_model(
    repo_path: str | Path,
    max_commits: int = 60,
    model_id: str = DEFAULT_MODEL_ID,
) -> ModelAnalysis:
    """Run optional LLM analysis and produce normalized score.

    This function is fail-open: if dependencies/model loading fail, it returns unavailable.
    """

    repo = Path(repo_path)
    if not repo.exists() or not _git_available(repo):
        return ModelAnalysis(False, 0.0, "repo_unreadable_or_not_git", model_id)

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline  # type: ignore
    except Exception:
        return ModelAnalysis(False, 0.0, "transformers_not_installed", model_id)

    prompt = _build_prompt(repo, max_commits=max_commits)

    try:
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(model_id)
        generator = pipeline("text-generation", model=model, tokenizer=tokenizer)
        result = generator(prompt, max_new_tokens=120, do_sample=False, temperature=0.0)
        text = result[0]["generated_text"]

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return ModelAnalysis(False, 0.0, "model_output_not_json", model_id)

        payload = json.loads(text[start : end + 1])
        score = max(0.0, min(1.0, float(payload.get("score", 0.0))))
        rationale = str(payload.get("rationale", ""))[:220]
        return ModelAnalysis(True, score, rationale or "model_json_without_rationale", model_id)
    except Exception as exc:
        return ModelAnalysis(False, 0.0, f"model_inference_failed:{type(exc).__name__}", model_id)
