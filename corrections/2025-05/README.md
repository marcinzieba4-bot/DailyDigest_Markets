# May 2025 historical market briefings

22 weekday editions, May 1–30, 2025, reconstructed in October 2026 using the
wide nine-section layout of the August 2026 reports. Each date has HTML, PDF and
machine-readable JSON. Exchange holidays still receive weekday editions, with
previous completed local sessions clearly identified.

The newest remote source branch at acquisition was
`codex/jun-2025-retrospective-20261030`, commit
`47823bbed891b32edacbc12523eff4f72fc48f55`. This May work is isolated on
`codex/may-2025-retrospective-20261030` and does not change the live Lambda.

## Historical boundary

News timestamps must be strictly earlier than the report date at 00:00 UTC.
Writers receive only their matching dated feed and market card. News and
previews use a seven-day window, results fourteen days, and macro/background
thirty-five days. Cited Google News URLs are resolved and screened for
publisher-path date conflicts. Any explicit availability exception must bind
independent timing evidence and appear in the source ledger; it cannot admit
later article facts.

Claims use the actual eligible headline or frozen market card. Original publisher
article bodies and their historical vintages are not independently archived.
Independent factual review covers the selected clauses and subsequent edits
listed in `checks/independent_selected_review.json`; it is not exhaustive review
of every sentence. Historical prices are current-vintage vendor data, so later
vendor revisions cannot be ruled out. Displayed share prices restore historical
units after later splits; returns use split-adjusted closes and exclude dividends.

## Inputs and checks

- `feeds/`: final compressed own-date news feeds (downloadable source ZIP).
- `feeds_initial/`: preserved initial drafting snapshots with their original hashes.
- `cards/`, `data/`, `audit/`: market cards, underlying series and provenance.
- `specs/`: narrative and the exact own-date source identifiers.
- `checks/`: author, selected-claim, chronology, retail and artifact receipts.
- `html/`, `json/`, `pdf/`, `collection/`: checked exports and collection downloads.

A coverage review found that shared weekly RSS queries could omit eligible
earlier-cutoff news even below the result ceiling, including late-Sunday EU
tariff headlines. The repair adds 7,040 prefixes ending at each straddled report
cutoff and refines capped windows into daily queries. Its 8,172 additional unique
query URLs bring the total to 11,096; 79,000 eligible rows were appended while
preserving every original item and citation ID. The remaining 109 distinct daily
search caps are disclosed.

Initial snapshots remain byte-exact in `feeds_initial/`. The initial
`tools/fetch_news.py` / `build_feed` path preserves v1 acquisition and replay;
final exports require the completed `tools/expand_capped_news.py` path and its
independent 22-date review. `tools/review_gate.py` checks current initial/final
feed hashes, acquisition code, the 130-file snapshot inventory and supporting
receipts before every build. The source download includes both feed versions,
draft and raw snapshots, the expansion check script and audit receipts.

The retail review compares strictly earlier editions and requires a documented
changed angle for full repeat stories. It does not impose a ticker or sector
quota. Full-month frequency diagnostics are a review aid, never future
information supplied to an earlier historical writer.

## Reproduce and validate

From this directory, with the frozen feeds extracted in place:

```sh
python tools/verify.py
python tools/audit_source_dates.py --offline
python tools/audit_attributions.py
python tools/review_gate.py
python ../retail-quality/retail_quality.py . \
  --decisions checks/retail_editorial_decisions.json \
  --output checks/retail_quality.json --require-reviewed
python tools/build_artifacts.py
python tools/finalize.py --local-only
```

Install the Python dependencies from `requirements.txt`. The builder also needs
Chromium at `/usr/bin/chromium`. The shared retail guard is
`../retail-quality/retail_quality.py`. Frozen feeds are excluded from git and
preserved separately in `May_2025_Frozen_News_Feeds.zip`. The report ZIP contains
an offline index and every HTML/PDF/JSON edition.

Publication is a separate gated step using the configured AWS runtime bindings:
`tools/publish.py` and `tools/publish_sources.py` default to dry-run. The publisher
backs up replaced files, conditionally updates origin objects and merges archive
links while preserving concurrent additions. It never writes `latest.html`,
weekend editions, Lambda code, email or Telegram messages. Exact origin and public
SHA receipts, rather than an upload attempt, determine publication status. After completed publication and live verification, `python tools/check_finalization.py` checks that stale delivery receipts and changed timing proofs are rejected without changing real receipts; run the finalizer again afterward.

Acquisition methods, access diagnostics, conservative source exclusions and
retrieval limits are recorded in this month's actual audit receipts.

## Collection and downloads

- [Read all May editions](https://d7g7nkeytae81.cloudfront.net/reports/2025-05.html)
- [All HTML/PDF/JSON reports and offline index](https://d7g7nkeytae81.cloudfront.net/reports/2025-05/May_2025_Weekday_Reports.zip)
- [Frozen feeds and source audit receipts](https://d7g7nkeytae81.cloudfront.net/reports/2025-05/May_2025_Frozen_News_Feeds.zip)
- [Historical method and limitations](https://d7g7nkeytae81.cloudfront.net/reports/2025-05/methodology.txt)

These are the collection's publication destinations. `checks/final_validation.json`
records the completed validation and delivery scope after publication. Source
archive receipts bind every downloaded byte by SHA256.
