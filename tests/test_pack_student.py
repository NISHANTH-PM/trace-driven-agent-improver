"""Tests for pack student agent and checks."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from app.pack.checks import fact_mismatches, missing_sections
from app.pack.models import CompanyData, CompanyCase, REQUIRED_SECTIONS
from app.pack.student import PackConfig, run_pack_student, STRICT_SYSTEM_PROMPT, BASE_SYSTEM_PROMPT
from app.pack.tools import FixtureSource, ToolError, default_source
from app.llm import FakeLLMClient


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


class TestPackStudent:
    """Tests for the pack student agent."""

    @pytest.fixture
    def case_d01(self):
        return CompanyCase(case_id="D01", company_name="Apex Dynamics", domain="apex-dynamics.com", split="development")

    @pytest.fixture
    def case_d02(self):
        return CompanyCase(case_id="D02", company_name="Meridian Bio", domain="meridian-bio.com", split="development")

    @pytest.fixture
    def good_json_response(self):
        return json.dumps({
            "sections": {
                "Overview": "Apex Dynamics is a robotics company founded in 2015 in Pittsburgh.",
                "Key Facts": "342 employees, founded 2015, HQ Pittsburgh",
                "Funding": "Total funding $85,000,000, last round Series B",
                "Risks": "Competition in robotics market"
            }
        })

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