"""Smoke test for neatlogs integration."""
from app.observability import initialize_neatlogs, shutdown_neatlogs, trace_span

initialize_neatlogs()

with trace_span("smoke_test", kind="WORKFLOW", attributes={"agent.version": "smoke", "benchmark.case_id": "SMOKE"}):
    with trace_span("smoke_child", kind="TOOL"):
        pass

shutdown_neatlogs()
print("smoke done")