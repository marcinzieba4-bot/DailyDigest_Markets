# Earnings-first Sector Deep Dive — editing brief (per report date D)

Reader: a professional investor who wants the sector section short, global and about EARNINGS: who reported and how it
went (and why), and who is set up for a surprising EPS boost. Rewrite the 13 sector blocks of the archived report so
they look as if written on D in the new format. Nothing else in the report changes.

All paths are relative to `/home/user/DailyDigest_Markets/corrections/china`. Run tools with `python3 -I tools/<tool>.py`.

## Inputs
- Current sector section: in `../2026-10-19/html/<D>.html`, from `<h2 …>📊 Sector Deep Dive</h2>` to the `<hr>` before
  "🔍 Underowned Themes". Keep each block's `<div>` opener and its `<h3>` line EXACTLY (emoji, sector name, stance word
  and colour) — the 13 headings must stay identical and in the same order.
- Earnings headlines for D: `python3 -I tools/digest.py --earn <D>` (buckets earn_reported, earn_outlook, earn_sector).
- Growth / China headlines for D: `python3 -I tools/digest.py <D>` (PMIs, credit, housing — for the Take line).
- The report itself for that day's quant figures (oil, yields, copper, gold, indices) — reuse them verbatim.

## Format — write `sectors/<D>.html`
Exactly 13 blocks, nothing else (no `<h2>`; the tool splices them under the existing heading):
```
<div style="margin-bottom:18px;padding:14px;background:#f9fff9;border-left:4px solid #34a853;border-radius:4px">
  <h3 …copied from the original…</h3>
  <p><strong>Narrative:</strong> …</p>
  <p><strong>Reported:</strong> …</p>
  <p><strong>EPS Upside Watch:</strong> …</p>
  <p>⚡ <strong>Breaking Convention:</strong> …</p>
</div>
```
About 100–160 words per block (the verifier warns above 185). Simple, quick, factual:
- **Narrative:** 1–2 sentences — the consensus, the direction (consistent with the heading's stance) and the single
  driver that matters now (rates, PMIs / new orders, credit, housing, AI capex, oil). Condense it from the original
  Narrative (`python3 -I tools/old_sectors.py <D>` prints it with the copper fixes applied) and the day's figures.
- **Reported:** 1–3 companies in that sector that reported in the 7 days before D — beat / miss, EPS or revenue vs
  estimates if the headline gives it, guidance raised / cut, share reaction, and the WHY in a few words. Tag each with
  source and date like the rest of the report: "Micron beat on record HBM revenue and guided higher, shares +15%
  (Forbes, [Jun 24])". If nobody relevant reported: "No major reports this week."
- **EPS Upside Watch:** 1–2 companies set up for a surprising EPS boost — guidance raised, estimates / targets lifted,
  pricing, volume or margin tailwinds, a preview pointing to a beat — with the mechanism, from the feed. If none: "None flagged."
- **⚡ Breaking Convention:** 1–3 sentences on the signal that goes against the sector's standard narrative and why it
  matters. Condense the original Breaking Convention (old_sectors.py) — keep its point if it still stands; if the
  original said none, or its point no longer fits the rest of the block, use a feed-backed one or "None today."
Facts taken from the original paragraphs come from that day's report and may stay untagged; anything new needs a
feed headline. Never carry over a Polish reference, a copper ratio or copper-as-China-gauge reasoning.

Sector mapping: XLK tech/software/hardware · XLC media/telecom/internet platforms · XLF banks/brokers/insurers/payments ·
XLE oil & gas, refiners, oil services · XLI industrials, transport, airlines, aerospace & defence · XLY retail,
restaurants, autos (US), travel, apparel · XLP food, beverage, household, tobacco, grocery · XLV pharma/biotech/medtech ·
XLB chemicals, miners, materials, packaging · XLRE REITs, homebuilders may go in XLRE or XLY (pick one) · XLU utilities,
power · European Auto (SXAP) European carmakers and suppliers · Semis (SOXX/ASML/TSMC) chipmakers and equipment.
A company appears in at most one sector.

## Hard rules
1. Only headlines dated strictly BEFORE D and at most 7 days old (D-7 … D-1) for results and news; nothing from D or
   later; no knowledge of 2026 from outside the feeds. Earnings dates you "know" from memory do not count — an upcoming
   report may be named only if a headline dated before D announces it.
2. Every number must appear verbatim in an eligible headline or in that day's original report. No arithmetic.
3. GLOBAL ONLY: no Polish companies, no Warsaw market (GPW / WIG), no Poland in this section (Poland has its own block).
4. Copper only as an asset framed as an AI data-centre / grid / electrification metal; no Gold/Copper or Oil/Copper ratios.
5. Company accuracy: describe what the company actually does / reported per the headline; if a headline is ambiguous,
   leave it out. A headline giving no numbers → describe the direction only ("beat", "raised guidance").
6. Never mention that anything was rewritten or produced later.

## Procedure per date
1. Read the current 13 blocks (keep their h3 lines), the earnings digest and the growth digest for D.
2. Write `sectors/<D>.html`.
3. `python3 -I tools/apply_edits.py <D>` (rebuilds the report from orig/ + China block + copper edits + your sectors).
4. `python3 -I tools/verify_sectors.py <D>` → PASS, no WARN. Then `tools/final_check.sh <D>` must show
   cn=PASS(0 warn) report=PASS(0 warn) cites_unmatched=0 sectors=PASS(0 warn).
   (verify_report's character diff can split a correct number — reword so the number stays whole.)
5. `check_cites.py` matches source + date only, so confirm each citation's headline TEXT is in D's own feed — a block
   carried over from D-1 often keeps a citation whose headline is missing from D's harvest (August lesson).
Do NOT edit new/, edits/, orig/, feeds*, or any tool; do NOT run build_json.py, upload.py, git or AWS.
Report back per date: the 2–3 most notable earnings stories, number of sectors with "No major reports", and anything
you were unsure about.
