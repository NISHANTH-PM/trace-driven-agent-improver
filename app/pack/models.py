"""Pack domain models (Pydantic v2)."""

from typing import Literal

from pydantic import BaseModel, Field


class CompanyData(BaseModel):
    """Company data from Crustdata fixture."""

    name: str
    domain: str
    industry: str
    description: str
    employee_count: int
    founded_year: int
    hq_city: str
    total_funding_usd: int
    last_round: str


class CompanyCase(BaseModel):
    """Benchmark case referencing a company fixture."""

    case_id: str
    company_name: str
    domain: str
    split: Literal["development", "held_out"]


class PackOutput(BaseModel):
    """Output from the pack agent."""

    case_id: str
    docx_path: str | None
    sections: dict[str, str]
    claimed_facts: dict[str, str | int]
    verified: bool
    tool_attempts: int
    rationale: str
    office_paths: dict[str, str] = Field(default_factory=dict)


REQUIRED_SECTIONS = ["Overview", "Key Facts", "Funding", "Risks"]