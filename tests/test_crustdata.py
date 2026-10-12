"""Tests for Crustdata source and snapshot functionality."""

import json
from unittest.mock import Mock, patch

import pytest

from app.pack.crustdata import CrustdataSource, map_company
from app.pack.models import CompanyData
from app.pack.tools import SnapshotSource, ToolError, truth_source
from app.pack.benchmark import pack_cases_for_split


class TestMapCompany:
    """Tests for map_company function."""

    def test_happy_path(self):
        """Test mapping with all fields present."""
        company_data = {
            "basic_info": {
                "name": "Test Corp",
                "company_type": "Technology",
                "description": "A test company",
                "year_founded": 2020,
            },
            "headcount": {"total": 100},
            "funding": {"total_investment_usd": 5000000, "last_round_type": "Series A"},
            "locations": {"headquarters": "San Francisco, CA, USA"},
        }
        result = map_company(company_data, "test.com")
        
        assert isinstance(result, CompanyData)
        assert result.name == "Test Corp"
        assert result.domain == "test.com"
        assert result.industry == "Technology"
        assert result.description == "A test company"
        assert result.employee_count == 100
        assert result.founded_year == 2020
        assert result.hq_city == "San Francisco"
        assert result.total_funding_usd == 5000000
        assert result.last_round == "Series A"

    def test_funding_none_to_zero_and_bootstrapped(self):
        """Test funding None -> 0 and last_round None -> 'Bootstrapped'."""
        company_data = {
            "basic_info": {
                "name": "Test Corp",
                "company_type": "Technology",
                "description": "",
                "year_founded": 2020,
            },
            "headcount": {"total": 100},
            "funding": {"total_investment_usd": None, "last_round_type": None},
            "locations": {"headquarters": "San Francisco, CA, USA"},
        }
        result = map_company(company_data, "test.com")
        
        assert result.total_funding_usd == 0
        assert result.last_round == "Bootstrapped"

    def test_missing_employee_count_raises(self):
        """Test missing employee_count raises ToolError."""
        company_data = {
            "basic_info": {
                "name": "Test Corp",
                "company_type": "Technology",
                "description": "",
                "year_founded": 2020,
            },
            "headcount": {},  # missing total
            "funding": {"total_investment_usd": 5000000, "last_round_type": "Series A"},
            "locations": {"headquarters": "San Francisco, CA, USA"},
        }
        with pytest.raises(ToolError, match="incomplete data: employee_count"):
            map_company(company_data, "test.com")

    def test_missing_founded_year_raises(self):
        """Test missing founded_year raises ToolError."""
        company_data = {
            "basic_info": {
                "name": "Test Corp",
                "company_type": "Technology",
                "description": "",
                # missing year_founded
            },
            "headcount": {"total": 100},
            "funding": {"total_investment_usd": 5000000, "last_round_type": "Series A"},
            "locations": {"headquarters": "San Francisco, CA, USA"},
        }
        with pytest.raises(ToolError, match="incomplete data: founded_year"):
            map_company(company_data, "test.com")

    def test_missing_hq_city_raises(self):
        """Test missing hq_city raises ToolError."""
        company_data = {
            "basic_info": {
                "name": "Test Corp",
                "company_type": "Technology",
                "description": "",
                "year_founded": 2020,
            },
            "headcount": {"total": 100},
            "funding": {"total_investment_usd": 5000000, "last_round_type": "Series A"},
            "locations": {},  # missing headquarters
        }
        with pytest.raises(ToolError, match="incomplete data: hq_city"):
            map_company(company_data, "test.com")

    def test_hq_city_from_dict(self):
        """Test hq_city extraction from dict."""
        company_data = {
            "basic_info": {"name": "Test", "company_type": "Tech", "description": "", "year_founded": 2020},
            "headcount": {"total": 100},
            "funding": {"total_investment_usd": 5000000, "last_round_type": "Series A"},
            "locations": {"headquarters": {"city": "Bengaluru", "state": "Karnataka"}},
        }
        result = map_company(company_data, "test.com")
        assert result.hq_city == "Bengaluru"

    def test_hq_city_prefers_locations_city(self):
        """Test hq_city uses locations.city when present (string)."""
        company_data = {
            "basic_info": {"name": "Test", "company_type": "Tech", "description": "", "year_founded": 2020},
            "headcount": {"total": 100},
            "funding": {"total_investment_usd": 5000000, "last_round_type": "Series A"},
            "locations": {
                "city": "Bengaluru",
                "headquarters": "Adugodi, Karnataka, India"
            },
        }
        result = map_company(company_data, "test.com")
        assert result.hq_city == "Bengaluru"

    def test_hq_city_falls_back_to_headquarters_when_city_empty(self):
        """Test hq_city falls back to headquarters first comma segment when city is empty."""
        company_data = {
            "basic_info": {"name": "Test", "company_type": "Tech", "description": "", "year_founded": 2020},
            "headcount": {"total": 100},
            "funding": {"total_investment_usd": 5000000, "last_round_type": "Series A"},
            "locations": {
                "city": "",
                "headquarters": "San Francisco, CA, USA"
            },
        }
        result = map_company(company_data, "test.com")
        assert result.hq_city == "San Francisco"

    def test_hq_city_falls_back_to_headquarters_when_city_missing(self):
        """Test hq_city falls back to headquarters when city key is missing."""
        company_data = {
            "basic_info": {"name": "Test", "company_type": "Tech", "description": "", "year_founded": 2020},
            "headcount": {"total": 100},
            "funding": {"total_investment_usd": 5000000, "last_round_type": "Series A"},
            "locations": {
                "headquarters": "London, England, UK"
            },
        }
        result = map_company(company_data, "test.com")
        assert result.hq_city == "London"

    def test_hq_city_title_cases_all_upper(self):
        """Test hq_city converts all-uppercase city to title case."""
        company_data = {
            "basic_info": {"name": "Test", "company_type": "Tech", "description": "", "year_founded": 2020},
            "headcount": {"total": 100},
            "funding": {"total_investment_usd": 5000000, "last_round_type": "Series A"},
            "locations": {
                "city": "DARLINGHURST",
                "headquarters": "Darlinghurst, NSW, Australia"
            },
        }
        result = map_company(company_data, "test.com")
        assert result.hq_city == "Darlinghurst"

    def test_hq_city_title_cases_all_upper_from_headquarters(self):
        """Test hq_city converts all-uppercase from headquarters when city missing."""
        company_data = {
            "basic_info": {"name": "Test", "company_type": "Tech", "description": "", "year_founded": 2020},
            "headcount": {"total": 100},
            "funding": {"total_investment_usd": 5000000, "last_round_type": "Series A"},
            "locations": {
                "headquarters": "DARLINGHURST, NSW, Australia"
            },
        }
        result = map_company(company_data, "test.com")
        assert result.hq_city == "Darlinghurst"

    def test_hq_city_preserves_mixed_case(self):
        """Test hq_city preserves mixed-case city names."""
        company_data = {
            "basic_info": {"name": "Test", "company_type": "Tech", "description": "", "year_founded": 2020},
            "headcount": {"total": 100},
            "funding": {"total_investment_usd": 5000000, "last_round_type": "Series A"},
            "locations": {
                "city": "San Francisco",
                "headquarters": "San Francisco, CA, USA"
            },
        }
        result = map_company(company_data, "test.com")
        assert result.hq_city == "San Francisco"


