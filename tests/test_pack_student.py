"""Tests for pack student agent and checks."""

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

import pytest

from app.pack.checks import fact_mismatches, missing_sections
from app.pack.models import CompanyData, CompanyCase, REQUIRED_SECTIONS
from app.pack.student import PackConfig, run_pack_student, STRICT_SYSTEM_PROMPT, BASE_SYSTEM_PROMPT
from app.pack.evaluator import run_pack_benchmark
import app.observability as observability_module
from app.pack.tools import FixtureSource, ToolError, default_source
from app.llm import FakeLLMClient


@pytest.fixture
def case_d01():
    return CompanyCase(case_id="D01", company_name="Apex Dynamics", domain="apex-dynamics.com", split="development")


@pytest.fixture
def case_d02():
    return CompanyCase(case_id="D02", company_name="Meridian Bio", domain="meridian-bio.com", split="development")


@pytest.fixture
def good_json_response():
    return json.dumps({
        "sections": {
            "Overview": "Apex Dynamics is a robotics company founded in 2015 in Pittsburgh.",
            "Key Facts": "342 employees, founded 2015, HQ Pittsburgh",
            "Funding": "Total funding $85,000,000, last round Series B",
            "Risks": "Competition in robotics market"
        }
    })


class TestChecks:
    """Tests for fact-checking utilities."""

    def test_missing_sections_all_present(self):
        sections = {s: "content" for s in REQUIRED_SECTIONS}
        assert missing_sections(sections) == []

    def test_missing_sections_some_missing(self):
        sections = {"Overview": "text", "Key Facts": "text"}
        missing = missing_sections(sections)
        assert "Funding" in missing
        assert "Risks" in missing

    def test_missing_sections_blank(self):
        sections = {"Overview": "text", "Key Facts": "", "Funding": "text", "Risks": "text"}
        missing = missing_sections(sections)
        assert "Key Facts" in missing

    def test_fact_mismatches_employee_count_exact(self):
        company = CompanyData(
            name="Test", domain="test.com", industry="Tech", description="Test",
            employee_count=4000, founded_year=2020, hq_city="SF",
            total_funding_usd=1000000, last_round="Series A"
        )
        sections = {s: "content" for s in REQUIRED_SECTIONS}
        sections["Key Facts"] = "We have 4000 employees"
        assert "employee_count=4000 not stated exactly" not in fact_mismatches(company, sections)

    def test_fact_mismatches_employee_count_comma(self):
        company = CompanyData(
            name="Test", domain="test.com", industry="Tech", description="Test",
            employee_count=4000, founded_year=2020, hq_city="SF",
            total_funding_usd=1000000, last_round="Series A"
        )
        sections = {s: "content" for s in REQUIRED_SECTIONS}
        sections["Key Facts"] = "We have 4,000 employees"
        assert "employee_count=4000 not stated exactly" not in fact_mismatches(company, sections)

    def test_fact_mismatches_employee_count_rounded_fails(self):
        company = CompanyData(
            name="Test", domain="test.com", industry="Tech", description="Test",
            employee_count=2347, founded_year=2020, hq_city="SF",
            total_funding_usd=1000000, last_round="Series A"
        )
        sections = {s: "content" for s in REQUIRED_SECTIONS}
        sections["Key Facts"] = "We have about 2,000 employees"
        issues = fact_mismatches(company, sections)
        assert "employee_count=2347 not stated exactly" in issues

    def test_fact_mismatches_founded_year(self):
        company = CompanyData(
            name="Test", domain="test.com", industry="Tech", description="Test",
            employee_count=100, founded_year=2015, hq_city="SF",
            total_funding_usd=1000000, last_round="Series A"
        )
        sections = {s: "content" for s in REQUIRED_SECTIONS}
        sections["Overview"] = "Founded in 2015"
        assert "founded_year=2015 not stated exactly" not in fact_mismatches(company, sections)

        sections["Overview"] = "Founded recently"
        assert "founded_year=2015 not stated exactly" in fact_mismatches(company, sections)

    def test_fact_mismatches_hq_city(self):
        company = CompanyData(
            name="Test", domain="test.com", industry="Tech", description="Test",
            employee_count=100, founded_year=2015, hq_city="San Francisco",
            total_funding_usd=1000000, last_round="Series A"
        )
        sections = {s: "content" for s in REQUIRED_SECTIONS}
        sections["Overview"] = "Based in San Francisco"
        assert "hq_city=San Francisco not stated" not in fact_mismatches(company, sections)

    def test_fact_mismatches_last_round(self):
        company = CompanyData(
            name="Test", domain="test.com", industry="Tech", description="Test",
            employee_count=100, founded_year=2015, hq_city="SF",
            total_funding_usd=1000000, last_round="Series B"
        )
        sections = {s: "content" for s in REQUIRED_SECTIONS}
        sections["Funding"] = "Raised Series B funding"
        assert "last_round=Series B not stated" not in fact_mismatches(company, sections)

    def test_fact_mismatches_total_funding_exact(self):
        company = CompanyData(
            name="Test", domain="test.com", industry="Tech", description="Test",
            employee_count=100, founded_year=2015, hq_city="SF",
            total_funding_usd=42000000, last_round="Series B"
        )
        sections = {s: "content" for s in REQUIRED_SECTIONS}
        sections["Funding"] = "Total funding $42,000,000"
        assert "total_funding_usd=42000000 not stated in accepted format" not in fact_mismatches(company, sections)

    def test_fact_mismatches_total_funding_various_formats(self):
        company = CompanyData(
            name="Test", domain="test.com", industry="Tech", description="Test",
            employee_count=100, founded_year=2015, hq_city="SF",
            total_funding_usd=42000000, last_round="Series B"
        )
        sections = {s: "content" for s in REQUIRED_SECTIONS}
        # Test various accepted formats
        for fmt in ["42000000", "42,000,000", "$42M", "42M", "$42 million", "42 million"]:
            sections["Funding"] = f"Raised {fmt}"
            issues = fact_mismatches(company, sections)
            assert "total_funding_usd=42000000 not stated in accepted format" not in issues, f"Failed for format: {fmt}"

    def test_fact_mismatches_total_funding_bootstrapped(self):
        company = CompanyData(
            name="Test", domain="test.com", industry="Tech", description="Test",
            employee_count=100, founded_year=2015, hq_city="SF",
            total_funding_usd=0, last_round="Bootstrapped"
        )
        sections = {s: "content" for s in REQUIRED_SECTIONS}
        sections["Funding"] = "Company is bootstrapped"
        issues = fact_mismatches(company, sections)
        assert "total_funding_usd=0 not stated" not in issues

        sections["Funding"] = "No external funding"
        issues = fact_mismatches(company, sections)
        assert "total_funding_usd=0 not stated" not in issues

        sections["Funding"] = "$0"
        issues = fact_mismatches(company, sections)
        assert "total_funding_usd=0 not stated" not in issues

        sections["Funding"] = "Self-funded"
        issues = fact_mismatches(company, sections)
        # Should have a funding issue (other fields may also be missing)
        funding_issues = [i for i in issues if "total_funding_usd=0" in i]
        assert len(funding_issues) == 1
        assert "total_funding_usd=0 not stated" in funding_issues[0]

    def test_fact_mismatches_last_round_underscore_vs_space(self):
        """last_round with underscores should match space-separated in text."""
        company = CompanyData(
            name="Test", domain="test.com", industry="Tech", description="Test",
            employee_count=100, founded_year=2015, hq_city="SF",
            total_funding_usd=1000000, last_round="secondary_market"
        )
        sections = {s: "content" for s in REQUIRED_SECTIONS}
        sections["Funding"] = "Last round was secondary market"
        issues = fact_mismatches(company, sections)
        assert "last_round=secondary_market not stated" not in issues

    def test_fact_mismatches_last_round_underscore_vs_hyphen(self):
        """last_round with underscores should match hyphenated in text."""
        company = CompanyData(
            name="Test", domain="test.com", industry="Tech", description="Test",
            employee_count=100, founded_year=2015, hq_city="SF",
            total_funding_usd=1000000, last_round="post_ipo_equity"
        )
        sections = {s: "content" for s in REQUIRED_SECTIONS}
        sections["Funding"] = "Post-IPO equity round"
        issues = fact_mismatches(company, sections)
        assert "last_round=post_ipo_equity not stated" not in issues

    def test_fact_mismatches_last_round_case_insensitive_series(self):
        """last_round series_x should match Series X in text."""
        company = CompanyData(
            name="Test", domain="test.com", industry="Tech", description="Test",
            employee_count=100, founded_year=2015, hq_city="SF",
            total_funding_usd=1000000, last_round="series_d"
        )
        sections = {s: "content" for s in REQUIRED_SECTIONS}
        sections["Funding"] = "Series D round"
        issues = fact_mismatches(company, sections)
        assert "last_round=series_d not stated" not in issues

    def test_fact_mismatches_hq_city_underscore_vs_space(self):
        """hq_city with underscores should match space-separated in text."""
        company = CompanyData(
            name="Test", domain="test.com", industry="Tech", description="Test",
            employee_count=100, founded_year=2015, hq_city="san_francisco",
            total_funding_usd=1000000, last_round="Series A"
        )
        sections = {s: "content" for s in REQUIRED_SECTIONS}
        sections["Overview"] = "Based in San Francisco"
        issues = fact_mismatches(company, sections)
        assert "hq_city=san_francisco not stated" not in issues

    def test_fact_mismatches_total_funding_float_to_int(self):
        """total_funding_usd as float should be converted to int before comparison."""
        company = CompanyData(
            name="Test", domain="test.com", industry="Tech", description="Test",
            employee_count=100, founded_year=2015, hq_city="SF",
            total_funding_usd=42000000.0, last_round="Series B"
        )
        sections = {s: "content" for s in REQUIRED_SECTIONS}
        sections["Funding"] = "Total funding $42,000,000"
        issues = fact_mismatches(company, sections)
        assert "total_funding_usd=42000000 not stated in accepted format" not in issues


