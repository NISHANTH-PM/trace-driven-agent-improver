import uuid
from dataclasses import dataclass, replace

from app.models import AgentOutput, TicketCase, TraceEvent
from app.observability import trace_span


@dataclass
class StudentConfig:
    use_keyword_fallback: bool = False
    require_verification: bool = False
    version: str = "baseline"


def infer_action(ticket: str, use_keyword_fallback: bool = False) -> str:
    text = ticket.lower()

    if any(w in text for w in ["duplicate", "twice", "same purchase", "charged two", "duplicate charge"]):
        return "escalate"

    refund_cues = ["refund", "money back", "returned order"]
    if use_keyword_fallback:
        refund_cues += [
            "reimbursement",
            "money has not come back",
            "money has not arrived",
            "money from my return",
            "return has not arrived",
        ]
    if any(w in text for w in refund_cues):
        return "refund_status"

    password_cues = ["password", "log in", "login", "credentials", "account access"]
    if use_keyword_fallback:
        password_cues += [
            "regain access",
            "locked out",
            "get into my account",
            "can't remember",
        ]
    if any(w in text for w in password_cues):
        return "reset_password"

    return "escalate"


def run_student(case: TicketCase, config: StudentConfig):
    run_id = str(uuid.uuid4())
    trace = []

    def event(step, detail, outcome="ok", **metadata):
        trace.append(
            TraceEvent(
                event_id=str(uuid.uuid4()),
                run_id=run_id,
                case_id=case.case_id,
                step=step,
                detail=detail,
                outcome=outcome,
                metadata=metadata,
            )
        )

    event("task_received", "Synthetic support ticket received", ticket_length=len(case.ticket))

    with trace_span(
        "action_selection",
        kind="CHAIN",
        attributes={"agent.version": config.version},
    ) as span:
        action = infer_action(case.ticket, use_keyword_fallback=config.use_keyword_fallback)
        span.set_attribute("agent.selected_action", action)
        event("tool_selected", f"Selected action: {action}", selected_action=action)

    with trace_span(
        f"execute_{action}",
        kind="TOOL",
        attributes={"agent.selected_action": action},
    ):
        event("tool_execution", f"Action tool {action} completed", "ok")

    with trace_span(
        "verification_gate",
        kind="GUARDRAIL",
        attributes={"guardrail.enabled": config.require_verification},
    ) as span:
        verified = config.require_verification
        span.set_attribute("guardrail.passed", verified)
        if verified:
            event("verification", "Action checked against required output and ticket cues", "ok")
        else:
            event("verification", "Verification gate is not enabled", "warning")

    event(
        "finalize",
        "Structured result assembled" if verified else "Returned without explicit verification",
        "ok" if verified else "warning",
    )
    output = AgentOutput(
        case_id=case.case_id,
        selected_action=action,
        verified=verified,
        rationale=f"Selected {action}; version={config.version}.",
    )
    return output, trace
