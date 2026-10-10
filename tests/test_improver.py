from app.benchmark import cases_for_split
from app.evaluator import run_benchmark
from app.improver import apply_proposals, propose_improvements, should_promote
from app.student import StudentConfig

def test_baseline_has_seeded_failures():
    summary = run_benchmark(cases_for_split("development"), StudentConfig(version="baseline"))
    assert summary.success_rate < 1.0
    assert summary.failure_counts

def test_improver_proposes_bounded_changes():
    baseline = run_benchmark(cases_for_split("development"), StudentConfig(version="baseline"))
    keys = {p.config_key for p in propose_improvements(baseline)}
    assert {"use_keyword_fallback", "require_verification"} <= keys

def test_candidate_improves_and_is_promoted():
    dev, held = cases_for_split("development"), cases_for_split("held_out")
    baseline = StudentConfig(version="baseline")
    bdev, bheld = run_benchmark(dev, baseline), run_benchmark(held, baseline)
    candidate = apply_proposals(baseline, propose_improvements(bdev))
    cdev, cheld = run_benchmark(dev, candidate), run_benchmark(held, candidate)
    promoted, _ = should_promote(bdev, cdev, bheld, cheld)
    assert cdev.success_rate > bdev.success_rate
    assert cheld.success_rate > bheld.success_rate
    assert promoted