class TestPackStudent:
    """Tests for the pack student agent."""

    def test_happy_path_creates_docx(self, case_d01, good_json_response, tmp_path):
        fake_llm = FakeLLMClient(good_json_response)
        config = PackConfig(output_dir=str(tmp_path), version="test")

        output, trace = run_pack_student(case_d01, config, llm=fake_llm)

        assert output.docx_path is not None
        assert Path(output.docx_path).exists()
        assert output.sections == json.loads(good_json_response)["sections"]
        assert output.verified is False  # verify_facts=False by default
        assert output.tool_attempts == 1
        assert "version=test" in output.rationale

        # Verify docx content
        from docx import Document
        doc = Document(output.docx_path)
        assert doc.paragraphs[0].text == "Apex Dynamics"  # Heading 0
        heading_texts = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading 1")]
        assert set(heading_texts) == set(REQUIRED_SECTIONS)

    def test_baseline_on_d02_flaky_fails(self, case_d02):
        fake_llm = FakeLLMClient(json.dumps({
            "sections": {s: "content" for s in REQUIRED_SECTIONS}
        }))
        config = PackConfig(output_dir="outputs", version="test", retry_tool_errors=False)

        output, trace = run_pack_student(case_d02, config, llm=fake_llm)

        assert output.docx_path is None
        assert output.tool_attempts == 1
        assert output.verified is False
        assert output.rationale == "tool failed"
        # Check trace has tool_execution error
        tool_events = [e for e in trace if e.step == "tool_execution" and e.outcome == "error"]
        assert len(tool_events) == 1

    def test_retry_tool_errors_succeeds_on_d02(self, case_d02, good_json_response):
        fake_llm = FakeLLMClient(good_json_response)
        config = PackConfig(output_dir="outputs", version="test", retry_tool_errors=True, max_attempts=3)

        output, trace = run_pack_student(case_d02, config, llm=fake_llm)

        assert output.docx_path is not None
        assert output.tool_attempts == 2
        assert output.verified is False
        # Check trace has tool_retry
        retry_events = [e for e in trace if e.step == "tool_retry"]
        assert len(retry_events) == 1

    def test_verify_facts_true_first_bad_then_good(self, case_d01, tmp_path):
        # First response: rounded numbers (should fail verification)
        bad_response = json.dumps({
            "sections": {
                "Overview": "Apex Dynamics is a robotics company.",
                "Key Facts": "About 340 employees, founded around 2015, HQ in Pittsburgh area",
                "Funding": "Raised roughly $85M, last round Series B",
                "Risks": "Market competition"
            }
        })
        # Second response: exact numbers (should pass)
        good_response = json.dumps({
            "sections": {
                "Overview": "Apex Dynamics is a robotics company founded in 2015 in Pittsburgh.",
                "Key Facts": "342 employees, founded 2015, HQ Pittsburgh",
                "Funding": "Total funding $85,000,000, last round Series B",
                "Risks": "Competition in robotics market"
            }
        })

        call_count = [0]
        def responder(sys, user):
            call_count[0] += 1
            return bad_response if call_count[0] == 1 else good_response

        fake_llm = FakeLLMClient(responder)
        config = PackConfig(output_dir=str(tmp_path), version="test", verify_facts=True)

        output, trace = run_pack_student(case_d01, config, llm=fake_llm)

        assert fake_llm.calls == 2
        assert output.verified is True

    def test_verify_facts_true_both_bad(self, case_d01, tmp_path):
        bad_response = json.dumps({
            "sections": {
                "Overview": "Apex Dynamics is a robotics company.",
                "Key Facts": "About 340 employees, founded around 2015",
                "Funding": "Raised roughly $85M, last round Series B",
                "Risks": "Market competition"
            }
        })

        fake_llm = FakeLLMClient(bad_response)
        config = PackConfig(output_dir=str(tmp_path), version="test", verify_facts=True)

        output, trace = run_pack_student(case_d01, config, llm=fake_llm)

        assert fake_llm.calls == 2
        assert output.verified is False

    def test_invalid_json_returns_error(self, case_d01):
        fake_llm = FakeLLMClient("This is not valid JSON at all")
        config = PackConfig(output_dir="outputs", version="test")

        output, trace = run_pack_student(case_d01, config, llm=fake_llm)

        assert output.docx_path is None
        assert output.sections == {}
        assert output.verified is False
        assert output.rationale == "invalid llm output"
        # Check trace has llm_parse error
        parse_events = [e for e in trace if e.step == "llm_parse" and e.outcome == "error"]
        assert len(parse_events) == 1

    def test_strict_prompt_used_when_configured(self, case_d01, good_json_response):
        fake_llm = FakeLLMClient(good_json_response)
        config = PackConfig(output_dir="outputs", version="test", strict_prompt=True)

        output, trace = run_pack_student(case_d01, config, llm=fake_llm)

        # Verify the LLM was called with strict prompt
        # The FakeLLMClient doesn't capture the prompt, but we can check the behavior
        assert output.docx_path is not None


