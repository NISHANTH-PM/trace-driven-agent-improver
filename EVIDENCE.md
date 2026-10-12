# Evidence for judges

Every claim below points to a file in this repository, a screenshot, or a link. Items marked `TODO` need a link from the author before submission.

Project: **trace-driven agent improver, applied to a company-briefing agent**. A cheap model (Nova Lite) turns Crustdata company data into a briefing (.docx, plus optional .pptx and .xlsx). A loop reads the agent's failures from the traces, proposes fixes, and promotes a fix only if development results improve and held-out results do not regress.

## 1. The agent improved (before and after, with numbers)

Real Crustdata data: 10 companies (6 development, 4 held-out). Baseline versus candidate:

| Run | Baseline dev | Baseline held-out | Candidate dev | Candidate held-out | Promoted |
|---|---|---|---|---|---|
| pack_run_20261012_003340 | 0/6 | 0/4 | 6/6 | 4/4 | yes |
| pack_run_20261012_003422 | 0/6 | 0/4 | 6/6 | 4/4 | yes |
| pack_run_20261012_003506 | 0/6 | 0/4 | 6/6 | 4/4 | yes |

Files: `evidence/pack_run_20261012_003340.json`, `..._003422.json`, `..._003506.json`; tables in `evidence/real_data_results.md`.

Ablation (which fix does what), file `evidence/pack_ablation_20261012_003253.json`:

| Config | Dev | Held-out | Failures (dev + held-out) | LLM calls | Cost (USD) |
|---|---|---|---|---|---|
| baseline | 0/6 | 0/4 | wrong_fact 7, tool_error 3 | 7 | 0.000533 |
| retry only | 0/6 | 0/4 | wrong_fact 10 | 10 | 0.000750 |
| strict prompt only | 4/6 | 3/4 | tool_error 3 | 7 | 0.000566 |
| verify only | 3/6 | 3/4 | tool_error 3, wrong_fact 1 | 14 | 0.001176 |
| strict + verify | 4/6 | 3/4 | tool_error 3 | 7 | 0.000567 |
| candidate (all three) | 6/6 | 4/4 | none | 10 | 0.000822 |

Reading: the strict prompt fixes wrong figures, retry fixes tool failures, and verification rescues a weak prompt (0/6 to 3/6) but adds nothing once the prompt is strict. No single fix is enough on its own.

Same-company before/after pair (Razorpay): baseline wrote "over 4,000 employees" and "approximately $817 million"; candidate wrote "4042" and "$816,600,000" (true values: 4,042 and 816,600,000). Screenshots: `evidence/screenshots/neat_baseline_fail.png`, `neat_candidate_success.png`; documents: `outputs/demo/` after running `scripts/demo_run.py`.

## 2. The agent recovers from failures

A run where the first data call failed and the agent retried: `neat_retry_recovery.png`. The first `fetch_company` span is an error (`FAILED attempt 1/3: upstream 503. Retrying.`), then a backoff, then a successful second attempt, and the case passes. Failures are injected (see Limitations). Without retry the same case ends as `tool_error` (`neat_tool_error.png`).

Verification recovery: `neat_verify_regeneration.png` shows the draft failing the fact check and a second LLM call (`llm_regenerate`) repairing it.

## 3. You used neatlogs

- Spans for every run: `benchmark_case` > `fetch_company` (TOOL) > LLM span (model, provider, tokens) > `verify_facts` (GUARDRAIL).
- Evaluator verdict on the trace: failed cases have an error status and an output line `FAILED <class>: <issues>. TRUTH: <true values>`; the traces list shows `PASSED` and `Execution Failed`.
- Screenshots: `neat_llm_attributes.png`, `neat_llm_io.png`, `neat_trace_list.png`, `neat_baseline_fail.png`, `neat_retry_recovery.png`, `neat_verify_regeneration.png`.
- Links (open in a private window to check): see `evidence/screenshots/LINKS.md`. TODO: fill in links.
- Labeled demo run: `evidence/demo_manifest.md` (names each scenario and its start time).

## 4. You used Entire

- Entire is enabled on this repository with OpenCode sessions captured as checkpoints; commits carry `Entire-Checkpoint` trailers.
- Checkpoint pages: https://entire.io/gh/NISHANTH-PM/trace-driven-agent-improver/commit/1df734c973a0643ba94bddaa21015097fa06f586/feat%2Fpack-agent and https://entire.io/gh/NISHANTH-PM/trace-driven-agent-improver/commit/7bb1d121b06fa48d991ce6dcf27a05136228fe8a/feat%2Fpack-agent
- Concrete use: during the build one coding-agent session wrote invented company data instead of calling Crustdata. The history and checkpoints made it possible to find and revert that (`c0cdfae`, "revert: remove mocked snapshot data"), and the affected evidence is labeled in `evidence/superseded/README.md`.
- entire-graph output: TODO (`evidence/entire_graph/` once the commands have been run).

## 5. You used cfo.ai

Business plan with pricing, costs, revenue and runway: `docs/BUSINESS_PLAN.md`, spreadsheets in `docs/cfo_plan/`, screenshots `cfo_scenario_comparison.png`, `cfo_api_price_margin.png`, `cfo_pricing_assumptions.png`, `cfo_economics_cash.png`. Measured LLM cost (about $0.00008 per briefing) feeds the plan; the API credit price is an unconfirmed assumption and the plan says so.

## 6. You built in public

Posts tagged #neatHack: TODO links.

## 7. The code was written during the hackathon

The first commit is dated 2026-10-10 13:22 IST, after the 12:30 IST start; all commits fall on Oct 10 to 12. History: `evidence/git_history.txt` and the GitHub commits page (`evidence/screenshots/github_commits.png`).

## Limitations (please read)

- The baseline prompt deliberately asks for rounded figures, so baseline failures are expected. It is a controlled weakness, not a typical agent.
- The evaluator and the verification step share `app/pack/checks.py`; ground truth is the Crustdata snapshot, not external reality. The document footer says "Figures checked against source" and covers only the five structured figures, not the narrative text.
- Tool failures are injected (simulated upstream outages on three companies) to test recovery. They say nothing about Crustdata's real reliability.
- A fact-check formatting normalization (for example "series_d" versus "Series D") was added after diagnosing false mismatches on real data. See `evidence/diagnosis_*.md`. It applies to every configuration equally.
- Improvement proposals are rule-mapped from failure classes; they are not LLM-diagnosed.
- Small sample (6 development, 4 held-out companies); results were identical across repeat runs, which reflects deterministic checks and a deliberately weak baseline more than robustness.
- Earlier runs on synthetic fixtures and on mismatched companies are kept, labeled, in `evidence/synthetic_fixtures/` and `evidence/superseded/`.
- Company data is Crustdata's and may be stale or wrong.
