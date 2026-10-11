from types import SimpleNamespace

from app.benchmark import cases_for_split
from app.evaluator import evaluate_case, run_benchmark
from app.models import TraceEvent
from app.student import StudentConfig, run_student


def test_invalid_output_is_classified_and_counted():
    case = cases_for_split("development")[0]
    invalid_output = SimpleNamespace(
        case_id=case.case_id,
        selected_action="not_a_supported_action",
        verified=False,
        rationale="invalid action",
    )

    result = evaluate_case(case, invalid_output, [])

    assert not result.success
    assert result.failure_class == "invalid_output"


def test_missing_output_is_classified_instead_of_crashing():
    case = cases_for_split("development")[0]

    result = evaluate_case(case, None, [])

    assert not result.success
    assert result.failure_class == "invalid_output"


def test_tool_execution_error_takes_precedence_over_output_mismatch():
    case = cases_for_split("development")[0]
    output, trace = run_student(case, StudentConfig(version="test"))
    trace.append(
        TraceEvent(
            event_id="tool-error-event",
            run_id="test-run",
            case_id=case.case_id,
            step="tool_execution",
            detail="Simulated tool failure",
            outcome="error",
        )
    )

    result = evaluate_case(case, output, trace)

    assert not result.success
    assert result.failure_class == "tool_error"


def test_benchmark_summary_counts_critical_failure_classes():
    case = cases_for_split("development")[0]
    output, trace = run_student(case, StudentConfig(version="test"))
    trace.append(
        TraceEvent(
            event_id="tool-error-event",
            run_id="test-run",
            case_id=case.case_id,
            step="tool_execution",
            detail="Simulated tool failure",
            outcome="error",
        )
    )
    from app.evaluator import summarize

    result = evaluate_case(case, output, trace)
    summary = summarize("test", "development", [result])

    assert summary.failure_counts == {"tool_error": 1}
    assert summary.successes == 0


def test_normal_benchmark_keeps_existing_behavior():
    summary = run_benchmark(
        cases_for_split("development"), StudentConfig(version="baseline")
    )

    assert summary.total == 10
    assert summary.successes == 6
    assert summary.failure_counts.get("wrong_tool", 0) > 0
    assert summary.failure_counts.get("missing_verification", 0) > 0
