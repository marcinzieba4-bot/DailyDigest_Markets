# April 2025 historical market briefings

22 weekday editions, April 1–30, 2025, reconstructed in October 2026 using the
wide nine-section layout of the August 2026 reports. Each edition has HTML, PDF
and machine-readable JSON. Exchange holidays receive weekday editions, with each
instrument's completed local session identified.

The newest remote application source at acquisition was
`codex/may-2025-retrospective-20261030`, commit
`774dc11cbfbd2c45709e0396ca42b0c34b96f90f`. This April work is isolated on
`codex/apr-2025-retrospective-20261030`. The code-discovery receipt records the
remote branch inventory used for that choice.

## Historical boundary

News timestamps must be strictly earlier than the edition's report date at
00:00 UTC. Writers receive only their matching dated feed and market card.
News and previews use a seven-day window, results fourteen days, and
macro/background thirty-five days. Claims use eligible headline facts or the
frozen market card. Original publisher article bodies and their historical
vintages are not independently archived.

Acquisition includes prefixes ending at every report cutoff straddled by a
shared weekly query, and daily refinements of capped multi-day queries, before
drafting. A date's merge accepts only query windows ending at or before that
date. Search caps and approximate news-index timestamps remain disclosed limits;
the coverage and readiness audits contain the actual request counts, exclusions
and outstanding daily caps. Parsed query-response caches, raw own-date snapshots,
metadata, final feeds and acquisition code are listed in
`audit/news_replay_inventory.json` and preserved in the source download.
These are retrieval-time historical search results; original RSS XML and
contemporaneous 2025 server responses are not archived.

Cited Google News URLs are resolved and screened for publisher-date conflicts.
Any explicit availability exception must bind independent timing evidence and
appear in the source ledger; it cannot admit later article facts. Independent
factual review covers the selected clauses and subsequent edits listed in
`checks/independent_selected_review.json`; it is not exhaustive review of every
sentence.

Historical prices are current-vintage vendor data, so later vendor revisions
cannot be ruled out. Displayed share prices restore historical units after later
splits; returns use split-adjusted closes and exclude dividends. Instrument
calendars, unavailable histories and corporate-action limits are recorded in the
market audits. Treasury yield changes and curve spreads use basis points.

The April acquisition retained 255,468 records across 22 frozen own-date feeds,
with 135 conservative exclusions from 255,603 raw records. All 11,211 query URLs
were retrieved successfully; 135 daily result caps remain a disclosed search
limit. Independent replay verified the 11,381-file inventory and 515,772
response-lineage edges.

Native canonical lookups encountered a Google challenge, and the managed HTTPS
tunnel subsequently returned HTTP 503 before Google, Treasury and S3 responses.
Reviewed public-URL-only GitHub Actions jobs recovered the affected RSS and
canonical metadata, with exact code, input, run, job, artifact and byte-hash
bindings. No publisher bodies, report prose or AWS credentials were sent to those
jobs. Normal CloudFront and credentialed S3 reads later recovered without local
proxy, TLS, IAM or credential changes. Actual evidence is in `audit/` and the
frozen replay inventory; mutable later cited-only mappings are kept separate.

## Inputs and checks

- `feeds/`: final compressed own-date news feeds, preserved in the source ZIP.
- `cards/`, `data/`, `audit/`: market inputs, source evidence and provenance.
- `specs/`: report narrative with exact own-date citation identifiers.
- `checks/`: author, selected-claim, chronology, retail and artifact receipts.
- `html/`, `json/`, `pdf/`, `collection/`: checked exports and collection downloads.

`tools/review_gate.py` binds current evidence, editorial and timing receipts.
The builder records that proof in `checks/artifact_manifest.json`; publication
and finalization reject proof drift. The source ZIP includes the replay
inventory and its exact files, market inputs, narrative specifications, code and
review receipts available at build time. Delivery receipts produced afterward
are retained in the source repository.

The retail review compares strictly earlier editions and requires a documented
changed angle for full repeat stories. It does not impose ticker or sector
quotas. Full-month frequency diagnostics are a review aid, never future
information supplied to an earlier historical writer.

## Reproduce and validate

From this directory, with the frozen source ZIP extracted in place:

```sh
python tools/check_news_acquisition.py
python tools/check_review_gate.py
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

Install Python dependencies from `requirements.txt`; PDF rendering also needs
Chromium at `/usr/bin/chromium`. The shared retail guard is checked into the
repository at `../retail-quality/retail_quality.py`. The report ZIP contains an
offline index and every HTML/PDF/JSON edition. The source ZIP is separate.

Rerunning a timestamped source or editorial audit changes its proof hash.
After rebuilding a local collection, use its newly generated manifest; do not
replace a published frozen archive or reuse its publication receipt with a
different build.

Publication is a gated step using the configured AWS runtime bindings.
`tools/publish.py` and `tools/publish_sources.py` default to dry-run. Publication
backs up replaced files, conditionally updates origin objects and merges archive
links while preserving existing additions. Protected objects include
`latest.html` and all eight April weekend dates in three formats. Exact origin
and public SHA receipts determine publication status. No Lambda invocation,
email or Telegram message is part of this pipeline.

After publication and live verification, `python tools/check_finalization.py`
checks that stale delivery receipts and changed timing proofs are rejected
without changing real receipts. Run the finalizer again afterward.

## Collection and downloads

- [Read all April editions](https://d7g7nkeytae81.cloudfront.net/reports/2025-04.html)
- [All HTML/PDF/JSON reports and offline index](https://d7g7nkeytae81.cloudfront.net/reports/2025-04/April_2025_Weekday_Reports.zip)
- [Frozen feeds and source audit receipts](https://d7g7nkeytae81.cloudfront.net/reports/2025-04/April_2025_Frozen_News_Feeds.zip)
- [Historical method and limitations](https://d7g7nkeytae81.cloudfront.net/reports/2025-04/methodology.txt)

These are the collection's publication destinations.
`checks/final_validation.json` records completed validation and delivery scope
when publication finishes.
