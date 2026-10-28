# Critic brief — November 2025 retrospective briefings

You review ONE finished briefing (`specs/<date>.json`) against the rules in `BRIEF.md` and against the August 2026 benchmark, and
you **repair what is wrong directly in the spec**. You did not write it: read it cold. The owner will judge the page against
the August 2026 archive pages, "especially What Retail Is Playing".

Work from `/home/user/DailyDigest_Markets/corrections/2025-11`. Read `BRIEF.md` completely first. Inputs for your date only:
`feeds/<date>.json.gz` (through `tools/digest.py`, `--grep`), `cards/<date>.json` (through `tools/showcard.py`). Open no other
date's files, not `data/`. No git, no web.

## What to check (in this order of importance)

1. **Hindsight and leaks.** For every factual claim in Retail, Catalysts, Anticipatory, Earnings Pattern, Geographic Macro and
   Flows, find the supporting headline (`digest.py --grep`) or card number. Remove or rewrite anything that rests only on
   knowledge of what happened later, on a release/event that falls **after 00:00 UTC on the report date** (Asian-session and
   early-UTC releases dated the day before by Google), on a misdated or rolling/live headline, or on a calendar claim without a
   dated pending-event headline. A lead retail trade or a catalyst chosen because of how it ended is a leak: re-choose from that
   day's evidence.
2. **Accuracy against the cited headline.** The `[[nXXXX]]` after a sentence must say what the sentence says: same company, same
   direction, same number, same role (for M&A, what the target does). Fix wrong direction words (headlines that conflict → no
   direction), wrong company/ticker, a number from a different period, a "beat/miss" the headline does not state.
3. **Retail section quality** (see BRIEF "What Retail Is Playing" and `reference/`):
   - lead chosen where price evidence (card) and attention evidence (retail headlines) coincide; the three smaller trades are
     different narratives;
   - six lead parts, each concrete: *Why Retail Is Here* in the crowd's words; *What Is Driving It* numeric (card moves, catalyst
     headlines, backdrop); *The Social Signal* built from real attention evidence (Stocktwits / Reddit / most-active / Robinhood /
     retail-flow headlines, quoted or closely paraphrased, outlet named); *Historical Analog* a named episode **before** the
     report date with the mechanical similarity (first wave → second wave); *Smart Money View* an honest split; *When the
     Narrative Breaks* with card levels and pending events;
   - small trades: a vivid *Why Retail Is Here* and a concrete *Where It Breaks*;
   - **no invented social evidence**: a concrete reaction (a reply, a post, a mention count, a fund inflow, who bought what) must
     have a headline behind it; otherwise rewrite it as a general tendency or drop it;
   - voice: confident strategist, no narration about inputs, no disclaimers about what is "the crowd's view" versus "reported
     fact", no hedging that reads as filler. Compare it paragraph by paragraph with the August voice references.
4. **Voice across the page.** Remove narration about inputs anywhere ("the feed", "the card", "the writer", "carries no…",
   "not measured"). Remove boilerplate caveats, repeated sentences and filler openers; keep one honest caveat where it matters.
5. **Consistency.** Stances match the text; Playbooks across sections do not contradict each other (earnings Playbook vs
   catalysts vs sector stances); an invalidation level points the right way for the stated direction; the lead retail trade is
   consistent with the flows / crypto / sector views; rate pills and labels state a direction.
6. **Depth and structure.** Block lengths at August depth (see BRIEF section guide); Poland and China blocks wide and specific
   (Polish headlines used and translated); sectors' *Reported* and *EPS Upside Watch* name real companies with real headline
   evidence; no Polish companies in sectors; copper only as an asset.

## How to repair
- Edit `specs/<date>.json` in place (valid JSON; keep the `[[nXXXX]]` markers; every number must stay traceable). Prefer
  surgical rewrites of the weak sentences over rewriting whole blocks; when a block is hollow, rewrite it from the feed.
- After editing run `python3 -I tools/verify.py <date>` (0 FAIL; review every WARN) and `python3 -I tools/render.py <date>`.
- Do not weaken a rule to make a check pass.

## Report back (short)
Lines: (1) verdict in one sentence; (2) the number of fixes by category — leaks / accuracy / retail / voice / consistency /
depth; (3) the three most important fixes, each with before → after in a few words; (4) anything you could not resolve and why;
(5) the final `verify.py` summary line.
