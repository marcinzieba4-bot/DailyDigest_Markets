February 2022 retrospective — Market Intelligence Briefings

20 Monday–Friday editions, 1–28 February 2022, including exchange holidays (US Presidents' Day,
21 February; Lunar New Year closures in China, Hong Kong and Korea; Japanese holidays on 11 and
23 February). Wide nine-section August 2026 layout, no top price dashboard or sector chart.
Built on the November 2023 retrospective pipeline (branch claude/funny-ramanujan-kvma9x) with the
same author contract, adapted for February 2022; see BRIEF.md / AUTHORING.md.

Deliverables — published 2026-11-18 to zembihf.xyz (receipt: checks/publication.json)
  https://zembihf.xyz/reports/2022-02.html
  https://zembihf.xyz/reports/2022-02/What_Retail_Is_Playing_2022-02.html
  https://zembihf.xyz/reports/2022-02/February_2022_Weekday_Reports.zip
  https://zembihf.xyz/reports/archive/2022-02-DD.html   (20 editions)
  (archive index updated with 20 links, 804 existing links preserved; scoped CloudFront invalidation)
  html/2022-02-DD.html                         20 archive pages with dated source ledgers
  json/2022-02-DD_Market_Intelligence.json     20 machine-readable copies
  pdf/                                         20 PDFs (gitignored; regenerate with tools/build_feb2022.py)
  retail/What_Retail_Is_Playing_2022-02.html   the month's retail collection (lead + 3 trades per day)
  collection/2022-02.html, methodology.txt     archive index page, sources and historical method
Totals: 204,109 words, 689 PDF pages; each edition 9,971–10,372 words, ≥239 distinct dated sources.
Note: the site serves its app shell for /Strategies/* paths (as for earlier months); the PDF and JSON
objects are verified at the S3 origin and are included in the month ZIP.

Historical boundary
Each edition uses only information before 00:00 UTC on its date: Google News RSS headlines
(news/previews 7 days, company results 14, macro releases 35), Yahoo Finance completed sessions
(crypto: prior UTC candle) and the US Treasury par curve. 16,818 own-cutoff query windows were
acquired (no failed or capped query; 265 transient attempts retried) from an ex-ante catalogue of
828 query contexts (companies listed after January 2022 removed). A release-clock screen of 223
scheduled releases, decisions, results and staged events — including the Russia–Ukraine sequence
(Duma appeal, claimed pull-back, recognition and troop order, Nord Stream 2 halt, sanctions tranches,
the 24 February invasion at ~03:00 UTC, $100 Brent, SWIFT measures), Super Bowl night and the Truth
Social launch — plus 32 reviewed guard dispositions and 145 editorial exclusions remove records that
report outcomes before they existed (day-granular index stamps), later-vintage pages and rolling pages.
Period identities are kept (Meta Platforms as FB, Block as SQ, Digital World Acquisition as DWAC).
Numeric spot-FX marks are excluded; DXY remains. Headlines are not article bodies.

Authoring and review
Nonretail sections: one writer per date. Retail ("What Retail Is Playing"): a dedicated chronological
writer chain in five date segments reading only strictly earlier retail notes as editorial memory, in
the vivid August 2026 voice. Every component received an independent AI review (not human) by an agent
other than its author (40 receipts in audit/independent_{nonretail,retail}_DATE.json binding feed, card,
exclusions and component hashes); 20 major, 111 moderate and 206 minor findings were recorded and
resolved. Six root corrections (audit receipts: root_deltas) removed day-stamped items whose publication
before the cutoff could not be established (Nvidia–Arm withdrawal scoop on 8 Feb; Fortune weekly wrap on
25 Feb; FT Russia/defence ETF flows on 24 Feb). Root exclusions were applied only to uncited records and
both receipts rebound (exclusion_rebinds). The retail-quality gate (tools/retail_quality_snapshot.py
--require-reviewed --decisions checks/retail_editorial_decisions.json) passes for all 20 dates with
0 hard failures and 0 unresolved flags (one DWAC concentration flag resolved as an evidence-bound
material update).
Cost note: nonretail reviews ran on a smaller model; writers and the retail chronology reviews ran on
the main model. Parallel writers briefly saw other dates' scratch files early on; every affected writer
re-derived its figures from its own card/feed and the independent reviews re-checked cross-date use.

Retail leads
02-01 GameStop · 02-02 Alphabet (split) · 02-03 Meta (FB) · 02-04 Meta (FB) record crash · 02-07 Snap
02-08 Bitcoin · 02-09 Peloton · 02-10 Disney · 02-11 TQQQ · 02-14 Bitcoin (Crypto Bowl)
02-15 Coinbase · 02-16 SOXL · 02-17 Shopify · 02-18 Palantir · 02-21 DWAC · 02-22 DWAC
02-23 Brent · 02-24 TQQQ (invasion risk, pre-cutoff) · 02-25 Aerospace & Defense ETF · 02-28 Berkshire

Rebuild
  python3 tools/verify.py                      # all 20 specs PASS
  python3 tools/retail_quality_snapshot.py . --decisions checks/retail_editorial_decisions.json --output checks/retail_quality.json --require-reviewed
  python3 tools/build_feb2022.py               # html/json/pdf, retail page, archive, ZIP
Publication: python3 tools/publish_feb2022.py [--go] (create-only S3 writes, index backup + conditional
merge, scoped CloudFront invalidation). No Lambda invocation, deployment, e-mail or Telegram message.
Large caches (cache/, work/) are not committed; query plan and request ledgers are kept gzipped in audit/.
