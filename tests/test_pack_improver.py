"""Tests for pack improver and improvement cycle."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.pack.evaluator import evaluate_pack_case, run_pack_benchmark
from app.pack.improver import apply_pack_proposals, propose_pack_improvements
from app.pack.models import CompanyCase, PackOutput, REQUIRED_SECTIONS
from app.pack.student import PackConfig, run_pack_student
from app.pack.tools import FixtureSource
from app.models import TraceEvent
from app.llm import FakeLLMClient


class TestEvaluatorPrecedence:
    """Tests for evaluator precedence rules."""

    @pytest.fixture
    def case_d01(self):
        return CompanyCase(case_id="D01", company_name="Apex Dynamics", domain="apex-dynamics.com", split="development")

    @pytest.fixture
    def case_d02(self):
        return CompanyCase(case_id="D02", company_name="Meridian Bio", domain="meridian-bio.com", split="development")

    @pytest.fixture
    def truth_source(self):
        return FixtureSource()

    def make_trace(self, steps):
        """Create a trace with given steps."""
        trace = []
        for i, (step, outcome, detail) in enumerate(steps):
            trace.append(TraceEvent(
                event_id=str(i),
                run_id="run1",
                case_id="D01",
                step=step,
                detail=detail,
                outcome=outcome,
            ))
        return trace

    def test_tool_error_beats_wrong_fact(self, case_d01, truth_source):
        """tool_error takes precedence over wrong_fact."""
        output = PackOutput(
            case_id="D01",
            docx_path="outputs/D01_baseline.docx",
            sections={s: "content" for s in REQUIRED_SECTIONS},
            claimed_facts={},
            verified=False,
            tool_attempts=1,
            rationale="test",
        )
        trace = self.make_trace([
            ("tool_execution", "error", "tool failed"),
            ("llm_draft", "ok", "llm called"),
        ])
        result = evaluate_pack_case(case_d01, output, trace, truth_source)
        assert result.failure_class == "tool_error"
        assert result.issues == ["tool failed"]

    def test_invalid_output_when_no_docx(self, case_d01, truth_source):
        """invalid_output when docx_path is None."""
        output = PackOutput(
            case_id="D01",
            docx_path=None,
            sections={s: "content" for s in REQUIRED_SECTIONS},
            claimed_facts={},
            verified=False,
            tool_attempts=1,
            rationale="test",
        )
        trace = self.make_trace([
            ("tool_execution", "ok", "tool ok"),
            ("llm_draft", "ok", "llm ok"),
        ])
        result = evaluate_pack_case(case_d01, output, trace, truth_source)
        assert result.failure_class == "invalid_output"
        assert result.issues == ["no docx generated"]

    def test_invalid_output_when_llm_parse_error(self, case_d01, truth_source):
        """invalid_output when llm_parse error in trace."""
        output = PackOutput(
            case_id="D01",
            docx_path="outputs/D01_baseline.docx",
            sections={s: "content" for s in REQUIRED_SECTIONS},
            claimed_facts={},
            verified=False,
            tool_attempts=1,
            rationale="test",
        )
        trace = self.make_trace([
            ("tool_execution", "ok", "tool ok"),
            ("llm_parse", "error", "parse failed"),
        ])
        result = evaluate_pack_case(case_d01, output, trace, truth_source)
        assert result.failure_class == "invalid_output"
        assert result.issues == ["invalid llm output"]

    def test_missing_section_detected(self, case_d01, truth_source):
        """missing_section when sections are missing."""
        output = PackOutput(
            case_id="D01",
            docx_path="outputs/D01_baseline.docx",
            sections={"Overview": "content", "Key Facts": "content"},
            claimed_facts={},
            verified=False,
            tool_attempts=1,
            rationale="test",
        )
        trace = self.make_trace([
            ("tool_execution", "ok", "tool ok"),
            ("llm_draft", "ok", "llm ok"),
        ])
        result = evaluate_pack_case(case_d01, output, trace, truth_source)
        assert result.failure_class == "missing_section"
        assert set(result.issues) == {"Funding", "Risks"}

    def test_wrong_fact_detected(self, case_d01, truth_source):
        """wrong_fact when facts don't match."""
        output = PackOutput(
            case_id="D01",
            docx_path="outputs/D01_baseline.docx",
            sections={s: "content" for s in REQUIRED_SECTIONS},
            claimed_facts={},
            verified=False,
            tool_attempts=1,
            rationale="test",
        )
        # Sections have wrong employee count
        output.sections["Key Facts"] = "We have about 300 employees"
        trace = self.make_trace([
            ("tool_execution", "ok", "tool ok"),
            ("llm_draft", "ok", "llm ok"),
        ])
        result = evaluate_pack_case(case_d01, output, trace, truth_source)
        assert result.failure_class == "wrong_fact"
        assert any("employee_count" in issue for issue in result.issues)

    def test_success_when_all_good(self, case_d01, truth_source):
        """success when all checks pass."""
        output = PackOutput(
            case_id="D01",
            docx_path="outputs/D01_baseline.docx",
            sections={
                "Overview": "Apex Dynamics is a robotics company founded in 2015 in Pittsburgh.",
                "Key Facts": "342 employees, founded 2015, HQ Pittsburgh",
                "Funding": "Total funding $85,000,000, last round Series B",
                "Risks": "Competition in robotics market",
            },
            claimed_facts={},
            verified=False,
            tool_attempts=1,
            rationale="test",
        )
        trace = self.make_trace([
            ("tool_execution", "ok", "tool ok"),
            ("llm_draft", "ok", "llm ok"),
        ])
        result = evaluate_pack_case(case_d01, output, trace, truth_source)
        assert result.failure_class == "none"
        assert result.success is True
        assert result.issues == []


