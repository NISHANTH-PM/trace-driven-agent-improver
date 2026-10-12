> **Status:** written for the original support-ticket MVP (Oct 10). The company-briefing agent added on Oct 11 to 12 is described in README.md and EVIDENCE.md.

> **Status:** written for the original support-ticket MVP (Oct 10). The company-briefing agent added on Oct 11 to 12 is described in README.md and EVIDENCE.md.

# Product Requirements Document (PRD)
## Trace-Driven Agent Improver

- **Status:** MVP specification
- **Version:** 0.1
- **Product type:** Agent reliability and evaluation tool
- **Primary goal:** Demonstrate a closed-loop system that uses execution evidence to improve a task-specific agent and verifies whether the change works.

---

## 1. Summary

Trace-Driven Agent Improver observes a task-specific AI agent, evaluates its outputs against a reproducible benchmark, identifies recurring failure patterns, proposes bounded changes, and tests a candidate version before promoting or rejecting it.

The product is not a general-purpose agent builder. The MVP focuses on one controlled workflow and demonstrates the loop:

**Run â†’ Trace â†’ Evaluate â†’ Diagnose â†’ Improve â†’ Re-evaluate â†’ Promote or reject**

The first task domain is synthetic support-ticket routing. The initial scaffold uses a deterministic adapter to validate the benchmark and promotion mechanics. A later milestone replaces or supplements it with an LLM-backed agent and real observability integration.

## 2. Problem

Task agents can fail in ways that are difficult to diagnose consistently: selecting the wrong tool, skipping verification, producing malformed output, repeating tool calls, or mishandling tool errors. Manual debugging often relies on ad hoc prompt edits and anecdotal examples rather than repeatable evidence.

Teams need a bounded workflow that connects failure evidence to a proposed change and then checks whether that change improves outcomes without introducing regressions.

## 3. Product goals

1. Produce reproducible baseline and candidate evaluations.
2. Capture structured evidence for each agent run.
3. Classify failures using deterministic checks where possible.
4. Generate a small, auditable set of improvement proposals.
5. Evaluate candidate changes on development and held-out cases.
6. Promote a candidate only when explicit acceptance criteria pass.
7. Make before/after results easy to inspect and demonstrate.
8. Integrate required hackathon tools meaningfully: neatlogs, Entire, and cfo.ai.

## 4. Non-goals

- A universal system that improves arbitrary agents or tasks.
- Training or fine-tuning a foundation model.
- Unrestricted self-modifying code or autonomous production deployment.
- Connecting to real customer-support systems or using real customer data.
- Guaranteeing that every proposed improvement succeeds.
- Treating LLM-generated explanations as proof of correctness.
- Building a complex dashboard before the improvement loop is reliable.

## 5. Target users

### Primary
Developers building task-specific AI agents who need to diagnose and reduce repeatable failures.

### Secondary
Hackathon judges and technical reviewers who need to verify that the system improved an agent using evidence rather than unsupported claims.

## 6. MVP use case

A synthetic support-ticket agent maps a ticket to one of three actions:

- `reset_password`
- `refund_status`
- `escalate`

The benchmark includes expected outcomes and seeded failures. The system runs the baseline, evaluates results, identifies supported failure categories, proposes bounded changes, evaluates a candidate, and records a promotion decision.

The task domain is deliberately narrow so the project can demonstrate the improvement mechanism rather than spend its time integrating many external systems.

## 7. Functional requirements

### FR-1: Benchmark management
- Maintain a fixed set of synthetic task cases.
- Each case must have an identifier, input, expected outcome, and split (`development` or `held_out`).
- Keep held-out cases out of proposal generation and tuning decisions.

### FR-2: Agent execution
- Run the task agent against a selected benchmark split.
- Record each meaningful step, tool/action selection, result, error, and verification outcome.
- Assign each execution a unique run ID.

### FR-3: Evaluation
- Compare actual output against the expected outcome.
- Calculate task success rate and failure counts by category.
- Track tool-call count and, once available, latency, tokens, and estimated cost.
- Keep raw case-level results available for inspection.

### FR-4: Failure diagnosis
- Identify supported failure patterns from evaluation results and trace evidence.
- Distinguish task/agent failures from tool errors and evaluator uncertainty where possible.
- Do not claim a root cause unless there is evidence for it.

