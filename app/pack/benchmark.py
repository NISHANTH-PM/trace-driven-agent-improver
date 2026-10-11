"""Pack benchmark case loading."""

from app.pack.models import CompanyCase


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


def pack_cases_for_split(split: str) -> list[CompanyCase]:
    """Return cases filtered by split."""
    cases = load_pack_cases()
    if split not in ("development", "held_out"):
        raise ValueError(f"Invalid split: {split}. Must be 'development' or 'held_out'.")
    return [c for c in cases if c.split == split]