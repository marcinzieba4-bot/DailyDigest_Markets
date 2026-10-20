# Retrospective China widening + growth-pulse rewrite — editing brief (per report date)

Reader: a professional macro investor. Each archived daily report must look as if it had been written on its date with
the new report scope: (1) a WIDE China block built on PMIs, credit impulse and property data, and (2) no use of copper,
the Gold/Copper ratio or the Oil/Copper ratio as a gauge of China demand, global growth or risk appetite. Copper is now an
AI data-centre / power-grid / electrification metal; read growth from PMIs (level vs 50, new orders), credit (China TSF /
new loans / M1-M2, US & euro-area bank lending, credit spreads) and real estate (home prices, sales, starts, investment,
mortgage rates, developer stress).

All paths are relative to `/home/user/DailyDigest_Markets/corrections/china`. Run tools with `python3 -I tools/<tool>.py`.
Worked examples (June and July, already published): `new/2026-06-2*.html`, `new/2026-06-30.html`, `edits/2026-06-*.json`.
Read ONE new block and ONE edits file before starting; match their voice, density and format.

## Inputs per date D
- `old/<D>.html` — the original thin China block (keep its `<div>` opener and `<h3>` line exactly: stance word, colour and
  rate pill; change them only if the feed clearly justifies it).
- `feeds/<D>.json` — the ONLY news source for D. Read it with `python3 -I tools/digest.py <D> [more dates]` (filtered,
  de-duplicated, sorted by date; each line `MM-DD | title - source`).
- The report itself: `../2026-10-19/html/<D>.html` (read-only for you; it supplies the day's quant figures and context —
  DXY / WTI / 10Y / VIX / gold / USD-PLN figures quoted there may be reused verbatim).

## HARD RULES
R1. Nothing from D or later. Use only digest lines dated **strictly before D**. News topics (PBOC operations, LPR, yuan,
    policy / Politburo / State Council, trade actions, tariffs, markets, developers) only from the **7 days before D**
    (dates D-7 … D-1). Monthly data releases (PMIs, CPI/PPI, credit/TSF/loans, retail sales, output, FAI, industrial
    profits, GDP, home prices, property investment, exports, ISM, flash PMIs, housing starts / sales, Case-Shiller) may
    be up to **35 days** old — call them "the June print", "May's data", never "this week" if older than 7 days.
    Do not use your own knowledge of 2026 at all. If it is not in the feed, it has not happened. A headline that
    announces a future event (e.g. "Politburo to meet next week") may be named as scheduled; never state its outcome.
    Google dates items by US-Eastern date: a Beijing release at 01:30 UTC shows up dated the PRIOR day — that is
    expected; the cut-off rule above already handles it.
R2. Numbers: every figure you add must appear verbatim in an eligible headline (or already in that day's report). No
    arithmetic, no remembered figures. If a headline says "rose" without a number, write "rose".
R3. Attribution in the report's style: "(Reuters, [Jul 14])", "per Caixin [Jul 15]". Use the headline's own source name.
    The `[Mon DD]` tag must be the headline's date in the digest.
R4. Conflicting headlines (e.g. "credit beat" vs "loans missed"): reconcile them explicitly (headline TSF vs bank loans).
R5. Voice: dense, analytical, professional; no bullet lists, no emojis beyond those in labels; English. Never mention that
    anything was rewritten, corrected, expanded or produced later.

## Part A — the China block → write `new/<D>.html`
Exactly one `<div ...>` (opener copied from old), one `<h3>` (copied from old), then these EIGHT `<p>` parts in order, each
label in `<strong>`: `Macro Stance:` · `PMIs &amp; Activity:` · `Credit Impulse:` · `Property:` ·
`Fiscal, Policy &amp; Trade:` · `Markets &amp; Flows:` · `New / Most Important:` ·
`Playbook ✓:` … `&nbsp;|&nbsp;` `<strong>⚠️ Divergence:</strong>` … (one paragraph).
Allowed tags: div, h3, span, p, strong, em, br. 450–850 prose words (verifier counts alphabetic words; hard cap 900).
Macro Stance = PBOC (LPR/RRR/liquidity ops/overnight repo), yuan fixing vs dollar, CPI/PPI. Divergence must explain the
transmission to global assets (AUD, EM, European exporters, iron ore / oil) through PMIs, credit and property — never
through copper. If a topic has nothing in the feed, one honest sentence. The old block may mention facts from the same
report (NYT piece, CITIC call, dollar vs won…) — you may keep those exact references.
Consecutive dates share monthly data: reuse and update the previous day's block (add new items, drop news items that
fell out of the 7-day window, re-tag), but make "New / Most Important" genuinely about that day's newest development.
Check: `python3 -I tools/verify_cn.py <D>` → must PASS with **no WARN**.

