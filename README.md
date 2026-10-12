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

### Real-data flow

1. **Crustdata snapshots**: Real company data is fetched from the Crustdata API via `scripts/snapshot_crustdata.py`. Requests use `exact_match=true`, 1.5 s pacing between calls, and 15 s wait + retry (max 2 retries) on HTTP 429.
2. **Acceptance rule**: A company is accepted only if (a) `basic_info.primary_domain` (lowercased, `www.` stripped) matches the requested domain, and (b) `headcount.total`, `basic_info.year_founded`, and `locations.headquarters` are all present. Mismatched or incomplete companies are skipped and reported.
3. **Storage**: Raw JSON responses saved to `data/snapshots/raw/<domain>.json`; mapped `CompanyData` saved to `data/snapshots/companies_real.json` with `dev_domains` and `held_out_domains` lists.
4. **PACK_SOURCE modes**:
   - `fixtures` (default): Uses synthetic fixtures in `data/fixtures/companies.json` (10 fictional companies).
   - `snapshot`: Uses real Crustdata snapshots from `data/snapshots/companies_real.json` (6 dev, 4 held-out companies).

### Run

```bash
# Full improvement cycle (baseline → proposals → candidate → promotion) on fixtures
python -m app.cli --task pack

# On real Crustdata snapshots
PACK_SOURCE=snapshot python -m app.cli --task pack

# Ablation study: runs 6 configs on both dev and held-out splits
python -m app.cli --task pack-ablation

# Ablation on real snapshots
PACK_SOURCE=snapshot python -m app.cli --task pack-ablation
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

Each ablation run uses a fresh `default_source()` and writes outputs to `outputs/ablation/<name>/`. Results are printed as a markdown table and saved to `evidence/pack_ablation_<timestamp>.json` with `source` and `companies` fields for verifiability.

### Results (real Crustdata snapshots)

**Ablation table (source: snapshot, 6 dev / 4 held-out companies)**

| Config | Dev k/n | Held-out k/n | Failure Counts (dev+held-out) | LLM Calls | Cost (USD) |
|--------|---------|--------------|-------------------------------|-----------|------------|
| baseline | 0/6 | 0/4 | {"wrong_fact": 7, "tool_error": 3} | 7 | 0.000533 |
| retry_only | 0/6 | 0/4 | {"wrong_fact": 10} | 10 | 0.000750 |
| strict_only | 4/6 | 3/4 | {"tool_error": 3} | 7 | 0.000566 |
| verify_only | 3/6 | 3/4 | {"tool_error": 3, "wrong_fact": 1} | 14 | 0.001176 |
| strict_verify | 4/6 | 3/4 | {"tool_error": 3} | 7 | 0.000567 |
| candidate | 6/6 | 4/4 | {} | 10 | 0.000822 |

*Source: evidence/pack_ablation_20261012_003253.json*

- Retry fixes tool errors but not wrong figures.
- The strict prompt is the main fix for wrong figures.
- Verification rescues a weak prompt (verify_only) but is never triggered in the final candidate because the strict prompt passes first time.

### Limitations

- The baseline prompt deliberately encourages rounding (a controlled weakness), so baseline failures are expected.
- The evaluator and the verification step share `app/pack/checks.py`, so verification is checked against its own rules; ground truth is the Crustdata snapshot, not external reality.
- The fact-check normalization for formatting (e.g. "series_d" vs "Series D") was added after diagnosing false mismatches; see `evidence/diagnosis_*.md`. It applies to all configs equally.
- Improvement proposals are rule-mapped from failure classes, not LLM-diagnosed.
- Small sample: 6 development and 4 held-out companies; the model is non-deterministic; see `evidence/repeat_runs_*.md` for run-to-run spread.
- Company data is Crustdata's, which can be stale or wrong.
- The promotion gate promotes on any dev improvement with no held-out regression; it is a guardrail, not a significance test.
- Earlier synthetic-fixture runs live in `evidence/synthetic_fixtures/` and are not comparable to real-data runs.
- Tool failures are injected (simulated upstream outages on 3 companies) to test recovery; they say nothing about Crustdata's real reliability.
- The baseline fails by design; its prompt asks for rounded figures.
