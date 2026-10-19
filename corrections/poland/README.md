# Poland-section widening of the archived briefings — work in progress

State saved from the session of 2026-10-19 so the job can resume without re-harvesting.

- `feeds/<date>.json` — Google News headlines (Polish and English) published in the 7 days up to 17:00 UTC on each
  report date, 117 dates (2026-06-25 … 2026-10-19). This is the only news source the writers may use for a date.
- `cards/<date>.json` — prior-session closes and 1W/4W moves for USD/PLN, EUR/PLN, EPOL and big Warsaw names.
- `old/<date>.html` — the original thin Poland block of each report.
- `new/<date>.html` — finished wide Poland blocks that pass `tools/verify_pl.py` (44 of 117 done; the rest still to write).
- `tools/BRIEF_PL.md` — the writing rules; `tools/verify_pl.py` — checks structure, length, dates not after the report
  date, and that every number comes from the feed or card; `tools/splice.py` — inserts a passing block into the report.
  Paths inside the tools point at the original scratch directory; adjust the `W` constants when resuming.

Remaining steps: write the missing blocks, splice all into the corrected reports (`corrections/2026-10-19/html/`),
rebuild JSON/PDF, upload with `corrections/2026-10-19/upload.py`, invalidate CloudFront.
The Lambda already carries the Poland-depth prompt and Polish feeds (deployed 2026-10-19).