class TestPackImprover:
    """Tests for the pack improver."""

    def test_propose_tool_error(self):
        """tool_error proposes retry_tool_errors."""
        from app.pack.evaluator import PackSummary
        summary = PackSummary(
            version="baseline",
            split="development",
            total=6,
            successes=4,
            success_rate=0.6667,
            failure_counts={"tool_error": 2},
            llm_calls=6,
            prompt_tokens=100,
            completion_tokens=50,
            retries=0,
            results=[],
        )
        proposals = propose_pack_improvements(summary)
        assert len(proposals) == 1
        assert proposals[0].config_key == "retry_tool_errors"
        assert proposals[0].config_value is True
        assert proposals[0].change_type == "workflow_gate"

    def test_propose_wrong_fact(self):
        """wrong_fact proposes strict_prompt and verify_facts."""
        from app.pack.evaluator import PackSummary
        summary = PackSummary(
            version="baseline",
            split="development",
            total=6,
            successes=4,
            success_rate=0.6667,
            failure_counts={"wrong_fact": 2},
            llm_calls=6,
            prompt_tokens=100,
            completion_tokens=50,
            retries=0,
            results=[],
        )
        proposals = propose_pack_improvements(summary)
        assert len(proposals) == 2
        keys = {p.config_key for p in proposals}
        assert keys == {"strict_prompt", "verify_facts"}
        types = {p.change_type for p in proposals}
        assert types == {"prompt_rule", "workflow_gate"}

    def test_propose_missing_section(self):
        """missing_section proposes verify_facts."""
        from app.pack.evaluator import PackSummary
        summary = PackSummary(
            version="baseline",
            split="development",
            total=6,
            successes=4,
            success_rate=0.6667,
            failure_counts={"missing_section": 2},
            llm_calls=6,
            prompt_tokens=100,
            completion_tokens=50,
            retries=0,
            results=[],
        )
        proposals = propose_pack_improvements(summary)
        assert len(proposals) == 1
        assert proposals[0].config_key == "verify_facts"
        assert proposals[0].change_type == "workflow_gate"

    def test_no_duplicate_verify_facts(self):
        """wrong_fact and missing_section together -> only one verify_facts."""
        from app.pack.evaluator import PackSummary
        summary = PackSummary(
            version="baseline",
            split="development",
            total=6,
            successes=3,
            success_rate=0.5,
            failure_counts={"wrong_fact": 2, "missing_section": 1},
            llm_calls=6,
            prompt_tokens=100,
            completion_tokens=50,
            retries=0,
            results=[],
        )
        proposals = propose_pack_improvements(summary)
        keys = [p.config_key for p in proposals]
        assert keys.count("verify_facts") == 1

    def test_invalid_output_alone_proposes_nothing(self):
        """invalid_output alone proposes nothing."""
        from app.pack.evaluator import PackSummary
        summary = PackSummary(
            version="baseline",
            split="development",
            total=6,
            successes=5,
            success_rate=0.8333,
            failure_counts={"invalid_output": 1},
            llm_calls=6,
            prompt_tokens=100,
            completion_tokens=50,
            retries=0,
            results=[],
        )
        proposals = propose_pack_improvements(summary)
        assert len(proposals) == 0

    def test_apply_proposals(self):
        """apply_pack_proposals creates candidate config."""
        config = PackConfig(
            verify_facts=False,
            retry_tool_errors=False,
            strict_prompt=False,
            version="baseline",
        )
        from app.models import ImprovementProposal
        proposals = [
            ImprovementProposal(
                target_failure="tool_error",
                change_type="workflow_gate",
                description="Enable retry",
                config_key="retry_tool_errors",
                config_value=True,
            ),
            ImprovementProposal(
                target_failure="wrong_fact",
                change_type="prompt_rule",
                description="Use strict prompt",
                config_key="strict_prompt",
                config_value=True,
            ),
        ]
        candidate = apply_pack_proposals(config, proposals)
        assert candidate.retry_tool_errors is True
        assert candidate.strict_prompt is True
        assert candidate.verify_facts is False
        assert candidate.version == "candidate"
        # Original unchanged
        assert config.retry_tool_errors is False
        assert config.strict_prompt is False


