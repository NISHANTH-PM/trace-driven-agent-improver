# Real-Data Results Tables (Corrected Snapshot)

Generated from evidence JSON files with `source: "snapshot"` created after HQ city fix and snapshot rebuild.

---

## (a) Real-Data Ablation

**Source:** snapshot  
**Companies (dev):** Razorpay, Postman, BrowserStack, Freshworks, Swiggy, Chargebee  
**Companies (held-out):** Figma, Linear, Canva, Notion  

| Config | Dev k/n | Held-out k/n | Failure Counts (dev+held-out) | LLM Calls | Cost (USD) |
|--------|---------|--------------|-------------------------------|-----------|------------|
| baseline | 0/6 | 0/4 | {"wrong_fact": 7, "tool_error": 3} | 7 | 0.000532 |
| retry_only | 0/6 | 0/4 | {"wrong_fact": 10} | 10 | 0.000754 |
| strict_only | 4/6 | 3/4 | {"tool_error": 3} | 7 | 0.000591 |
| verify_only | 3/6 | 3/4 | {"tool_error": 3, "wrong_fact": 1} | 14 | 0.001133 |
| strict_verify | 4/6 | 3/4 | {"tool_error": 3} | 7 | 0.000570 |
| candidate | 6/6 | 4/4 | {} | 10 | 0.000832 |

*Source file: evidence/pack_ablation_20261012_000908.json*

---

## (b) Repeat Runs (3 runs on corrected snapshot)

All pack_run JSON files in evidence/ with `source: "snapshot"` created after the snapshot rebuild:

| Run (file) | Baseline Dev k/n | Baseline Held-out k/n | Candidate Dev k/n | Candidate Held-out k/n | Baseline Failure Counts | Promoted | Baseline Cost (USD) | Candidate Cost (USD) |
|------------|------------------|-----------------------|-------------------|------------------------|-------------------------|----------|---------------------|----------------------|
| pack_run_20261012_001001.json | 0/6 | 0/4 | 6/6 | 4/4 | dev: {"wrong_fact": 4, "tool_error": 2}, held: {"tool_error": 1, "wrong_fact": 3} | Yes | 0.000515 | 0.000832 |
| pack_run_20261012_001046.json | 0/6 | 0/4 | 6/6 | 4/4 | dev: {"wrong_fact": 4, "tool_error": 2}, held: {"tool_error": 1, "wrong_fact": 3} | Yes | 0.000518 | 0.000822 |
| pack_run_20261012_001130.json | 0/6 | 0/4 | 6/6 | 4/4 | dev: {"wrong_fact": 4, "tool_error": 2}, held: {"tool_error": 1, "wrong_fact": 3} | Yes | 0.000534 | 0.000791 |

---

## Company Names (from corrected snapshot)

**Development (6):** Razorpay, Postman, BrowserStack, Freshworks, Swiggy, Chargebee  
**Held-out (4):** Figma, Linear, Canva, Notion