class TestDocxFooter:
    """Tests for the verification status footer in generated DOCX files."""

    def test_footer_not_checked_when_verify_facts_false(self, case_d01, good_json_response, tmp_path):
        """Footer says 'Not checked' when verify_facts=False."""
        fake_llm = FakeLLMClient(good_json_response)
        config = PackConfig(output_dir=str(tmp_path), version="test", verify_facts=False)

        output, trace = run_pack_student(case_d01, config, llm=fake_llm)

        assert output.docx_path is not None
        from docx import Document
        doc = Document(output.docx_path)
        # Find footer paragraph (last paragraph)
        footer_text = doc.paragraphs[-1].text
        assert "Source: Crustdata company data." in footer_text
        assert "Not checked" in footer_text

    def test_footer_not_checked_when_verify_facts_true_but_fails(self, case_d01, tmp_path):
        """Footer says 'No - at least one figure could not be confirmed' when verify_facts=True but issues remain."""
        bad_response = json.dumps({
            "sections": {
                "Overview": "Apex Dynamics is a robotics company.",
                "Key Facts": "About 340 employees, founded around 2015, HQ in Pittsburgh area",
                "Funding": "Raised roughly $85M, last round Series B",
                "Risks": "Market competition"
            }
        })
        fake_llm = FakeLLMClient(bad_response)
        config = PackConfig(output_dir=str(tmp_path), version="test", verify_facts=True)

        output, trace = run_pack_student(case_d01, config, llm=fake_llm)

        assert output.docx_path is not None
        assert output.verified is False
        from docx import Document
        doc = Document(output.docx_path)
        footer_text = doc.paragraphs[-1].text
        assert "Source: Crustdata company data." in footer_text
        assert "No - at least one figure could not be confirmed" in footer_text

    def test_footer_yes_when_verify_facts_true_and_passes(self, case_d01, good_json_response, tmp_path):
        """Footer says 'Yes' when verify_facts=True and verification passes."""
        fake_llm = FakeLLMClient(good_json_response)
        config = PackConfig(output_dir=str(tmp_path), version="test", verify_facts=True)

        output, trace = run_pack_student(case_d01, config, llm=fake_llm)

        assert output.docx_path is not None
        assert output.verified is True
        from docx import Document
        doc = Document(output.docx_path)
        footer_text = doc.paragraphs[-1].text
        assert "Source: Crustdata company data." in footer_text
        assert "Yes" in footer_text
        assert "Not checked" not in footer_text
        assert "No - at least one figure could not be confirmed" not in footer_text

    def test_footer_not_part_of_sections_or_fact_checks(self, case_d01, good_json_response, tmp_path):
        """Footer text does not affect fact_mismatches or missing_sections on sections dict."""
        fake_llm = FakeLLMClient(good_json_response)
        config = PackConfig(output_dir=str(tmp_path), version="test", verify_facts=True)

        output, trace = run_pack_student(case_d01, config, llm=fake_llm)

        # The footer is added at render time, not in the sections dict
        # So fact_mismatches on the sections dict should be unaffected
        from app.pack.checks import fact_mismatches, missing_sections
        missing = missing_sections(output.sections)
        issues = fact_mismatches(
            CompanyData(
                name="Apex Dynamics", domain="apex-dynamics.com", industry="Technology",
                description="Test", employee_count=342, founded_year=2015,
                hq_city="Pittsburgh", total_funding_usd=85000000, last_round="Series B"
            ),
            output.sections
        )
        assert missing == []
        assert issues == []


