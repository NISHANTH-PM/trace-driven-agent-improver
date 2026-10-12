> **Status:** written for the original support-ticket MVP (Oct 10). The company-briefing agent added on Oct 11 to 12 is described in README.md and EVIDENCE.md.

> **Status:** written for the original support-ticket MVP (Oct 10). The company-briefing agent added on Oct 11 to 12 is described in README.md and EVIDENCE.md.

# System Design
## Trace-Driven Agent Improver

- **Version:** 0.1
- **Status:** MVP design
- **Design principle:** Keep the agent being improved small; make the evidence and evaluation loop trustworthy.

---

## 1. Architecture overview

```text
                 â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                 â”‚ Benchmark / Task Cases  â”‚
                 â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â”‚
                              â–¼
                 â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                 â”‚      Student Agent      â”‚
                 â”‚ task-specific adapter   â”‚
                 â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â”‚
                              â–¼
                 â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                 â”‚ Trace Collector / Sink  â”‚â”€â”€â”€â”€â”€â”€â–º neatlogs
                 â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â”‚
                              â–¼
                 â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                 â”‚ Deterministic Evaluator â”‚
                 â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â”‚
                              â–¼
                 â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                 â”‚ Failure Classifier      â”‚
                 â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â”‚ evidence + failure counts
                              â–¼
                 â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                 â”‚ Bounded Improver        â”‚
                 â”‚ proposes allowed change â”‚
                 â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â”‚
                              â–¼
                 â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                 â”‚ Candidate Configuration â”‚â”€â”€â”€â”€â”€â”€â–º Git / Entire
                 â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â”‚
                              â–¼
                 â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                 â”‚ Candidate Evaluation    â”‚
                 â”‚ development + held-out  â”‚
                 â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â”‚
                              â–¼
                 â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                 â”‚ Promotion Gate          â”‚
                 â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                         â”Œâ”€â”€â”€â”€â”´â”€â”€â”€â”€â”
                         â–¼         â–¼
                     Promote     Reject
                         â”‚         â”‚
                         â””â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”˜
                              â–¼
                 â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                 â”‚ Results / API / UI      â”‚
                 â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

cfo.ai: business plan and product unit-economics analysis
```

## 2. Core components

### 2.1 Benchmark
Stores synthetic cases with stable IDs, expected outputs, split labels, and optional seeded-failure metadata. The benchmark runner must not expose held-out expected answers to the Improver during proposal generation.

### 2.2 Student agent
A replaceable adapter that accepts a case and a versioned configuration and returns a structured output plus trace events. The first adapter is deterministic to test system mechanics. A later adapter may use an LLM and tools.

### 2.3 Trace collector
Normalizes execution steps into trace events:
- run ID and case ID
- step name
- action/tool selected
- outcome
- error or warning
- relevant metadata
- latency/token/cost fields when available

Avoid logging secrets or personal data. The initial synthetic benchmark contains no real customer data.

### 2.4 Evaluator
Compares agent outputs to expected outcomes. For known benchmark tasks, the evaluatorâ€”not the Improver's narrativeâ€”determines correctness. It emits per-case results and aggregate metrics.

### 2.5 Failure classifier
Groups failures into a small taxonomy:
- `wrong_tool`
- `missing_verification`
- `invalid_output`
- `tool_error`
- `none`

The taxonomy may grow only when a failure can be detected and tested reliably.

### 2.6 Improver
Reads development-split failures and proposes changes from an allowlist:
- `prompt_rule`
- `tool_schema`
- `workflow_gate`

For the first version, improvements are configuration changes, not arbitrary code generation. Every proposal includes target failure class, description, configuration key/value, and supporting evidence.

### 2.7 Candidate evaluator
Runs baseline and candidate with the same development cases, then checks candidate generalization on held-out cases. Report both case-level and aggregate outcomes.

### 2.8 Promotion gate
Promotes only if acceptance criteria pass. It must reject a candidate that fails to improve the required metric or regresses on held-out tests/critical checks. The baseline is immutable during an experiment.

### 2.9 API
- `GET /health`: liveness check.
- `POST /improve`: executes a complete cycle and returns baseline metrics, proposals, candidate metrics, and promotion decision.

### 2.10 Partner integrations
- **neatlogs:** external trace observability where current access/API supports it.
- **Entire:** repository/checkpoint evidence for meaningful candidate changes.
- **cfo.ai:** business plan and unit economics; not part of the task agent's runtime loop unless a future requirement justifies it.

## 3. Execution state machine

```text
IDLE
  â†“ start run
BASELINE_RUNNING
  â†“ traces captured
BASELINE_EVALUATED
  â†“ failures identified
PROPOSALS_READY
  â†“ candidate isolated
CANDIDATE_RUNNING
  â†“ candidate evaluated
PROMOTION_CHECK
  â”œâ”€â”€ pass â”€â”€â–º PROMOTED
  â””â”€â”€ fail â”€â”€â–º REJECTED
```

Each transition should record a timestamp and a reason. Exceptions should move the run into a failed state with a readable error rather than silently continuing.

## 4. Data model

### TicketCase
- `case_id`: stable identifier
- `ticket`: synthetic task input
- `expected_action`: expected action
- `expected_verified`: whether verification is required
- `split`: `development` or `held_out`
- `seeded_failure`: optional deterministic fault injection

### AgentOutput
- `case_id`
- `selected_action`
- `verified`
- `rationale`

### TraceEvent
- `event_id`
- `run_id`
- `case_id`
- `step`
- `detail`
- `outcome`
- `metadata`

### CaseResult
- expected and actual action
- verification status
- success boolean
- failure class
- associated trace

### BenchmarkSummary
- version
- split
- total cases
- successful cases
- success rate
- failure counts
- average tool calls
- case-level results

### ImprovementProposal
- target failure
- change type
- description
- configuration key/value

## 5. Promotion policy

Initial policy:
1. Candidate development success must exceed baseline development success.
2. Candidate held-out success must not regress.
3. Candidate must pass all critical safety checks.
4. If cost/latency limits are configured, candidate must remain within them.
5. A rejected candidate must not replace the active baseline.

For a tiny benchmark, one or two cases can change the percentage substantially. The UI and demo should show raw counts alongside percentages. If statistical confidence is not available, do not claim statistical significance.

## 6. Failure and recovery behavior

- Tool error: record the error; retry only if the tool operation is safe and retryable.
- Invalid output: fail schema validation and classify it.
- Evaluator exception: mark evaluation as errored; do not promote.
- Improver exception: keep baseline active and return a failure reason.
- Candidate regression: reject and preserve baseline.
- Trace sink unavailable: keep local trace records and mark external observability as unavailable; do not claim the external integration succeeded.

## 7. Security and safety

- Synthetic inputs only in the MVP.
- Keep model/API credentials in environment variables.
- Do not log secrets.
- Do not run arbitrary generated shell commands.
- Do not deploy candidates to production.
- Limit the Improver to allowlisted configuration changes.
- Require explicit human action before any future real-world write operation.

## 8. Future dashboard design

Suggested pages:
1. **Overview:** baseline/candidate scorecards and active version.
2. **Runs:** case results and traces.
3. **Failure analysis:** counts, categories, evidence, and proposed changes.
4. **Candidate comparison:** diff, benchmark results, regressions, cost/latency.
5. **History:** accepted/rejected candidates and reasons.
6. **Submission evidence:** partner links/screenshots and measured results.

The dashboard is intentionally deferred until the API and improvement loop are reliable.
