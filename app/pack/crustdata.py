"""Crustdata Company Enrich API integration."""

import os
import requests
from typing import Any

from app.pack.models import CompanyData
from app.pack.tools import ToolError


CRUSTDATA_API_URL = "https://api.crustdata.com/company/enrich"
CRUSTDATA_API_VERSION = "2025-11-01"
CRUSTDATA_FIELDS = ["basic_info", "headcount", "funding", "locations"]


def _extract_hq_city(locations: dict[str, Any]) -> str:
    """Extract HQ city from locations data. Prefer locations.city if present."""
    city = locations.get("city")
    if isinstance(city, str) and city.strip():
        return city.strip()
    
    hq = locations.get("headquarters")
    if not hq:
        return ""
    
    if isinstance(hq, str):
        # Format like "Bengaluru, Karnataka, India" -> take part before first comma
        return hq.split(",")[0].strip()
    elif isinstance(hq, dict):
        # Try common city-like keys
        for key in ["city", "headquarters_city", "hq_city", "location"]:
            if key in hq and hq[key]:
                return str(hq[key]).strip()
        # Fallback to first non-empty value
        for v in hq.values():
            if v:
                return str(v).split(",")[0].strip()
    return ""


def map_company(company_data: dict[str, Any], domain: str) -> CompanyData:
    """Map Crustdata API response to CompanyData."""
    basic_info = company_data.get("basic_info", {})
    headcount = company_data.get("headcount", {})
    funding = company_data.get("funding", {})
    locations = company_data.get("locations", {})
    
    name = basic_info.get("name", "")
    industry = basic_info.get("company_type") or "Technology"
    description = basic_info.get("description", "") or ""
    employee_count = headcount.get("total")
    founded_year = basic_info.get("year_founded")
    hq_city = _extract_hq_city(locations)
    total_funding_usd = funding.get("total_investment_usd") or 0
    last_round = funding.get("last_round_type") or "Bootstrapped"
    
    missing = []
    if employee_count is None:
        missing.append("employee_count")
    if founded_year is None:
        missing.append("founded_year")
    if not hq_city:
        missing.append("hq_city")
    
    if missing:
        raise ToolError(f"incomplete data: {', '.join(missing)}")
    
    return CompanyData(
        name=name,
        domain=domain,
        industry=industry,
        description=description,
        employee_count=employee_count,
        founded_year=founded_year,
        hq_city=hq_city,
        total_funding_usd=total_funding_usd,
        last_round=last_round,
    )


class CrustdataSource:
    """Fetches company data from Crustdata Company Enrich API."""
    
    def __init__(self):
        api_key = os.getenv("CRUSTDATA_API_KEY")
        if not api_key:
            raise ValueError("CRUSTDATA_API_KEY must be set in environment")
        self._api_key = api_key
        self._last_credits_used = 0
    
    @property
    def last_credits_used(self) -> int:
        return self._last_credits_used
    
    def get_company(self, domain: str, attempt: int = 1) -> CompanyData:
        """Get company data from Crustdata API."""
        headers = {
            "authorization": f"Bearer {self._api_key}",
            "x-api-version": CRUSTDATA_API_VERSION,
            "content-type": "application/json",
        }
        payload = {
            "domains": [domain],
            "fields": CRUSTDATA_FIELDS,
        }
        
        try:
            response = requests.post(
                CRUSTDATA_API_URL,
                headers=headers,
                json=payload,
                timeout=30,
            )
        except requests.RequestException as e:
            raise ToolError(f"network error: {e}")
        
        # Read credits used from header if present
        credits_header = response.headers.get("X-Credits-Used")
        if credits_header:
            try:
                self._last_credits_used = int(credits_header)
            except ValueError:
                pass
        
        if response.status_code != 200:
            raise ToolError(f"HTTP {response.status_code}")
        
        try:
            data = response.json()
        except ValueError:
            raise ToolError("invalid JSON response")
        
        if not isinstance(data, list) or len(data) == 0:
            raise ToolError("unexpected response format")
        
        result = data[0]
        matches = result.get("matches", [])
        
        if not matches:
            raise ToolError("no match")
        
        # Use highest confidence_score match
        best_match = max(matches, key=lambda m: m.get("confidence_score", 0))
        company_data = best_match.get("company_data", {})
        
        return map_company(company_data, domain)