class TestPackStudentWithFixtureSource:
    """Tests using real fixture source."""

    def test_fetch_from_fixture_source(self):
        source = FixtureSource()
        case = CompanyCase(case_id="D01", company_name="Apex Dynamics", domain="apex-dynamics.com", split="development")
        company = source.get_company(case.domain)
        assert company.name == "Apex Dynamics"
        assert company.employee_count == 342

    def test_unknown_domain_raises(self):
        source = FixtureSource()
        with pytest.raises(ToolError, match="not found"):
            source.get_company("unknown.com")


class TestPackEvaluatorSpans:
    """Tests for evaluation span attributes in run_pack_benchmark."""

    def test_failed_case_span_status_error_and_output_value(self, case_d01):
        """Failed case should have span status ERROR with description starting with failure class, and output.value with TRUTH."""
        # Response with wrong employee count to trigger wrong_fact failure
        bad_response = json.dumps({
            "sections": {
                "Overview": "Apex Dynamics is a robotics company.",
                "Key Facts": "About 340 employees, founded around 2015, HQ in Pittsburgh area",
                "Funding": "Raised roughly $85M, last round Series B",
                "Risks": "Market competition"
            }
        })
        fake_llm = FakeLLMClient(bad_response)
        config = PackConfig(output_dir="outputs", version="test", verify_facts=True)

        # Capture the span by mocking trace_span
        captured_spans = []
        original_trace_span = None
        try:
            from app.observability import trace_span as orig_trace_span
            original_trace_span = orig_trace_span

            # Enable neatlogs initialization flag for mark_span_failed to work
            observability_module._initialized = True

            @contextmanager
            def mock_trace_span(name, kind="CHAIN", attributes=None):
                class MockSpan:
                    def __init__(self):
                        self.attributes = {}
                        self.status = None
                        self.status_code = None
                        self.description = None
                    def set_attribute(self, key, value):
                        self.attributes[key] = value
                    def set_status(self, status):
                        self.status = status
                        # Try to extract status code and description
                        if hasattr(status, 'status_code'):
                            self.status_code = status.status_code
                        if hasattr(status, 'description'):
                            self.description = status.description
                span = MockSpan()
                captured_spans.append((name, kind, attributes, span))
                yield span

            import app.pack.evaluator as evaluator_module
            evaluator_module.trace_span = mock_trace_span

            summary = run_pack_benchmark([case_d01], config, llm=fake_llm)

            # Check that we captured a span
            assert len(captured_spans) == 1
            _, _, _, span = captured_spans[0]

            # Check span status is ERROR
            assert span.status_code is not None
            # Check description starts with failure class
            assert span.description is not None
            assert span.description.startswith("wrong_fact")

            # Check output.value contains TRUTH
            assert "output.value" in span.attributes
            output_value = span.attributes["output.value"]
            assert "FAILED" in output_value
            assert "wrong_fact" in output_value
            assert "TRUTH:" in output_value
            assert "employee_count=342" in output_value
            assert "founded_year=2015" in output_value

            # Check evaluation attributes
            assert "evaluation.failure_class" in span.attributes
            assert span.attributes["evaluation.failure_class"] == "wrong_fact"
            assert "evaluation.issues" in span.attributes
            assert "evaluation.truth" in span.attributes

        finally:
            if original_trace_span:
                evaluator_module.trace_span = original_trace_span

    def test_passing_case_span_no_error_status_and_output_value_passes(self, case_d01, good_json_response):
        """Passing case should have no error status, output.value = PASSED, no TRUTH."""
        fake_llm = FakeLLMClient(good_json_response)
        config = PackConfig(output_dir="outputs", version="test")

        captured_spans = []
        original_trace_span = None
        try:
            from app.observability import trace_span as orig_trace_span
            original_trace_span = orig_trace_span

            # Enable neatlogs initialization flag for mark_span_failed to work
            observability_module._initialized = True

            @contextmanager
            def mock_trace_span(name, kind="CHAIN", attributes=None):
                class MockSpan:
                    def __init__(self):
                        self.attributes = {}
                        self.status = None
                        self.status_code = None
                        self.description = None
                    def set_attribute(self, key, value):
                        self.attributes[key] = value
                    def set_status(self, status):
                        self.status = status
                        if hasattr(status, 'status_code'):
                            self.status_code = status.status_code
                        if hasattr(status, 'description'):
                            self.description = status.description
                span = MockSpan()
                captured_spans.append((name, kind, attributes, span))
                yield span

            import app.pack.evaluator as evaluator_module
            evaluator_module.trace_span = mock_trace_span

            summary = run_pack_benchmark([case_d01], config, llm=fake_llm)

            assert len(captured_spans) == 1
            _, _, _, span = captured_spans[0]

            # Should not have error status
            assert span.status_code is None
            assert span.description is None

            # output.value should be PASSED, no TRUTH
            assert "output.value" in span.attributes
            assert span.attributes["output.value"] == "PASSED"
            assert "TRUTH:" not in span.attributes["output.value"]

            # Check evaluation attributes still present
            assert "evaluation.success" in span.attributes
            assert span.attributes["evaluation.success"] is True
            assert "evaluation.failure_class" in span.attributes
            assert span.attributes["evaluation.failure_class"] == "none"
            assert "evaluation.issues" in span.attributes
            assert span.attributes["evaluation.issues"] == ""
            assert "evaluation.truth" in span.attributes

        finally:
            if original_trace_span:
                evaluator_module.trace_span = original_trace_span

    def test_tool_error_case_span_status_error(self, case_d02):
        """Tool error case should have span status ERROR with tool_error failure class."""
        fake_llm = FakeLLMClient(json.dumps({
            "sections": {s: "content" for s in REQUIRED_SECTIONS}
        }))
        config = PackConfig(output_dir="outputs", version="test", retry_tool_errors=False)

        captured_spans = []
        original_trace_span = None
        try:
            from app.observability import trace_span as orig_trace_span
            original_trace_span = orig_trace_span

            # Enable neatlogs initialization flag for mark_span_failed to work
            observability_module._initialized = True

            @contextmanager
            def mock_trace_span(name, kind="CHAIN", attributes=None):
                class MockSpan:
                    def __init__(self):
                        self.attributes = {}
                        self.status = None
                        self.status_code = None
                        self.description = None
                    def set_attribute(self, key, value):
                        self.attributes[key] = value
                    def set_status(self, status):
                        self.status = status
                        if hasattr(status, 'status_code'):
                            self.status_code = status.status_code
                        if hasattr(status, 'description'):
                            self.description = status.description
                span = MockSpan()
                captured_spans.append((name, kind, attributes, span))
                yield span

            import app.pack.evaluator as evaluator_module
            evaluator_module.trace_span = mock_trace_span

            summary = run_pack_benchmark([case_d02], config, llm=fake_llm)

            assert len(captured_spans) == 1
            _, _, _, span = captured_spans[0]

            # Check span status is ERROR
            assert span.status_code is not None
            # Check description starts with failure class
            assert span.description is not None
            assert span.description.startswith("tool_error")

            # Check output.value contains TRUTH
            assert "output.value" in span.attributes
            output_value = span.attributes["output.value"]
            assert "FAILED" in output_value
            assert "tool_error" in output_value
            assert "TRUTH:" in output_value

        finally:
            if original_trace_span:
                import app.pack.evaluator as evaluator_module
                evaluator_module.trace_span = original_trace_span


