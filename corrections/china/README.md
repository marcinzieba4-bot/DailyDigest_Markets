# China widening + growth-pulse rewrite of the archived briefings — June done (2026-06-25 … 2026-06-30)

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
Repeat per month: `fetch_feeds.py <dates>` → `extract_old.py` → write `new/` blocks and `edits/` → `apply_edits.py`,
`verify_cn.py`, `verify_report.py` → `build_json.py` → `upload.py --go`. From 2026-09-28 the China block is already
wide (but was starved by the broken China feeds), so later months mainly need the copper / gold pass and a PMI /
credit / property refresh of the China block.
