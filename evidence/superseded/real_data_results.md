# Real-Data Results Tables

Generated from evidence JSON files with `source: "snapshot"`.

---

## (a) Real-Data Ablation

**Source:** snapshot  
**Companies (dev):** Postman, Swiggy, Freshworks, BrowserStack, Razorpay, Chargebee  
**Companies (held-out):** Figma, Linear, Canva, Notion  

| Config | Dev k/n | Held-out k/n | Failure Counts (dev+held-out) | LLM Calls | Cost (USD) |
|--------|---------|--------------|-------------------------------|-----------|------------|
| baseline | 0/6 | 0/4 | {"tool_error": 3, "wrong_fact": 7} | 7 | 0.000529 |
| retry_only | 0/6 | 0/4 | {"wrong_fact": 10} | 10 | 0.000763 |
| strict_only | 4/6 | 3/4 | {"tool_error": 3} | 7 | 0.000598 |
| verify_only | 3/6 | 3/4 | {"tool_error": 3, "wrong_fact": 1} | 14 | 0.001146 |
| strict_verify | 4/6 | 3/4 | {"tool_error": 3} | 7 | 0.000586 |
| candidate | 6/6 | 4/4 | {} | 10 | 0.000813 |

*Source file: evidence/pack_ablation_20261011_230135.json*

---

## (b) Repeat Runs

All pack_run JSON files in evidence/ with `source: "snapshot"`:

| Run (file) | Baseline Dev k/n | Baseline Held-out k/n | Candidate Dev k/n | Candidate Held-out k/n | Baseline Failure Counts | Promoted | Baseline Cost (USD) | Candidate Cost (USD) |
|------------|------------------|-----------------------|-------------------|------------------------|-------------------------|----------|---------------------|----------------------|
| pack_run_20261011_222702.json | 0/6 | 1/2 | 3/6 | 1/2 | dev: {"wrong_fact": 4, "tool_error": 2}, held: {"tool_error": 1} | Yes | 0.000341 | 0.000912 |
| pack_run_20261011_224432.json | 0/6 | 0/4 | 1/6 | 0/4 | dev: {"tool_error": 2, "wrong_fact": 4}, held: {"tool_error": 1, "wrong_fact": 3} | Yes | 0.000526 | 0.001605 |
| pack_run_20261011_224831.json | 0/6 | 0/4 | 6/6 | 4/4 | dev: {"tool_error": 2, "wrong_fact": 4}, held: {"tool_error": 1, "wrong_fact": 3} | Yes | 0.000528 | 0.000808 |
| pack_run_20261011_230234.json | 0/6 | 0/4 | 6/6 | 4/4 | dev: {"tool_error": 2, "wrong_fact": 4}, held: {"tool_error": 1, "wrong_fact": 3} | Yes | 0.000520 | 0.000784 |
| pack_run_20261011_230320.json | 0/6 | 0/4 | 6/6 | 4/4 | dev: {"tool_error": 2, "wrong_fact": 4}, held: {"tool_error": 1, "wrong_fact": 3} | Yes | 0.000531 | 0.000828 |
| pack_run_20261011_230408.json | 0/6 | 0/4 | 6/6 | 4/4 | dev: {"tool_error": 2, "wrong_fact": 4}, held: {"tool_error": 1, "wrong_fact": 3} | Yes | 0.000518 | 0.000811 |

**Note:** pack_run_20261011_222702.json used an earlier held-out set (Figma, Linear only - 2 companies). All others use the current held-out set (Figma, Linear, Canva, Notion - 4 companies).

---

## Company Names (from latest snapshot)

**Development (6):** Postman, Swiggy, Freshworks, BrowserStack, Razorpay, Chargebee  
**Held-out (4):** Figma, Linear, Canva, Notion
