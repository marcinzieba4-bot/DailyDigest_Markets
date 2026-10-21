# China widening + growth-pulse rewrite of the archived briefings — June to October done (2026-06-25 … 2026-10-20)

Status: June live on S3 since 2026-10-20 (backups under `*/_pre_china_backup/`, CloudFront invalidated). The report Lambda
`daily-trends-digest` runs the new prompt and feeds from the same day (code-only update; layer `daily-digest-deps:3` unchanged).
July (31 reports) written by five parallel agents from `tools/BRIEF_CN.md`, live on S3 since 2026-10-20; June re-published
the same day with citation fixes (7-day news window). All 37 reports pass `tools/final_check.sh` (verify_cn, verify_report
and `check_cites.py`, which matches every "(Source, [Mon DD])" to a headline in that date's own feed). August (31 reports) done the same way and live on S3 since 2026-10-20 (all pass final_check.sh). September (30 reports) done the
same way and live since 2026-10-20 (Sep 28-30 rebuilt too: their wider block had been written on the broken feeds);
Aug 31 re-published with a corrected rate pill. October 1-19 done the same way (their long
China blocks, written on the broken feeds, rebuilt in the eight-part structure). October 20 is the first report generated
by the new Lambda prompt: its China block was already compliant; only its last Underowned Theme, cut off mid-sentence by
max_tokens, was removed (edits/2026-10-20.json).

Two changes, applied to the corrected archive in `corrections/2026-10-19/html/` (which already carries the US-yield fix
and the wide Poland block):

1. **Wide China block.** The thin 2-3 sentence China block is replaced by the structure the Lambda now asks for
   (Macro Stance · PMIs & Activity · Credit Impulse · Property · Fiscal, Policy & Trade · Markets & Flows · New / Most
   Important · Playbook | Divergence), 450-850 words, stance and rate pill kept from the original.
2. **Copper / gold de-emphasis.** Every use of copper, the Gold/Copper ratio or the Oil/Copper ratio as a gauge of China
   demand, global growth or risk appetite is replaced by growth-pulse evidence (PMIs, credit, housing) from the same
   date-bounded feed. Copper stays only as an asset (Materials, framed as an AI data-centre / grid-capex metal; KGHM in
   the Poland block). Gold stays where it is discussed as an asset; ratio reasoning on it is removed.

No wording indicates a correction. Nothing dated on or after a report's date is used.

**2026-06-24** (added 2026-10-21): the report of that day had no archive page (HTML publishing started 06-25). It
was rebuilt from its original JSON and given every layer — yields, wide Poland and China blocks, copper rules,
four-part sectors, Earnings Pattern — on feeds dated before 06-24; live with an index row. See
`corrections/2026-06-24/README.md`.

## Layout
- `feeds/<date>.json` — Google News headlines harvested with `after:/before:` bounds (`tools/fetch_feeds.py`). Google
  dates items by roughly US-Eastern date, so a Beijing release at 01:30 UTC carries the prior day and the private PMI for
  June (out 1 Jul, 01:45 UTC) is tagged "Jun 30". Only items dated **strictly before** the report date are kept. News
  topics use 7 days, monthly data (PMIs, credit, home prices, activity, exports) 35 days — the same windows as the Lambda.
- `old/<date>.html` — original China block; `new/<date>.html` — the wide block (passes `tools/verify_cn.py`).
- `edits/<date>.json` — exact `[old, new]` sentence replacements for the copper / gold passages.
- `orig/<date>.html` — the report as it was before this pass (`tools/apply_edits.py` always rebuilds from it).
- `tools/` — `fetch_feeds.py`, `digest.py` (reading aid), `extract_old.py`, `verify_cn.py`, `show_copper.py`,
  `apply_edits.py`, `verify_report.py` (no copper ratios, no copper-as-growth-gauge, new numbers / tags traceable to the
  eligible feed), `build_json.py` (rebuilds the JSON copy with the Lambda's parser), `upload.py` (date-scoped publish).

## Per date (stance kept from the original)
| Date | Stance | Main China story |
|---|---|---|
| 06-25 | Mixed | First fiscal-gap cutback since 2023; TSF beat on bonds while loans missed; LPR held 13th month |
| 06-26 | Mixed | PBOC plans an overnight reverse repo (survey 1.35%); Beijing land sales −66%, Evergrande unit deal collapse |
| 06-27 | Mixed | PBOC urges banks to lend as demand stays weak; May profit growth dips; Hang Seng worst week in a year |
| 06-28 | Mixed | Advisers call for a fix to the two-speed economy; profit growth slows for first time in six months |
| 06-29 | Bearish | Overnight reverse repo debuts at 1.25%, below the 1.35% expected; HK tech rebound on AI issuance |
| 06-30 | Mixed | June official PMI back to 50.3 (non-mfg 50.2), export-led; EU-China October deadline on the trade deficit |

## Publishing
`python3 -I corrections/china/tools/upload.py <dates>` is a dry run; add `--go` to back up the live objects to
`*/_pre_china_backup/` (a new prefix — the older `_pre_correction_backup` originals are never touched), write HTML, JSON and a
regenerated PDF under the original keys and invalidate only those archive paths. `reports/latest.html` is not touched.
Do **not** use `corrections/2026-10-19/upload.py` for this: it re-uploads all 117 dates, overwrites
`_pre_correction_backup/` and repoints `latest.html` to 2026-10-19.

## Next months
Repeat per month: `fetch_feeds.py <dates>` → `extract_old.py` → write `new/` blocks and `edits/` (brief: `tools/BRIEF_CN.md`)
→ `apply_edits.py` → `final_check.sh <dates>` → `build_json.py` → `upload.py <dates> --go`. From 2026-09-28 the China block is already
wide (but was starved by the broken China feeds), so later months mainly need the copper / gold pass and a PMI /
credit / property refresh of the China block.

## Future reports (live Lambda)
Since 2026-10-21 the report also has an **🧮 Earnings Pattern — What the Market Pays For** section after the Sector Deep
Dive: Rewarded / Punished / Pattern / Attention into EPS / Playbook, read from two weeks of results and share reactions
(this-week and previous-week earnings queries) and applied to the stocks getting attention into their reports.
The rules used here are built into `lambda_function.py` (deployed): wide eight-part China block (450-800 words) on
short-query China feeds, the growth-pulse rule (PMIs, credit impulse, housing; copper only as an AI / grid asset, no
copper ratios — the snapshot no longer computes them), rate pills that state a direction, and no release-calendar claims
without a headline. Each run logs `Report-scope check:` warnings in CloudWatch (`compliance_issues()`) if a report slips:
copper ratio used, China label missing, China block under 400 words, meta rate pill, or a missing section. Since
2026-10-21 the four Claude calls run in parallel (part 1 split into Geo and Sectors + Underowned) with 512 MB memory,
after the wider blocks made the 2026-10-20 run hit max_tokens and the Lambda timeout.

## Earnings-first Sector Deep Dive (live from 2026-10-21; archive: 06-24 to September)
Each of the 13 sector blocks has four short parts (about 100-160 words): **Narrative** (consensus, direction, the driver
that matters), **Reported** (who reported in the last 7 days — beat / miss, guidance, reaction, why), **EPS Upside Watch**
(who is set up for an EPS surprise and the mechanism) and **⚡ Breaking Convention** (the signal against the standard
narrative). No Polish companies or Warsaw market in this section — the live sector call gets a feed without the Polish
feeds plus three earnings feeds. Archive: `tools/fetch_earnings.py` → `feeds_earn/<date>.json`; blocks in
`sectors/<date>.html` (brief: `tools/BRIEF_SECTORS.md`; `tools/old_sectors.py` shows the original Narrative / Breaking
Convention with the copper fixes applied), spliced by `apply_edits.py`, checked by `tools/verify_sectors.py`
(part of `final_check.sh`).
Status: June and July (2026-06-25 … 07-31) rewritten in the four-part format and live since 2026-10-21. August
(08-01 … 08-31) rewritten the same way by eight parallel agents on its own earnings feeds (31 dates, no failed queries);
all 31 pass `final_check.sh`; live since 2026-10-21. September (09-01 … 09-30) done the same way (30 earnings feeds, no
failed queries; all 30 pass `final_check.sh`), live since 2026-10-21. October onwards not yet. `check_cites.py --content` additionally flags citations whose
claim shares few words with the cited headline (a review aid — most flags are paraphrases or day-to-day harvest
differences, not wrong sources).
**August lesson:** `check_cites.py` matches source + date only, so a citation can pass against a *different* headline from
the same outlet on the same day (each date's harvest differs, so a carried-forward citation often loses its headline).
Check every carried-forward citation's headline text in the new date's own feed; for the China blocks this found wrong
sources from the earlier pass (e.g. 08-02 BMW "China slump" is RTE.ie, not Investing.com), fixed in `new/`.
**September lessons:** the same review fixed 09-03 / 11 / 12 / 15 China blocks, and the July-CPI claim carried in the China
blocks of 08-25 … 09-08 ("CPI slowed to 0.5%") now cites the BigGo [Aug 9] headline that says so. A stricter triage
(do the claim's proper nouns appear in any headline of the cited outlet that day?) is a useful extra pass — headlines
often name a company by ticker only (OLLI, NEE, CRDO, IBKR), so a flag needs a look, not a fix. Writers also dropped
re-dated stale results (Q2 recaps dated mid-September, TSMC "raises guidance"), conflicting share reactions (both "rose"
and "fell" headlines → no reaction), and a Reuters PetroChina story that Reuters withdrew (08-31 now cites OilPrice.com).

## Earnings Pattern in the archive (06-24 to September done)
`pattern/<date>.html` holds the section (brief: `tools/BRIEF_PATTERN.md`), built from two weeks of earnings headlines:
the date's own earnings feed plus the previous week (`feeds_earn_prev/<date>.json` for 06-25 … 07-01, harvested by
`tools/fetch_earn_prev.py`; otherwise the earnings feed of D-7). `apply_edits.py` inserts it after the Sector Deep Dive;
`tools/verify_pattern.py` (part of `final_check.sh`) checks heading, five labels, length, the 14-day window and numbers.
2026-06-25 … 07-31 live since 2026-10-21. August 01 … 31 written and verified (the previous week comes from
`feeds_earn/<D-7>`, so no `feeds_earn_prev` was needed); live since 2026-10-21 (CloudFront invalidated). In the cloud
session the default `AWS_ACCESS_KEY_ID` is invalid — publish with `AWS_ACCESS_KEY_ID=$AWS_Key
AWS_SECRET_ACCESS_KEY=$AWS_Pass python3 -I tools/upload.py <dates> --go` (needs `boto3` and `matplotlib` for the PDF).
September 01 … 30 written and verified the same way, live since 2026-10-21. October onwards not yet.
