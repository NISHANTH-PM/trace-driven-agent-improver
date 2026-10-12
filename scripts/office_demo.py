"""Demo script for rendering all three office outputs on real snapshot data."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.observability import initialize_neatlogs, shutdown_neatlogs, trace_span
from app.pack.benchmark import pack_cases_for_split
from app.pack.evaluator import evaluate_pack_case, truth_source
from app.pack.student import PackConfig, run_pack_student, _compute_cost_usd
from app.pack.tools import default_source
from app.llm import get_llm


def main():
    # Check required env vars
    if os.getenv("PACK_SOURCE") != "snapshot":
        print("ERROR: PACK_SOURCE must be 'snapshot'", file=sys.stderr)
        sys.exit(1)
    if os.getenv("LLM_MODE") != "live":
        print("ERROR: LLM_MODE must be 'live'", file=sys.stderr)
        sys.exit(1)

    # Print model name
    model_name = os.getenv("MODEL_NAME", "unknown")
    print(f"Model: {model_name}")

    # Initialize neatlogs
    if not initialize_neatlogs():
        print("WARNING: neatlogs not initialized (no API key)", file=sys.stderr)

    try:
        # Get all cases (dev + held-out)
        dev_cases = pack_cases_for_split("development")
        held_cases = pack_cases_for_split("held_out")
        all_cases = dev_cases + held_cases

        print(f"Running office demo on {len(all_cases)} cases ({len(dev_cases)} dev, {len(held_cases)} held-out)")

        # Shared LLM
        llm = get_llm()

        # Candidate config with all three outputs
        candidate_config = PackConfig(
            version="candidate",
            output_dir="outputs/office",
            retry_tool_errors=True,
            strict_prompt=True,
            verify_facts=True,
            outputs=("docx", "pptx", "xlsx"),
        )

        results = []
        total_llm_calls = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_cost_usd = 0.0
        artifact_passes = 0
        evaluator_passes = 0

        for case in all_cases:
            print(f"\nProcessing {case.case_id} ({case.company_name})...")

            # Record token/call counters before
            calls_before = llm.calls
            prompt_before = llm.prompt_tokens
            completion_before = llm.completion_tokens

            with trace_span(f"office_{case.case_id}", kind="WORKFLOW", attributes={"demo.label": f"office_{case.case_id}"}):
                source = default_source()
                truth = truth_source()

                # Run the pack student directly to get output with sections
                output, trace = run_pack_student(case, candidate_config, source=source, llm=llm)

                # Evaluate using the output sections
                eval_result = evaluate_pack_case(case, output, trace, truth)

                # Record deltas
                calls_after = llm.calls
                prompt_after = llm.prompt_tokens
                completion_after = llm.completion_tokens

                case_llm_calls = calls_after - calls_before
                case_prompt_tokens = prompt_after - prompt_before
                case_completion_tokens = completion_after - completion_before
                case_cost_usd = _compute_cost_usd(case_prompt_tokens, case_completion_tokens)

                total_llm_calls += case_llm_calls
                total_prompt_tokens += case_prompt_tokens
                total_completion_tokens += case_completion_tokens
                total_cost_usd += case_cost_usd

                artifact_pass = len(eval_result.issues) == 0 and output.docx_path is not None
                evaluator_pass = eval_result.success

                if artifact_pass:
                    artifact_passes += 1
                if evaluator_pass:
                    evaluator_passes += 1

                # Record result
                case_result = {
                    "case_id": case.case_id,
                    "company": case.company_name,
                    "docx": Path(output.docx_path).as_posix() if output.docx_path else None,
                    "pptx": Path(output.office_paths.get("pptx", "")).as_posix() if output.office_paths.get("pptx") else None,
                    "xlsx": Path(output.office_paths.get("xlsx", "")).as_posix() if output.office_paths.get("xlsx") else None,
                    "artifact_check_pass": artifact_pass,
                    "evaluator_pass": evaluator_pass,
                    "tool_attempts": output.tool_attempts,
                    "llm_calls": case_llm_calls,
                    "prompt_tokens": case_prompt_tokens,
                    "completion_tokens": case_completion_tokens,
                    "cost_usd": round(case_cost_usd, 6),
                    "failure_class": eval_result.failure_class,
                    "issues": eval_result.issues,
                }
                results.append(case_result)

                print(f"  {case.case_id}: artifact={'PASS' if artifact_pass else 'FAIL'}, eval={'PASS' if evaluator_pass else 'FAIL'}, cost=${case_cost_usd:.6f}, calls={case_llm_calls}")

        # Write evidence JSON
        os.makedirs("evidence", exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        evidence_path = f"evidence/office_outputs_{timestamp}.json"
        with open(evidence_path, "w") as f:
            json.dump({
                "timestamp": timestamp,
                "config": "candidate",
                "outputs": ["docx", "pptx", "xlsx"],
                "total_cases": len(all_cases),
                "artifact_passes": artifact_passes,
                "evaluator_passes": evaluator_passes,
                "total_llm_calls": total_llm_calls,
                "total_prompt_tokens": total_prompt_tokens,
                "total_completion_tokens": total_completion_tokens,
                "total_cost_usd": round(total_cost_usd, 6),
                "cost_per_case_usd": round(total_cost_usd / len(all_cases), 6),
                "results": results,
            }, f, indent=2, default=str)
        print(f"\nEvidence written to {evidence_path}")

        # Write markdown table
        md_path = f"evidence/office_outputs_{timestamp}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Office Outputs Demo Results\n\n")
            f.write(f"Generated: {timestamp}\n")
            f.write(f"Config: candidate (retry + strict + verify)\n")
            f.write(f"Outputs: docx, pptx, xlsx\n")
            f.write(f"Model: {model_name}\n\n")

            f.write("## Per-Case Results\n\n")
            f.write("| Case | Company | Docx | Pptx | Xlsx | Artifact Check | Evaluator Pass | LLM Calls | Cost (USD) |\n")
            f.write("|------|---------|------|------|------|----------------|----------------|-----------|------------|\n")
            for r in results:
                docx_ok = "Yes" if r["docx"] else "No"
                pptx_ok = "Yes" if r["pptx"] else "No"
                xlsx_ok = "Yes" if r["xlsx"] else "No"
                artifact = "PASS" if r["artifact_check_pass"] else "FAIL"
                evaluator = "PASS" if r["evaluator_pass"] else "FAIL"
                f.write(f"| {r['case_id']} | {r['company']} | {docx_ok} | {pptx_ok} | {xlsx_ok} | {artifact} | {evaluator} | {r['llm_calls']} | {r['cost_usd']:.6f} |\n")

            f.write("\n## Totals\n\n")
            f.write(f"- Total cases: {len(results)}\n")
            f.write(f"- Artifact checks passed: {artifact_passes}/{len(results)}\n")
            f.write(f"- Evaluator passed: {evaluator_passes}/{len(results)}\n")
            f.write(f"- Total LLM calls: {total_llm_calls}\n")
            f.write(f"- Total prompt tokens: {total_prompt_tokens}\n")
            f.write(f"- Total completion tokens: {total_completion_tokens}\n")
            f.write(f"- Total cost: ${total_cost_usd:.6f}\n")
            f.write(f"- Cost per case: ${total_cost_usd / len(results):.6f}\n")

        print(f"Markdown written to {md_path}")
        print("\n=== SUMMARY ===")
        print(f"Total cases: {len(results)}")
        print(f"Artifact checks passed: {artifact_passes}/{len(results)}")
        print(f"Evaluator passed: {evaluator_passes}/{len(results)}")
        print(f"Total LLM calls: {total_llm_calls}")
        print(f"Total prompt tokens: {total_prompt_tokens}")
        print(f"Total completion tokens: {total_completion_tokens}")
        print(f"Total cost: ${total_cost_usd:.6f}")
        print(f"Cost per case: ${total_cost_usd / len(results):.6f}")

    finally:
        shutdown_neatlogs()


if __name__ == "__main__":
    main()