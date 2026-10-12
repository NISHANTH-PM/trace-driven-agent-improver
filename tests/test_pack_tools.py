"""Tests for pack tools and fixtures."""

import pytest

from app.pack.benchmark import load_pack_cases, pack_cases_for_split
from app.pack.models import CompanyData
from app.pack.tools import FixtureSource, FlakySource, ToolError, default_source


class TestFixtures:
    """Tests for the company fixtures."""

    def test_loads_all_10_companies(self):
        source = FixtureSource()
        companies = []
        for domain in [
            "apex-dynamics.com",
            "meridian-bio.com",
            "solaris-grid.com",
            "nexus-logistics.com",
            "quantumleap-analytics.com",
            "verdant-foods.com",
            "ironclad-security.com",
            "orbit-comm.com",
            "astraea-materials.com",
            "cedar-health.com",
        ]:
            company = source.get_company(domain)
            assert isinstance(company, CompanyData)
            companies.append(company)
        assert len(companies) == 10

    def test_unknown_domain_raises(self):
        source = FixtureSource()
        with pytest.raises(ToolError, match="not found"):
            source.get_company("unknown-domain.com")

    def test_all_companies_have_required_fields(self):
        source = FixtureSource()
        for domain in [
            "apex-dynamics.com",
            "meridian-bio.com",
            "solaris-grid.com",
            "nexus-logistics.com",
            "quantumleap-analytics.com",
            "verdant-foods.com",
            "ironclad-security.com",
            "orbit-comm.com",
            "astraea-materials.com",
            "cedar-health.com",
        ]:
            company = source.get_company(domain)
            assert company.name
            assert company.domain == domain
            assert company.industry
            assert company.description
            assert 15 <= company.employee_count <= 4000
            assert 2008 <= company.founded_year <= 2022
            assert 0 <= company.total_funding_usd <= 400_000_000
            assert company.hq_city
            assert company.last_round


class TestFlakySource:
    """Tests for FlakySource wrapper."""

    def test_flaky_fails_on_attempt_1_succeeds_on_attempt_2(self):
        source = default_source()
        domain = "meridian-bio.com"  # D02

        # First attempt should fail
        with pytest.raises(ToolError, match="upstream 503"):
            source.get_company(domain)

        # Second attempt should succeed
        company = source.get_company(domain)
        assert company.name == "Meridian Bio"
        assert company.domain == domain

    def test_d05_flaky(self):
        source = default_source()
        domain = "quantumleap-analytics.com"  # D05

        with pytest.raises(ToolError, match="upstream 503"):
            source.get_company(domain)

        company = source.get_company(domain)
        assert company.name == "QuantumLeap Analytics"

    def test_h02_flaky(self):
        source = default_source()
        domain = "orbit-comm.com"  # H02

        with pytest.raises(ToolError, match="upstream 503"):
            source.get_company(domain)

        company = source.get_company(domain)
        assert company.name == "Orbit Communications"

    def test_non_flaky_domains_work_on_first_attempt(self):
        source = default_source()
        domain = "apex-dynamics.com"  # D01 - not flaky

        company = source.get_company(domain)
        assert company.name == "Apex Dynamics"
        assert company.domain == domain


class TestBenchmarkCases:
    """Tests for benchmark case loading."""

    def test_development_split_has_6_cases(self):
        cases = pack_cases_for_split("development")
        assert len(cases) == 6
        assert all(c.split == "development" for c in cases)
        assert [c.case_id for c in cases] == ["D01", "D02", "D03", "D04", "D05", "D06"]

    def test_held_out_split_has_4_cases(self):
        cases = pack_cases_for_split("held_out")
        assert len(cases) == 4
        assert all(c.split == "held_out" for c in cases)
        assert [c.case_id for c in cases] == ["H01", "H02", "H03", "H04"]

    def test_all_10_cases_loaded(self):
        cases = load_pack_cases()
        assert len(cases) == 10

    def test_no_duplicate_domains(self):
        cases = load_pack_cases()
        domains = [c.domain for c in cases]
        assert len(domains) == len(set(domains)), f"Duplicate domains found: {domains}"

    def test_invalid_split_raises(self):
        with pytest.raises(ValueError, match="Invalid split"):
            pack_cases_for_split("invalid")

    def test_case_ids_match_expected(self):
        cases = load_pack_cases()
        case_ids = [c.case_id for c in cases]
        assert case_ids == ["D01", "D02", "D03", "D04", "D05", "D06", "H01", "H02", "H03", "H04"]