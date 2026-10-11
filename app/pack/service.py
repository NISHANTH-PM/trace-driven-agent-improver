from app.pack.benchmark import pack_cases_for_split
from app.pack.evaluator import run_pack_benchmark
from app.pack.improver import apply_pack_proposals, propose_pack_improvements, should_promote
from app.pack.student import PackConfig
from app.llm import get_llm


def run_pack_improvement_cycle(llm=None):
    """Run the pack improvement cycle."""
    llm = llm or get_llm()

    baseline_config = PackConfig(version="baseline", output_dir="outputs/baseline")
    dev = pack_cases_for_split("development")
    held = pack_cases_for_split("held_out")

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

    # Build cost dict
    def cost_dict(summary):
        return {
            "llm_calls": summary.llm_calls,
            "prompt_tokens": summary.prompt_tokens,
            "completion_tokens": summary.completion_tokens,
        }

    return {
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
            "baseline": cost_dict(bdev),
            "candidate": cost_dict(cdev),
        },
        "note": "LLM-backed pack agent; results are measured on a small synthetic fixture set.",
    }