"""Pack benchmark case loading."""

import os

from app.pack.models import CompanyCase
from app.pack.tools import truth_source


def load_pack_cases() -> list[CompanyCase]:
    """Load all 10 pack benchmark cases."""
    return [
        CompanyCase(case_id="D01", company_name="Apex Dynamics", domain="apex-dynamics.com", split="development"),
        CompanyCase(case_id="D02", company_name="Meridian Bio", domain="meridian-bio.com", split="development"),
        CompanyCase(case_id="D03", company_name="Solaris Grid", domain="solaris-grid.com", split="development"),
        CompanyCase(case_id="D04", company_name="Nexus Logistics", domain="nexus-logistics.com", split="development"),
        CompanyCase(case_id="D05", company_name="QuantumLeap Analytics", domain="quantumleap-analytics.com", split="development"),
        CompanyCase(case_id="D06", company_name="Verdant Foods", domain="verdant-foods.com", split="development"),
        CompanyCase(case_id="H01", company_name="Ironclad Security", domain="ironclad-security.com", split="held_out"),
        CompanyCase(case_id="H02", company_name="Orbit Communications", domain="orbit-comm.com", split="held_out"),
        CompanyCase(case_id="H03", company_name="Astraea Materials", domain="astraea-materials.com", split="held_out"),
        CompanyCase(case_id="H04", company_name="Cedar Health", domain="cedar-health.com", split="held_out"),
    ]


def load_pack_cases_from_snapshot() -> list[CompanyCase]:
    """Load pack benchmark cases from Crustdata snapshot."""
    source = truth_source()
    if not hasattr(source, "get_dev_domains"):
        raise ValueError("truth_source does not support snapshot mode")
    
    dev_domains = source.get_dev_domains()
    held_domains = source.get_held_domains()
    
    cases = []
    for i, domain in enumerate(dev_domains, 1):
        company = source.get_company(domain)
        cases.append(CompanyCase(case_id=f"D{i:02d}", company_name=company.name, domain=domain, split="development"))
    
    for i, domain in enumerate(held_domains, 1):
        company = source.get_company(domain)
        cases.append(CompanyCase(case_id=f"H{i:02d}", company_name=company.name, domain=domain, split="held_out"))
    
    return cases


def pack_cases_for_split(split: str) -> list[CompanyCase]:
    """Return cases filtered by split."""
    pack_source = os.getenv("PACK_SOURCE", "fixtures").lower()
    
    if pack_source == "snapshot":
        cases = load_pack_cases_from_snapshot()
    else:
        cases = load_pack_cases()
    
    if split not in ("development", "held_out"):
        raise ValueError(f"Invalid split: {split}. Must be 'development' or 'held_out'.")
    return [c for c in cases if c.split == split]