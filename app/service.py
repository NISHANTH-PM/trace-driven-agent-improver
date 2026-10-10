from app.benchmark import cases_for_split
from app.evaluator import run_benchmark
from app.improver import apply_proposals, propose_improvements, should_promote
from app.student import StudentConfig

def run_improvement_cycle():
    baseline_config = StudentConfig(version="baseline")
    dev, held = cases_for_split("development"), cases_for_split("held_out")
    bdev = run_benchmark(dev, baseline_config)
    bheld = run_benchmark(held, baseline_config)
    proposals = propose_improvements(bdev)
    candidate_config = apply_proposals(baseline_config, proposals)
    cdev = run_benchmark(dev, candidate_config)
    cheld = run_benchmark(held, candidate_config)
    promoted, reasons = should_promote(bdev, cdev, bheld, cheld)
    return {
        "baseline": {"development": bdev.model_dump(), "held_out": bheld.model_dump()},
        "proposals": [p.model_dump() for p in proposals],
        "candidate": {"development": cdev.model_dump(), "held_out": cheld.model_dump()},
        "promotion": {"promoted": promoted, "reasons": reasons},
        "active_version": candidate_config.version if promoted else baseline_config.version,
        "note": "Deterministic scaffold validates the loop, not LLM performance."
    }
