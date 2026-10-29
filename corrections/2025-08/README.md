# August 2025 retrospective briefings

Scope: all 21 Monday–Friday report dates from August 1–29, 2025, including weekday exchange holidays. Each report is reconstructed at 00:00 UTC on its report date, using only eligible earlier news and completed market sessions. The visual reference is the wide August 2026 nine-section report format.

The source base is commit `76f537b5a42c168c4d9b6777c23ed67427a628a8`, the newest remote branch head at discovery on October 29, 2026. The local checkout originally pointed to the README-only initial `main` commit. This month adapts the validated September retrospective pipeline rather than invoking the current-time production Lambda.

## Published collection

All 21 editions are published: 216,226 words and 524 PDF pages. The 66 origin artifacts, 24 public files, 21 archive links and the frozen-source ZIP passed body/hash verification. The latest report and weekend objects remain unchanged. [Final validation](checks/final_validation.json) records the authoritative completion state.

[Read the collection](https://d7g7nkeytae81.cloudfront.net/reports/2025-08.html) · [Download HTML, PDF and JSON](https://d7g7nkeytae81.cloudfront.net/reports/2025-08/August_2025_Weekday_Reports.zip) · [Methodology](https://d7g7nkeytae81.cloudfront.net/reports/2025-08/methodology.txt) · [Frozen sources](https://d7g7nkeytae81.cloudfront.net/reports/2025-08/August_2025_Frozen_News_Feeds.zip)

The final date screen covers 2,140 cited records and 1,394 distinct canonical URLs, with no unresolved conflicts. Three individually documented timing exceptions cover a Guardian Australia publication timestamp and two Japanese releases before midnight UTC. All 28 retail continuity flags have evidence-bound editorial decisions. Market validation passed 63,077 assertions. Selected independent factual reviews cover critical passages in every edition; these are not exhaustive original article-body verification.

The managed HTTPS tunnel intermittently failed despite ready credentials. Public-source metadata was recovered through an isolated, contents-read GitHub job, with hash-checked payloads and no credentials or publisher bodies. Native AWS access subsequently recovered, allowing ordinary publication and public verification. No credential or network-policy changes were made. See [access recovery](checks/access_recovery_final.json).

## Historical boundary

- Information cutoff: strictly before 00:00 UTC on each report date.
- Source-query lookbacks: seven days for fresh news and previews; fourteen days for company results; thirty-five days for macro releases and policy baselines. Query labels are approximate. Older policy or program evidence is dated background, not a newly completed event; stale ordinary company news is excluded.
- Indexed news timestamps require editorial checks against event timing. A preview cannot support a completed outcome; rolling pages are excluded.
- Writers use their own report date's frozen feed and market card. Later report evidence and later outcomes do not select earlier stances or retail themes.
- Historical quotes are current-vintage vendor observations. Returns use comparable split-adjusted prices; displayed levels restore contemporaneous share units where supportable. Original vendor vintages and unread article bodies cannot be assumed.

## Build and publication tools

The artifact builder and publisher require the complete month and the shared retail editorial review. Each edition must have checked HTML, PDF and JSON artifacts. The artifact manifest binds those outputs to exact spec, feed, market-card, renderer and builder hashes.

```sh
python tools/build_artifacts.py
/workspace/.report-tools/bin/python -I tools/publish.py
/workspace/.report-tools/bin/python -I tools/publish.py --self-test
```

Raw feeds, PDFs, ZIPs and authoring scratch files are excluded from Git. Before rebuilding, download the frozen-source ZIP above, verify its SHA256 against `checks/source_archive_publication.json`, and extract it into this directory. The canonical specs, dated market cards, market histories, renderer and audits are committed. Do not regenerate final prose from ignored authoring scripts. Rebuilt exports may contain new generation timestamps.

The publisher dry run performs no remote operations. Once all validation is complete, `--go` publishes the checked month; `--resume` retains the original backups and confirmed object hashes after interruption. Report and source-archive publication are separate operations:

```sh
/workspace/.report-tools/bin/python -I tools/publish.py --go --attempts 6 --backoff-seconds 2 --max-backoff-seconds 15
/workspace/.report-tools/bin/python -I tools/publish_sources.py --go
python -I tools/verify_live.py
```

Publication uses the existing configured AWS credentials without saving them. Replacements are backed up, object writes use preconditions, concurrent archive links are preserved, and the latest report and August weekend objects are protected. Email, Telegram and the live report Lambda are not invoked. All daily HTML pages, the collection, methodology and full report ZIP receive public SHA256 checks; PDF/JSON variants are delivered within that ZIP because their canonical `Strategies/*` storage keys are not public report routes.

Published keys: `reports/2025-08.html`, `reports/2025-08/August_2025_Weekday_Reports.zip` and `reports/2025-08/August_2025_Frozen_News_Feeds.zip`. Publication, backups and delivery receipts are under `checks/`.
