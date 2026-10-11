"""Pack student agent with retry, verification, and DOCX rendering."""

import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from docx import Document

from app.models import TraceEvent
from app.observability import trace_span
from app.llm import FakeLLMClient, LLMClient, get_llm
from app.pack.models import CompanyCase, PackOutput, REQUIRED_SECTIONS
from app.pack.tools import FixtureSource, FlakySource, ToolError, default_source
from app.pack.checks import fact_mismatches, missing_sections


BASE_SYSTEM_PROMPT = (
    "You write one-page company briefings for busy executives. "
    "Return ONLY JSON: {\"sections\": {\"Overview\": str, \"Key Facts\": str, \"Funding\": str, \"Risks\": str}}. "
    "Keep it concise and readable; prefer rounded, reader-friendly figures "
    "(for example 'about 2,000 employees', 'roughly $40M')."
)

STRICT_SYSTEM_PROMPT = (
    "You write one-page company briefings for busy executives. "
    "Return ONLY JSON: {\"sections\": {\"Overview\": str, \"Key Facts\": str, \"Funding\": str, \"Risks\": str}}. "
    "State every figure exactly as given in the data (employee count, founding year, "
    "headquarters city, total funding in USD, last funding round). Never round or estimate."
)


def _compute_cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
    """Compute cost in USD from token counts and env price config."""
    price_in = float(os.getenv("LLM_PRICE_IN_PER_M", "0"))
    price_out = float(os.getenv("LLM_PRICE_OUT_PER_M", "0"))
    return (prompt_tokens * price_in + completion_tokens * price_out) / 1_000_000


def _set_llm_attrs(span, prompt_tokens: int, completion_tokens: int,
                    system: str, user: str, response: str, model_name: str, cost_usd: float) -> None:
    """Set all SDK-recognized LLM span attributes + existing custom ones."""
    total = prompt_tokens + completion_tokens
    # SDK-recognized keys
    span.set_attribute("llm.model_name", model_name)
    span.set_attribute("llm.provider", "litellm")
    span.set_attribute("llm.system", "litellm")
    span.set_attribute("llm.token_count.prompt", prompt_tokens)
    span.set_attribute("llm.token_count.completion", completion_tokens)
    span.set_attribute("llm.token_count.total", total)
    span.set_attribute("gen_ai.usage.input_tokens", prompt_tokens)
    span.set_attribute("gen_ai.usage.output_tokens", completion_tokens)
    span.set_attribute("gen_ai.request.model", model_name)
    span.set_attribute("llm.cost_usd", cost_usd)
    # Generic IO (truncated to 2000 chars)
    input_text = f"{system}\n\n{user}"
    span.set_attribute("input.value", input_text[:2000])
    span.set_attribute("output.value", response[:2000])
    # Existing custom attrs (keep for backward compat)
    span.set_attribute("llm.prompt_tokens", prompt_tokens)
    span.set_attribute("llm.completion_tokens", completion_tokens)


def _extract_json(text: str) -> dict | None:
    """Extract JSON from text, handling ```json fences."""
    text = text.strip()
    if text.startswith("```"):
        # Remove code fences
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


@dataclass
class PackConfig:
    """Configuration for the pack student agent."""
    verify_facts: bool = False
    retry_tool_errors: bool = False
    strict_prompt: bool = False
    max_attempts: int = 3
    version: str = "baseline"
    output_dir: str = "outputs"


