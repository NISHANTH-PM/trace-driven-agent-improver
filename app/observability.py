"""Neatlogs observability integration, with a local-only fallback."""

from contextlib import contextmanager
import os

try:
    import neatlogs
except ImportError:  # Keep local tests usable if the optional SDK isn't installed.
    neatlogs = None

_initialized = False


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
    return True


def shutdown_neatlogs() -> None:
    """Flush and stop Neatlogs after a short-lived process or at server shutdown."""
    global _initialized

    if not _initialized or neatlogs is None:
        return

    try:
        neatlogs.flush()
    finally:
        neatlogs.shutdown()
        _initialized = False


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
