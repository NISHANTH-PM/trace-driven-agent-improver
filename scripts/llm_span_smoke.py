"""Smoke test for LLM span attributes - exports real span to dashboard."""
from app.observability import initialize_neatlogs, shutdown_neatlogs, trace_span
from app.pack.student import _set_llm_attrs

initialize_neatlogs()

model_name = "test-model"
system = "You are a helpful assistant."
user = "Say hello."
response = "Hello! How can I help you?"
prompt_tokens, completion_tokens = 15, 12
cost = 0.0001

with trace_span("llm_span_smoke", kind="LLM") as span:
    _set_llm_attrs(span, prompt_tokens, completion_tokens, system, user, response, model_name, cost)
    # Best-effort print of keys set
    if hasattr(span, '_attributes'):
        print("Attributes set:", list(span._attributes.keys()))

shutdown_neatlogs()
print("LLM span smoke test done")