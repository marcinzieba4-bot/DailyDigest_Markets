> Retail revision: the reconstructed retail sections have been reviewed and revised. The new exports are prepared; public archive replacement is pending managed-network recovery. Live editions, including August2026, are unchanged. See [revision status](../retail-quality/README.md) and the shared final validation record.

# September 2025 weekday retrospective briefings

Published: 22 dated Market Intelligence Briefings, September 1–30, 2025, in the wide August 2026 nine-section format. The opening price dashboard and sector leadership chart are omitted. The complete set contains 208,836 words and 526 PDF pages.

[Read September 2025](https://d7g7nkeytae81.cloudfront.net/reports/2025-09.html) · [Download HTML, PDF and JSON](https://d7g7nkeytae81.cloudfront.net/reports/2025-09/September_2025_Weekday_Reports.zip) · [Methodology](https://d7g7nkeytae81.cloudfront.net/reports/2025-09/methodology.txt)

All 22 editions passed structural, numerical, citation-window and desktop/mobile checks. Each has an independent selected factual review and a separate consistency sample; those are not exhaustive original article-body verification. All 516 cited direct Reuters URLs passed the canonical-date check with no lookup failures or unresolved conflicts. Three release-guard matches were reviewed as false positives. The 68-entry ZIP was checked against all 66 daily artifact hashes and its methodology. Publication receipts and final public-delivery verification are under checks/.

## Inputs and historical boundary

Each report uses only its own frozen news feed and market card, strictly before its date at 00:00 UTC. News/policy/previews use seven days, results fourteen days and monthly releases thirty-five days. The 22 ready feeds contain 200,238 own-date headline records, with zero age/cutoff violations, duplicate IDs or failed source windows. The harvest covers 440 topics and 2,924 shared windows; 180 may be capped, so coverage is broad rather than exhaustive.

Priority Reuters screening checked 1,862 per-report records and conservatively excluded 147 unverified date conflicts, preserving surviving IDs. All 516 cited direct Reuters URLs passed the separate canonical-date audit, with zero failed lookups or unresolved conflicts. Early-local releases are assessed in UTC, with documented timing exceptions where appropriate. Headlines supply headline facts only; original article bodies and vintages are not independently archived.

Each of the 22 market cards has 292 instruments. Verified existing histories were supplemented with actual July observations, restoring complete September 1 comparisons through foreign exchange holidays. The matrix passes 66,017 assertions. ZoneInfo determines exchange dates; crypto uses completed UTC days. Split-adjusted closes supply comparable returns, reconstructed as-traded levels supply displayed prices, and CMCSA levels are suppressed because of its spin-off adjustment. Pre-split historical price references are not direct post-split triggers. Official US Treasury 2Y/10Y yields and changes use basis points. Labor Day keeps August 29 US closes in the September 2 report.

Current-vintage historical quotes may contain later vendor revisions; futures may reflect contract rolls. These limits and publisher-index timestamp uncertainty are retained in the methodology.

## Frozen news archive

[Download all 22 frozen feeds and provenance](https://d7g7nkeytae81.cloudfront.net/reports/2025-09/September_2025_Frozen_News_Feeds.zip). The 50.9 MB ZIP passed origin and public SHA256 verification. Extract it into this directory before rebuilding. Large raw feeds and generated PDF/ZIP files stay out of Git; every cited evidence item is also included in report JSON.

## Access recovery

An intermittent managed HTTPS tunnel fault returned Envoy 503 despite ready environment credentials and policy. Market inputs were restored through validated caches plus actual July requests. An isolated GitHub workflow retrieved the remaining public news inputs; 21 per-date bundles were imported only after artifact and ready-feed hash checks, while the first local feed stayed unchanged. The workflow uses contents-read permission, no AWS credentials and no production report invocation. Source provenance is in audit/news_ci_ingestion.json and checks/access_recovery.json. A second metadata-only CI job recovered 13 cited URLs; its verified artifact is documented in audit/cited_metadata_ci_ingestion.json. The temporary recovery PR was closed without merging. No proxy bypass or credential change was used.

## Rebuild and publication

Python 3.12, Playwright, pypdf, boto3 and BeautifulSoup are required. Chromium is /usr/bin/chromium. In this workspace use system Python for browser exports and /workspace/.report-tools/bin/python for AWS operations.

```sh
python tools/build_artifacts.py
/workspace/.report-tools/bin/python -I tools/publish.py
/workspace/.report-tools/bin/python -I tools/publish.py --go --attempts 6 --backoff-seconds 2 --max-backoff-seconds 15
```

The dry run does not access AWS. The publisher requires all 22 checked reports and exact input/artifact hashes, backs up replacements, conditionally merges the archive index and verifies all 69 stored artifacts. Public reports/* routing serves the HTML, collection, method and full ZIP; backend Strategies/* PDF/JSON files are publicly delivered within the ZIP. The latest report and weekend objects are protected. Interrupted upload/verification stages can resume with the original receipt. The source archive uploader separately preserves verified multipart progress. AWS_KEY/AWS_SECRET are selected explicitly; no credential values are saved.

Specs are canonical. Ignored authoring scripts must not regenerate final prose after repairs. Reviewer-only release chronology, source-date checks and per-date critical samples remain under posthoc/ and checks/. Writers must not read later-date inputs or reviewer chronology.
