# Technical Stack
## Trace-Driven Agent Improver

- **Version:** 0.1
- **Principle:** Use the smallest stack that supports reproducible evaluation, visible traces, and a safe improvement loop.

---

## 1. Selected stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Fast iteration, tests, agent ecosystem |
| API | FastAPI | Small typed HTTP API and interactive OpenAPI docs |
| Data validation | Pydantic v2 | Typed input/output models and schema validation |
| Initial persistence | JSON/in-memory; SQLite if history needs to persist | Keep the first build small; add durable storage when required |
| Student agent (initial) | Deterministic Python adapter | Reproducible baseline and fault injection |
| Student agent (next milestone) | One LLM via a provider adapter | Enables realistic tool selection while keeping provider replaceable |
| Improver (initial) | Bounded rule-based proposal generator | Auditable changes and predictable tests |
| Improver (later) | LLM-assisted diagnosis constrained by an allowlist | Natural-language trace diagnosis without surrendering evaluation authority |
| Evaluation | Python benchmark runner + pytest | Repeatable correctness checks and regression tests |
| Tracing | Local structured events first; neatlogs integration next | Local fallback plus required external observability evidence |
| Version control | Git + Entire | Reproducible code changes and checkpoint/history evidence |
| Frontend | Defer; then React/Vite or a simple Streamlit UI | Avoid spending early time on UI |
| Business planning | cfo.ai | Required pricing, cost, revenue, and runway plan |
| Packaging | `venv` + `requirements.txt` | Simple local setup for a hackathon |

## 2. Dependencies in the scaffold

- `fastapi`
- `uvicorn[standard]`
- `pydantic`
- `pytest`

Install using:

```bash
pip install -r requirements.txt
```

## 3. Suggested project structure

```text
trace-driven-agent-improver/
├── app/
│   ├── __init__.py
│   ├── main.py             # FastAPI routes
│   ├── cli.py              # Run cycle from terminal
│   ├── models.py           # Pydantic data contracts
│   ├── benchmark.py        # Synthetic benchmark cases
│   ├── student.py          # Agent adapter and trace events
│   ├── evaluator.py        # Correctness checks and metrics
│   ├── improver.py         # Bounded proposals and promotion policy
│   └── service.py          # Improvement-cycle orchestration
├── tests/
│   └── test_improver.py
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── PRD.md
├── DESIGN.md
└── TECH_STACK.md
```

## 4. LLM integration decision

Do not hard-code provider-specific API calls into the evaluator or promotion gate. Add a small interface, for example:

```python
class StudentAgent:
    def run(self, task, config):
        \"\"\"Return a structured result and trace events.\"\"\"
        raise NotImplementedError
```

Implement one provider adapter first. Use structured output/tool calling if supported. Validate every model response against Pydantic schemas. Keep deterministic benchmark assertions as the source of truth for correctness.

For the Improver, begin with bounded edits to prompt/configuration/workflow rules. Avoid unrestricted self-modifying code in the MVP.

Before choosing a provider, verify current pricing, free-tier quotas, tool-calling support, latency, and API availability. These details change and should not be assumed.

## 5. Observability strategy

Each run should carry:
- `run_id`
- `case_id`
- `agent_version`
- `benchmark_split`
- step and tool names
- success/error outcome
- elapsed time
- token usage and estimated cost when the provider returns them
- final evaluator result

Use local structured traces as a fallback. Add neatlogs instrumentation only after verifying the currently supported SDK/API and access requirements. Do not make the core benchmark depend on the external trace service being available.

## 6. Storage strategy

For the first working cycle, in-memory objects and JSON output are enough. Add SQLite when the system needs:
- run history across server restarts
- versioned proposals and promotion decisions
- searchable trace summaries
- dashboard history

Avoid adding a vector database unless the chosen task genuinely requires semantic retrieval. The initial support-ticket benchmark does not.

## 7. Testing strategy

- Unit tests for evaluator correctness.
- Unit tests for each failure classifier.
- Tests proving seeded faults fail baseline cases.
- Tests proving bounded proposals target observed failures.
- Tests for promotion and rejection behavior.
- Regression tests ensuring rejected candidates do not replace the baseline.
- Integration test for `POST /improve`.
- Repeatability test for the deterministic adapter.
- Later: provider-adapter contract tests using mocked responses.

## 8. Environment configuration

Use `.env` or environment variables for model configuration:
- `MODEL_BASE_URL`
- `MODEL_API_KEY`
- `MODEL_NAME`

Never commit actual API keys. The initial deterministic mode should run without any model credentials.

## 9. Deployment

Develop locally first. If a public demo is needed, deploy the FastAPI service to a suitable host only after secrets, request limits, and logging are reviewed. Keep any candidate execution sandboxed and do not expose arbitrary command execution over a public endpoint.

## 10. Stack decisions to revisit

- Whether the dashboard is React/Vite or Streamlit.
- Which LLM provider is reliable and affordable during the event.
- Whether run history requires SQLite.
- Which neatlogs integration path is currently available.
- How Entire should be used to capture the candidate-change workflow.
- Whether a real code-editing candidate is feasible after configuration-level improvement works.
