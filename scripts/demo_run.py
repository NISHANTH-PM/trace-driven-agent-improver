"""Demo run script for labeled neatlogs traces and .docx outputs."""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.observability import initialize_neatlogs, shutdown_neatlogs, trace_span
from app.pack.benchmark import pack_cases_for_split
from app.pack.evaluator import run_pack_benchmark
from app.pack.student import PackConfig
from app.pack.tools import default_source, truth_source
from app.llm import get_llm


def get_cases():
    """Get snapshot cases."""
    dev_cases = pack_cases_for_split("development")
    # Build a lookup by case_id
    cases = {c.case_id: c for c in dev_cases}
    return cases


def run_scenario(
    label: str,
    case_id: str,
    config: PackConfig,
    cases: dict,
    output_dir: Path,
) -> dict[str, Any]:
    """Run a single scenario and return result dict."""
    case = cases[case_id]
    config.output_dir = str(output_dir / label)
    
    source = default_source()
    truth = truth_source()
    llm = get_llm()
    
    start_time = datetime.now(timezone.utc)
    
    with trace_span(f"demo_{label}", kind="WORKFLOW", attributes={"demo.label": label}):
        summary = run_pack_benchmark([case], config, source=source, llm=llm)
    
    end_time = datetime.now(timezone.utc)
    
    result = summary.results[0]
    
    # Get true values from truth source
    true_company = truth.get_company(case.domain)
    
    # Get sections text
    key_facts_text = ""
    funding_text = ""
    if result.docx_path:
        # We can get sections from the output if available
        pass
    
    return {
        "label": label,
        "case_id": case_id,
        "company": case.company_name,
        "domain": case.domain,
        "config": {
            "retry_tool_errors": config.retry_tool_errors,
            "strict_prompt": config.strict_prompt,
            "verify_facts": config.verify_facts,
            "version": config.version,
        },
        "failure_class": result.failure_class,
        "success": result.success,
        "tool_attempts": result.tool_attempts,
        "llm_calls": summary.llm_calls,
        "prompt_tokens": summary.prompt_tokens,
        "completion_tokens": summary.completion_tokens,
        "cost_usd": round(
            (summary.prompt_tokens * float(os.getenv("LLM_PRICE_IN_PER_M", "0")) +
             summary.completion_tokens * float(os.getenv("LLM_PRICE_OUT_PER_M", "0"))) / 1_000_000,
            6
        ),
        "docx_path": result.docx_path,
        "start_time_utc": start_time.isoformat(),
        "end_time_utc": end_time.isoformat(),
        "issues": result.issues,
        "true_values": {
            "employee_count": true_company.employee_count,
            "founded_year": true_company.founded_year,
            "hq_city": true_company.hq_city,
            "total_funding_usd": true_company.total_funding_usd,
            "last_round": true_company.last_round,
        },
    }


def find_verify_regeneration_case(cases: dict) -> str | None:
    """Find the first case among D01, D03, D04, D06 that triggers regeneration (2 LLM calls)."""
    config = PackConfig(
        version="verify_only",
        output_dir="outputs/demo/verify_regeneration",
        verify_facts=True,
        strict_prompt=False,
        retry_tool_errors=False,
    )
    source = default_source()
    truth = truth_source()
    llm = get_llm()
    
    for case_id in ["D01", "D03", "D04", "D06"]:
        if case_id not in cases:
            continue
        case = cases[case_id]
        
        # Create a fresh LLM for each attempt
        llm = get_llm()
        initial_calls = llm.calls
        
        with trace_span(f"demo_verify_regeneration", kind="WORKFLOW", attributes={"demo.label": "verify_regeneration"}):
            summary = run_pack_benchmark([case], config, source=source, llm=llm)
        
        if summary.llm_calls >= 2:
            return case_id
    
    return None


