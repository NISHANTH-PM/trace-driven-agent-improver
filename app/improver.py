from dataclasses import replace

from app.models import BenchmarkSummary, ImprovementProposal
from app.student import StudentConfig


def propose_improvements(baseline: BenchmarkSummary):
    proposals = []
    failures = baseline.failure_counts
    if failures.get("wrong_tool", 0):
        proposals.append(ImprovementProposal(
            target_failure="wrong_tool",
            change_type="tool_schema",
            description="Enable keyword-backed action validation before executing a selected action.",
            config_key="use_keyword_fallback",
            config_value=True,
        ))
    if failures.get("missing_verification", 0):
        proposals.append(ImprovementProposal(
            target_failure="missing_verification",
            change_type="workflow_gate",
            description="Require a verification step before finalizing the ticket outcome.",
            config_key="require_verification",
            config_value=True,
        ))
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


def should_promote(baseline_dev, candidate_dev, baseline_holdout, candidate_holdout):
    """Promote only when development improves and held-out performance does not regress.

    The held-out split is a guardrail, not an optimization target: equal held-out
    performance is acceptable, but a regression must reject the candidate.
    """
    reasons = []

    if candidate_dev.success_rate <= baseline_dev.success_rate:
        reasons.append("Development success rate did not improve.")

    if candidate_holdout.success_rate < baseline_holdout.success_rate:
        reasons.append("Held-out success rate regressed.")

    if reasons:
        return False, reasons

    return True, [
        "Development success rate improved.",
        "Held-out success rate did not regress.",
    ]