class TestCrustdataSource:
    """Tests for CrustdataSource class."""

    @patch("app.pack.crustdata.requests.post")
    def test_http_401_raises_tool_error_no_key(self, mock_post):
        """Test HTTP 401 raises ToolError without exposing key."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.headers = {}
        mock_post.return_value = mock_response
        
        source = CrustdataSource.__new__(CrustdataSource)
        source._api_key = "test-key"
        source._last_credits_used = 0
        
        with pytest.raises(ToolError, match="HTTP 401"):
            source.get_company("test.com")
        # Ensure the error message doesn't contain the API key
        assert "test-key" not in str(ToolError("HTTP 401"))

    @patch("app.pack.crustdata.requests.post")
    def test_empty_matches_raises_tool_error(self, mock_post):
        """Test empty matches raises ToolError."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"matched_on": "domain", "match_type": "exact", "matches": []}]
        mock_response.headers = {}
        mock_post.return_value = mock_response
        
        source = CrustdataSource.__new__(CrustdataSource)
        source._api_key = "test-key"
        source._last_credits_used = 0
        
        with pytest.raises(ToolError, match="no match"):
            source.get_company("test.com")

    @patch("app.pack.crustdata.requests.post")
    def test_network_error_raises_tool_error(self, mock_post):
        """Test network exception raises ToolError."""
        import requests
        mock_post.side_effect = requests.RequestException("connection failed")
        
        source = CrustdataSource.__new__(CrustdataSource)
        source._api_key = "test-key"
        source._last_credits_used = 0
        
        with pytest.raises(ToolError, match="network error"):
            source.get_company("test.com")

    @patch("app.pack.crustdata.requests.post")
    def test_successful_response(self, mock_post):
        """Test successful response maps correctly."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{
            "matched_on": "domain",
            "match_type": "exact",
            "matches": [{
                "confidence_score": 0.95,
                "company_data": {
                    "basic_info": {"name": "Test Corp", "company_type": "Technology", "description": "Desc", "year_founded": 2020},
                    "headcount": {"total": 100},
                    "funding": {"total_investment_usd": 5000000, "last_round_type": "Series A"},
                    "locations": {"headquarters": "San Francisco, CA, USA"},
                }
            }]
        }]
        mock_response.headers = {"X-Credits-Used": "2"}
        mock_post.return_value = mock_response
        
        source = CrustdataSource.__new__(CrustdataSource)
        source._api_key = "test-key"
        source._last_credits_used = 0
        
        result = source.get_company("test.com")
        
        assert isinstance(result, CompanyData)
        assert result.name == "Test Corp"
        assert source.last_credits_used == 2


class TestSnapshotSource:
    """Tests for SnapshotSource class."""

    def test_loads_snapshot(self, tmp_path):
        """Test SnapshotSource loads data correctly."""
        # Create a mock snapshot file
        snapshot_data = {
            "_note": "Test snapshot",
            "companies": [
                {
                    "name": "Test Corp",
                    "domain": "test.com",
                    "industry": "Technology",
                    "description": "A test company",
                    "employee_count": 100,
                    "founded_year": 2020,
                    "hq_city": "San Francisco",
                    "total_funding_usd": 5000000,
                    "last_round": "Series A",
                }
            ],
            "dev_domains": ["test.com"],
            "held_out_domains": [],
        }
        snapshot_file = tmp_path / "companies_real.json"
        with snapshot_file.open("w") as f:
            json.dump(snapshot_data, f)
        
        # Patch the path
        import app.pack.tools as tools_module
        original_path = tools_module.SNAPSHOTS_PATH
        tools_module.SNAPSHOTS_PATH = snapshot_file
        
        try:
            source = SnapshotSource()
            company = source.get_company("test.com")
            assert company.name == "Test Corp"
            assert source.get_dev_domains() == ["test.com"]
            assert source.get_held_domains() == []
        finally:
            tools_module.SNAPSHOTS_PATH = original_path


class TestPackSourceEnv:
    """Tests for PACK_SOURCE environment variable."""

    def test_snapshot_yields_6_dev_4_held(self, tmp_path, monkeypatch):
        """Test PACK_SOURCE=snapshot yields 6 dev + 4 held-out cases."""
        # Create a mock snapshot file with 6 dev and 4 held-out
        companies = []
        dev_domains = [f"dev{i}.com" for i in range(1, 7)]
        held_domains = [f"held{i}.com" for i in range(1, 5)]
        
        for i, domain in enumerate(dev_domains, 1):
            companies.append({
                "name": f"Dev Company {i}",
                "domain": domain,
                "industry": "Technology",
                "description": "",
                "employee_count": 100,
                "founded_year": 2020,
                "hq_city": "San Francisco",
                "total_funding_usd": 5000000,
                "last_round": "Series A",
            })
        
        for i, domain in enumerate(held_domains, 1):
            companies.append({
                "name": f"Held Company {i}",
                "domain": domain,
                "industry": "Technology",
                "description": "",
                "employee_count": 100,
                "founded_year": 2020,
                "hq_city": "San Francisco",
                "total_funding_usd": 5000000,
                "last_round": "Series A",
            })
        
        snapshot_data = {
            "_note": "Test snapshot",
            "companies": companies,
            "dev_domains": dev_domains,
            "held_out_domains": held_domains,
        }
        snapshot_file = tmp_path / "companies_real.json"
        with snapshot_file.open("w") as f:
            json.dump(snapshot_data, f)
        
        # Patch the path and env
        import app.pack.tools as tools_module
        original_path = tools_module.SNAPSHOTS_PATH
        tools_module.SNAPSHOTS_PATH = snapshot_file
        
        monkeypatch.setenv("PACK_SOURCE", "snapshot")
        
        try:
            # Need to reload the module to pick up the env var
            import importlib
            import app.pack.benchmark as benchmark_module
            importlib.reload(benchmark_module)
            
            dev_cases = benchmark_module.pack_cases_for_split("development")
            held_cases = benchmark_module.pack_cases_for_split("held_out")
            
            assert len(dev_cases) == 6
            assert len(held_cases) == 4
            assert all(c.split == "development" for c in dev_cases)
            assert all(c.split == "held_out" for c in held_cases)
        finally:
            tools_module.SNAPSHOTS_PATH = original_path
            monkeypatch.delenv("PACK_SOURCE", raising=False)
            importlib.reload(benchmark_module)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])