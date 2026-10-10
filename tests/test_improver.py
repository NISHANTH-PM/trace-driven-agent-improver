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
    keys = {proposal.config_key for proposal in propose_improvements(baseline)}
    assert {"use_keyword_fallback", "require_verification"} <= keys


def test_candidate_improves_and_is_promoted():
    dev = cases_for_split("development")
    held = cases_for_split("held_out")
    baseline = StudentConfig(version="baseline")
    baseline_dev = run_benchmark(dev, baseline)
    baseline_held = run_benchmark(held, baseline)
    candidate = apply_proposals(baseline, propose_improvements(baseline_dev))
    candidate_dev = run_benchmark(dev, candidate)
    candidate_held = run_benchmark(held, candidate)

    promoted, reasons = should_promote(
        baseline_dev, candidate_dev, baseline_held, candidate_held
    )

    assert candidate_dev.success_rate > baseline_dev.success_rate
    assert candidate_held.success_rate >= baseline_held.success_rate
    assert promoted
    assert "Held-out success rate did not regress." in reasons


def test_equal_heldout_performance_does_not_block_promotion():
    baseline_dev = type("Summary", (), {"success_rate": 0.6})()
    candidate_dev = type("Summary", (), {"success_rate": 0.8})()
    baseline_held = type("Summary", (), {"success_rate": 0.75})()
    candidate_held = type("Summary", (), {"success_rate": 0.75})()

    promoted, reasons = should_promote(
        baseline_dev, candidate_dev, baseline_held, candidate_held
    )

    assert promoted
    assert reasons == [
        "Development success rate improved.",
        "Held-out success rate did not regress.",
    ]


def test_candidate_is_rejected_if_heldout_regresses():
    baseline_dev = type("Summary", (), {"success_rate": 0.6})()
    candidate_dev = type("Summary", (), {"success_rate": 0.8})()
    baseline_held = type("Summary", (), {"success_rate": 0.75})()
    candidate_held = type("Summary", (), {"success_rate": 0.5})()

    promoted, reasons = should_promote(
        baseline_dev, candidate_dev, baseline_held, candidate_held
    )

    assert not promoted
    assert reasons == ["Held-out success rate regressed."]


def test_candidate_is_rejected_if_development_does_not_improve():
    baseline_dev = type("Summary", (), {"success_rate": 0.8})()
    candidate_dev = type("Summary", (), {"success_rate": 0.8})()
    baseline_held = type("Summary", (), {"success_rate": 0.75})()
    candidate_held = type("Summary", (), {"success_rate": 0.75})()

    promoted, reasons = should_promote(
        baseline_dev, candidate_dev, baseline_held, candidate_held
    )

    assert not promoted
    assert reasons == ["Development success rate did not improve."]
