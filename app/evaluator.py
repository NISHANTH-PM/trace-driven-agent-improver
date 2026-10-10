from collections import Counter

from app.models import BenchmarkSummary, CaseResult, FailureClass
from app.observability import trace_span
from app.student import run_student


def evaluate_case(case, output, trace):
    action_ok = output.selected_action == case.expected_action
    verification_ok = (not case.expected_verified) or output.verified
    success = action_ok and verification_ok
    if success:
        failure: FailureClass = "none"
    elif not action_ok:
        failure = "wrong_tool"
    else:
        failure = "missing_verification"
    return CaseResult(
        case_id=case.case_id,
        split=case.split,
        expected_action=case.expected_action,
        selected_action=output.selected_action,
        expected_verified=case.expected_verified,
        verified=output.verified,
        success=success,
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