def write_manifest(results: list[dict], manifest_path: Path):
    """Write the demo manifest markdown file."""
    lines = []
    lines.append("# Demo Run Manifest")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")
    
    for r in results:
        lines.append(f"## {r['label']}")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        lines.append(f"| label | {r['label']} |")
        lines.append(f"| case_id | {r['case_id']} |")
        lines.append(f"| company | {r['company']} |")
        lines.append(f"| domain | {r['domain']} |")
        lines.append(f"| config.retry_tool_errors | {r['config']['retry_tool_errors']} |")
        lines.append(f"| config.strict_prompt | {r['config']['strict_prompt']} |")
        lines.append(f"| config.verify_facts | {r['config']['verify_facts']} |")
        lines.append(f"| config.version | {r['config']['version']} |")
        lines.append(f"| failure_class | {r['failure_class']} |")
        lines.append(f"| success | {r['success']} |")
        lines.append(f"| tool_attempts | {r['tool_attempts']} |")
        lines.append(f"| llm_calls | {r['llm_calls']} |")
        lines.append(f"| prompt_tokens | {r['prompt_tokens']} |")
        lines.append(f"| completion_tokens | {r['completion_tokens']} |")
        lines.append(f"| cost_usd | {r['cost_usd']:.6f} |")
        lines.append(f"| docx_path | {r['docx_path']} |")
        lines.append(f"| start_time_utc | {r['start_time_utc']} |")
        lines.append(f"| end_time_utc | {r['end_time_utc']} |")
        lines.append(f"| issues | {r['issues']} |")
        lines.append("")
        lines.append("**True Values:**")
        lines.append("")
        tv = r.get("true_values", {})
        if tv:
            lines.append(f"- employee_count: {tv.get('employee_count', 'n/a')}")
            lines.append(f"- founded_year: {tv.get('founded_year', 'n/a')}")
            lines.append(f"- hq_city: {tv.get('hq_city', 'n/a')}")
            lines.append(f"- total_funding_usd: {tv.get('total_funding_usd', 'n/a')}")
            lines.append(f"- last_round: {tv.get('last_round', 'n/a')}")
        else:
            lines.append("- (no true values recorded)")
        lines.append("")
        lines.append(f"In neatlogs: search for `demo.label = {r['label']}` (or the span name `demo_{r['label']}`)")
        lines.append("")
    
    # Screenshot checklist
    lines.append("---")
    lines.append("")
    lines.append("## Screenshot Checklist")
    lines.append("")
    lines.append("| Scenario | Screenshot File | Description |")
    lines.append("|----------|-----------------|-------------|")
    lines.append("| a) baseline_wrong_fact | neat_baseline_fail.png | open the llm_draft I/O tab and the benchmark_case attributes |")
    lines.append("| c) candidate_retry_recovery | neat_retry_recovery.png | span tree with two fetch_company spans |")
    lines.append("| d) candidate_success | neat_candidate_success.png | |")
    lines.append("| d) candidate_success | neat_llm_attributes.png | |")
    lines.append("| d) candidate_success | neat_llm_io.png | |")
    lines.append("| e) verify_regeneration | neat_verify_regeneration.png | llm_regenerate nested in verify_facts |")
    lines.append("| a vs d | neat_compare.png | if the dashboard offers a compare view |")
    lines.append("")
    lines.append("**Additional screenshots for CFO/Entire/GitHub:**")
    lines.append("")
    lines.append("| Screenshot File | Description |")
    lines.append("|-----------------|-------------|")
    lines.append("| entire_checkpoints.png | `entire status` output |")
    lines.append("| entire_graph_or_status.png | `entire-graph` output or `entire status` |")
    lines.append("| cfo_scenario_comparison.png | CFO scenario comparison view |")
    lines.append("| cfo_api_price_margin.png | CFO API price/margin view |")
    lines.append("| cfo_pricing_assumptions.png | CFO pricing assumptions view |")
    lines.append("| cfo_economics_cash.png | CFO economics/cash view |")
    lines.append("| agent_output_docx.png | Open both D01 baseline and D01 candidate .docx in Word |")
    lines.append("| ablation_table.png | Ablation table from evidence/ |")
    lines.append("| github_commits.png | GitHub commits page |")
    lines.append("| ci_green.png | CI green check |")
    lines.append("")
    
    # D01 docx paths
    baseline_d01 = None
    candidate_d01 = None
    for r in results:
        if r['case_id'] == 'D01' and r['config']['version'] == 'baseline':
            baseline_d01 = r['docx_path']
        if r['case_id'] == 'D01' and r['config']['version'] == 'candidate':
            candidate_d01 = r['docx_path']
    
    if baseline_d01 and candidate_d01:
        lines.append(f"D01 baseline .docx: {baseline_d01}")
        lines.append(f"D01 candidate .docx: {candidate_d01}")
        lines.append("Open both in Word: agent_output_docx.png")
        lines.append("")
    
    with open(manifest_path, "w") as f:
        f.write("\n".join(lines))


