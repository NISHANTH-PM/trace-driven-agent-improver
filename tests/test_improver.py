from types import SimpleNamespace

from app.benchmark import cases_for_split
from app.evaluator import run_benchmark
from app.improver import apply_proposals, propose_improvements, should_promote
from app.student import StudentConfig


def test_baseline_exposes_action_and_verification_failures():
    summary = run_benchmark(cases_for_split("development"), StudentConfig(version="baseline"))

    assert summary.success_rate < 1.0
    assert summary.failure_counts.get("wrong_tool", 0) > 0
    assert summary.failure_counts.get("missing_verification", 0) > 0


def test_improver_proposes_bounded_changes_for_observed_failures():
    baseline = run_benchmark(cases_for_split("development"), StudentConfig(version="baseline"))
    proposals = propose_improvements(baseline)
    keys = {proposal.config_key for proposal in proposals}

    assert {"use_keyword_fallback", "require_verification"} <= keys
    assert all(proposal.target_failure in baseline.failure_counts for proposal in proposals)


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

    # Pin the benchmark counts so the demo cannot silently drift.
    assert (baseline_dev.successes, baseline_dev.total) == (6, 10)
    assert (candidate_dev.successes, candidate_dev.total) == (10, 10)
    assert (baseline_held.successes, baseline_held.total) == (4, 6)
    assert (candidate_held.successes, candidate_held.total) == (6, 6)
    assert candidate_dev.success_rate > baseline_dev.success_rate
    assert candidate_held.success_rate >= baseline_held.success_rate
    assert promoted
    assert "Held-out success rate did not regress." in reasons


def test_equal_heldout_performance_does_not_block_promotion():
    baseline_dev = SimpleNamespace(success_rate=0.6)
    candidate_dev = SimpleNamespace(success_rate=0.8)
    baseline_held = SimpleNamespace(success_rate=0.75)
    candidate_held = SimpleNamespace(success_rate=0.75)

    promoted, reasons = should_promote(
        baseline_dev, candidate_dev, baseline_held, candidate_held
    )

    assert promoted
    assert reasons == [
        "Development success rate improved.",
        "Held-out success rate did not regress.",
    ]


def test_candidate_is_rejected_if_heldout_regresses():
    baseline_dev = SimpleNamespace(success_rate=0.6)
    candidate_dev = SimpleNamespace(success_rate=0.8)
    baseline_held = SimpleNamespace(success_rate=0.75)
    candidate_held = SimpleNamespace(success_rate=0.5)

    promoted, reasons = should_promote(
        baseline_dev, candidate_dev, baseline_held, candidate_held
    )

    assert not promoted
    assert reasons == ["Held-out success rate regressed."]


def test_candidate_is_rejected_if_development_does_not_improve():
    baseline_dev = SimpleNamespace(success_rate=0.8)
    candidate_dev = SimpleNamespace(success_rate=0.8)
    baseline_held = SimpleNamespace(success_rate=0.75)
    candidate_held = SimpleNamespace(success_rate=0.75)

    promoted, reasons = should_promote(
        baseline_dev, candidate_dev, baseline_held, candidate_held
    )

    assert not promoted
    assert reasons == ["Development success rate did not improve."]
