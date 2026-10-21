# Earnings Pattern section — editing brief (per report date D)

The live report now has a section after the Sector Deep Dive: **🧮 Earnings Pattern — What the Market Pays For**. It
reads, from two weeks of earnings results and share reactions, which result profiles the market rewarded and which it
punished, states the rule, and applies it to the stocks getting attention into their upcoming reports. Add this
section to the archived report for D, as if written on D. Nothing else in the report changes.

All paths are relative to `/home/user/DailyDigest_Markets/corrections/china`. Run tools with `python3 -I tools/<tool>.py`.

## Inputs
- Two weeks of earnings headlines: `python3 -I tools/digest.py --earn2 <D>` (D's own 7-day earnings feed plus the
  previous week). Results / reactions: earn_reported; previews, estimate and target changes, calendars, implied moves:
  earn_outlook; by sector: earn_sector.
- That day's report `../2026-10-19/html/<D>.html` — especially its Sector Deep Dive (Reported / EPS Upside Watch),
  which is already verified for D: reuse those results and their citations, and keep the section consistent with it.

## Format — write `pattern/<D>.html` (exactly this shape)
```
<h2 style="color:#1a1a2e;border-bottom:2px solid #00897b;padding-bottom:6px">🧮 Earnings Pattern — What the Market Pays For</h2>
<div style="margin-bottom:18px;padding:14px;background:#f0faf8;border-left:4px solid #00897b;border-radius:4px">
  <p><strong>Rewarded:</strong> …</p>
  <p><strong>Punished:</strong> …</p>
  <p><strong>Pattern:</strong> …</p>
  <p><strong>Attention into EPS:</strong> …</p>
  <p><strong>Playbook:</strong> …</p>
</div>
```
About 250–350 words in total. Simple, quick, concrete:
- **Rewarded:** the result profile the market paid for in the last two weeks (e.g. beat + raised guidance, an AI
  revenue line, pricing power), with 2–4 examples and the share move from the headline, each tagged "(Source, [Mon DD])".
- **Punished:** the profile it sold even on a beat (higher capex / costs, China or tariff exposure, volume weakness,
  weak guidance), 2–4 examples with the share move.
- **Pattern:** the rule in 1–2 sentences — what matters more than the EPS beat itself right now. If the two weeks show
  no clear rule, say what is mixed and why.
- **Attention into EPS:** 3–5 stocks getting attention ahead of their report — previews, estimate / target changes,
  implied moves, "what to expect" pieces dated in the 7 days before D. Name an upcoming report only if a headline
  dated before D announces it. For each: what is priced in, which side of the pattern it falls on, the reaction the
  pattern implies.
- **Playbook:** 1–2 concrete ideas from the pattern (own into the print / fade the beat / pair), with the risk.
If fewer than about 5 results were reported in the two weeks (quiet season), write that in Rewarded / Punished /
Pattern in one line each and put the weight on Attention into EPS and Playbook.

## Hard rules
1. Only headlines dated strictly BEFORE D; results and reactions at most 14 days old (D-14 … D-1); previews and
   estimate changes at most 7 days old. Nothing from D or later, no knowledge of 2026 from outside the feeds, no
   earnings dates "known" from memory.
2. Every number must appear verbatim in an eligible headline or in that day's report. No arithmetic.
3. A reaction ("rose 15%", "fell despite the beat") must come from a headline — never infer it.
4. Global only: no Polish companies or Warsaw market. Copper only as an AI data-centre / grid metal; no copper ratios.
5. Never mention that anything was added or produced later.

## Procedure per date
1. Read the earnings digest (--earn2) and the day's Sector Deep Dive. Consecutive dates share most of the window:
   reuse the previous day's section, drop items older than 14 days (results) / 7 days (previews), add new ones and
   re-check every citation against D's own feeds (`check_cites.py --content <D>` lists weak matches to review).
2. Write `pattern/<D>.html`; run `python3 -I tools/apply_edits.py <D>`.
3. `python3 -I tools/verify_pattern.py <D>` → PASS, no WARN; then `tools/final_check.sh <D>` must show
   cn=PASS(0 warn) report=PASS(0 warn) cites_unmatched=0 sectors=PASS(0 warn) pattern=PASS(0 warn).
Do NOT edit new/, edits/, sectors/, orig/, feeds*, or any tool; do NOT run build_json.py, upload.py, git or AWS.
Report back per date in one line: the Pattern rule, and anything you were unsure about.
