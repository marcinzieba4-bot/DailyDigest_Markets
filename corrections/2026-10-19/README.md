# Retrospective correction of the archived briefings (2026-06-25 to 2026-10-18)

What is here:

- `html/` — the 116 corrected reports, same file names as `reports/archive/` in S3. Only US Treasury yield / curve
  sentences were changed; everything else is untouched. No wording indicates a correction.
- `json/` — matching machine-readable copies (same structure as `Strategies/json/`, original `date` and `generated_at` kept).
- `cards/` — per-report ground truth used for the edits: official Treasury closes up to the prior business day, the live
  10Y reading the report already contained, 4-week changes in bps, curve shape and curve-move labels. Nothing after the
  report date was used.
- `CORRECTIONS_SUMMARY.md` — before/after table of the key figures for every date.
- `upload.py` — writes the corrected files to S3 under the original keys (backing originals up first) and invalidates
  CloudFront. See its docstring. It regenerates the PDFs with the Lambda's own renderer.
- `BRIEF.md`, `verify.py`, `cards.py`, `truth.py`, `totext.py` — the editing rules and checks used to produce and verify
  the corrections (verify.py expects the scratch-directory layout it was written for; kept for reference).

The two bugs, both fixed in `lambda_function.py` on this branch:

1. The "US 2Y" in the quant snapshot was the Yahoo 13-week T-bill (^IRX). The 10Y-2Y spread was therefore overstated by
   roughly 50 to 80 bps and the curve was called "normal" or "steep" when it was flat.
2. Yield changes were quoted as percent of the yield ("↑5.8%") instead of basis points (+25 bps).

Reports before 2026-06-25 exist only as JSON/PDF under `Strategies/` and were not corrected.