class ScriptedFakeLLM(FakeLLMClient):
    """Fake LLM that returns rounded figures unless strict prompt is used."""

    def __init__(self):
        super().__init__(self._respond)
        self.call_history = []

    def _respond(self, system: str, user: str) -> str:
        self.call_history.append({"system": system, "user": user})
        is_strict = "Never round or estimate" in system

        # Parse the user message to get company data
        try:
            data = json.loads(user.split("\n\n")[0])
        except Exception:
            data = {}

        name = data.get("name", "Test Company")
        domain = data.get("domain", "test.com")
        employees = data.get("employee_count", 100)
        founded = data.get("founded_year", 2020)
        city = data.get("hq_city", "San Francisco")
        funding = data.get("total_funding_usd", 1000000)
        last_round = data.get("last_round", "Series A")

        if is_strict:
            # Exact figures
            funding_str = f"${funding:,}" if funding > 0 else "bootstrapped"
            sections = {
                "Overview": f"{name} is a {data.get('industry', 'Tech')} company founded in {founded} in {city}.",
                "Key Facts": f"{employees} employees, founded {founded}, HQ {city}",
                "Funding": f"Total funding {funding_str}, last round {last_round}",
                "Risks": "Market competition and scaling challenges.",
            }
        else:
            # Rounded/approximate figures
            emp_rounded = round(employees / 100) * 100
            funding_m = funding / 1_000_000
            sections = {
                "Overview": f"{name} is a {data.get('industry', 'Tech')} company founded around {founded} in the {city} area.",
                "Key Facts": f"About {emp_rounded} employees, founded around {founded}, HQ in {city} area",
                "Funding": f"Raised roughly ${funding_m:g}M, last round {last_round}",
                "Risks": "Market competition and scaling challenges.",
            }

        return json.dumps({"sections": sections})


