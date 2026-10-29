# July 2025 historical market briefings

23 weekday editions, July 1–31, 2025, reconstructed in October 2026 using the
wide nine-section layout of the August 2026 reports. Each date has HTML, PDF and
machine-readable JSON. July 4 is included as a weekday holiday edition, with the
previous completed US session clearly identified.

The repository's original main checkout contained only a README. The newest
source branch found at acquisition was `codex/aug-2025-retrospective-20261029`,
commit `634f1465a0ec398104df659f0b3ee2351b9aea10`. This July work is isolated on
`codex/jul-2025-retrospective-20261029`; it does not change the live Lambda.

## Historical boundary

News timestamps must be strictly earlier than the report date at 00:00 UTC.
Writers receive only their matching immutable feed and market card. News and
previews use a seven-day window, results fourteen days, and macro/background
thirty-five days. All cited Google News URLs are resolved and screened for
publisher-path date conflicts. Explicit exceptions document an original
publication or underlying release proved available before the cutoff, with
visible annotations in the source ledger. They do not admit later article facts.

Claims use the actual eligible headline or frozen market card. Original publisher
article bodies and their historical vintages are not independently archived.
Independent factual review covers the selected clauses and subsequent edits
listed in `checks/independent_selected_review.json`; it is not exhaustive review
of every sentence. Historical prices are current-vintage vendor data, so later
vendor revisions cannot be ruled out. Displayed share prices restore historical
units after later splits; returns use split-adjusted closes and exclude dividends.

## Inputs and checks

- `feeds/`: 23 immutable compressed own-date news feeds (downloadable source ZIP).
- `cards/`, `data/`, `audit/`: market cards, underlying series and provenance.
- `specs/`: narrative and the exact own-date source identifiers.
- `checks/`: author, selected-claim, chronology, retail and artifact receipts.
- `html/`, `json/`, `pdf/`, `collection/`: checked exports and collection downloads.

The retail review compares strictly earlier editions and requires a documented
changed angle for full repeat stories. It does not impose a ticker or sector
quota. The full-month frequency diagnostics are a review aid, never future
information supplied to an earlier historical writer.

## Reproduce and validate

From this directory, with the frozen feeds extracted in place:

```sh
python tools/verify.py
python tools/audit_source_dates.py --offline
python tools/review_gate.py
python ../retail-quality/retail_quality.py . \
  --decisions checks/retail_editorial_decisions.json \
  --output checks/retail_quality.json --require-reviewed
python tools/build_artifacts.py
python tools/finalize.py --local-only
```

Install the Python dependencies from `requirements.txt`. The builder also needs
Chromium at `/usr/bin/chromium`.
The shared retail guard is `../retail-quality/retail_quality.py`. Frozen feeds are
excluded from git and preserved separately in `July_2025_Frozen_News_Feeds.zip`.
The report ZIP contains an offline index and every HTML/PDF/JSON edition.

Publication is a separate gated step using the configured AWS runtime bindings:
`tools/publish.py` and `tools/publish_sources.py` default to dry-run. The publisher
backs up replaced files, conditionally updates origin objects and merges archive
links while preserving concurrent additions. It never writes `latest.html`,
weekend editions, Lambda code, email or Telegram messages. Exact origin and public
SHA receipts, rather than an upload attempt, determine publication status.

A temporary public-metadata-only GitHub Actions branch recovered canonical URLs
when the native gateway failed. The job received public news URLs and no AWS
credentials or report prose. Its hash-bound payloads were checked against the
exact requested URL set before import. This is documented in `audit/metadata_ci*`.

## Collection and downloads

- [Read all July editions](https://d7g7nkeytae81.cloudfront.net/reports/2025-07.html)
- [All HTML/PDF/JSON reports and offline index](https://d7g7nkeytae81.cloudfront.net/reports/2025-07/July_2025_Weekday_Reports.zip)
- [Frozen feeds and source audit receipts](https://d7g7nkeytae81.cloudfront.net/reports/2025-07/July_2025_Frozen_News_Feeds.zip)
- [Historical method and limitations](https://d7g7nkeytae81.cloudfront.net/reports/2025-07/methodology.txt)

`checks/final_validation.json` records the exact completed validation and delivery
scope. Source archive receipts bind every downloaded byte by SHA256.
