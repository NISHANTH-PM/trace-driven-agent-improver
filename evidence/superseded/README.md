# Superseded Evidence

This directory contains evidence files from earlier runs that have been superseded by later corrections.

## Files

### pack_run_20261011_222702.json
- **Run on companies later found to be mis-matched by Crustdata**: This run used the initial snapshot which included `meesho.com` (matched to "Fashnear Technologies Private Limited" instead of Meesho) and `notion.so` (matched to "Hustá" instead of Notion). These companies were removed in the corrected snapshot (commit 0762a0c) because they failed the domain acceptance rule (primary_domain mismatch).

### pack_run_20261011_224432.json
- **Run before the fact-check formatting fix**: This run was performed before the fix in `app/pack/checks.py` (commit db39c70) that normalized formatting for `last_round` (underscores vs spaces/hyphens), `hq_city`, and `total_funding_usd` (float to int). As a result, the candidate run shows 9 false mismatches on `last_round` (e.g., "secondary_market" vs "secondary market", "series_d" vs "Series D"). See `evidence/diagnosis_20261011_224432.md` for details.

### pack_ablation_20261011_225757.json
- **First ablation run (before checker fix and snapshot correction)**: This was the first ablation run on real Crustdata snapshots. It was run before:
  1. The fact-check formatting fix (commit db39c70) - so it suffers from the same false mismatches as 224432
  2. The HQ city fix (this commit) - so it uses the old `hq_city` values from `locations.headquarters` first comma segment
  3. The corrected snapshot with proper domain acceptance (commit 0762a0c)
  
  The candidate config achieved 5/6 dev and 4/4 held-out (83.3% dev, 100% held-out) with 1 wrong_fact failure.

### real_data_results.md
- **Original results table**: Described data from the superseded runs above. Replaced by a new version generated from the final corrected runs.

### repeat_runs_20261011_230408.md
- **Original repeat runs table**: Described 4 runs including superseded data. Replaced by a new version generated from the final 3 corrected runs.

---

These files are **not deleted** but kept for transparency and audit trail. They should not be used for decision-making as they reflect earlier, incorrect data or code states.