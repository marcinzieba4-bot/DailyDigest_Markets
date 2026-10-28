# October 1-20 — sectors + Earnings Pattern (per report date D)

For each of your dates, in date order, do BOTH passes on the archived report `../2026-10-19/html/<D>.html`:

1. **Sector Deep Dive** → `sectors/<D>.html`, following `tools/BRIEF_SECTORS.md` exactly (13 blocks, original `<h3>`
   lines, Narrative / Reported / EPS Upside Watch / ⚡ Breaking Convention, ~100-160 words each, no Poland).
2. **Earnings Pattern** → `pattern/<D>.html`, following `tools/BRIEF_PATTERN.md` exactly (Rewarded / Punished / Pattern /
   Attention into EPS / Playbook, ~250-350 words, consistent with that day's new sector blocks).

Then `python3 -I tools/apply_edits.py <D>` and `tools/final_check.sh <D>` (run it with a long timeout — it can take a
few minutes when other agents run it too). The date is done when it shows
`cn=PASS(0 warn) report=PASS(0 warn) … cites_unmatched=0 | sectors=PASS(0 warn) | pattern=PASS(0 warn)`
(for 2026-10-20 the China block is the live one: `cn=live` is expected there).

Worked examples (September, already published): `sectors/2026-09-30.html`, `pattern/2026-09-30.html`. Read them first
and match their voice, length and citation style. Consecutive dates share most of the window: reuse your previous date's
files, then drop what aged out and re-check every citation against the new date's own feeds.

## October specifics
- Early October is pre-season (previews, estimate revisions, pre-announcements, a few off-cycle reporters); Q3 season
  opens with the big US banks around mid-month, so later dates should have many real results. Only results whose
  headline is dated D-7 … D-1 go in **Reported**; the Pattern may use D-14 … D-1.
- Lessons from August / September: confirm each citation's headline TEXT is in D's own feed (`check_cites.py` matches
  source + date only; `python3 -I tools/check_cites.py --content <D>` lists weak matches to review). Drop re-dated stale
  results (a Q2 recap or an old guidance raise dated in October). If headlines give conflicting share reactions, give no
  reaction. Ticker-only headlines (e.g. "OLLI") are fine if the company is unambiguous.
- Do NOT edit new/, edits/, orig/, feeds*, or any tool; do NOT run build_json.py, upload.py, git or AWS.

Report back, one line per date: the 2-3 most notable earnings stories, the Pattern rule in a few words, the number of
sectors with "No major reports", the final_check line, and anything you were unsure about.
