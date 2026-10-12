"""Demo script for rendering all three office outputs on real snapshot data."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.observability import initialize_neatlogs, shutdown_neatlogs, trace_span
from app.pack.benchmark import pack_cases_for_split
from app.pack.evaluator import evaluate_pack_case, truth_source
from app.pack.student import PackConfig, run_pack_student
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
        total_cost = 0.0
        artifact_passes = 0
        evaluator_passes = 0

        for case in all_cases:
            print(f"\nProcessing {case.case_id} ({case.company_name})...")

            with trace_span(f"office_{case.case_id}", kind="WORKFLOW", attributes={"demo.label": f"office_{case.case_id}"}):
                source = default_source()
                truth = truth_source()

                # Run the pack student directly to get output with sections
                output, trace = run_pack_student(case, candidate_config, source=source, llm=llm)

                # Evaluate using the output sections
                eval_result = evaluate_pack_case(case, output, trace, truth)

                # Collect metrics from trace
                cost = 0.0
                prompt_tokens = 0
                completion_tokens = 0
                llm_calls = 0
                for event in trace:
                    if event.step in ("llm_draft", "llm_regenerate"):
                        # Extract token info from metadata
                        meta = event.metadata or {}
                        prompt_tokens = meta.get("prompt_tokens", 0)
                        completion_tokens = meta.get("completion_tokens", 0)
                        if prompt_tokens or completion_tokens:
                            price_in = float(os.getenv("LLM_PRICE_IN_PER_M", "0"))
                            price_out = float(os.getenv("LLM_PRICE_OUT_PER_M", "0"))
                            cost = (prompt_tokens * price_in + completion_tokens * price_out) / 1_000_000
                            break

                total_cost += cost

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
                    "docx": output.docx_path,
                    "pptx": output.office_paths.get("pptx"),
                    "xlsx": output.office_paths.get("xlsx"),
                    "artifact_check_pass": artifact_pass,
                    "evaluator_pass": evaluator_pass,
                    "tool_attempts": output.tool_attempts,
                    "llm_calls": len([e for e in trace if e.step in ("llm_draft", "llm_regenerate")]),
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "cost_usd": round(cost, 6),
                    "failure_class": eval_result.failure_class,
                    "issues": eval_result.issues,
                }
                results.append(case_result)

                print(f"  {case.case_id}: artifact={'PASS' if artifact_pass else 'FAIL'}, eval={'PASS' if evaluator_pass else 'FAIL'}, cost=${cost:.6f}")

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
                "total_cost_usd": round(total_cost, 6),
                "cost_per_case_usd": round(total_cost / len(all_cases), 6),
                "results": results,
            }, f, indent=2, default=str)
        print(f"\nEvidence written to {evidence_path}")

        # Write markdown table
        md_path = f"evidence/office_outputs_{timestamp}.md"
        with open(md_path, "w") as f:
            f.write("# Office Outputs Demo Results\n\n")
            f.write(f"Generated: {timestamp}\n")
            f.write(f"Config: candidate (retry + strict + verify)\n")
            f.write(f"Outputs: docx, pptx, xlsx\n\n")

            f.write("## Per-Case Results\n\n")
            f.write("| Case | Company | Docx | Pptx | Xlsx | Artifact Check | Evaluator Pass | Cost (USD) |\n")
            f.write("|------|---------|------|------|------|----------------|----------------|------------|\n")
            for r in results:
                docx_ok = "Yes" if r["docx"] else "No"
                pptx_ok = "Yes" if r["pptx"] else "No"
                xlsx_ok = "Yes" if r["xlsx"] else "No"
                artifact = "PASS" if r["artifact_check_pass"] else "FAIL"
                evaluator = "PASS" if r["evaluator_pass"] else "FAIL"
                f.write(f"| {r['case_id']} | {r['company']} | {docx_ok} | {pptx_ok} | {xlsx_ok} | {artifact} | {evaluator} | {r['cost_usd']:.6f} |\n")

            f.write("\n## Totals\n\n")
            f.write(f"- Total cases: {len(results)}\n")
            f.write(f"- Artifact checks passed: {artifact_passes}/{len(results)}\n")
            f.write(f"- Evaluator passed: {evaluator_passes}/{len(results)}\n")
            f.write(f"- Total cost: ${total_cost:.6f}\n")
            f.write(f"- Cost per case: ${total_cost / len(results):.6f}\n")

        print(f"Markdown written to {md_path}")
        print("\n=== SUMMARY ===")
        print(f"Total cases: {len(results)}")
        print(f"Artifact checks passed: {artifact_passes}/{len(results)}")
        print(f"Evaluator passed: {evaluator_passes}/{len(results)}")
        print(f"Total cost: ${total_cost:.6f}")
        print(f"Cost per case: ${total_cost / len(results):.6f}")

    finally:
        shutdown_neatlogs()


if __name__ == "__main__":
    main()