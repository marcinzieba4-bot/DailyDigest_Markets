# February 2026 — retrospective briefings for the 20 weekdays (2026-02-02 … 2026-02-27)

The report Lambda started publishing in March 2026, so February had no briefings. These 20 pages were written as of
each report's **information cutoff, 00:00 UTC on the report date**, in the layout of the March 2026 retrospective
briefings (same CSS, cutoff line, dated Google News citations, Yahoo Finance / US Treasury prior-close data, "Dated
sources" list, JSON copy with an `evidence` map, PDF from the Lambda's own renderer). Weekdays only, so 2026-02-16
(US Presidents' Day) is included; its US figures are the 2026-02-13 closes.

## Time discipline
- **News**: `tools/fetch_news.py` harvests Google News RSS with `after:/before:` bounds and keeps an item only if its
  RSS publication time is strictly before the cutoff (news 7 days, monthly releases 35 days, earnings reactions 14
  days, as in the Lambda). 217 short queries per date (US, Europe, China, Japan, Australia, Poland incl. Polish-language
  queries, sectors, earnings, crypto, flows, retail, geopolitics), 0 failed queries.
- **Market data**: `tools/fetch_market.py` + `tools/build_cards.py`. Each card holds only completed observations
  dated before the report date (exchange-local session dates; crypto UTC days; Treasury par curve at the prior
  business day) with 1-, 5- and 20-session changes. The pipeline reproduces the figures printed in the 2026-03-02
  archive page exactly (2Y 3.38%, 10Y 3.97%, +59 bps, S&P 500 6,878.88, DXY 97.61, BTC 65,738.10).
- **Writing**: `BRIEF.md`. Ten writers, two consecutive dates each, written in date order and allowed to open only
  their date's files. Every fact cites a feed item; every number must be in the card or in a headline cited in the
  same paragraph.
- **Checks**: `tools/verify.py` (structure and labels, citations exist in that date's feed, number traceability,
  no month-day reference on/after the report date unless a cited headline carries it, data-source tags match card
  session dates, no hindsight wording, no copper-as-growth-gauge).

Status: work in progress — data harvested and tooling in place; reports being written and verified.

## Layout
- `feeds/<date>.json.gz` — the harvested, date-bounded headlines (ids `nXXXX` are what the specs cite).
- `data/` — Yahoo daily closes and the Treasury par curve as downloaded; `cards/<date>.json` — per-report market card.
- `specs/<date>.json` — the written report (plain text + `[[nXXXX]]` citations).
- `html/<date>.html`, `json/<date>_Market_Intelligence.json` — rendered page and machine-readable copy (`tools/render.py`).
- `tools/upload.py <dates> [--go]` — publishes HTML, JSON and PDF under the archive keys, adds the index rows, backs up
  anything it overwrites under `reports/_retrospective_backup/february-weekdays/<UTC stamp>/`, invalidates CloudFront.
  `reports/latest.html` is not touched. Needs `LAMBDA_PY` pointing at the report Lambda source (PDF renderer).
