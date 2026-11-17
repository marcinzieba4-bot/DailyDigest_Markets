November 2023 retrospective — Market Intelligence Briefings

22 Monday–Friday editions, 1–30 November 2023, including exchange holidays (US Thanksgiving,
23 November). Wide nine-section August 2026 layout, no top price dashboard or sector chart.
Built on the April 2024 retrospective pipeline (branch codex/apr-2024-retrospective-20261110,
commit 482f7f7) with the same author contract; see BRIEF.md / AUTHORING.md.

Deliverables — published 2026-11-17 to zembihf.xyz (receipt: checks/publication.json)
  https://zembihf.xyz/reports/2023-11.html
  https://zembihf.xyz/reports/2023-11/What_Retail_Is_Playing_2023-11.html
  https://zembihf.xyz/reports/2023-11/November_2023_Weekday_Reports.zip
  (archive index updated with 22 links; CloudFront invalidation completed)
  html/2023-11-DD.html                         22 archive pages with dated source ledgers
  json/2023-11-DD_Market_Intelligence.json     22 machine-readable copies
  pdf/                                         22 PDFs (gitignored; regenerate with tools/build_nov2023.py)
  retail/What_Retail_Is_Playing_2023-11.html   the month's retail collection (lead + 3 trades per day)
  collection/2023-11.html                      archive index page
  collection/methodology.txt                   sources and historical method
  collection/November_2023_Weekday_Reports.zip HTML + PDF + JSON bundle (gitignored)
Totals: 222,710 words, 729 PDF pages; each edition 9,942–10,324 words, ≥127 distinct dated sources.

Historical boundary
Each edition uses only information before 00:00 UTC on its date: Google News RSS headlines
(news/previews 7 days, company results 14, macro releases 35), Yahoo Finance completed sessions
(crypto: prior UTC candle) and the US Treasury par curve. 16,331 own-cutoff query windows were
acquired (no failed or capped query). A release-clock screen (138 scheduled releases, decisions,
results and staged events) plus 326 editorial exclusions remove records that report outcomes
before they existed (day-granular index stamps), later-vintage evergreen pages, rolling/live pages
and semantic traps (e.g. a Ukrainian budget headline easily misread as Poland's). Numeric spot-FX
marks are excluded; DXY remains. Headlines are not article bodies.

Authoring and review
Nonretail sections: one writer per date. Retail ("What Retail Is Playing"): a dedicated
chronological writer chain using only strictly earlier retail notes as editorial memory, in the
vivid August 2026 voice. Every component received an independent AI review (not human) by an
agent other than its author; 345 findings were recorded and resolved (receipts in
audit/independent_{nonretail,retail}_DATE.json bind feed, card, exclusions and component hashes).
Root post-review corrections are recorded as root_deltas/exclusion_rebinds in those receipts.
The retail-quality gate (tools/retail_quality_snapshot.py --require-reviewed) passes for all 22
dates with 0 hard failures and 0 unresolved flags (checks/retail_quality.json).
Cost-saving note: reviews of 9–30 November ran on a smaller model; reviewers there were sometimes
more conservative than necessary (e.g. removing valid after-close Palo Alto results).

Retail leads
11-01 Bitcoin (ETF front-running) · 11-02 AMD · 11-03 Eli Lilly · 11-06 ARKK · 11-07 Microsoft
11-08 WTI crude · 11-09 Eli Lilly (Zepbound) · 11-10 Ether · 11-13 Plug Power · 11-14 Boeing
11-15 Russell 2000 · 11-16 Target · 11-17 Walmart · 11-20 Microsoft (OpenAI) · 11-21 Nvidia
11-22 Bitcoin (Binance) · 11-23 Nvidia · 11-24 Novo Nordisk · 11-27 Amazon · 11-28 Tesla
11-29 Marathon Digital · 11-30 GameStop

Rebuild
  python3 tools/verify.py                      # all 22 specs PASS
  python3 tools/retail_quality_snapshot.py . --output checks/retail_quality.json --require-reviewed
  python3 tools/build_nov2023.py               # html/json/pdf, retail page, archive, ZIP
Publication: python3 tools/publish_nov2023.py [--go] (create-only S3 writes, index backup + conditional
merge, scoped CloudFront invalidation). No Lambda invocation, deployment, e-mail or Telegram message.
Large caches (cache/, work/) are not committed; query plan and request ledgers are kept gzipped in audit/.
