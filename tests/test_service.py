from app import service


def test_critical_heldout_failure_keeps_baseline_active(monkeypatch):
    original_run_benchmark = service.run_benchmark
    calls = 0

    def run_with_candidate_tool_failure(cases, config):
        nonlocal calls
        calls += 1
        summary = original_run_benchmark(cases, config)

        # The fourth benchmark is the candidate's held-out evaluation.
        if calls == 4:
            assert summary.split == "held_out"
            assert summary.version == "candidate"
            summary = summary.model_copy(
                update={
                    "successes": summary.successes - 1,
                    "success_rate": (summary.successes - 1) / summary.total,
                    "failure_counts": {"tool_error": 1},
                }
            )
        return summary

    monkeypatch.setattr(service, "run_benchmark", run_with_candidate_tool_failure)

    result = service.run_improvement_cycle()

    assert calls == 4
    assert result["candidate"]["held_out"]["failure_counts"]["tool_error"] == 1
    assert result["promotion"]["promoted"] is False
    assert any(
        "tool_error" in reason and "increased" in reason
        for reason in result["promotion"]["reasons"]
    )
    assert result["active_version"] == "baseline"


def test_successfully_promoted_candidate_becomes_active():
    result = service.run_improvement_cycle()

    assert result["promotion"]["promoted"] is True
    assert result["active_version"] == "candidate"
    assert (
        result["candidate"]["development"]["success_rate"]
        > result["baseline"]["development"]["success_rate"]
    )
    assert (
        result["candidate"]["held_out"]["success_rate"]
        >= result["baseline"]["held_out"]["success_rate"]
    )
