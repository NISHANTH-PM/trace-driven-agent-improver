"""Optional Neatlogs integration with a safe local-only fallback."""

from contextlib import contextmanager
import os

try:
    import neatlogs
except ImportError:  # Local tests can still run before optional dependencies are installed.
    neatlogs = None

_initialized = False


class _NullSpan:
    """No-op span used when Neatlogs is not configured."""

    def set_attribute(self, key, value):
        return None


def initialize_neatlogs() -> bool:
    """Initialize Neatlogs once when a project API key is configured."""
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
        workflow_name="trace-driven-agent-improver",
        tags=["neathack", "trace-driven-agent-improver"],
    )
    _initialized = True
    return True


def shutdown_neatlogs() -> None:
    """Flush pending traces and stop the SDK in short-lived processes."""
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
    """Create a Neatlogs span when configured; otherwise behave as a no-op."""
    if not _initialized or neatlogs is None:
        yield _NullSpan()
        return

    with neatlogs.trace(name, kind=kind) as span:
        for key, value in (attributes or {}).items():
            if value is not None and isinstance(value, (str, bool, int, float)):
                span.set_attribute(key, value)
        yield span