def run_pack_student(
    case: CompanyCase,
    config: PackConfig,
    source: FixtureSource | FlakySource | None = None,
    llm: FakeLLMClient | LLMClient | None = None,
) -> tuple[PackOutput, list[TraceEvent]]:
    """Run the pack student agent for a single case."""
    source = source or default_source()
    llm = llm or get_llm()

    run_id = str(uuid.uuid4())
    trace: list[TraceEvent] = []

    def event(step: str, detail: str, outcome: str = "ok", **metadata: Any) -> None:
        trace.append(
            TraceEvent(
                event_id=str(uuid.uuid4()),
                run_id=run_id,
                case_id=case.case_id,
                step=step,
                detail=detail,
                outcome=outcome,  # type: ignore
                metadata=metadata,
            )
        )

    # Track token usage before each LLM call
    def get_token_deltas() -> tuple[int, int]:
        """Get token usage deltas since last call."""
        prompt_before = llm.prompt_tokens
        completion_before = llm.completion_tokens
        return prompt_before, completion_before

    # Step a) Fetch company data
    max_attempts = config.max_attempts if config.retry_tool_errors else 1
    company: Any = None
    tool_attempts = 0

    for attempt in range(1, max_attempts + 1):
        tool_attempts = attempt
        with trace_span(
            "fetch_company",
            kind="TOOL",
            attributes={"tool.attempt": attempt, "pack.company": case.company_name},
        ):
            try:
                company = source.get_company(case.domain, attempt)
                event("tool_execution", f"Fetched company data on attempt {attempt}", "ok")
                break
            except ToolError as e:
                if attempt < max_attempts:
                    event("tool_retry", f"Tool error on attempt {attempt}: {e}", "warning", attempt=attempt)
                else:
                    event("tool_execution", f"Tool failed after {attempt} attempts: {e}", "error", attempt=attempt)
                    return (
                        PackOutput(
                            case_id=case.case_id,
                            docx_path=None,
                            sections={},
                            claimed_facts={},
                            verified=False,
                            tool_attempts=tool_attempts,
                            rationale="tool failed",
                        ),
                        trace,
                    )

    # Step b) Draft
    system_prompt = STRICT_SYSTEM_PROMPT if config.strict_prompt else BASE_SYSTEM_PROMPT
    user_message = company.model_dump_json()

    prompt_before, completion_before = get_token_deltas()

    with trace_span(
        "llm_draft",
        kind="LLM",
        attributes={"pack.company": case.company_name},
    ) as span:
        try:
            response = llm.complete(system_prompt, user_message, json_mode=True)
        except Exception as e:
            event("llm_draft", f"LLM call failed: {e}", "error")
            return (
                PackOutput(
                    case_id=case.case_id,
                    docx_path=None,
                    sections={},
                    claimed_facts={},
                    verified=False,
                    tool_attempts=tool_attempts,
                    rationale="llm call failed",
                ),
                trace,
            )

        prompt_after = llm.prompt_tokens
        completion_after = llm.completion_tokens
        prompt_delta = prompt_after - prompt_before
        completion_delta = completion_after - completion_before
        cost = _compute_cost_usd(prompt_delta, completion_delta)

        model_name = os.getenv("MODEL_NAME", "unknown")
        _set_llm_attrs(span, prompt_delta, completion_delta, system_prompt, user_message, response, model_name, cost)

        data = _extract_json(response)
        if not data or "sections" not in data or not isinstance(data["sections"], dict):
            event("llm_parse", "Invalid LLM output: missing or malformed sections", "error")
            return (
                PackOutput(
                    case_id=case.case_id,
                    docx_path=None,
                    sections={},
                    claimed_facts={},
                    verified=False,
                    tool_attempts=tool_attempts,
                    rationale="invalid llm output",
                ),
                trace,
            )

        sections = data["sections"]

    # Step c) Verify
    verified = False
    issues: list[str] = []

    if config.verify_facts:
        issues = missing_sections(sections) + fact_mismatches(company, sections)

        with trace_span(
            "verify_facts",
            kind="GUARDRAIL",
            attributes={"guardrail.enabled": True, "pack.verify_passed": len(issues) == 0},
        ):
            if issues:
                # One regeneration with strict prompt
                prompt_before2, completion_before2 = get_token_deltas()

                fix_message = (
                    f"{user_message}\n\n"
                    f"Fix these problems in your previous answer: {'; '.join(issues)}"
                )

                with trace_span("llm_regenerate", kind="LLM") as regen_span:
                    response2 = llm.complete(STRICT_SYSTEM_PROMPT, fix_message, json_mode=True)

                    prompt_after2 = llm.prompt_tokens
                    completion_after2 = llm.completion_tokens
                    prompt_delta2 = prompt_after2 - prompt_before2
                    completion_delta2 = completion_after2 - completion_before2
                    cost2 = _compute_cost_usd(prompt_delta2, completion_delta2)

                    model_name = os.getenv("MODEL_NAME", "unknown")
                    _set_llm_attrs(regen_span, prompt_delta2, completion_delta2,
                                  STRICT_SYSTEM_PROMPT, fix_message, response2, model_name, cost2)

                data2 = _extract_json(response2)
                if data2 and "sections" in data2 and isinstance(data2["sections"], dict):
                    sections = data2["sections"]
                    issues = missing_sections(sections) + fact_mismatches(company, sections)

            verified = len(issues) == 0
            event("verification", "Fact verification passed" if verified else f"Fact verification failed: {issues}", "ok" if verified else "warning")
    else:
        verified = False
        with trace_span(
            "verify_facts",
            kind="GUARDRAIL",
            attributes={"guardrail.enabled": False, "pack.verify_passed": False},
        ):
            event("verification", "Verification not enabled", "warning")

    # Step d) Render DOCX
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    docx_path = output_dir / f"{case.case_id}_{config.version}.docx"

    doc = Document()
    doc.add_heading(company.name, level=0)

    for section_name in REQUIRED_SECTIONS:
        doc.add_heading(section_name, level=1)
        content = sections.get(section_name, "")
        if content:
            doc.add_paragraph(content)
        else:
            doc.add_paragraph("[Section not provided]")

    doc.save(docx_path)

    # Step e) Return output
    rationale = f"version={config.version}"
    output = PackOutput(
        case_id=case.case_id,
        docx_path=str(docx_path),
        sections=sections,
        claimed_facts={},  # Could be populated if needed
        verified=verified,
        tool_attempts=tool_attempts,
        rationale=rationale,
    )

    event("finalize", f"Pack output generated at {docx_path}", "ok" if verified else "warning")

    return output, trace