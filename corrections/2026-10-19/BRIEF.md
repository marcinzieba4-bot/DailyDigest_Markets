# Retrospective correction of archived Market Intelligence Briefings — editing brief

You are correcting archived daily market reports (HTML). Each report was generated on its `report_date` by a pipeline
that had TWO systematic bugs in its US-Treasury data:

1. **"2Y" was never the 2-year note.** The pipeline fell back to the Yahoo ticker ^IRX, the *13-week T-bill*, and labelled it
   "US 2Y Yield". Every "2Y at 3.xx%" figure, every "10Y-2Y spread +NNNbps" figure (typically +70 to +130 bps) and every
   narrative built on them ("2Y barely moved", "front end anchored", "curve steepest in years", "+106bps normal curve",
   "best NIM environment in years", "bear-steepening blow-out") is wrong. The real 2Y was ~0.4-0.7 pp higher, and the real
   10Y-2Y spread was roughly a third to a half of the quoted number (about +20 to +50 bps: positive, but still FLAT by
   historical standards — the long-run average is about +90 to +100 bps).
2. **Yield changes were expressed in percent of the yield** ("10Y at 4.74% (↑5.8% vs 4W)") instead of basis points.
   A move from 4.49% to 4.74% is +25 bps, not "+5.8%". Phrases such as "yields surged 5.8%", "10Y ↑5.0%" must become bps.

The 10Y level itself (e.g. "10Y at 4.74%") was read live from ^TNX on the report day and is CORRECT — keep it.

## Ground truth — the only numbers you may introduce
For each report there is a card: `/tmp/claude-0/-home-user/01233cf7-f758-5bad-b280-d38226412ca9/scratchpad/work/cards/<date>.json`.
All values in it were available on `report_date` (official Treasury closes up to the prior business day, plus the live 10Y
reading the report already contained). **Use nothing else.** No knowledge of what happened after `report_date` may enter
the text — no later yield levels, no later Fed decisions, no hindsight of any kind.

Card fields:
- `live_10y_reading_in_report` — the 10Y figure the report already quotes (keep it). `live_10y_change_vs_4w_bps` — its change
  vs 4 weeks earlier in bps (replaces the "↑x.x% vs 4W" figure).
- `prior_official_close_date` and `prior_close` — official Treasury closes on the last business day BEFORE the report date:
  `2y`, `10y`, `3m_bill`, `5y`, `30y`, and `spread_10y_2y_bps` (= 10y − 2y at that close). This is the only consistent curve
  snapshot; use it for the spread. Also `spread_10y_3m_bps`, `spread_30y_10y_bps` if the text discusses those.
- `four_weeks_before_prior_close` and `change_vs_4w_at_prior_close` — 2Y / 10Y / spread changes in bps over the prior 4 weeks,
  with `curve_move` already classified (bear steepening / bull flattening / little changed ...).
- `curve_shape_label` — the correct qualitative description of the spread.
- `wrong_2y_values_in_report_actually_13w_tbill` — the bogus 2Y figures to hunt down in this file.
- `flagged_sentences` — every sentence mentioning yields/curve keywords, to help you find what to inspect. Not all need editing.

## Editing rules
R1. Edit ONLY sentences about US Treasury yields, the US yield curve / 2s10s / front end / long end, or NIM/bank or duration
    arguments that explicitly rest on the wrong spread or the wrong 2Y. Leave everything else in the report untouched
    (other assets, foreign yields quoted from headlines, equities, crypto, headings, styling, HTML tags, entities like &mdash;).
R2. Keep the author's voice, tense and density. Make the smallest change that makes the sentence true. Do not add new
    analysis, new instruments, new facts, or new events. Do not lengthen sections.
R3. Percent-of-yield changes → bps. "(↑5.8% vs 4W)" after the 10Y → "(+25 bps vs 4W)" using `live_10y_change_vs_4w_bps`
    (format: "+25 bps" / "−10 bps" / "unchanged"; sign always shown except for 0). In prose: "yields surged 5.8%" → "yields
    rose 25 bps". Never leave a yield move in %.
R4. Bogus 2Y → real 2Y at the prior close, labelled once per sentence as prior close, e.g.
    "the 2Y at 4.28% (prior close, +14 bps vs 4W)". Its 4W change comes from `change_vs_4w_at_prior_close.2y_bps`.
R5. Spread → `prior_close.spread_10y_2y_bps` and describe it with `curve_shape_label`; direction over 4 weeks from
    `change_vs_4w_at_prior_close` (e.g. "+47 bps at the prior close, 12 bps steeper than four weeks ago"). Replace
    "normal curve", "healthy +100bps", "steepest in years", "blown out" etc. with the honest version: positive but still
    flat / modestly steeper / flatter. If the spread barely changed (|Δ| < 5 bps), say so.
R6. Re-derive the narrative honestly from the card. Typical fixes:
    - "the 2Y barely moved (↑0.4%)" → if `2y_bps` is +14, the 2Y rose 14 bps; the "front end anchored" claim is false, rewrite.
    - "bear steepening" is only right if `curve_move` says so; otherwise use the card's label (bear flattening, bull steepening…).
    - "best NIM environment in years / curve at +107bps" → the spread is ~+40 bps: still thin for NIMs; tone the claim down.
    - "term premium blow-out as long end runs away from the anchored front end" → check 10Y vs 2Y bps; both often rose together.
    - Checklist/rule items like "[10Y-2Y spread +107bps positive ✓]" → "[10Y-2Y spread +40 bps positive ✓]" — keep the tick
      only if the condition still holds with the true number; if the condition fails, change ✓ to ✗ and adjust the
      conclusion wording minimally (e.g. "ROTATION, NOT RECESSION" stays only if the rule's AND-conditions still hold).
    - The 10Y-3M spread (`spread_10y_3m_bps`) may be mentioned only if the original sentence was really about bills.
R7. Do NOT mention that anything was corrected, revised, mislabelled, or that a T-bill was involved. The result must read as if
    the report had been written correctly on its date. No notes, no banners, no footnotes.
R8. Numbers: every number you introduce must be in the card (bps values may be rounded by ±1). Do not compute new ratios.
    Yields with 2 decimals and %, spreads/changes as integers with "bps".
R9. Preserve HTML exactly apart from the text you change: same tags, same attributes, same entities. Edit text inside
    existing <p>/<li>/<h3> nodes only. UTF-8 characters (↑ ↓ — ✓) are fine to keep or use.

## Procedure (per report)
1. Read the card, then read the whole HTML file `/tmp/claude-0/-home-user/01233cf7-f758-5bad-b280-d38226412ca9/scratchpad/work/edited/<date>.html`.
2. Apply the edits with the Edit tool (exact old_string/new_string).
3. Run `python3 -I /tmp/claude-0/-home-user/01233cf7-f758-5bad-b280-d38226412ca9/scratchpad/work/verify.py <date>` and fix every FAIL.
   Review every WARN: a "numbers not in original or card" warning must be resolved unless the number is a legitimate rounding
   of a card value — explain any you keep in your final report.
4. Keep a short per-report note of what you changed (2-4 lines) for your final summary.

Do not touch files outside `edited/`. Do not touch reports not assigned to you.
