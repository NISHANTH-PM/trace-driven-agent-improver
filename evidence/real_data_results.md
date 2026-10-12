# Real-Data Results Tables (Corrected Snapshot - HQ City Fix)

Generated from evidence JSON files with `source: "snapshot"` created after HQ city fix (commit 8651033) and snapshot rebuild.

---

## (a) Real-Data Ablation

**Source:** snapshot  
**Companies (dev):** Razorpay, Postman, BrowserStack, Freshworks, Swiggy, Chargebee  
**Companies (held-out):** Figma, Linear, Canva, Notion  

| Config | Dev k/n | Held-out k/n | Failure Counts (dev+held-out) | LLM Calls | Cost (USD) |
|--------|---------|--------------|-------------------------------|-----------|------------|
| baseline | 0/6 | 0/4 | {"wrong_fact": 7, "tool_error": 3} | 7 | 0.000533 |
| retry_only | 0/6 | 0/4 | {"wrong_fact": 10} | 10 | 0.000750 |
| strict_only | 4/6 | 3/4 | {"tool_error": 3} | 7 | 0.000566 |
| verify_only | 3/6 | 3/4 | {"tool_error": 3, "wrong_fact": 1} | 14 | 0.001176 |
| strict_verify | 4/6 | 3/4 | {"tool_error": 3} | 7 | 0.000567 |
| candidate | 6/6 | 4/4 | {} | 10 | 0.000822 |

*Source file: evidence/pack_ablation_20261012_003253.json*

---

## (b) Repeat Runs (3 runs on corrected snapshot with HQ city fix)

| Run (file) | Baseline Dev k/n | Baseline Held-out k/n | Candidate Dev k/n | Candidate Held-out k/n | Baseline Failure Counts | Candidate Failure Counts | Promoted | Baseline Cost (USD) | Candidate Cost (USD) |
|------------|------------------|-----------------------|-------------------|------------------------|-------------------------|--------------------------|----------|---------------------|----------------------|
| pack_run_20261012_003340.json | 0/6 | 0/4 | 6/6 | 4/4 | dev: {"wrong_fact": 4, "tool_error": 2}, held: {"tool_error": 1, "wrong_fact": 3} | dev: {}, held: {} | Yes | 0.000520 | 0.000812 |
| pack_run_20261012_003422.json | 0/6 | 0/4 | 6/6 | 4/4 | dev: {"wrong_fact": 4, "tool_error": 2}, held: {"tool_error": 1, "wrong_fact": 3} | dev: {}, held: {} | Yes | 0.000539 | 0.000839 |
| pack_run_20261012_003506.json | 0/6 | 0/4 | 6/6 | 4/4 | dev: {"wrong_fact": 4, "tool_error": 2}, held: {"tool_error": 1, "wrong_fact": 3} | dev: {}, held: {} | Yes | 0.000526 | 0.000856 |

---

## (c) Company Names with HQ City (from corrected snapshot)

| Domain | Company | HQ City |
|--------|---------|---------|
| razorpay.com | Razorpay | Bengaluru |
| postman.com | Postman | San Francisco |
| browserstack.com | BrowserStack | Dublin |
| freshworks.com | Freshworks | San Mateo |
| swiggy.com | Swiggy | Bengaluru |
| chargebee.com | Chargebee | Rockville |
| figma.com | Figma | San Francisco |
| linear.app | Linear | San Francisco |
| canva.com | Canva | Darlinghurst |
| notion.com | Notion | San Francisco |

*Source: data/snapshots/companies_real.json (rebuilt with city preference and title-case rule)*