from typing import Literal

from pydantic import BaseModel, Field

FailureClass = Literal["wrong_tool", "missing_verification", "invalid_output", "tool_error", "wrong_fact", "missing_section", "none"]


class TicketCase(BaseModel):
    case_id: str
    ticket: str
    expected_action: Literal["reset_password", "refund_status", "escalate"]
    expected_verified: bool = False
    split: Literal["development", "held_out"] = "development"


class AgentOutput(BaseModel):
    case_id: str
    selected_action: Literal["reset_password", "refund_status", "escalate"]
    verified: bool
    rationale: str


class TraceEvent(BaseModel):
    event_id: str
    run_id: str
    case_id: str
    step: str
    detail: str
    outcome: Literal["ok", "error", "warning"]
    metadata: dict = Field(default_factory=dict)


class CaseResult(BaseModel):
    case_id: str
    split: str
    expected_action: str
    selected_action: str
    expected_verified: bool
    verified: bool
    success: bool
    failure_class: FailureClass
    trace: list[TraceEvent]


class BenchmarkSummary(BaseModel):
    version: str
    split: str
    total: int
    successes: int
    success_rate: float
    failure_counts: dict[str, int]
    average_tool_calls: float
    results: list[CaseResult]


class ImprovementProposal(BaseModel):
    target_failure: FailureClass
    change_type: Literal["prompt_rule", "tool_schema", "workflow_gate"]
    description: str
    config_key: str
    config_value: bool | str
