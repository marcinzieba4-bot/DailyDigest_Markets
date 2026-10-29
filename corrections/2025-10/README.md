> Retail revision: the reconstructed retail sections have been reviewed and revised. The new exports are prepared; public archive replacement is pending managed-network recovery. Live editions, including August2026, are unchanged. See [revision status](../retail-quality/README.md) and the shared final validation record.

# October 2025 weekday retrospective briefings

23 dated Market Intelligence Briefings, October 1–31, 2025, in a wider version of the August 2026 nine-section layout. Each has HTML, PDF, JSON and linked dated evidence. The top price dashboard and sector leadership chart were removed at the user’s request; the nine report sections and their dated analysis are unchanged.

[Open the month collection](https://d7g7nkeytae81.cloudfront.net/reports/2025-10.html) · [Download HTML/PDF/JSON](https://d7g7nkeytae81.cloudfront.net/reports/2025-10/October_2025_Weekday_Reports.zip) · [Historical method and limits](https://d7g7nkeytae81.cloudfront.net/reports/2025-10/methodology.txt)

The base is the newest remote branch found at task discovery: `1c7b3594e68e7252634a32793634007a79f889d7` (October 28, 2026). The live Lambda is not invoked: its handler uses current-time inputs and delivery channels.

## Historical boundary

News is strictly before each report date at 00:00 UTC: 7-day news/policy/previews, 14-day results, 35-day monthly releases. Each writer uses only the own-date frozen feed and market card. Obvious RSS date mismatches, rolling pages and later-day releases are excluded. Independent primary release-date checks cover selected high-risk events.

Yahoo daily observations use completed prior exchange-local sessions. Later splits are reversed for displayed historical price units; returns use comparable split-adjusted closes and exclude dividends. CMCSA levels are suppressed because its adjustment includes a spin-off. Treasury uses actual official 2Y/10Y par yields and basis-point changes. The October 13 bond holiday is handled separately from equity sessions.

Original article vintages are not independently archived, current-vintage historical quotes may contain later vendor revisions, and 228 Google News query windows may be capped. Coverage is broad and is not asserted exhaustive. The source ledger and method describe these limits.

## Files and checks

`specs/` is authoritative prose; scratch authoring scripts must not regenerate final specs. `feeds/` contains frozen own-date evidence, `cards/` the dated market observations, and `html/`/`json/` the rendered copies. PDFs and the ZIP are reproducible generated artifacts and are not committed.

`checks/artifact_manifest.json` binds final specs, inputs and rendered files by SHA256. `checks/independent_factual_review.json` records all 23 critical-claim samples and seven authorized precision repairs; this was not exhaustive fact verification. `checks/editorial_root_notes.json` records release-boundary review. `audit/market_validation.json` records 34,539 passing market checks. Publication status and backup keys are in `checks/publication.json` after upload.

## Frozen news source archive

The complete 23 dated feeds (199,847 own-date headline records) are preserved in a [separate frozen source archive](https://d7g7nkeytae81.cloudfront.net/reports/2025-10/October_2025_Frozen_News_Feeds.zip). Keeping the raw search snapshot out of Git avoids large, unreliable code pushes. The rendered JSON committed here still contains every cited evidence item. Extract the full source ZIP into this directory before rebuilding; it restores `feeds/<date>.json.gz` with the original hashes and IDs. `checks/source_archive_publication.json` records the archive digest.

## Rebuild and publish

Python 3.12, matplotlib, pypdf, Playwright, boto3 and BeautifulSoup are required, with Chromium at `/usr/bin/chromium`. In this workspace, use the system Python for browser exports and `/workspace/.report-tools/bin/python` for AWS operations.

```sh
python tools/build_artifacts.py
/workspace/.report-tools/bin/python tools/publish.py
/workspace/.report-tools/bin/python tools/publish.py --go
```

The dry run makes no remote changes. The publisher requires the full validated 23-date manifest, checks input/artifact hashes, backs up replaced objects, merges the archive index conditionally, uploads all formats, and invalidates only the written paths. It never invokes email or Telegram delivery. Runtime authentication uses ready `AWS_KEY`/`AWS_SECRET` bindings through a boto3 session; no credential values are saved here.

The stale README-only checkout was resolved by fetching all remote branches into an isolated worktree. Authenticated S3, Lambda metadata, CloudFront, Yahoo Finance, US Treasury and Google News were verified. Anonymous S3 origin access is private by design; authenticated S3 and the public CloudFront route work.

Final set: 226,433 verified words and 2,673 per-report distinct cited-headline entries. PDF totals are recorded in the artifact manifest. All 23 reports pass structural, numerical and cutoff checks.

## Recovered publication

The managed HTTPS tunnel temporarily returned Envoy503 across S3, CloudFront and GitHub. Approved requests recovered without credential or network-policy changes. The publisher now supports safe `--resume`, bounded backoff, atomic GET/SHA verification, version checks that reuse earlier SHA proofs, and incremental confirmations. The original backups and run identity were retained. All 72 artifacts were verified before the index merge; the latest daily report and weekend objects were unchanged. CDN invalidation completed.

Resume command for an interrupted run:

```sh
/workspace/.report-tools/bin/python -I tools/publish.py --resume --go --attempts 6 --backoff-seconds 2 --max-backoff-seconds 15
```

`checks/transport_diagnosis.json` retains the failure and recovery record. `checks/live_verification.json` records public CDN content-hash checks after publication.

The public CDN routes `reports/*` to the report bucket root. Canonical `Strategies/*` files are backend storage; every PDF/JSON is also included in the public downloadable ZIP. Public verification therefore hashes all 23 HTMLs, the month collection, methodology and full ZIP, while origin verification covers all 72 stored artifacts.
