> Retail revision published and verified: 20 reconstructed editions were exported with reviewed dated catalysts and continuation decisions. Live editions, including August 2026, are unchanged. Current proof: [final validation](checks/final_validation.json); shared publication and backups: [revision audit](../retail-quality/audit/final_validation.json).

# November 2025 weekday retrospective briefings

Twenty dated Market Intelligence Briefings, November 3–28, 2025, using the wide August 2026 nine-section structure. The opening price dashboard and sector leadership chart are omitted. HTML, PDF and machine-readable JSON are built from date-isolated source records and market cards.

[Open November 2025](https://d7g7nkeytae81.cloudfront.net/reports/2025-11.html) · [Download HTML PDF and JSON](https://d7g7nkeytae81.cloudfront.net/reports/2025-11/November_2025_Weekday_Reports.zip) · [Historical method](https://d7g7nkeytae81.cloudfront.net/reports/2025-11/methodology.txt)

## Historical boundary

The news cutoff is strictly before each report date at 00:00 UTC. Eligible source ages are 7 days for news/policy/previews, 14 days for earnings results and 35 days for monthly releases. After deduplication, 21 category-window mismatches were removed while preserving surviving IDs. The frozen feeds contain 163,721 own-date headline records, with zero failed source queries and zero remaining timestamp/window violations. Headlines supply headline facts only. Misdated outcomes and rolling pages are excluded editorially. A cached publisher-URL audit resolves cited Reuters links through Google News metadata; same-day date mismatches trigger claim review, with UTC assessment of early-local releases. Candidate dispositions and repairs are retained in checks/reuters_repairs_*.json.

Market observations use completed prior exchange-local sessions with ZoneInfo, and completed UTC days for crypto. Displayed levels reverse later stock splits into historical share units; returns use comparable split-adjusted closes. CMCSA price levels are withheld because of a spin-off adjustment. Official US Treasury 2Y/10Y par yields and basis-point changes handle bond holidays separately from stocks. All 20 cards pass 30,156 market assertions.

Original article vintages are not independently archived and current-vintage historical quotes may contain later vendor revisions. Search-index limits mean coverage is broad rather than exhaustive. Selected release-date checks record their evidence and timing uncertainty explicitly.

## Source code and inputs

The original base was commit 1c7b3594e68e7252634a32793634007a79f889d7. A fresh remote-branch discovery found 75f12ededa072406eb74b841f6b971b2977119fe, which added November split repairs and a compact dossier tool. Its relevant changes are covered by the stronger October market machinery and copied dossier tool; checks/code_discovery.json records the comparison.

Authoritative prose is in specs/. Writers use only their own date’s feeds/ and cards/ files. Full raw feeds are restored from the [frozen source archive](https://d7g7nkeytae81.cloudfront.net/reports/2025-11/November_2025_Frozen_News_Feeds.zip) before rebuilding. The 39.5 MB archive contains all 20 ready feeds and eligibility-repair records; origin and public SHA256 checks passed (checks/source_archive_publication.json). Generated PDF/ZIP files are not committed. Future corporate-action audit metadata stays outside writer inputs.

## Rebuild and publish

Python 3.12, Playwright, pypdf, boto3 and BeautifulSoup are required. Chromium is /usr/bin/chromium. In this workspace use system Python for browser export and /workspace/.report-tools/bin/python for AWS operations.

```sh
python tools/build_artifacts.py
/workspace/.report-tools/bin/python -I tools/publish.py
/workspace/.report-tools/bin/python -I tools/publish.py --go --attempts 6 --backoff-seconds 2 --max-backoff-seconds 15
```

The publisher requires all 20 validated weekday reports and matching input/artifact hashes. It backs up replacements, conditionally merges the archive index, verifies exact bytes, and invalidates the affected CDN paths. It preserves reports/latest.html and weekend reports. Interrupted upload/verification stages can resume with --resume and the original checked artifacts. Runtime AWS_KEY/AWS_SECRET bindings are explicitly selected; no credential values are saved. No Lambda, email or Telegram delivery is invoked.

Public reports/* paths route to the report bucket. Canonical Strategies/* PDF/JSON keys are backend storage; public PDF/JSON delivery is inside the verified month ZIP. tools/verify_live.py checks public HTML, collection, method and ZIP hashes, while the publisher verifies all 63 stored artifacts.

## Review records

checks/existing_two_review.json records repairs to the two inherited reports. checks/independent_factual_review.json will record critical-claim samples for new reports, not exhaustive verification. checks/primary_release_timestamp_checks.json separates index-backed release dates from independently unverified intraday timing. audit/feed_window_repairs.json preserves rejected records and original/ready hashes. audit/market_access_audit.json records data corrections.

The final rendered set contains 187,681 words and 471 PDF pages across all 20 reports. Every report passes structural, numerical, news-window, desktop/mobile and removed-widget checks. The full ZIP has 62 files and no chart images. Final review covers selected critical claims in all 20 reports; 507 currently cited direct Reuters links pass canonical-date review, with two documented pre-midnight Japanese release exceptions. See checks/final_validation.json.

Publication receipts and public-content verification are recorded in checks/publication.json and checks/live_verification.json after upload. Download and extract the frozen source archive into this directory before rebuilding; the ZIP restores feeds/ and eligibility audit records with the checked hashes.


## Published and verified

Published October 29, 2026. All 63 stored artifacts passed exact-content verification; the public collection, 20 HTML reports, methodology and ZIP passed SHA256 checks. All 20 archive links are present and CDN refresh completed. The latest report and November weekend objects were unchanged. The frozen news source archive was separately verified in origin storage and through the public CDN. Receipts are in checks/publication.json, checks/live_verification.json and checks/source_archive_publication.json.
