import os
from app.pack.benchmark import pack_cases_for_split
from app.pack.evaluator import run_pack_benchmark
from app.pack.improver import apply_pack_proposals, propose_pack_improvements, should_promote
from app.pack.student import PackConfig, _compute_cost_usd
from app.llm import get_llm


def run_pack_improvement_cycle(llm=None):
    """Run the pack improvement cycle."""
    llm = llm or get_llm()

    pack_source = os.getenv("PACK_SOURCE", "fixtures").lower()
    dev = pack_cases_for_split("development")
    held = pack_cases_for_split("held_out")

    dev_companies = [c.company_name for c in dev]
    held_companies = [c.company_name for c in held]

    baseline_config = PackConfig(version="baseline", output_dir="outputs/baseline")

    # Baseline runs
    bdev = run_pack_benchmark(dev, baseline_config, llm=llm)
    bheld = run_pack_benchmark(held, baseline_config, llm=llm)

    # Proposals from DEV only
    proposals = propose_pack_improvements(bdev)

    # Candidate config
    candidate_config = apply_pack_proposals(baseline_config, proposals)
    candidate_config.output_dir = "outputs/candidate"

    # Candidate runs
    cdev = run_pack_benchmark(dev, candidate_config, llm=llm)
    cheld = run_pack_benchmark(held, candidate_config, llm=llm)

    promoted, reasons = should_promote(bdev, cdev, bheld, cheld)

    def compute_totals(dev_summary, held_summary):
        total_calls = dev_summary.llm_calls + held_summary.llm_calls
        total_prompt = dev_summary.prompt_tokens + held_summary.prompt_tokens
        total_completion = dev_summary.completion_tokens + held_summary.completion_tokens
        cost_usd = _compute_cost_usd(total_prompt, total_completion)
        total_cases = dev_summary.total + held_summary.total
        cost_per_case_usd = cost_usd / total_cases if total_cases else 0.0
        return {
            "llm_calls": total_calls,
            "prompt_tokens": total_prompt,
            "completion_tokens": total_completion,
            "cost_usd": cost_usd,
            "cost_per_case_usd": cost_per_case_usd,
        }

    baseline_totals = compute_totals(bdev, bheld)
    candidate_totals = compute_totals(cdev, cheld)

    return {
        "source": pack_source,
        "companies": {
            "development": dev_companies,
            "held_out": held_companies,
        },
        "baseline": {
            "development": bdev.__dict__,
            "held_out": bheld.__dict__,
        },
        "proposals": [p.model_dump() for p in proposals],
        "candidate": {
            "development": cdev.__dict__,
            "held_out": cheld.__dict__,
        },
        "promotion": {"promoted": promoted, "reasons": reasons},
        "active_version": candidate_config.version if promoted else baseline_config.version,
        "cost": {
            "baseline": baseline_totals,
            "candidate": candidate_totals,
        },
        "note": "LLM-backed pack agent; results are measured on a small synthetic fixture set.",
    }