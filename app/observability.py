"""Neatlogs observability integration, with a local-only fallback."""

from contextlib import contextmanager
from typing import Any
import os

try:
    import neatlogs
except ImportError:  # Keep local tests usable if the optional SDK isn't installed.
    neatlogs = None

_initialized = False

# Custom attributes that must survive the Neatlogs attribute processor and
# appear in the backend's queryable span_metadata. The SDK only materializes
# `neatlogs.*` namespace attributes into span_metadata. We must map our custom
# attributes to `neatlogs.*` equivalents via the attribute-mapping.json mappings.
#
# Structure: (source_attribute, target_neatlogs_attribute)
_CUSTOM_ATTRIBUTE_MAPPINGS = (
    ("benchmark.case_id", "neatlogs.benchmark.case_id"),
    ("benchmark.split", "neatlogs.benchmark.split"),
    ("agent.version", "neatlogs.agent.version"),
    ("agent.selected_action", "neatlogs.agent.selected_action"),
    ("evaluation.success", "neatlogs.evaluation.success"),
    ("evaluation.failure_class", "neatlogs.evaluation.failure_class"),
    ("evaluation.expected_action", "neatlogs.evaluation.expected_action"),
    ("evaluation.selected_action", "neatlogs.evaluation.selected_action"),
    ("evaluation.issues", "neatlogs.evaluation.issues"),
    ("evaluation.truth", "neatlogs.evaluation.truth"),
    ("guardrail.enabled", "neatlogs.guardrail.enabled"),
    # guardrail.passed already maps to neatlogs.guardrail.passed in SDK
    ("pack.company", "neatlogs.pack.company"),
    ("tool.attempt", "neatlogs.tool.attempt"),
    ("llm.prompt_tokens", "neatlogs.llm.prompt_tokens"),
    ("llm.completion_tokens", "neatlogs.llm.completion_tokens"),
    ("llm.cost_usd", "neatlogs.llm.cost_usd"),
    ("pack.verify_passed", "neatlogs.pack.verify_passed"),
    ("demo.label", "neatlogs.demo.label"),
)

# Also add to keep_as_is as a fallback for any attributes that don't map
_CUSTOM_KEEP_AS_IS_ATTRIBUTES = tuple(src for src, _ in _CUSTOM_ATTRIBUTE_MAPPINGS) + (
    "guardrail.passed",
)


def _patch_attribute_mapping() -> None:
    """Extend the Neatlogs attribute mapping to preserve custom attributes.

    The Neatlogs SDK loads its attribute-mapping.json once at span processor
    initialization. The UnifiedAttributeProcessor reads `keep_as_is.attributes`
    and `ignore.patterns` from the TOP LEVEL of the config, but the JSON file
    incorrectly nests them inside `mappings`. This function fixes that structural
    mismatch and adds our custom attribute mappings so they appear in the
    `neatlogs.*` namespace and are materialized into backend span_metadata.

    Note: keep_as_is does EXACT matching, not prefix matching. We must list
    every attribute name individually.
    """
    if neatlogs is None:
        return

    try:
        from neatlogs.init import _span_processor
        if _span_processor is None:
            return
        unified_processor = getattr(_span_processor, "unified_processor", None)
        if unified_processor is None:
            return
        mapping = getattr(unified_processor, "mapping", None)
        if not isinstance(mapping, dict):
            return

        # SDK bug: attribute-mapping.json nests keep_as_is/ignore inside mappings,
        # but UnifiedAttributeProcessor._apply_namespace_mapping expects them at
        # the top level. Promote them to where the code actually looks.
        mappings = mapping.get("mappings", {})
        if isinstance(mappings, dict):
            if "keep_as_is" in mappings and "keep_as_is" not in mapping:
                mapping["keep_as_is"] = mappings["keep_as_is"]
            if "ignore" in mappings and "ignore" not in mapping:
                mapping["ignore"] = mappings["ignore"]

        # Now add our custom attribute mappings to the mappings dict so they
        # get transformed to `neatlogs.*` namespace and materialized into span_metadata
        if isinstance(mappings, dict):
            # Add a new mapping section for our custom attributes.
            # The SDK's _map_recursive expects a "mappings" key with nested attribute configs.
            custom_mappings = mappings.setdefault("custom", {})
            if not isinstance(custom_mappings, dict):
                custom_mappings = {}
                mappings["custom"] = custom_mappings

            # Wrap in "mappings" key as expected by _map_recursive
            if "mappings" not in custom_mappings:
                custom_mappings["mappings"] = {}

            for src_attr, target_attr in _CUSTOM_ATTRIBUTE_MAPPINGS:
                custom_mappings["mappings"][src_attr] = {
                    "sources": [src_attr],
                    "target": target_attr,
                }

        # Also add to keep_as_is as a fallback
        keep_as_is = mapping.setdefault("keep_as_is", {}).setdefault("attributes", [])
        if not isinstance(keep_as_is, list):
            return
        for attr_name in _CUSTOM_KEEP_AS_IS_ATTRIBUTES:
            if attr_name not in keep_as_is:
                keep_as_is.append(attr_name)
    except Exception:
        # Best-effort patch; if the SDK internals change, we fail silently
        # and the custom attributes will be dropped (observability degradation only).
        pass


class _NullSpan:
    """No-op span used when Neatlogs is not configured."""

    def set_attribute(self, key, value):
        return None


def initialize_neatlogs() -> bool:
    """Initialize Neatlogs if a project API key is configured."""
    global _initialized

    if _initialized:
        return True
    if neatlogs is None:
        return False

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    api_key = os.getenv("NEATLOGS_API_KEY")
    if not api_key:
        return False

    neatlogs.init(
        api_key=api_key,
        endpoint=os.getenv("NEATLOGS_ENDPOINT", "https://ingest.neatlogs.com"),
        workflow_name="trace-driven-agent-improver",
        tags=["neathack", "trace-driven-agent-improver"],
    )
    _initialized = True
    _patch_attribute_mapping()
    return True


def shutdown_neatlogs() -> None:
    """Flush and stop Neatlogs after a short-lived process or at server shutdown."""
    global _initialized

    if not _initialized or neatlogs is None:
        return

    try:
        neatlogs.flush()
        neatlogs.shutdown()
    except Exception as e:
        print(f"Warning: neatlogs shutdown failed: {e}")
    finally:
        _initialized = False


def mark_span_failed(span: Any, description: str) -> None:
    """Mark a span as failed with an error status and description.

    Uses OpenTelemetry Status/StatusCode if available; otherwise falls back
    to setting an error attribute.
    """
    if not _initialized or neatlogs is None:
        return
    try:
        from opentelemetry.trace import Status, StatusCode
        span.set_status(Status(StatusCode.ERROR, description))
    except Exception:
        # Fallback: set error attribute if OpenTelemetry not available
        span.set_attribute("error", True)
        span.set_attribute("error.description", description)


@contextmanager
def trace_span(name: str, kind: str = "CHAIN", attributes: dict | None = None):
    """Open a Neatlogs span when initialized, otherwise no-op."""
    if not _initialized or neatlogs is None:
        yield _NullSpan()
        return

    with neatlogs.trace(name, kind=kind) as span:
        for key, value in (attributes or {}).items():
            if value is not None and isinstance(value, (str, bool, int, float)):
                span.set_attribute(key, value)
        yield span