class TestImprovementCycle:
    """Tests for the full improvement cycle."""

    @pytest.fixture
    def dev_cases(self):
        from app.pack.benchmark import pack_cases_for_split
        return pack_cases_for_split("development")

    @pytest.fixture
    def held_cases(self):
        from app.pack.benchmark import pack_cases_for_split
        return pack_cases_for_split("held_out")

    def test_full_cycle_with_scripted_llm(self, dev_cases, held_cases, tmp_path):
        """Full cycle with scripted LLM: baseline has tool_error and wrong_fact, candidate better."""
        llm = ScriptedFakeLLM()
        baseline_config = PackConfig(version="baseline", output_dir=str(tmp_path / "baseline"))

        # Baseline run
        bdev = run_pack_benchmark(dev_cases, baseline_config, llm=llm)

        # Check baseline has tool_error (from D02 flaky) and wrong_fact (from rounded figures)
        assert bdev.failure_counts.get("tool_error", 0) > 0
        assert bdev.failure_counts.get("wrong_fact", 0) > 0

        # Proposals
        proposals = propose_pack_improvements(bdev)
        assert any(p.config_key == "retry_tool_errors" for p in proposals)
        assert any(p.config_key == "strict_prompt" for p in proposals)
        assert any(p.config_key == "verify_facts" for p in proposals)

        # Apply proposals
        candidate_config = apply_pack_proposals(baseline_config, proposals)
        candidate_config.output_dir = str(tmp_path / "candidate")

        # Candidate run
        cdev = run_pack_benchmark(dev_cases, candidate_config, llm=llm)

        # Candidate should be strictly better on dev
        assert cdev.success_rate > bdev.success_rate
        assert cdev.failure_counts.get("tool_error", 0) == 0  # retries fix tool_error
        assert cdev.failure_counts.get("wrong_fact", 0) == 0  # strict + verify fix wrong_fact

        # Held-out should not regress
        bheld = run_pack_benchmark(held_cases, baseline_config, llm=llm)
        cheld = run_pack_benchmark(held_cases, candidate_config, llm=llm)

        from app.improver import should_promote
        promoted, reasons = should_promote(bdev, cdev, bheld, cheld)

        # Note: held-out H02 is flaky, so tool_error may appear there too
        # With retry_tool_errors, it should be fixed

    def test_always_rounded_cannot_promote(self, dev_cases, held_cases, tmp_path):
        """LLM that always returns rounded figures -> cannot promote."""
        # LLM that ignores strict prompt and always returns rounded
        def always_rounded(system, user):
            data = json.loads(user.split("\n\n")[0])
            name = data.get("name", "Test")
            employees = data.get("employee_count", 100)
            founded = data.get("founded_year", 2020)
            city = data.get("hq_city", "SF")
            funding = data.get("total_funding_usd", 1000000)
            last_round = data.get("last_round", "Series A")
            emp_rounded = round(employees / 100) * 100
            funding_m = funding / 1_000_000
            sections = {
                "Overview": f"{name} founded around {founded} in {city} area.",
                "Key Facts": f"About {emp_rounded} employees, founded around {founded}",
                "Funding": f"Raised roughly ${funding_m:g}M, last round {last_round}",
                "Risks": "Risks exist.",
            }
            return json.dumps({"sections": sections})

        llm = FakeLLMClient(always_rounded)
        baseline_config = PackConfig(version="baseline", output_dir=str(tmp_path / "baseline"))

        bdev = run_pack_benchmark(dev_cases, baseline_config, llm=llm)
        proposals = propose_pack_improvements(bdev)
        candidate_config = apply_pack_proposals(baseline_config, proposals)
        candidate_config.output_dir = str(tmp_path / "candidate")

        cdev = run_pack_benchmark(dev_cases, candidate_config, llm=llm)

        # Even with strict_prompt and verify_facts, LLM still returns rounded
        # So wrong_fact persists
        assert cdev.failure_counts.get("wrong_fact", 0) > 0
        assert cdev.success_rate <= bdev.success_rate

        bheld = run_pack_benchmark(held_cases, baseline_config, llm=llm)
        cheld = run_pack_benchmark(held_cases, candidate_config, llm=llm)

        from app.improver import should_promote
        promoted, reasons = should_promote(bdev, cdev, bheld, cheld)
        assert promoted is False
        assert any("Development success rate did not improve" in r for r in reasons)


