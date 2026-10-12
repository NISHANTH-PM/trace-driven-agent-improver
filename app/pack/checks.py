"""Pack fact-checking utilities."""

import re

from app.pack.models import CompanyData, REQUIRED_SECTIONS


def _normalize_for_fact_check(value: str) -> str:
    """Normalize a value for fuzzy fact checking: lowercase, replace underscores/hyphens with spaces, collapse whitespace."""
    v = value.lower()
    v = v.replace("_", " ").replace("-", " ")
    v = re.sub(r"\s+", " ", v).strip()
    return v


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

    # employee_count: exact "4000" or "4,000" (strict - no formatting changes)
    emp_str = str(company.employee_count)
    emp_str_comma = f"{company.employee_count:,}"
    if emp_str not in text and emp_str_comma not in text:
        issues.append(f"employee_count={company.employee_count} not stated exactly")

    # founded_year: exact year string (strict - no formatting changes)
    year_str = str(company.founded_year)
    if year_str not in text:
        issues.append(f"founded_year={year_str} not stated exactly")

    # hq_city: normalized comparison (case-insensitive, underscores/hyphens as spaces)
    hq_norm = _normalize_for_fact_check(company.hq_city)
    text_norm = _normalize_for_fact_check(text)
    if hq_norm not in text_norm:
        issues.append(f"hq_city={company.hq_city} not stated")

    # last_round: normalized comparison (case-insensitive, underscores/hyphens as spaces)
    lr_norm = _normalize_for_fact_check(company.last_round)
    if lr_norm not in text_norm:
        issues.append(f"last_round={company.last_round} not stated")

    # total_funding_usd: ensure int conversion, accept existing forms
    usd = int(company.total_funding_usd)
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