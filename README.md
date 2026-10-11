# Trace-Driven Agent Improver

A hackathon MVP that observes a task agent, classifies failures, applies bounded improvements, and promotes a candidate only when benchmark evidence supports it.

## Current scope

- Synthetic support-ticket routing task.
- Two real baseline failure classes: wrong action selection and missing verification.
- Separate development and held-out benchmark splits.
- Local structured trace events plus optional Neatlogs spans.
- Bounded improvement proposals and a promotion/rejection gate.
- CLI and FastAPI endpoints.

The current student agent is deterministic. Neatlogs integration makes its workflow and evaluation outcomes observable; it does not imply that this version uses an LLM or proves general self-improvement.

## Setup

Requires Python 3.11+.

\`\`\`bash
python -m venv .venv
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
\`\`\`

Copy .env.example to .env and set NEATLOGS_API_KEY to the project key from your Neatlogs dashboard. Do not commit .env. If the key is absent, the app and tests run locally without exporting traces.

## Run

\`\`\`bash
python -m pytest -q
python -m app.cli
uvicorn app.main:app --reload
\`\`\`

Open http://127.0.0.1:8000/docs. Call POST /improve to run a complete benchmark and improvement cycle. With a valid NEATLOGS_API_KEY, each benchmark case is exported as a workflow trace with nested action-selection, tool-execution, and verification spans. Check the Neatlogs dashboard for the trace-driven-agent-improver workflow.

## Improvement loop

Benchmark → Student agent → trace/evaluate → classify failures → propose bounded change → candidate benchmark → promotion gate.

The held-out set is used only as a final regression guardrail. It must not be used to generate proposals or tune the candidate.

## Guardrails

1. Never modify the baseline in place.
2. Generate proposals from development-set failures only.
3. Promote only when development performance improves and held-out performance does not regress.
4. Report only measured results, including raw counts alongside percentages.
5. Use synthetic data; no production actions or customer data.

## Pack agent

The pack agent writes one-page company briefings: it fetches company data from a tool, drafts sections via an LLM, optionally verifies facts against the source data, and renders a `.docx` file.

### Run

```bash
# Full improvement cycle (baseline → proposals → candidate → promotion)
python -m app.cli --task pack

# Ablation study: runs 6 configs on both dev and held-out splits
python -m app.cli --task pack-ablation
```

### Ablation configs

| Config | Description |
|--------|-------------|
| `baseline` | No retries, base prompt, no verification |
| `retry_only` | Retry tool errors (max 3 attempts) |
| `strict_only` | Strict prompt (requires exact figures) |
| `verify_only` | Fact verification with one regeneration |
| `strict_verify` | Strict prompt + verification |
| `candidate` | All three: retry + strict + verification |

Each ablation run uses a fresh `default_source()` and writes outputs to `outputs/ablation/<name>/`. Results are printed as a markdown table and saved to `evidence/pack_ablation_<timestamp>.json`.

### Limitations

- **Baseline prompt deliberately encourages rounding** as a controlled weakness (e.g., "about 2,000 employees") so that `wrong_fact` failures appear and the improvement loop has something to fix.
- **Proposals are rule-mapped from failure classes**, not LLM-diagnosed. The mapping is fixed: `tool_error → retry_tool_errors`, `wrong_fact → strict_prompt + verify_facts`, `missing_section → verify_facts`.
- **Fixtures are fictional** (6 dev cases, 4 held-out cases) with synthetic company data.
- **Small sample size** (6 dev / 4 held-out) limits statistical power.
- **No general self-improvement is claimed**. This is a controlled demonstration of a trace-driven improvement loop on a synthetic task.
