# Trace-Driven Agent Improver

A hackathon MVP for observing a task agent, classifying failures, applying bounded improvements, and promoting a candidate only when benchmark evidence supports it.

## Current scope
- Synthetic support-ticket routing task
- Two seeded failure classes: wrong tool/action and missing verification
- Development and held-out benchmark splits
- Structured traces, deterministic evaluation, bounded improvement proposals
- Promotion/rejection gate and FastAPI endpoints

This first version uses a deterministic adapter to validate the improvement loop reproducibly. It is not evidence of LLM performance. The student-agent interface is isolated so an LLM-backed adapter can be added next.

## Run
Requires Python 3.11+.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pytest -q
python -m app.cli
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs.

## Loop
Benchmark → Student agent → trace/evaluate → classify failures → propose bounded change → candidate benchmark → promotion gate.

## Guardrails
1. Never modify baseline in place.
2. Do not use held-out results to choose the change.
3. Promote only when the candidate improves the target metric without held-out regression.
4. Report only measured results.
5. Use synthetic data; no production actions or customer data.
