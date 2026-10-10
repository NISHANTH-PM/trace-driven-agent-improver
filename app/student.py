import uuid
from dataclasses import dataclass, replace
from app.models import AgentOutput, TicketCase, TraceEvent

@dataclass
class StudentConfig:
    use_keyword_fallback: bool = False
    require_verification: bool = False
    version: str = "baseline"

def infer_action(ticket: str) -> str:
    text = ticket.lower()
    if any(w in text for w in ["duplicate", "twice", "same purchase", "charged two"]):
        return "escalate"
    if any(w in text for w in ["refund", "reimbursement", "money back", "returned order"]):
        return "refund_status"
    if any(w in text for w in ["password", "locked out", "log in", "login", "credentials", "account access"]):
        return "reset_password"
    return "escalate"

def run_student(case: TicketCase, config: StudentConfig):
    run_id = str(uuid.uuid4())
    trace = []
    def event(step, detail, outcome="ok", **metadata):
        trace.append(TraceEvent(event_id=str(uuid.uuid4()), run_id=run_id, case_id=case.case_id,
                                step=step, detail=detail, outcome=outcome, metadata=metadata))

    event("task_received", "Synthetic support ticket received", ticket_length=len(case.ticket))
    action = infer_action(case.ticket)
    event("tool_selected", f"Selected action: {action}", selected_action=action)

    if case.seeded_failure == "wrong_tool" and not config.use_keyword_fallback:
        action = next(a for a in ["reset_password", "refund_status", "escalate"] if a != action)
        event("tool_execution", f"Incorrect action simulated: {action}", "error", injected_failure="wrong_tool")
    else:
        event("tool_execution", f"Action tool {action} completed", "ok")

    # Only seeded missing-verification cases fail this check in the baseline.
    verified = not (case.seeded_failure == "missing_verification" and not config.require_verification)
    if verified:
        event("verification", "Action checked against required output and ticket cues", "ok")
    else:
        event("verification", "Verification gate skipped", "warning", injected_failure="missing_verification")

    event("finalize", "Structured result assembled" if verified else "Returned without required verification",
          "ok" if verified else "error")
    output = AgentOutput(case_id=case.case_id, selected_action=action, verified=verified,
                         rationale=f"Selected {action}; version={config.version}.")
    return output, trace
