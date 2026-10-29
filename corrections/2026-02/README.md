> Retail revision published and verified: 20 reconstructed editions were exported with reviewed dated catalysts and continuation decisions. Live editions, including August 2026, are unchanged. Current proof: [final validation](checks/final_validation.json); shared publication and backups: [revision audit](../retail-quality/audit/final_validation.json).

# February 2026 — retrospective briefings for the 20 weekdays (2026-02-02 … 2026-02-27)

The report Lambda started publishing in March 2026, so February had no briefings. These 20 pages were written as of
each report's **information cutoff, 00:00 UTC on the report date**, in the layout of the March 2026 retrospective
briefings (same CSS, cutoff line, dated Google News citations, Yahoo Finance / US Treasury prior-close data, "Dated
sources" list, JSON copy with an `evidence` map, PDF from the Lambda's own renderer). Weekdays only, so 2026-02-16
(US Presidents' Day) is included; its US figures are the 2026-02-13 closes.

## Time discipline
- **News**: `tools/fetch_news.py` harvests Google News RSS with `after:/before:` bounds and keeps an item only if its
  RSS publication time is strictly before the cutoff (news 7 days, monthly releases 35 days, earnings reactions 14
  days, as in the Lambda). Google stamps most items with a date only (08:00 GMT), so an item dated the day before
  the report can be a late US-evening story; that is the same convention as the earlier archive passes. 217 short queries per date (US, Europe, China, Japan, Australia, Poland incl. Polish-language
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

Status: **live on S3 since 2026-10-26** (`tools/upload.py <20 dates> --go`): `reports/archive/2026-02-*.html`,
`Strategies/json/…` and `Strategies/….pdf`; the archive index went from 223 to 243 rows (its previous version is
under `reports/_retrospective_backup/february-weekdays/20261026T215814Z/`); CloudFront invalidation
I9070AIEUPDV8P4YAA73KQ9TJ3. No February object existed before, so nothing else was overwritten. All 20 pass
`verify.py` with 0 FAIL (6 WARN on 02-10 / 02-11: "this week" wording, each backed by a week-ahead headline);
70–92 cited headlines and 4,800–6,000 words per report.

Writers dropped, among others: misdated headlines (an April payrolls preview dated Feb 4, "ECB hike / 3.8% inflation"
items contradicting the 1.7% print, old FXStreet / ABC archive items with current dates), events that fell after the
cutoff although Google dated them earlier (RBA decision 03:30 UTC Feb 3, China's private PMI 01:45 UTC Feb 2, the
State of the Union 02:00 UTC Feb 25, Australia's CPI 00:30 UTC Feb 25, Monday Asia-session moves, Morning-Bid notes
written after Nvidia's results), live / rolling pages, and directions that conflict with the card.

## Layout
- `feeds/<date>.json.gz` — the harvested, date-bounded headlines (ids `nXXXX` are what the specs cite).
- `data/` — Yahoo daily closes and the Treasury par curve as downloaded; `cards/<date>.json` — per-report market card.
- `specs/<date>.json` — the written report (plain text + `[[nXXXX]]` citations).
- `html/<date>.html`, `json/<date>_Market_Intelligence.json` — rendered page and machine-readable copy (`tools/render.py`).
- `tools/upload.py <dates> [--go]` — publishes HTML, JSON and PDF under the archive keys, adds the index rows, backs up
  anything it overwrites under `reports/_retrospective_backup/february-weekdays/<UTC stamp>/`, invalidates CloudFront.
  `reports/latest.html` is not touched. Needs `LAMBDA_PY` pointing at the report Lambda source (PDF renderer).
- `posthoc/` — **not part of the reports and never visible to the writers** (prices after February, downloaded outside
  the repo while the reports were written): `score.py` measures the sector stances against the S&P 500 5 and 20
  sessions later.

## Post-hoc check of the calls (for the reader, not in the pages)
Sector stances vs the S&P 500 (SXAP vs STOXX 600), 20 reports × 13 sectors, overlapping windows (one month of
calls, so not independent evidence):

| Stance | n | 5 sessions: mean excess / hit | 20 sessions: mean excess / hit |
|---|---|---|---|
| Bullish | 117 | +1.26% / 87 of 117 | +1.33% / 50 of 117 |
| Bearish | 67 | −0.07% / 39 of 67 | −0.63% / 45 of 67 |
| Mixed | 76 | +0.31% | +0.30% |

Persistent month-long calls and their excess return vs the S&P 500 from Feb 2 to Mar 31 / Apr 30: Energy Bullish
16 of 20 days (+25.9% / +13.0%, the late-February Iran premium the feeds were already flagging), Utilities Bullish
16 (+12.0% / +4.4%), Semis Bullish 19 (+0.8% / +29.4%), Materials Bullish 16 (+7.3% / +0.6%), Industrials Bullish
20 (+3.7% / +1.6%); European autos Bearish 17 (−6.0% / −8.7% vs STOXX 600), Discretionary Bearish 16 (−4.1% /
−6.2%). The miss: Technology Bearish 12 (−1.7% to Mar 31, but +7.0% to Apr 30) — the "AI eats software" selloff
mean-reverted within two months.