## Part B — copper / gold passages → write `edits/<D>.json`
List them with `python3 -I tools/show_copper.py <D>` (skips the China and Poland blocks). `edits/<D>.json` is a JSON list
of `[old, new]` pairs; each `old` must be an exact substring of the report occurring exactly once (copy it from the
show_copper output, including HTML entities like `&nbsp;` and tags). Rules:
- Remove every Gold/Copper and Oil/Copper ratio reference (text, model conditions, "FEAR-elevated" ratio talk).
- Where copper (or a ratio) was evidence of China demand / global growth / risk appetite / terms of trade, replace it with
  growth-pulse evidence from the eligible feed (PMIs, credit, housing, China property / retail / credit) — or simply drop
  the clause if nothing fits. Keep the sentence's role and the paragraph's conclusion unless the new evidence contradicts it.
- Capital Flows models built on copper or a ratio: swap those conditions for PMI / credit / housing conditions with real
  feed figures, keep the model's format (✓/✗, → verdict — trade). Trades on copper miners may stay, re-justified as an AI /
  grid-capex play.
- Materials (XLB) and miners: copper may stay as an asset, framed as an AI data-centre / grid-capex metal.
- Gold stays where it is discussed as an asset (price, central-bank buying, real rates); strip only ratio reasoning.
  Gold/BTC is a crypto metric — leave it.
- Do NOT touch the China block (Part A replaces it) or the Poland block (KGHM / copper there is legitimate), and do not
  change anything unrelated to copper / ratios (yields, Poland, stocks…).
- Fix factual slips you meet in the edited sentence (e.g. "copper collapsing faster than gold" when gold fell more), and
  never claim "the ratio is rising/falling" — the old snapshot never gave a direction.
Then: `python3 -I tools/apply_edits.py <D>` (rebuilds the report from `orig/` + your block + your edits; safe to rerun)
and `python3 -I tools/verify_report.py <D>` → must PASS with **no WARN**. Remaining copper mentions should be only XLB /
miner / AI-grid framings and the Poland block. Typical: 5–12 edits per report.

## Lessons from July (read before starting)
- **Each date has its own feed.** Google returns a different set per harvest, so a headline in D's digest may be missing
  from D+1's feed. When you reuse the previous day's block, re-check every citation: run
  `python3 -I tools/check_cites.py <D>` — it matches each "(Source, [Mon DD])" to a headline with that source and date in
  D's own feed and must report **0 unmatched**. Untagged references are allowed only for facts already in that day's
  original report.
- **News items age out.** Carrying a block forward easily keeps a PBOC / policy / market item past D-7. Only monthly data
  may be older than 7 days.
- **Stance word** must be exactly Bullish, Mixed or Bearish (verify_cn). If the original had a qualifier ("Bullish Lean",
  "Bullish (contrarian)"), use the nearest single word, keep its colour, and keep the qualifier's argument in the text.
- **verify_report false WARNs**: its character diff can split a correct number ("15.4%" → "5.4"); reword the sentence so
  the number stays whole rather than leaving a WARN.
- **show_copper** now prints every block segment (p / div / li / headings / `<br>` lines) — each is an exact substring.
- Fix factual slips in edited sentences (e.g. "gold outperforming copper" when the snapshot shows the opposite).
- **No release-calendar knowledge (August lesson).** "Industrial profits are due this week", "the PMIs follow at
  month-end", "ahead of the flash PMIs" are facts about the future and need a headline dated before D that announces
  them (or the same wording in that day's original report). Without one, drop the clause or say "the next print".
- Final gate for each date: `tools/final_check.sh <D>` → `cn=PASS(0 warn) report=PASS(0 warn) … cites_unmatched=0`.

## Done per date
`tools/final_check.sh <D>` shows cn=PASS(0 warn), report=PASS(0 warn), cites_unmatched=0. Do NOT run build_json.py,
upload.py, git, or anything touching AWS. Report back per date: stance, the main China story (one line), number of edits,
copper mentions before → after, and anything you were unsure about.
