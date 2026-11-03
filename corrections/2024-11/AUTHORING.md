# November 2024 Market Intelligence Briefings — author contract

This condenses the latest `corrections/2025-03/BRIEF.md`, its writer/editor/auditor instructions, and `corrections/retail-quality/README.md`. Use the August 2026 pages for voice and depth only. Their facts, names, numbers, dates and wording are not November evidence.

Write an ordinary briefing of the assigned day, as it would have stood at **00:00:00 UTC on that report date**. The scope is every Monday–Friday date in November 2024, including exchange holidays: November 1, 4–8, 11–15, 18–22, and 25–29 (21 editions). Use the wide nine-section layout, without a top price dashboard or sector leadership chart.

## Own-date evidence and isolation

- Use only the assigned date's frozen feed, market card and spec. Facts must come from the feed headline or card. Do not read another date's feed/card/spec, raw price history, or reviewer/posthoc files. Writers may read the reference excerpts and author tools. A chronological retail editor may additionally read strictly earlier retail selections as editorial memory, never as evidence for a fact.
- Publication timestamps must be strictly before the cutoff. Fresh news and previews have a seven-day window, company results fourteen days, macro releases/policy baselines thirty-five days. An old company event does not become fresh because a macro query found it.
- You have a headline, not an article. Claim only what it establishes. Reject live blogs, rolling pages, contradictory directions, advertisements, irrelevant matches, and clearly misdated outcomes. A preview establishes a pending event, never its result.
- A release on the report's UTC day is after cutoff. Evaluate actual release time: Japanese morning data can fall before UTC midnight; Asian same-local-day data are not automatically eligible or ineligible. Omit a doubtful completed-event claim rather than resolving it from later editions or memory.
- Calendar claims need an eligible preview that says when the event is due. Otherwise say “the next print” without a date. Named historical-episode facts also need eligible own-date support; otherwise explain a general mechanism without invented episode details.
- No hindsight, later outcomes, later prices, later policy decisions, later election/legal results, or reconstruction commentary. Choose stories and stances from that day's evidence alone.

## Voice, numbers and attribution

Write like a senior strategist: direct thesis, specific evidence, causal mechanism, conflicting signal, and an actionable trigger. Interpret evidence without inventing facts. Use general/modal language for behavioral tendencies; concrete posts, replies, counts, flows, rankings, institutional actions and purchases need a supporting headline.

Do not narrate the inputs: no “the feed,” “the card,” “the writer,” “our sources,” “information cutoff,” or explanations of missing evidence. Leave an unsupported claim out or write around it. Market caveats describe an investment risk, not the author's data collection.

Use inline outlet attribution and preserve `[[nXXXX]]` citation IDs immediately after supported sentences. Aim for at least fifty distinct headlines per edition and no more than four uses of an individual citation. Source names must match metadata; distinguish analyst expectations from company guidance. No Polish companies in the Sector Deep Dive; discuss them in Poland.

Every number must be in the own-date card or in a headline cited in the same paragraph. Quote card values exactly, with permitted rounding; do not calculate new ratios or rescale share units. The card supplies reconstructed as-traded prices and comparable split-adjusted returns. Missing new-listing history stays missing. Prices need currency or index points; every signed return needs `%`. DXY is an index. PMI readings are index points. Yields use two decimals and `%`; yield changes/spreads use bps. Use the card's curve-shape and curve-move wording. Never call a positive curve inverted or describe copper/metal ratios as growth signals; use activity, PMI, credit and housing evidence for growth.

Market figures use each instrument's actual completed exchange-local session, strictly before cutoff. Crypto uses its prior completed UTC daily close. Source tags: `(Yahoo Finance, prior close YYYY-MM-DD)`; `(US Treasury, prior close YYYY-MM-DD)`; crypto `(Yahoo Finance, prior completed daily close YYYY-MM-DD)`. Do not assume one country's session applies to another or replace Treasury yields with an IRX proxy.

Use plain text inside content strings; the renderer adds presentation. Stances are exactly `Bullish`, `Bearish`, or `Mixed`. Each Playbook states an action, its trigger and what changes the call; keep actions consistent across sections. Target **9,500–11,000 words**, with specific analysis rather than padding.

## Exact spec structure and labels

Write `specs/DATE.json` with top-level keys `date`, `geo`, `sectors`, `earnings_pattern`, `underowned`, `crypto`, `flows`, `anticipatory`, `catalysts`, `retail_intro`, `retail`. Blocks use `parts`: ordered `[label, text]` pairs. Preserve exact keys, counts, order and labels.

1. **Geographic Macro Overview:** `geo` keys in order `US, EU, CN, JP, AU, PL`, each with `key`, `stance`, a short policy `label`, and `parts`.
   - US, 400–500 words: `Macro Stance`; `Rates & Curve`; `New / Most Important`; `Playbook ✓`. Include prior-close 2Y/10Y/spread, twenty-observation bps changes and curve wording; relevant S&P/VIX/DXY context.
   - EU, 250–350: `Macro Stance`; `Credit & Inflation` (or `Activity & Inflation`); `New / Most Important`; `Playbook ✓`.
   - CN, 800–950, exactly: `Macro Stance`; `PMIs & Activity`; `Credit Impulse`; `Property`; `Fiscal, Policy & Trade`; `Markets & Flows`; `New / Most Important`; `Playbook ✓`. End the Playbook with `⚠ Divergence:` and the contradictory signal.
   - JP, 270–350: `Macro Stance`; `Activity & Currency`; `Playbook ✓`.
   - AU, 200–300: `Macro Stance`; `Demand & Financing`; `Playbook ✓`.
   - PL, 850–1,050, exactly: `Macro Stance`; `Markets`; `Fiscal & Politics`; `Corporate & Sectors`; `Geopolitics & Security`; `New / Most Important`; `Playbook ✓`. End with `⚠ Divergence:`. Translate and use relevant Polish-language headlines; cover domestic policy/activity, currency/market context, companies, fiscal politics and security from evidence.
