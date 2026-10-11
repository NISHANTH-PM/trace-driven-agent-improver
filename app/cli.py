import argparse
import json
import os
from datetime import datetime
from collections import Counter

from app.observability import initialize_neatlogs, shutdown_neatlogs
from app.service import run_improvement_cycle
from app.pack.service import run_pack_improvement_cycle
from app.pack.benchmark import pack_cases_for_split
from app.pack.evaluator import run_pack_benchmark
from app.pack.student import PackConfig, _compute_cost_usd
from app.llm import get_llm


def run_ticket_task():
    initialize_neatlogs()
    try:
        result = run_improvement_cycle()
        print(
            json.dumps(
                {
                    "baseline": {
                        key: result["baseline"][key]["success_rate"]
                        for key in ["development", "held_out"]
                    },
                    "candidate": {
                        key: result["candidate"][key]["success_rate"]
                        for key in ["development", "held_out"]
                    },
                    "proposals": result["proposals"],
                    "promotion": result["promotion"],
                    "active_version": result["active_version"],
                    "note": result["note"],
                },
                indent=2,
            )
        )
    finally:
        shutdown_neatlogs()


def run_pack_task():
    initialize_neatlogs()
    try:
        result = run_pack_improvement_cycle()

        # Compact summary for stdout
        summary = {
            "baseline": {
                "development": {
                    "success_rate": result["baseline"]["development"]["success_rate"],
                    "successes": f"{result['baseline']['development']['successes']}/{result['baseline']['development']['total']}",
                    "failure_counts": result["baseline"]["development"]["failure_counts"],
                },
                "held_out": {
                    "success_rate": result["baseline"]["held_out"]["success_rate"],
                    "successes": f"{result['baseline']['held_out']['successes']}/{result['baseline']['held_out']['total']}",
                    "failure_counts": result["baseline"]["held_out"]["failure_counts"],
                },
            },
            "candidate": {
                "development": {
                    "success_rate": result["candidate"]["development"]["success_rate"],
                    "successes": f"{result['candidate']['development']['successes']}/{result['candidate']['development']['total']}",
                    "failure_counts": result["candidate"]["development"]["failure_counts"],
                },
                "held_out": {
                    "success_rate": result["candidate"]["held_out"]["success_rate"],
                    "successes": f"{result['candidate']['held_out']['successes']}/{result['candidate']['held_out']['total']}",
                    "failure_counts": result["candidate"]["held_out"]["failure_counts"],
                },
            },
            "proposals": result["proposals"],
            "promotion": result["promotion"],
            "active_version": result["active_version"],
            "cost": result["cost"],
        }
        print(json.dumps(summary, indent=2))

        # Write full result to evidence/
        os.makedirs("evidence", exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        evidence_path = f"evidence/pack_run_{timestamp}.json"
        with open(evidence_path, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nFull result written to {evidence_path}")
    finally:
        shutdown_neatlogs()


def run_pack_ablation_task():
    initialize_neatlogs()
    try:
        llm = get_llm()
        dev_cases = pack_cases_for_split("development")
        held_cases = pack_cases_for_split("held_out")

        configs = {
            "baseline": PackConfig(
                version="baseline",
                output_dir="outputs/ablation/baseline",
                retry_tool_errors=False,
                strict_prompt=False,
                verify_facts=False,
            ),
            "retry_only": PackConfig(
                version="retry_only",
                output_dir="outputs/ablation/retry_only",
                retry_tool_errors=True,
                strict_prompt=False,
                verify_facts=False,
            ),
            "strict_only": PackConfig(
                version="strict_only",
                output_dir="outputs/ablation/strict_only",
                retry_tool_errors=False,
                strict_prompt=True,
                verify_facts=False,
            ),
            "verify_only": PackConfig(
                version="verify_only",
                output_dir="outputs/ablation/verify_only",
                retry_tool_errors=False,
                strict_prompt=False,
                verify_facts=True,
            ),
            "strict_verify": PackConfig(
                version="strict_verify",
                output_dir="outputs/ablation/strict_verify",
                retry_tool_errors=False,
                strict_prompt=True,
                verify_facts=True,
            ),
            "candidate": PackConfig(
                version="candidate",
                output_dir="outputs/ablation/candidate",
                retry_tool_errors=True,
                strict_prompt=True,
                verify_facts=True,
            ),
        }

        results = {}
        for name, config in configs.items():
            # Fresh source for each run
            from app.pack.tools import default_source
            source = default_source()

            bdev = run_pack_benchmark(dev_cases, config, source=source, llm=llm)
            bheld = run_pack_benchmark(held_cases, config, source=source, llm=llm)

            # Merge failure counts
            merged_failures = dict(Counter(bdev.failure_counts) + Counter(bheld.failure_counts))

            total_calls = bdev.llm_calls + bheld.llm_calls
            total_prompt = bdev.prompt_tokens + bheld.prompt_tokens
            total_completion = bdev.completion_tokens + bheld.completion_tokens
            cost_usd = _compute_cost_usd(total_prompt, total_completion)

            results[name] = {
                "dev": {
                    "k": bdev.successes,
                    "n": bdev.total,
                    "success_rate": bdev.success_rate,
                },
                "held_out": {
                    "k": bheld.successes,
                    "n": bheld.total,
                    "success_rate": bheld.success_rate,
                },
                "failure_counts": merged_failures,
                "llm_calls": total_calls,
                "prompt_tokens": total_prompt,
                "completion_tokens": total_completion,
                "cost_usd": cost_usd,
            }

        # Print markdown table
        print("| Config | Dev k/n | Held-out k/n | Failure Counts (dev+held-out) | LLM Calls | Prompt Tokens | Completion Tokens | Cost (USD) |")
        print("|--------|---------|--------------|-------------------------------|-----------|---------------|-------------------|------------|")
        for name in ["baseline", "retry_only", "strict_only", "verify_only", "strict_verify", "candidate"]:
            r = results[name]
            dev_str = f"{r['dev']['k']}/{r['dev']['n']}"
            held_str = f"{r['held_out']['k']}/{r['held_out']['n']}"
            fail_str = str(r["failure_counts"])
            print(f"| {name} | {dev_str} | {held_str} | {fail_str} | {r['llm_calls']} | {r['prompt_tokens']} | {r['completion_tokens']} | {r['cost_usd']:.6f} |")

        # Write evidence JSON
        os.makedirs("evidence", exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        evidence_path = f"evidence/pack_ablation_{timestamp}.json"
        with open(evidence_path, "w") as f:
            json.dump({
                "timestamp": timestamp,
                "results": results,
            }, f, indent=2, default=str)
        print(f"\nFull ablation result written to {evidence_path}")
    finally:
        shutdown_neatlogs()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["ticket", "pack", "pack-ablation"], default="ticket")
    args = parser.parse_args()

    if args.task == "ticket":
        run_ticket_task()
    elif args.task == "pack":
        run_pack_task()
    else:
        run_pack_ablation_task()
