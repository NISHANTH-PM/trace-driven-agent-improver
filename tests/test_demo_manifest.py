"""Tests for demo run manifest builder."""

import json
import tempfile
from pathlib import Path

import pytest

from scripts.demo_run import write_manifest


def sample_results():
    """Return sample results for testing."""
    return [
        {
            "label": "baseline_wrong_fact",
            "case_id": "D01",
            "company": "Test Corp",
            "domain": "test.com",
            "config": {
                "retry_tool_errors": False,
                "strict_prompt": False,
                "verify_facts": False,
                "version": "baseline",
            },
            "failure_class": "wrong_fact",
            "success": False,
            "tool_attempts": 1,
            "llm_calls": 1,
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "cost_usd": 0.00001,
            "docx_path": "outputs/demo/baseline_wrong_fact/D01_baseline.docx",
            "start_time_utc": "2026-10-12T00:00:00+00:00",
            "end_time_utc": "2026-10-12T00:00:05+00:00",
            "issues": ["employee_count=100 not stated exactly"],
            "true_values": {
                "employee_count": 100,
                "founded_year": 2020,
                "hq_city": "San Francisco",
                "total_funding_usd": 1000000,
                "last_round": "Series A",
            },
        },
        {
            "label": "candidate_success",
            "case_id": "D01",
            "company": "Test Corp",
            "domain": "test.com",
            "config": {
                "retry_tool_errors": True,
                "strict_prompt": True,
                "verify_facts": True,
                "version": "candidate",
            },
            "failure_class": "none",
            "success": True,
            "tool_attempts": 1,
            "llm_calls": 1,
            "prompt_tokens": 150,
            "completion_tokens": 80,
            "cost_usd": 0.00002,
            "docx_path": "outputs/demo/candidate_success/D01_candidate.docx",
            "start_time_utc": "2026-10-12T00:01:00+00:00",
            "end_time_utc": "2026-10-12T00:01:05+00:00",
            "issues": [],
            "true_values": {
                "employee_count": 100,
                "founded_year": 2020,
                "hq_city": "San Francisco",
                "total_funding_usd": 1000000,
                "last_round": "Series A",
            },
        },
    ]


def test_write_manifest_creates_file(tmp_path):
    """Test that write_manifest creates a valid markdown file."""
    manifest_path = tmp_path / "demo_manifest.md"
    results = sample_results()
    
    write_manifest(results, manifest_path)
    
    assert manifest_path.exists()
    content = manifest_path.read_text()
    
    # Check basic structure
    assert "# Demo Run Manifest" in content
    assert "## baseline_wrong_fact" in content
    assert "## candidate_success" in content
    assert "## Screenshot Checklist" in content
    
    # Check fields for first scenario
    assert "baseline_wrong_fact" in content
    assert "D01" in content
    assert "Test Corp" in content
    assert "wrong_fact" in content
    assert "employee_count=100 not stated exactly" in content
    assert "employee_count: 100" in content
    assert "founded_year: 2020" in content
    assert "hq_city: San Francisco" in content
    assert "total_funding_usd: 1000000" in content
    assert "last_round: Series A" in content
    assert "demo.label = baseline_wrong_fact" in content
    
    # Check fields for second scenario
    assert "candidate_success" in content
    assert "none" in content  # failure_class
    assert "success" in content.lower()


def test_write_manifest_includes_docx_paths(tmp_path):
    """Test that manifest includes D01 baseline and candidate docx paths."""
    manifest_path = tmp_path / "demo_manifest.md"
    results = sample_results()
    
    write_manifest(results, manifest_path)
    
    content = manifest_path.read_text()
    
    assert "outputs/demo/baseline_wrong_fact/D01_baseline.docx" in content
    assert "outputs/demo/candidate_success/D01_candidate.docx" in content
    assert "Open both in Word: agent_output_docx.png" in content


def test_write_manifest_handles_empty_results(tmp_path):
    """Test write_manifest with empty results list."""
    manifest_path = tmp_path / "demo_manifest.md"
    results = []
    
    write_manifest(results, manifest_path)
    
    assert manifest_path.exists()
    content = manifest_path.read_text()
    assert "# Demo Run Manifest" in content
    assert "## Screenshot Checklist" in content


def test_write_manifest_handles_verify_regeneration_none(tmp_path):
    """Test manifest handles verify_regeneration with no case."""
    manifest_path = tmp_path / "demo_manifest.md"
    results = sample_results() + [
        {
            "label": "verify_regeneration",
            "case_id": "none",
            "company": "none",
            "domain": "none",
            "config": {
                "retry_tool_errors": False,
                "strict_prompt": False,
                "verify_facts": True,
                "version": "verify_only",
            },
            "failure_class": "none",
            "success": False,
            "tool_attempts": 0,
            "llm_calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost_usd": 0.0,
            "docx_path": None,
            "start_time_utc": "2026-10-12T00:02:00+00:00",
            "end_time_utc": "2026-10-12T00:02:00+00:00",
            "issues": [],
            "true_values": {},
        }
    ]
    
    write_manifest(results, manifest_path)
    
    content = manifest_path.read_text()
    assert "verify_regeneration" in content
    assert "none" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])