2. **Sector Deep Dive:** thirteen blocks, `key` order `XLK, XLC, XLF, XLE, XLI, XLY, XLP, XLV, XLB, XLRE, XLU, SXAP, SOXX`, each with stance and 150–200 words. Exact labels: `Narrative`; `Reported`; `EPS Upside Watch`; `⚡ Breaking Convention`. SXAP is European autos; SOXX is US–Asia semis, including ASML/TSMC. Keep reported results, previews and conditional earnings logic distinct.
3. **Earnings Pattern:** one titled block, 350–420 words. `Rewarded`; `Punished`; `Pattern`; `Attention into EPS`; `Playbook`.
4. **Underowned Themes:** four titled themes, 110–150 words each. `Attention Gap`; `Exposure & Risk`; `Trigger to Watch`. Name instruments without inventing measured ownership.
5. **Crypto:** one titled block, 290–360 words. `Market Context`; `New / Most Important`; `Playbook`.
6. **Capital Flows & Liquidity:** one titled block, 600–750 words. `Global Liquidity`; `Rates & Dollar`; `Credit Check`; `Equity & Fund Flows`; `Portfolio Implication`. Price changes alone are not flow evidence.
7. **Anticipatory Positioning:** four titled scenarios, 140–190 words each. `What Is Priced`; `Conditional Expression`; `Risk`. Use only events known to be pending.
8. **Stock Catalysts:** six single names, each with title, stance and 100–140 words. `Catalyst & Thesis`; `Price Hurdle & Risk`; `Trade Expression`.
9. **What Retail Is Playing:** the structure below.

## What Retail Is Playing — select before writing

This is a narrative essay about the crowd: **one lead plus three smaller, distinct trades**, approximately **1,200–1,350 words**. Title format: `Name / TICKER — the hook`; hook at most eight words, without quotation marks. `retail_intro` is one sentence naming the dominant popular narrative and any supportable earlier analogy/general mechanism. No future analogies or unsupported episode details.

Build a candidate shortlist from own-day price moves (surges and drawdowns), retail-attention evidence and concrete sector/earnings/crypto catalysts. The strongest lead combines a significant move, attention evidence and a simple repeatable story. Secondary trades must express different narratives; no reserved metals/AI/crypto/comeback slots or arbitrary ticker variety quota.

**Lead: 650–850 words, exactly six parts in this order:**

- `Why Retail Is Here`: simple thesis, emotional attraction and relevant price anchor, in vivid connected prose.
- `What Is Driving It`: cited catalyst plus exact own-card moves and relevant cross-asset backdrop.
- `The Social Signal`: attributed real attention evidence; no invented posts, counts, flows or rankings. Broader genuine broker/ETF/options/volume evidence may be used for what it establishes.
- `Historical Analog`: supported earlier episode and mechanical similarity, or general mechanics without invented historical facts.
- `Smart Money View`: headline-supported analysts/institutions, honestly split where appropriate; general tendencies stay modal.
- `When the Narrative Breaks`: observable invalidation, supported price context, pending catalyst and relevant instrument/leverage/liquidity risk.

**Each smaller trade: 150–220 words, exactly two parts:** `Why Retail Is Here`; `Where It Breaks`.

Compare selections chronologically with strictly earlier retail notes/editions. A persistent theme may remain when its catalyst, reaction or attention changes materially. A new price, subtitle or wrapper does not justify another full essay. An unchanged carryover is brief and secondary; a repeat lead needs newly eligible supporting evidence. Record the change and cite it. Do not use later-month popularity/performance to choose earlier stories.

Write `notes/DATE.json`: `date`, `lead`, `smaller` (three titles), `why_lead`, `why_smaller`, `evidence_ids`, `considered_not_chosen`. Selection reasons must match that date's evidence and final spec.

## Completion and review

Run the own-date verifier, fix every failure and review warnings; render cleanly. Independently check every cited claim against its headline/card, timing, actual versus preview, named company role, numbers/units, social evidence and cross-section consistency. Retail chronology review may change only retail text/notes and must use strictly earlier history. Re-run validation after edits.

Before publication run the shared `corrections/retail-quality/retail_quality.py` preflight, independently review its flags and record evidence-bound dispositions. Repeated-basket/family diagnostics are not automatic errors; unchanged full leads cannot be cleared by generic approval. `material_update` needs newly published eligible evidence cited in the item; `brief_carryover` is secondary and at most 160 words. Do not fabricate review dispositions. `--require-reviewed` must pass and receipts must bind final spec hashes. Source membership/timestamps remain hard checks; passing automated checks does not replace factual/editorial review. Writers do not publish, invoke Lambda, or send messages.


## FX data amendment (2026-11-03)

Frozen card bytes remain unchanged for auditability. Do not quote numerical levels, returns or prior-close/session-close labels for any Yahoo `=X` currency pair in report prose. The vendor daily close convention cannot be certified as the completed market session and conflicts with contemporaneous direction reporting on the election date. Use eligible dated FX headlines for direction and general transmission analysis. DXY is an independently quoted dollar index and remains admissible. Do not shift date labels, substitute later quotes or calculate a synthetic close.
