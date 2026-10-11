from collections import Counter

from app.models import BenchmarkSummary, CaseResult, FailureClass
from app.observability import trace_span
from app.student import run_student

_ALLOWED_ACTIONS = {"reset_password", "refund_status", "escalate"}


def _has_tool_error(trace) -> bool:
    """Return whether a recorded tool execution explicitly failed."""
    return any(
        getattr(event, "step", None) == "tool_execution"
        and getattr(event, "outcome", None) == "error"
        for event in trace
    )


def _is_valid_output(case, output) -> bool:
    """Validate the output contract before comparing it with expected behavior."""
    if output is None:
        return False

    selected_action = getattr(output, "selected_action", None)
    verified = getattr(output, "verified", None)
    output_case_id = getattr(output, "case_id", None)
    rationale = getattr(output, "rationale", None)

    return (
        isinstance(selected_action, str)
        and selected_action in _ALLOWED_ACTIONS
        and isinstance(verified, bool)
        and output_case_id == case.case_id
        and isinstance(rationale, str)
        and bool(rationale.strip())
    )


def evaluate_case(case, output, trace):
    # A recorded tool failure means the requested action did not complete,
    # regardless of whether the agent produced a plausible final output.
    if _has_tool_error(trace):
        failure: FailureClass = "tool_error"
    elif not _is_valid_output(case, output):
        failure = "invalid_output"
    else:
        action_ok = output.selected_action == case.expected_action
        verification_ok = (not case.expected_verified) or output.verified
        if action_ok and verification_ok:
            failure = "none"
        elif not action_ok:
            failure = "wrong_tool"
        else:
            failure = "missing_verification"

    selected_action = getattr(output, "selected_action", None)
    if not isinstance(selected_action, str):
        selected_action = repr(selected_action)
    verified = getattr(output, "verified", False)
    if not isinstance(verified, bool):
        verified = False

    return CaseResult(
        case_id=case.case_id,
        split=case.split,
        expected_action=case.expected_action,
        selected_action=selected_action,
        expected_verified=case.expected_verified,
        verified=verified,
        success=failure == "none",
        failure_class=failure,
        trace=trace,
    )


def summarize(version, split, results):
    total = len(results)
    successes = sum(r.success for r in results)
    failures = Counter(r.failure_class for r in results if not r.success)
    tool_calls = [sum(e.step == "tool_execution" for e in r.trace) for r in results]
    return BenchmarkSummary(
        version=version,
        split=split,
        total=total,
        successes=successes,
        success_rate=round(successes / total, 4) if total else 0.0,
        failure_counts=dict(failures),
        average_tool_calls=round(sum(tool_calls) / total, 2) if total else 0,
        results=results,
    )


def run_benchmark(cases, config):
    results = []
    for case in cases:
        with trace_span(
            "benchmark_case",
            kind="WORKFLOW",
            attributes={
                "benchmark.case_id": case.case_id,
                "benchmark.split": case.split,
                "agent.version": config.version,
            },
        ) as span:
            output, trace = run_student(case, config)
            result = evaluate_case(case, output, trace)
            span.set_attribute("evaluation.success", result.success)
            span.set_attribute("evaluation.failure_class", result.failure_class)
            span.set_attribute("evaluation.expected_action", result.expected_action)
            span.set_attribute("evaluation.selected_action", result.selected_action)
            results.append(result)

    return summarize(config.version, cases[0].split if cases else "empty", results)
