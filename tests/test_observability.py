"""Tests for observability attribute preservation."""

import os

import pytest

# Ensure no real API key is used
os.environ.pop("NEATLOGS_API_KEY", None)

# InMemoryDiagnosticSpanExporter not available in neatlogs 1.4.26
pytest.importorskip("neatlogs", minversion="2.0.0", reason="InMemoryDiagnosticSpanExporter requires neatlogs >= 2.0.0")

from neatlogs import InMemoryDiagnosticSpanExporter
from neatlogs.init import shutdown
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.observability import initialize_neatlogs
from app.evaluator import run_benchmark
from app.student import StudentConfig
from app.benchmark import cases_for_split


@pytest.fixture
def in_memory_exporter():
    """Create an in-memory span exporter for testing."""
    provider = TracerProvider()
    exporter = InMemoryDiagnosticSpanExporter(max_spans=500)
    # Don't add processor yet - will add after init
    return provider, exporter


def test_benchmark_spans_preserve_custom_attributes(in_memory_exporter):
    """Test that benchmark evaluation spans preserve custom attributes through the pipeline."""
    provider, exporter = in_memory_exporter

    # Initialize Neatlogs with the test provider using the app's initialize function
    # This sets the _initialized flag in app.observability
    import neatlogs
    from neatlogs._wrap_utils import set_neatlogs_provider
    
    set_neatlogs_provider(provider)
    neatlogs.init(
        api_key="test-key",
        endpoint="https://ingest.neatlogs.com",
        workflow_name="test-workflow",
        tracer_provider=provider,
        disable_export=True,
    )
    # Now call the app's initialize to set the flag
    from app.observability import _initialized
    import app.observability as obs
    obs._initialized = True

    # Add our own batch processor with the in-memory exporter
    # (Neatlogs doesn't add one when disable_export=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))

    try:
        # Run a small benchmark
        dev_cases = cases_for_split("development")[:2]  # Just 2 cases
        config = StudentConfig(version="test-version")
        summary = run_benchmark(dev_cases, config)

        # Flush spans
        provider.force_flush(timeout_millis=5000)

        # Get the exported spans
        spans = exporter.get_finished_envelopes()

        # Find benchmark_case spans
        benchmark_spans = [s for s in spans if s.name == "benchmark_case"]
        assert len(benchmark_spans) == 2, f"Expected 2 benchmark_case spans, got {len(benchmark_spans)}"

        # Verify custom attributes are present on benchmark_case spans
        for span in benchmark_spans:
            attrs = span.attributes or {}
            assert "benchmark.case_id" in attrs, f"Missing benchmark.case_id in {attrs}"
            assert "benchmark.split" in attrs, f"Missing benchmark.split in {attrs}"
            assert "agent.version" in attrs, f"Missing agent.version in {attrs}"
            assert "evaluation.success" in attrs, f"Missing evaluation.success in {attrs}"
            assert "evaluation.failure_class" in attrs, f"Missing evaluation.failure_class in {attrs}"
            assert "evaluation.expected_action" in attrs, f"Missing evaluation.expected_action in {attrs}"
            assert "evaluation.selected_action" in attrs, f"Missing evaluation.selected_action in {attrs}"

            # Verify values are correct
            assert attrs["benchmark.split"] == "development"
            assert attrs["agent.version"] == "test-version"
            assert attrs["evaluation.success"] in (True, False)
            assert attrs["evaluation.failure_class"] in ("none", "wrong_tool", "missing_verification", "invalid_output", "tool_error")

        # Also verify action_selection spans have agent attributes
        action_spans = [s for s in spans if s.name == "action_selection"]
        assert len(action_spans) == 2
        for span in action_spans:
            attrs = span.attributes or {}
            assert "agent.version" in attrs, f"Missing agent.version in {attrs}"
            assert "agent.selected_action" in attrs, f"Missing agent.selected_action in {attrs}"
            assert attrs["agent.version"] == "test-version"
            assert attrs["agent.selected_action"] in ("reset_password", "refund_status", "escalate")

        # And verification_gate spans have guardrail attributes
        guardrail_spans = [s for s in spans if s.name == "verification_gate"]
        assert len(guardrail_spans) == 2
        for span in guardrail_spans:
            attrs = span.attributes or {}
            assert "guardrail.enabled" in attrs, f"Missing guardrail.enabled in {attrs}"
            assert "guardrail.passed" in attrs, f"Missing guardrail.passed in {attrs}"

    finally:
        shutdown()


def test_missing_neatlogs_config_does_not_break_benchmark():
    """Test that benchmark runs correctly when Neatlogs is not configured."""
    # Ensure no API key
    os.environ.pop("NEATLOGS_API_KEY", None)

    dev_cases = cases_for_split("development")[:2]
    config = StudentConfig(version="test-version")
    summary = run_benchmark(dev_cases, config)

    assert summary.total == 2
    assert summary.version == "test-version"
    assert summary.split == "development"
    assert 0.0 <= summary.success_rate <= 1.0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])