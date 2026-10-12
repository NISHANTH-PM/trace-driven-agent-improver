# Demo Run Manifest

Generated: 2026-10-12T00:54:37.169048+00:00

## baseline_wrong_fact

| Field | Value |
|-------|-------|
| label | baseline_wrong_fact |
| case_id | D01 |
| company | Razorpay |
| domain | razorpay.com |
| config.retry_tool_errors | False |
| config.strict_prompt | False |
| config.verify_facts | False |
| config.version | baseline |
| failure_class | wrong_fact |
| success | False |
| tool_attempts | 1 |
| llm_calls | 1 |
| prompt_tokens | 555 |
| completion_tokens | 250 |
| cost_usd | 0.000093 |
| docx_path | outputs\demo\baseline_wrong_fact\D01_baseline.docx |
| start_time_utc | 2026-10-12T00:54:18.765986+00:00 |
| end_time_utc | 2026-10-12T00:54:21.505042+00:00 |
| issues | ['employee_count=4042 not stated exactly', 'total_funding_usd=816600000 not stated in accepted format'] |

**True Values:**

- employee_count: 4042
- founded_year: 2014
- hq_city: Bengaluru
- total_funding_usd: 816600000
- last_round: secondary_market

In neatlogs: search for `demo.label = baseline_wrong_fact` (or the span name `demo_baseline_wrong_fact`)

## baseline_tool_error

| Field | Value |
|-------|-------|
| label | baseline_tool_error |
| case_id | D02 |
| company | Postman |
| domain | postman.com |
| config.retry_tool_errors | False |
| config.strict_prompt | False |
| config.verify_facts | False |
| config.version | baseline |
| failure_class | tool_error |
| success | False |
| tool_attempts | 1 |
| llm_calls | 0 |
| prompt_tokens | 0 |
| completion_tokens | 0 |
| cost_usd | 0.000000 |
| docx_path | None |
| start_time_utc | 2026-10-12T00:54:21.505042+00:00 |
| end_time_utc | 2026-10-12T00:54:21.506884+00:00 |
| issues | ['tool failed'] |

**True Values:**

- employee_count: 3547
- founded_year: 2014
- hq_city: San Francisco
- total_funding_usd: 433000000
- last_round: series_d

In neatlogs: search for `demo.label = baseline_tool_error` (or the span name `demo_baseline_tool_error`)

## candidate_retry_recovery

| Field | Value |
|-------|-------|
| label | candidate_retry_recovery |
| case_id | D02 |
| company | Postman |
| domain | postman.com |
| config.retry_tool_errors | True |
| config.strict_prompt | True |
| config.verify_facts | True |
| config.version | candidate |
| failure_class | none |
| success | True |
| tool_attempts | 2 |
| llm_calls | 1 |
| prompt_tokens | 261 |
| completion_tokens | 283 |
| cost_usd | 0.000084 |
| docx_path | outputs\demo\candidate_retry_recovery\D02_candidate.docx |
| start_time_utc | 2026-10-12T00:54:21.506884+00:00 |
| end_time_utc | 2026-10-12T00:54:24.111467+00:00 |
| issues | [] |

**True Values:**

- employee_count: 3547
- founded_year: 2014
- hq_city: San Francisco
- total_funding_usd: 433000000
- last_round: series_d

In neatlogs: search for `demo.label = candidate_retry_recovery` (or the span name `demo_candidate_retry_recovery`)

## candidate_success

| Field | Value |
|-------|-------|
| label | candidate_success |
| case_id | D01 |
| company | Razorpay |
| domain | razorpay.com |
| config.retry_tool_errors | True |
| config.strict_prompt | True |
| config.verify_facts | True |
| config.version | candidate |
| failure_class | none |
| success | True |
| tool_attempts | 1 |
| llm_calls | 1 |
| prompt_tokens | 554 |
| completion_tokens | 305 |
| cost_usd | 0.000106 |
| docx_path | outputs\demo\candidate_success\D01_candidate.docx |
| start_time_utc | 2026-10-12T00:54:24.112467+00:00 |
| end_time_utc | 2026-10-12T00:54:26.785219+00:00 |
| issues | [] |

**True Values:**

- employee_count: 4042
- founded_year: 2014
- hq_city: Bengaluru
- total_funding_usd: 816600000
- last_round: secondary_market

In neatlogs: search for `demo.label = candidate_success` (or the span name `demo_candidate_success`)

## verify_regeneration

| Field | Value |
|-------|-------|
| label | verify_regeneration |
| case_id | D01 |
| company | Razorpay |
| domain | razorpay.com |
| config.retry_tool_errors | False |
| config.strict_prompt | False |
| config.verify_facts | True |
| config.version | verify_only |
| failure_class | none |
| success | True |
| tool_attempts | 1 |
| llm_calls | 2 |
| prompt_tokens | 1150 |
| completion_tokens | 506 |
| cost_usd | 0.000190 |
| docx_path | outputs\demo\verify_regeneration\D01_verify_only.docx |
| start_time_utc | 2026-10-12T00:54:31.899033+00:00 |
| end_time_utc | 2026-10-12T00:54:37.169048+00:00 |
| issues | [] |

**True Values:**

- employee_count: 4042
- founded_year: 2014
- hq_city: Bengaluru
- total_funding_usd: 816600000
- last_round: secondary_market

In neatlogs: search for `demo.label = verify_regeneration` (or the span name `demo_verify_regeneration`)

---

## Screenshot Checklist

| Scenario | Screenshot File | Description |
|----------|-----------------|-------------|
| a) baseline_wrong_fact | neat_baseline_fail.png | open the llm_draft I/O tab and the benchmark_case attributes |
| c) candidate_retry_recovery | neat_retry_recovery.png | span tree with two fetch_company spans |
| d) candidate_success | neat_candidate_success.png | |
| d) candidate_success | neat_llm_attributes.png | |
| d) candidate_success | neat_llm_io.png | |
| e) verify_regeneration | neat_verify_regeneration.png | llm_regenerate nested in verify_facts |
| a vs d | neat_compare.png | if the dashboard offers a compare view |

**Additional screenshots for CFO/Entire/GitHub:**

| Screenshot File | Description |
|-----------------|-------------|
| entire_checkpoints.png | `entire status` output |
| entire_graph_or_status.png | `entire-graph` output or `entire status` |
| cfo_scenario_comparison.png | CFO scenario comparison view |
| cfo_api_price_margin.png | CFO API price/margin view |
| cfo_pricing_assumptions.png | CFO pricing assumptions view |
| cfo_economics_cash.png | CFO economics/cash view |
| agent_output_docx.png | Open both D01 baseline and D01 candidate .docx in Word |
| ablation_table.png | Ablation table from evidence/ |
| github_commits.png | GitHub commits page |
| ci_green.png | CI green check |

D01 baseline .docx: outputs\demo\baseline_wrong_fact\D01_baseline.docx
D01 candidate .docx: outputs\demo\candidate_success\D01_candidate.docx
Open both in Word: agent_output_docx.png
