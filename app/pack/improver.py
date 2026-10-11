from dataclasses import replace

from app.models import ImprovementProposal, FailureClass
from app.pack.evaluator import PackSummary
from app.pack.student import PackConfig


def propose_pack_improvements(summary: PackSummary) -> list[ImprovementProposal]:
    """Generate improvement proposals from a pack benchmark summary."""
    proposals = []
    failures = summary.failure_counts
    seen_keys = set()

    # tool_error -> retry_tool_errors
    if failures.get("tool_error", 0) > 0:
        proposals.append(
            ImprovementProposal(
                target_failure="tool_error",
                change_type="workflow_gate",
                description="Enable retry for tool errors to handle transient upstream failures.",
                config_key="retry_tool_errors",
                config_value=True,
            )
        )
        seen_keys.add("retry_tool_errors")

    # wrong_fact -> strict_prompt AND verify_facts
    if failures.get("wrong_fact", 0) > 0:
        proposals.append(
            ImprovementProposal(
                target_failure="wrong_fact",
                change_type="prompt_rule",
                description="Use strict prompt that requires exact figures from data.",
                config_key="strict_prompt",
                config_value=True,
            )
        )
        seen_keys.add("strict_prompt")

        proposals.append(
            ImprovementProposal(
                target_failure="wrong_fact",
                change_type="workflow_gate",
                description="Enable fact verification to catch and fix hallucinated figures.",
                config_key="verify_facts",
                config_value=True,
            )
        )
        seen_keys.add("verify_facts")

    # missing_section -> verify_facts
    if failures.get("missing_section", 0) > 0 and "verify_facts" not in seen_keys:
        proposals.append(
            ImprovementProposal(
                target_failure="missing_section",
                change_type="workflow_gate",
                description="Enable fact verification to ensure all required sections are present.",
                config_key="verify_facts",
                config_value=True,
            )
        )
        seen_keys.add("verify_facts")

    # invalid_output alone proposes nothing
    return proposals


def apply_pack_proposals(config: PackConfig, proposals: list[ImprovementProposal]) -> PackConfig:
    """Apply proposals to a config, returning a new candidate config."""
    updated = replace(config)
    for proposal in proposals:
        if proposal.config_key == "retry_tool_errors":
            updated.retry_tool_errors = bool(proposal.config_value)
        elif proposal.config_key == "strict_prompt":
            updated.strict_prompt = bool(proposal.config_value)
        elif proposal.config_key == "verify_facts":
            updated.verify_facts = bool(proposal.config_value)
    updated.version = "candidate"
    return updated


# Reuse should_promote from app.improver
from app.improver import should_promote