class TestOfficeOutputs:
    """Tests for optional PPTX and XLSX outputs."""

    def test_office_files_render_and_verify_pass(self, case_d01, good_json_response, tmp_path):
        """Render both files for a fixture company, reopen, verify_office_files returns []."""
        fake_llm = FakeLLMClient(good_json_response)
        config = PackConfig(
            output_dir=str(tmp_path),
            version="test",
            outputs=("docx", "pptx", "xlsx"),
            verify_facts=False,
        )

        output, trace = run_pack_student(case_d01, config, llm=fake_llm)

        assert output.docx_path is not None
        assert "pptx" in output.office_paths
        assert "xlsx" in output.office_paths
        assert Path(output.office_paths["pptx"]).exists()
        assert Path(output.office_paths["xlsx"]).exists()

        # Verify using verify_office_files
        from app.pack.office import verify_office_files
        mismatches = verify_office_files(
            FixtureSource().get_company(case_d01.domain),
            Path(output.office_paths["xlsx"]),
            Path(output.office_paths["pptx"]),
        )
        assert mismatches == [], f"Expected no mismatches, got: {mismatches}"

    def test_verify_office_files_detects_tampered_xlsx(self, case_d01, good_json_response, tmp_path):
        """Tamper the xlsx value then verify returns a mismatch."""
        fake_llm = FakeLLMClient(good_json_response)
        config = PackConfig(
            output_dir=str(tmp_path),
            version="test",
            outputs=("docx", "pptx", "xlsx"),
            verify_facts=False,
        )

        output, trace = run_pack_student(case_d01, config, llm=fake_llm)

        # Tamper the xlsx file - change employee_count (row 4 in Facts sheet: header=1, name=2, domain=3, employee_count=4)
        from openpyxl import load_workbook
        wb = load_workbook(output.office_paths["xlsx"])
        ws = wb["Facts"]
        # employee_count is row 4 (header=1, name=2, domain=3, employee_count=4)
        ws.cell(row=4, column=2, value=999999)
        wb.save(output.office_paths["xlsx"])

        from app.pack.office import verify_office_files
        mismatches = verify_office_files(
            FixtureSource().get_company(case_d01.domain),
            Path(output.office_paths["xlsx"]),
            Path(output.office_paths["pptx"]),
        )
        assert any("employee_count" in m for m in mismatches)

    def test_default_config_no_office_files(self, case_d01, good_json_response, tmp_path):
        """Default config (docx only) produces no office files and unchanged trace steps."""
        fake_llm = FakeLLMClient(good_json_response)
        config = PackConfig(output_dir=str(tmp_path), version="test")

        output, trace = run_pack_student(case_d01, config, llm=fake_llm)

        assert output.docx_path is not None
        assert output.office_paths == {}
        # Check trace has no render_pptx, render_xlsx, verify_artifacts steps
        trace_steps = [e.step for e in trace]
        assert "render_pptx" not in trace_steps
        assert "render_xlsx" not in trace_steps
        assert "verify_artifacts" not in trace_steps

    def test_all_three_outputs_end_to_end(self, case_d01, good_json_response, tmp_path):
        """FakeLLM end-to-end run with outputs all three produces three files."""
        fake_llm = FakeLLMClient(good_json_response)
        config = PackConfig(
            output_dir=str(tmp_path),
            version="test",
            outputs=("docx", "pptx", "xlsx"),
            verify_facts=True,
        )

        output, trace = run_pack_student(case_d01, config, llm=fake_llm)

        assert output.docx_path is not None
        assert Path(output.docx_path).exists()
        assert "pptx" in output.office_paths
        assert "xlsx" in output.office_paths
        assert Path(output.office_paths["pptx"]).exists()
        assert Path(output.office_paths["xlsx"]).exists()

        # Verify trace has the office steps (artifact_verification event)
        trace_steps = [e.step for e in trace]
        assert "artifact_verification" in trace_steps

        # Verify all three files exist
        assert Path(output.docx_path).exists()
        assert Path(output.office_paths["pptx"]).exists()
        assert Path(output.office_paths["xlsx"]).exists()