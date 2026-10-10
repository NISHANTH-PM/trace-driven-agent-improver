from dataclasses import replace

from app.models import BenchmarkSummary, ImprovementProposal
from app.student import StudentConfig


def propose_improvements(baseline: BenchmarkSummary):
    proposals = []
    failures = baseline.failure_counts

    if failures.get("wrong_tool", 0):
        proposals.append(
            ImprovementProposal(
                target_failure="wrong_tool",
                change_type="prompt_rule",
                description="Expand action-matching cues for paraphrased password and refund requests.",
                config_key="use_keyword_fallback",
                config_value=True,
            )
        )

    if failures.get("missing_verification", 0):
        proposals.append(
            ImprovementProposal(
                target_failure="missing_verification",
                change_type="workflow_gate",
                description="Require an explicit verification step before finalizing cases that need verification.",
                config_key="require_verification",
                config_value=True,
            )
        )

    return proposals


def apply_proposals(config: StudentConfig, proposals):
    updated = replace(config)
    for proposal in proposals:
        if proposal.config_key == "use_keyword_fallback":
            updated.use_keyword_fallback = bool(proposal.config_value)
        elif proposal.config_key == "require_verification":
            updated.require_verification = bool(proposal.config_value)
    updated.version = "candidate"
    return updated


def _validate_heldout_failure_counts(summary) -> tuple[dict[str, int] | None, str | None]:
    """Validate that a held-out summary has a valid failure_counts dict.

    Returns (failure_counts_dict, None) on success.
    Returns (None, reason) on failure where reason explains the validation error.
    """
    fc = getattr(summary, "failure_counts", None)
    if fc is None:
        return None, "Held-out summary missing failure_counts attribute."
    if not isinstance(fc, dict):
        return None, f"Held-out failure_counts is not a dict (got {type(fc).__name__})."

    # Validate that all values are non-negative integers.
    for key, value in fc.items():
        if not isinstance(value, int) or isinstance(value, bool):
            return None, f"Held-out failure_counts['{key}'] must be a non-negative integer (got {type(value).__name__})."
        if value < 0:
            return None, f"Held-out failure_counts['{key}'] must be non-negative (got {value})."

    return fc, None


def should_promote(baseline_dev, candidate_dev, baseline_holdout, candidate_holdout):
    """Promote when development improves, held-out does not regress, and no critical failures increase.

    Critical failure classes are 'invalid_output' and 'tool_error'. These are
    defined in the failure taxonomy (app/models.py) but the current evaluator
    (app/evaluator.py) does not emit them; they are reserved for future LLM-based
    agents where schema violations and tool crashes are safety-relevant.
    """
    reasons = []

    if candidate_dev.success_rate <= baseline_dev.success_rate:
        reasons.append("Development success rate did not improve.")

    if candidate_holdout.success_rate < baseline_holdout.success_rate:
        reasons.append("Held-out success rate regressed.")

    # Validate held-out failure metrics before checking critical failures.
    # Fail closed: missing or malformed failure_counts on either held-out
    # summary causes promotion rejection with a clear reason.
    baseline_fc, base_err = _validate_heldout_failure_counts(baseline_holdout)
    candidate_fc, cand_err = _validate_heldout_failure_counts(candidate_holdout)

    if base_err:
        reasons.append(f"Baseline held-out validation failed: {base_err}")
    if cand_err:
        reasons.append(f"Candidate held-out validation failed: {cand_err}")

    if baseline_fc is not None and candidate_fc is not None:
        critical_classes = {"invalid_output", "tool_error"}
        for fc in critical_classes:
            baseline_count = baseline_fc.get(fc, 0)
            candidate_count = candidate_fc.get(fc, 0)
            if candidate_count > baseline_count:
                reasons.append(
                    f"Held-out critical failure '{fc}' increased ({baseline_count} \u2192 {candidate_count})."
                )

    if reasons:
        return False, reasons

    return True, [
        "Development success rate improved.",
        "Held-out success rate did not regress.",
        "No critical failure regression on held-out.",
    ]