### FR-5: Improvement proposals
- Propose bounded changes from an allowlist, such as prompt rules, tool schema clarification, or workflow verification gates.
- Each proposal must state the target failure, proposed change, and rationale/evidence.
- Preserve the baseline unchanged.

### FR-6: Candidate evaluation
- Apply proposals to an isolated candidate configuration or branch.
- Rerun the development benchmark.
- Evaluate on the held-out benchmark after the candidate is selected.
- Compare success rate, failure recurrence, regressions, cost, and latency when available.

### FR-7: Promotion gate
- Accept or reject candidates using explicit rules.
- A candidate must improve the target metric and must not regress on held-out cases or critical safety checks.
- Store the decision and reasons.
- If a candidate is rejected, keep the baseline active.

### FR-8: API
- `GET /health` returns service health.
- `POST /improve` executes one complete improvement cycle and returns baseline, proposals, candidate metrics, and promotion decision.

### FR-9: Observability and partner evidence
- Instrument execution runs with neatlogs to the extent supported by available product/API access.
- Use Entire to preserve and inspect meaningful repository changes/checkpoints.
- Produce the required cfo.ai business plan covering pricing, costs, revenue assumptions, and runway.
- Never treat a screenshot or nominal integration as proof that a tool materially contributed; document the actual usage.

### FR-10: Reproducibility
- Same benchmark, configuration, and deterministic adapter should produce the same task outcomes.
- Record version identifiers and benchmark split for each run.
- Clearly label deterministic scaffold results versus LLM-backed results.

## 8. Quality attributes

- **Safety:** synthetic data only; no production writes or destructive actions.
- **Auditability:** every proposal and promotion decision has a recorded reason.
- **Reproducibility:** baseline is immutable during candidate experiments.
- **Modularity:** agent adapter, evaluator, trace sink, and improvement policy can be replaced independently.
- **Usability:** results should be understandable without reading raw logs.
- **Cost awareness:** avoid unnecessary model calls and report cost when measurable.

## 9. Success metrics

Initial success criteria for the engineering MVP:

1. All unit tests pass.
2. A complete improvement cycle runs from the CLI and API.
3. At least two seeded failure classes are detected.
4. The candidate is evaluated on both development and held-out data.
5. The promotion gate rejects a candidate that fails acceptance criteria.
6. The final demo shows a real trace, a specific change, and measured before/after results.

Product-level metrics to report:
- Task success rate
- Absolute success-rate change (percentage points)
- Failure recurrence by class
- Held-out regression rate
- Tool calls per task
- Median/p95 latency when available
- Cost per run and cost per successful task when measurable

No numeric improvement target should be claimed until measured against the implemented benchmark.

## 10. Constraints and assumptions

- Hackathon implementation time is limited.
- External tool/API access and quotas must be confirmed before relying on them.
- A small synthetic benchmark is for demonstrating the loop, not proving broad generalization.
- LLM-based diagnosis may be wrong; deterministic evaluation remains authoritative for known expected outcomes.
- Held-out evaluation on a small set has high uncertainty and should be described honestly.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Over-scoping into a general agent platform | Support one task domain and a few bounded interventions |
| False root-cause claims | Require trace/evaluator evidence and preserve uncertainty |
| Overfitting to benchmark | Separate development and held-out cases; add unseen cases if time allows |
| Candidate regression | Immutable baseline, isolated candidate, explicit promotion gate |
| LLM cost or rate limits | Keep calls bounded; allow deterministic mode for tests |
| Partner integration unavailable | Verify access early; avoid fabricating integration evidence |
| Demo results look hard-coded | Show code, traces, test cases, and reproducible commands; label seeded faults clearly |

## 12. MVP acceptance checklist

- [ ] Setup works from a clean environment.
- [ ] Tests pass.
- [ ] Baseline produces traceable failures.
- [ ] Failure categories are visible.
- [ ] Improver produces a bounded proposal tied to observed evidence.
- [ ] Candidate is evaluated on development and held-out cases.
- [ ] Promotion/rejection decision includes reasons.
- [ ] Baseline remains intact after candidate rejection.
- [ ] LLM-backed results, if added, are reported separately from deterministic scaffold results.
- [ ] Required partner usage and business-plan evidence are captured.