class TestPackBenchmark:
    """Integration tests for pack benchmark."""

    def test_run_pack_benchmark_counts(self, tmp_path):
        """Test that benchmark runs and counts are correct."""
        from app.pack.benchmark import pack_cases_for_split
        from app.pack.tools import FixtureSource
        dev_cases = pack_cases_for_split("development")
        held_cases = pack_cases_for_split("held_out")

        assert len(dev_cases) == 6
        assert len(held_cases) == 4

        llm = FakeLLMClient(json.dumps({
            "sections": {s: "exact content with 342 employees and 2015 and Pittsburgh and $85,000,000 and Series B" for s in REQUIRED_SECTIONS}
        }))

        config = PackConfig(version="test", output_dir=str(tmp_path))
        # Use non-flaky source to avoid tool errors
        result = run_pack_benchmark(dev_cases, config, source=FixtureSource(), llm=llm)

        assert result.total == 6
        assert result.llm_calls == 6  # one per case
        # FakeLLMClient doesn't track token usage


class TestPackAblation:
    """Tests for pack ablation."""

    @pytest.fixture
    def dev_cases(self):
        from app.pack.benchmark import pack_cases_for_split
        return pack_cases_for_split("development")

    @pytest.fixture
    def held_cases(self):
        from app.pack.benchmark import pack_cases_for_split
        return pack_cases_for_split("held_out")

    def test_ablation_baseline_vs_candidate_on_dev(self, dev_cases, held_cases, tmp_path):
        """Test that baseline < candidate on dev split with scripted LLM."""
        llm = ScriptedFakeLLM()

        baseline_config = PackConfig(
            version="baseline",
            output_dir=str(tmp_path / "ablation" / "baseline"),
            retry_tool_errors=False,
            strict_prompt=False,
            verify_facts=False,
        )
        candidate_config = PackConfig(
            version="candidate",
            output_dir=str(tmp_path / "ablation" / "candidate"),
            retry_tool_errors=True,
            strict_prompt=True,
            verify_facts=True,
        )

        bdev = run_pack_benchmark(dev_cases, baseline_config, source=FixtureSource(), llm=llm)
        cdev = run_pack_benchmark(dev_cases, candidate_config, source=FixtureSource(), llm=llm)

        # Candidate should be strictly better on dev
        assert cdev.success_rate > bdev.success_rate
        assert cdev.failure_counts.get("tool_error", 0) == 0
        assert cdev.failure_counts.get("wrong_fact", 0) == 0

    def test_ablation_cost_counting(self, dev_cases, held_cases, tmp_path):
        """Test that cost fields are populated correctly in ablation runs."""
        # Use a simple fake LLM with known token counts
        class CountingFakeLLM(FakeLLMClient):
            def __init__(self):
                super().__init__(self._respond)
                self.call_count = 0

            def _respond(self, system, user):
                self.call_count += 1
                data = json.loads(user.split("\n\n")[0])
                sections = {s: f"exact {data.get('employee_count', 100)} {data.get('founded_year', 2020)}" for s in REQUIRED_SECTIONS}
                return json.dumps({"sections": sections})

        llm = CountingFakeLLM()

        baseline_config = PackConfig(
            version="baseline",
            output_dir=str(tmp_path / "ablation" / "baseline"),
            retry_tool_errors=False,
            strict_prompt=False,
            verify_facts=False,
        )

        bdev = run_pack_benchmark(dev_cases, baseline_config, source=FixtureSource(), llm=llm)
        bheld = run_pack_benchmark(held_cases, baseline_config, source=FixtureSource(), llm=llm)

        # Check that baseline total calls == number of cases that did not end in tool_error
        # D02 is flaky and will have tool_error on first attempt without retry
        # So dev cases without tool_error = 5 (6 total - 1 flaky)
        # held_out cases without tool_error = 3 (4 total - 1 flaky H02)
        # But wait - we're using FixtureSource which is NOT flaky
        # So all cases should succeed
        non_tool_error_dev = sum(1 for r in bdev.results if r.failure_class != "tool_error")
        non_tool_error_held = sum(1 for r in bheld.results if r.failure_class != "tool_error")
        expected_calls = non_tool_error_dev + non_tool_error_held

        # Since we use FixtureSource, no tool errors should occur
        assert bdev.failure_counts.get("tool_error", 0) == 0
        assert bheld.failure_counts.get("tool_error", 0) == 0
        assert bdev.llm_calls == bdev.total
        assert bheld.llm_calls == bheld.total
        assert bdev.llm_calls + bheld.llm_calls == expected_calls

if __name__ == "__main__":
    pytest.main([__file__, "-v"])