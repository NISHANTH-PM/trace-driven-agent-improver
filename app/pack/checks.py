"""Pack fact-checking utilities."""

import re

from app.pack.models import CompanyData, REQUIRED_SECTIONS


def missing_sections(sections: dict) -> list[str]:
    """Return names of REQUIRED_SECTIONS that are absent or blank."""
    missing = []
    for name in REQUIRED_SECTIONS:
        if name not in sections or not sections[name].strip():
            missing.append(name)
    return missing


def fact_mismatches(company: CompanyData, sections: dict) -> list[str]:
    """Check that key facts from CompanyData appear in the sections text."""
    issues = []
    text = " ".join(sections.values()).lower()

    # employee_count: exact "4000" or "4,000"
    emp_str = str(company.employee_count)
    emp_str_comma = f"{company.employee_count:,}"
    if emp_str not in text and emp_str_comma not in text:
        issues.append(f"employee_count={company.employee_count} not stated exactly")

    # founded_year: exact year string
    year_str = str(company.founded_year)
    if year_str not in text:
        issues.append(f"founded_year={year_str} not stated exactly")

    # hq_city: city name substring (case-insensitive)
    if company.hq_city.lower() not in text:
        issues.append(f"hq_city={company.hq_city} not stated")

    # last_round: substring (case-insensitive)
    if company.last_round.lower() not in text:
        issues.append(f"last_round={company.last_round} not stated")

    # total_funding_usd
    usd = company.total_funding_usd
    if usd == 0:
        # bootstrapped case
        bootstrapped_terms = ["bootstrapped", "no external funding", "$0"]
        if not any(term in text for term in bootstrapped_terms):
            issues.append("total_funding_usd=0 not stated (expected 'bootstrapped', 'no external funding', or '$0')")
    else:
        m = usd / 1_000_000
        # Build accepted forms
        accepted = [
            f"{usd:,}",  # 42,000,000
            str(usd),    # 42000000
            f"${m:g}M",  # $42M
            f"{m:g}M",   # 42M
            f"${m:g} million",  # $42 million
            f"{m:g} million",   # 42 million
        ]
        # Also handle cases where M is capitalized differently
        accepted += [a.replace("M", "m") for a in accepted]
        accepted += [a.replace("million", "Million") for a in accepted]

        if not any(term.lower() in text for term in accepted):
            issues.append(f"total_funding_usd={usd} not stated in accepted format")

    return issues