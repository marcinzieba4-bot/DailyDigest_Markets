# Widening the Poland section of archived Market Intelligence Briefings — editing brief

Each archived daily report has a thin "🇵🇱 Poland" block (2-3 sentences). The reader is a Poland-focused professional
investor and wants a WIDE Poland section, written as if it had been produced on the report's date, from Polish and
English sources available on that date. You rewrite that block only.

Paths (replace <date> with the report date, e.g. 2026-08-01):
- Old block (HTML):            /tmp/claude-0/-home-user/01233cf7-f758-5bad-b280-d38226412ca9/scratchpad/work/pl/old/<date>.html
- News feed for that date:     /tmp/claude-0/-home-user/01233cf7-f758-5bad-b280-d38226412ca9/scratchpad/work/pl/feeds/<date>.json
- Market card (prior closes):  /tmp/claude-0/-home-user/01233cf7-f758-5bad-b280-d38226412ca9/scratchpad/work/pl/cards/<date>.json
- Write the new block to:      /tmp/claude-0/-home-user/01233cf7-f758-5bad-b280-d38226412ca9/scratchpad/work/pl/new/<date>.html
- Verify:                      python3 -I /tmp/claude-0/-home-user/01233cf7-f758-5bad-b280-d38226412ca9/scratchpad/work/pl/verify_pl.py <date>

## The feed
`feeds/<date>.json` holds Google News headlines (Polish and English) published in the 7 days up to the report's
publication time (17:00 UTC on the report date), grouped by topic: nbp (NBP / RPP rates), cpi (inflation), data (GUS
GDP / retail / industry / wages), gpw (Warsaw stock exchange), pln (zloty), bonds (POLGBs), fiscal (budget / debt /
finance ministry), policy (government / Sejm / taxes / EU funds), corp (large listed companies), energy, housing,
geo (Ukraine / security), banks, plus finer buckets (data_gdp, data_retail, data_industry, data_wages, fiscal_deficit, fiscal_debt, fiscal_mf, banks_credit, wibor, chf, corp_orlen … corp_lpp, energy_prices, energy_nuclear) and English-language en_econ / en_mkt / en_stocks / en_geo / en_zloty / en_bonds / en_wig. Some buckets may be empty on a given date. Each item has a UTC
timestamp `t`, a `src` and a `title`. Titles are mostly Polish — translate the substance into English.
Items from the same day as the report were published before the report, so they count as known. Timestamps carry the date only (times are nominal), so a [Mon DD] tag is the publication date of the headline.
If a headline reports a decision or release without its date ("RPP nie ruszyła stóp"), write it undated ("at its last decision") rather than guessing a date. When an aggregator headline conflicts with a GUS / NBP / agency figure, use the official figure.

## The card
`cards/<date>.json` gives prior-session closes and 1-week / 4-week percent changes for USD/PLN, EUR/PLN, the EPOL ETF
(MSCI Poland in USD) and the big Warsaw names (PKO, Pekao, Orlen, KGHM, PGE, Allegro, Dino, CD Projekt, LPP). These
are the ONLY market figures you may quote for Poland apart from numbers that appear inside a headline.

## Hard rules
R1. ABSOLUTE: nothing from after the report date. Use only the feed, the card and the old block. Do not use your own
    knowledge of 2026 events at all — if it is not in the feed, it did not happen yet as far as this report knows.
    Events in the feed have already happened: past tense, dated with a tag like [Jul 31]. Call something "upcoming"
    only if a headline explicitly announces a future date (for example an RPP decision "w środę") — then name it as
    scheduled, never as having happened, and never state its outcome.
R2. Numbers: every figure you write (rates, CPI, GDP, PLN levels, percent moves, prices, deficits) must appear verbatim
    in a headline (Polish decimal comma 3,1 proc. → 3.1%) or in the card. No arithmetic, no remembered figures.
    If a headline says "inflacja wzrosła" without a number, write that it rose, without a number.
R3. Attribute: key claims carry a source and date tag in the report's style, e.g. "(Parkiet, [Jul 31])" or
    "per Business Insider Polska [Jul 31]". Keep tags inside the sentence; do not add link lists or footnotes.
R4. Width: 550–900 prose words (the verifier counts alphabetic words only; numbers, tickers and [Mon DD] tags are not counted, so attribute and quote figures freely). Use this structure, each as its own <p> with the label in
    <strong>; keep the same container <div ...> and the <h3> line from the old block, updating only the stance word
    (Bullish / Mixed / Bearish with its existing colour code: Bullish #2d7a2d, Mixed #b07d00, Bearish #c0392b) and the
    rate pill text (e.g. "→ hold", "↓ cut bias", "↑ hike risk") if the feed justifies a change:
      Macro Stance — NBP / RPP decision and guidance, CPI (GUS flash / final), growth and labour data, wages.
      Markets — GPW / WIG20 action and leaders from the gpw / corp headlines; the zloty from the card (USD/PLN, EUR/PLN
                with 1W / 4W moves); POLGBs only from headlines; EPOL and the named stocks from the card where relevant.
      Fiscal & Politics — budget / deficit / debt issuance, government and Sejm decisions, EU funds, taxes.
      Corporate & Sectors — banks, energy (Orlen, PGE), retail (Dino, LPP, Allegro), mining (KGHM), gaming (CD Projekt),
                housing / mortgages: whatever the feed actually contains.
      Geopolitics & Security — Ukraine, border, defence spending, NATO, Russia-related headlines affecting Poland.
      New / Most Important — the single development that matters most this week and why, in the report's analytical voice.
      Playbook ✓: … &nbsp;|&nbsp; ⚠️ Divergence: … — one paragraph, same format as the old block.
    If a topic has genuinely nothing in the feed, write one honest sentence ("No fiscal headlines this week") rather
    than padding or inventing.
R5. Voice: the report's existing voice — dense, analytical, professional, no fluff, no bullet lists, no emojis beyond the
    ones in the labels. English throughout; Polish names as they are (NBP, RPP, GUS, GPW, Orlen, Sejm, zloty).
R6. HTML: output exactly one <div ...> ... </div> block, same opening tag as the old block, one <h3>, then <p> elements.
    Allowed tags: div, h3, span, p, strong, em, br. Use &nbsp;|&nbsp; between Playbook and Divergence as in the old block.
    No attributes other than those copied from the old block. No markdown.
R7. Never mention that the section was rewritten, expanded, corrected or produced later. No notes.
R8. Coherence with the rest of that day's report: the old block may mention global facts from the same report (oil
    shock, Fed, etc.) — you may keep those exact references.

## Procedure per date
1. Read the old block, the card, then the feed (all of it; skim forum noise).
2. Write the new block to pl/new/<date>.html.
3. Run the verifier; fix every FAIL; resolve every WARN (a number the verifier cannot find in the feed or card must be
   removed or replaced with the exact headline figure). Repeat until PASS with no WARN.
4. Note in 2 lines per date what the stance is and the main story, for your final summary.
