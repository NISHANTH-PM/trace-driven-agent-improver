from collections import Counter
from dataclasses import dataclass

from app.models import FailureClass, ImprovementProposal, TraceEvent
from app.observability import trace_span
from app.pack.models import CompanyCase, PackOutput, REQUIRED_SECTIONS
from app.pack.tools import FixtureSource, default_source, truth_source
from app.pack.tools import SnapshotSource
from app.pack.checks import fact_mismatches, missing_sections
from app.pack.student import run_pack_student, PackConfig
from app.llm import FakeLLMClient, LLMClient, get_llm


@dataclass
class PackCaseResult:
    case_id: str
    split: str
    success: bool
    failure_class: FailureClass
    issues: list[str]
    tool_attempts: int
    docx_path: str | None
    trace: list[TraceEvent]


@dataclass
class PackSummary:
    version: str
    split: str
    total: int
    successes: int
    success_rate: float
    failure_counts: dict[str, int]
    llm_calls: int
    prompt_tokens: int
    completion_tokens: int
    retries: int
    results: list[PackCaseResult]


def evaluate_pack_case(
    case: CompanyCase,
    output: PackOutput,
    trace: list[TraceEvent],
    truth: FixtureSource | SnapshotSource,
) -> PackCaseResult:
    """Evaluate a single pack case output against ground truth."""
    # Tool failures take precedence
    has_tool_error = any(
        getattr(event, "step", None) == "tool_execution"
        and getattr(event, "outcome", None) == "error"
        for event in trace
    )

    if has_tool_error:
        failure_class: FailureClass = "tool_error"
        issues = ["tool failed"]
    else:
        # Check for llm_parse error or missing docx -> invalid_output
        has_llm_parse_error = any(
            getattr(event, "step", None) == "llm_parse"
            and getattr(event, "outcome", None) == "error"
            for event in trace
        )
        if has_llm_parse_error or output.docx_path is None:
            failure_class = "invalid_output"
            issues = ["invalid llm output" if has_llm_parse_error else "no docx generated"]
        else:
            # Check missing sections
            missing = missing_sections(output.sections)
            if missing:
                failure_class = "missing_section"
                issues = missing
            else:
                # Check fact mismatches
                truth_company = truth.get_company(case.domain)
                fact_issues = fact_mismatches(truth_company, output.sections)
                if fact_issues:
                    failure_class = "wrong_fact"
                    issues = fact_issues
                else:
                    failure_class = "none"
                    issues = []

    success = failure_class == "none"

    return PackCaseResult(
        case_id=case.case_id,
        split=case.split,
        success=success,
        failure_class=failure_class,
        issues=issues,
        tool_attempts=output.tool_attempts,
        docx_path=output.docx_path,
        trace=trace,
    )


def run_pack_benchmark(
    cases: list[CompanyCase],
    config: PackConfig,
    source: FixtureSource | SnapshotSource | None = None,
    llm: FakeLLMClient | LLMClient | None = None,
) -> PackSummary:
    """Run pack benchmark over a list of cases."""
    source = source or default_source()
    # Use a plain source for ground truth (never flaky)
    truth = truth_source()
    llm = llm or get_llm()

    # Capture initial token counts
    initial_calls = llm.calls
    initial_prompt = llm.prompt_tokens
    initial_completion = llm.completion_tokens

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
            output, trace = run_pack_student(case, config, source=source, llm=llm)
            result = evaluate_pack_case(case, output, trace, truth)
            span.set_attribute("evaluation.success", result.success)
            span.set_attribute("evaluation.failure_class", result.failure_class)
            results.append(result)

    # Compute token deltas
    llm_calls = llm.calls - initial_calls
    prompt_tokens = llm.prompt_tokens - initial_prompt
    completion_tokens = llm.completion_tokens - initial_completion
    retries = sum(r.tool_attempts - 1 for r in results)

    failure_counts = Counter(r.failure_class for r in results if not r.success)
    total = len(results)
    successes = sum(r.success for r in results)

    return PackSummary(
        version=config.version,
        split=cases[0].split if cases else "empty",
        total=total,
        successes=successes,
        success_rate=round(successes / total, 4) if total else 0.0,
        failure_counts=dict(failure_counts),
        llm_calls=llm_calls,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        retries=retries,
        results=results,
    )