def main():
    # Check required env vars
    if os.getenv("PACK_SOURCE") != "snapshot":
        print("ERROR: PACK_SOURCE must be 'snapshot'", file=sys.stderr)
        sys.exit(1)
    if os.getenv("LLM_MODE") != "live":
        print("ERROR: LLM_MODE must be 'live'", file=sys.stderr)
        sys.exit(1)
    
    # Initialize neatlogs
    if not initialize_neatlogs():
        print("WARNING: neatlogs not initialized (no API key)", file=sys.stderr)
    
    try:
        cases = get_cases()
        print(f"Available cases: {list(cases.keys())}")
        
        # Ensure output directory exists
        output_dir = Path("outputs/demo")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results = []
        
        # a) baseline_wrong_fact: baseline on D01
        print("\n=== Running baseline_wrong_fact (D01) ===")
        config = PackConfig(version="baseline", output_dir="outputs/demo/baseline_wrong_fact", retry_tool_errors=False, strict_prompt=False, verify_facts=False)
        r = run_scenario("baseline_wrong_fact", "D01", config, cases, output_dir)
        results.append(r)
        print(f"  failure_class={r['failure_class']}, success={r['success']}, tool_attempts={r['tool_attempts']}, llm_calls={r['llm_calls']}, cost={r['cost_usd']:.6f}")
        
        # b) baseline_tool_error: baseline on D02
        print("\n=== Running baseline_tool_error (D02) ===")
        config = PackConfig(version="baseline", output_dir="outputs/demo/baseline_tool_error", retry_tool_errors=False, strict_prompt=False, verify_facts=False)
        r = run_scenario("baseline_tool_error", "D02", config, cases, output_dir)
        results.append(r)
        print(f"  failure_class={r['failure_class']}, success={r['success']}, tool_attempts={r['tool_attempts']}, llm_calls={r['llm_calls']}, cost={r['cost_usd']:.6f}")
        
        # c) candidate_retry_recovery: candidate on D02
        print("\n=== Running candidate_retry_recovery (D02) ===")
        config = PackConfig(version="candidate", output_dir="outputs/demo/candidate_retry_recovery", retry_tool_errors=True, strict_prompt=True, verify_facts=True)
        r = run_scenario("candidate_retry_recovery", "D02", config, cases, output_dir)
        results.append(r)
        print(f"  failure_class={r['failure_class']}, success={r['success']}, tool_attempts={r['tool_attempts']}, llm_calls={r['llm_calls']}, cost={r['cost_usd']:.6f}")
        
        # d) candidate_success: candidate on D01
        print("\n=== Running candidate_success (D01) ===")
        config = PackConfig(version="candidate", output_dir="outputs/demo/candidate_success", retry_tool_errors=True, strict_prompt=True, verify_facts=True)
        r = run_scenario("candidate_success", "D01", config, cases, output_dir)
        results.append(r)
        print(f"  failure_class={r['failure_class']}, success={r['success']}, tool_attempts={r['tool_attempts']}, llm_calls={r['llm_calls']}, cost={r['cost_usd']:.6f}")
        
        # e) verify_regeneration: verify_only on first of D01, D03, D04, D06 that triggers regeneration
        print("\n=== Finding verify_regeneration case ===")
        regen_case = find_verify_regeneration_case(cases)
        if regen_case:
            print(f"  Found regeneration case: {regen_case}")
            config = PackConfig(version="verify_only", output_dir="outputs/demo/verify_regeneration", verify_facts=True, strict_prompt=False, retry_tool_errors=False)
            r = run_scenario("verify_regeneration", regen_case, config, cases, output_dir)
            results.append(r)
            print(f"  failure_class={r['failure_class']}, success={r['success']}, tool_attempts={r['tool_attempts']}, llm_calls={r['llm_calls']}, cost={r['cost_usd']:.6f}")
        else:
            print("  No case triggered regeneration (no case made 2 LLM calls)")
            results.append({
                "label": "verify_regeneration",
                "case_id": "none",
                "company": "none",
                "domain": "none",
                "config": {"retry_tool_errors": False, "strict_prompt": False, "verify_facts": True, "version": "verify_only"},
                "failure_class": "none",
                "success": False,
                "tool_attempts": 0,
                "llm_calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cost_usd": 0.0,
                "docx_path": None,
                "start_time_utc": datetime.now(timezone.utc).isoformat(),
                "end_time_utc": datetime.now(timezone.utc).isoformat(),
                "issues": [],
                "true_values": {},
            })
        
        # Write manifest
        manifest_path = Path("evidence/demo_manifest.md")
        write_manifest(results, manifest_path)
        print(f"\nManifest written to {manifest_path}")
        
        # Print summary
        print("\n=== SUMMARY ===")
        for r in results:
            print(f"{r['label']}: case={r['case_id']}, company={r['company']}, failure_class={r['failure_class']}, success={r['success']}, tool_attempts={r['tool_attempts']}, llm_calls={r['llm_calls']}, cost_usd={r['cost_usd']:.6f}")
        
    finally:
        shutdown_neatlogs()


if __name__ == "__main__":
    main()