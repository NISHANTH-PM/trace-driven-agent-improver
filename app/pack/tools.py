"""Pack data access tools."""

import json
from pathlib import Path
from typing import Any

from app.pack.models import CompanyData


FIXTURES_PATH = Path(__file__).parent.parent.parent / "data" / "fixtures" / "companies.json"


class ToolError(Exception):
    """Raised when a tool operation fails."""
    pass


class FixtureSource:
    """Reads company data from the local JSON fixture."""

    def __init__(self):
        self._data: dict[str, CompanyData] = {}
        self._load()

    def _load(self) -> None:
        with FIXTURES_PATH.open() as f:
            raw = json.load(f)
        for company in raw["companies"]:
            self._data[company["domain"]] = CompanyData(**company)

    def get_company(self, domain: str, attempt: int = 1) -> CompanyData:
        """Get company by domain. Raises ToolError if not found."""
        if domain not in self._data:
            raise ToolError("not found")
        return self._data[domain]


class FlakySource:
    """Wraps a source and fails first N attempts for configured domains."""

    def __init__(self, inner: FixtureSource, fail_first: dict[str, int]):
        self._inner = inner
        self._fail_first = fail_first
        self._attempts: dict[str, int] = {}

    def get_company(self, domain: str, attempt: int = 1) -> CompanyData:
        """Get company, failing for configured domains on early attempts."""
        if domain not in self._attempts:
            self._attempts[domain] = 0
        self._attempts[domain] += 1

        fail_count = self._fail_first.get(domain, 0)
        if self._attempts[domain] <= fail_count:
            raise ToolError("upstream 503")

        return self._inner.get_company(domain, attempt)


def default_source() -> FlakySource:
    """Default source with flaky domains for D02, D05, H02."""
    fail_first = {
        "meridian-bio.com": 1,      # D02
        "quantumleap-analytics.com": 1,  # D05
        "orbit-comm.com": 1,        # H02
    }
    return FlakySource(FixtureSource(), fail_first)