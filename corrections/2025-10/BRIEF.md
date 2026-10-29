# Writing brief — October 2025 retrospective Market Intelligence Briefings

You write the daily **Market Intelligence Briefing** for a weekday in October 2025 **as it would have been written at
the report's information cutoff: 00:00 UTC on the report date**. The page goes into the public report archive next to the
August 2026 briefings and must read like one of them: an ordinary report of that day, written by a confident senior
strategist for a professional investor who wants to *act* on it.

Paths below are relative to `corrections/2025-10/` (absolute: `/workspace/work/oct2025/code/corrections/2025-10/`).
Work only inside that folder. Do not run git, do not browse the web, do not install anything.

## The one rule that matters most: nothing after the cutoff
You know a lot about late 2025 and 2026 from training — including what happened *after* each report date. **None of it may
enter the report.** The only admissible facts are:

1. **The date's feed** — `feeds/<date>.json.gz`, read through `tools/digest.py`. Google News headlines whose publication
   time is strictly before the cutoff (news ≤ 7 days old, monthly data releases ≤ 35 days, earnings reactions ≤ 14
   days). You only have the **headline**, not the article: claim nothing the headline does not say.
2. **The date's market card** — `cards/<date>.json`, read through `tools/showcard.py`. Completed closes before the cutoff
   (Yahoo Finance, exchange-local session dates; crypto UTC days) and the official US Treasury par curve at the prior
   close, with 1-, 5- and 20-session changes.

General economic reasoning (how a supply shock transmits, why a flat curve squeezes bank margins, how a crowd behaves in
a squeeze) is fine. Facts — an event, a data print, a company result, a policy decision, a price, a date, a schedule — must
come from (1) or (2). Never mention a later outcome, a later price, a later decision, or "what happened next". Do **not**
choose a lead trade, a stance or a catalyst because you know how it ended; choose from what that day's evidence shows. If you
notice yourself "knowing" how something turned out, leave it out.

**File discipline:** open only your own date's feed, card and spec. Never list, read or grep another date's feed, card, spec,
html or json, nor `data/` (raw price history), nor `posthoc`-style files. You may read this brief, `tools/` and the two
files in `reference/`.

Headline hygiene (Google's dates are approximate):
- A headline that describes an event which, per other headlines, had **not happened yet** by the cutoff is misdated — drop
  it (e.g. a "December payrolls" preview dated in early November, a central-bank "decision" headline dated before the meeting).
- **Releases in the early hours UTC of the report date are after the cutoff** even when Google stamps them the day before:
  China's private PMI (01:45 UTC), RBA decisions (03:30 UTC), Australian data (00:30 UTC), Japanese data released at 23:50
  UTC the evening before is fine. If a headline's content is such a release, drop it.
- Do not cite live blogs / rolling pages ("live updates", "LIVE", "as it happened", "stock market today" pages): their titles
  change after publication.
- Monthly releases can be weeks old: call them "the October ISM print", never "this week's".
- Calendar claims ("Nvidia reports on Wednesday", "jobs data Friday") need a feed headline that says so (a preview / week
  ahead headline dated before the cutoff). Otherwise write "the next print" without a date.
- When headlines conflict (one says shares rose, another fell), give no direction.
- The US federal shutdown (from 1 October) delayed official data. Say what the latest available print was and what is
  delayed — only as the headlines say.

Market calendar: use each instrument's session date in the card as the authority. Markets have different holiday calendars. At 00:00 UTC, that date's Asian economic releases are still future events. The October 1 shutdown itself begins after the October 1 report cutoff: discuss the imminent risk, not a completed shutdown, on October 1. Never import later shutdown outcomes.

## Voice — read this before you write a word
The benchmark is the August 2026 archive pages. Their voice: a strategist who has read everything and tells the reader what it
means for positioning, in plain, vivid, specific sentences. The reader never sees your inputs, so:

- **Never narrate the inputs.** Not in the text: "the feed", "the card", "the writer", "the brief", "headlines in our sources",
  "carries no …", "has no data on …", "not a reported fact", "this is the crowd's view, not …", "inferred rather than
  measured", "as of the cutoff", "information cutoff". `tools/verify.py` fails a page that does this (August pages: about three
  mentions of "the feed" per report and none of the rest; the December set averaged about eighteen of "the feed" and nineteen of
  "the writer").
- **When you lack evidence for something, leave it out or write around it — never write about the gap.** A caveat is about the
  market ("the move rests on one print", "positioning can unwind fast"), not about your data.
- **Attribute like a strategist**, inline, by outlet: "Reuters reported…", "per Bloomberg…", "Stocktwits flagged …", "CNBC's
  piece asks…". The page carries no source list; the `[[nXXXX]]` markers are stripped when it is rendered.
- **Interpretation is welcome and expected; invention is not.** Say what retail believes in general terms ("retail reads the
  pivot as redemption"), what institutions are likely doing ("desks are likely trimming…"), how a narrative can break ("the
  risk is…"), plainly and without a disclaimer on every claim. But a **concrete event** — a reply, a post, a mention count, a
  fund inflow, a broker statistic, who bought what — needs a headline behind it; without one, phrase it as a tendency
  ("dip-buyers typically …"), never as something that happened. One honest caveat where it matters.
- **Specific beats general**: name the print, the level, the company, the move, the action. No filler openers ("It is
  important to note…"), no repeated sentences across sections, no boilerplate.
- Open `reference/retail_voice_A_stock_lead.txt` and `reference/retail_voice_B_macro_lead.txt` once: they are the **voice and
  depth reference only** (August 2026 pages). None of their facts, numbers, names, dates or phrases may appear in your report.

## Numbers
Every number you write must be in the card, or in a headline cited **in the same paragraph** (`verify.py` enforces this).
- Market data sentences end with a source tag: `(Yahoo Finance, prior close 2025-09-30)` using the card's `session`
  date of that instrument, or `(US Treasury, prior close 2025-09-30)` using `treasury.prior_close_date`. Both may be
  combined: `(Yahoo Finance, prior close 2025-09-30; US Treasury, prior close 2025-09-30)`. For crypto use the
  crypto session date (weekends included) and say "prior completed daily close".
- Yields with two decimals and %; **yield changes and spreads in bps, never in % of the yield**. Use the card's
  `curve_shape` and `curve_move_20obs` wording for the curve ("positively sloped but still flat by historical
  standards", "moderately steep, approaching the long-run average", "bull flattening") verbatim; never "normal",
  "healthy" or "steepest in years".
- Price changes: use the card's `chg_1s_pct` / `chg_5s_pct` / `chg_20s_pct` (you may round to one decimal). Say
  "over 20 sessions" / "over five sessions" / "in the prior session". Direction words must match the sign.
- Allowed without a source: small counts (≤ 12), "20 sessions", years, and names such as S&P 500, Russell 2000,
  Nasdaq 100, STOXX 600, 10Y, 2Y, Q3.
- Do not compute new ratios or derived figures.

## Citations
Write `[[n0123]]` (the feed item id) immediately after the sentence it supports. It is removed by the renderer; the
published page has no links. Prefer Reuters, Bloomberg, CNBC, FT, WSJ, AP, Barron's, MarketWatch, Nikkei Asia, SCMP,
Caixin, central-bank and statistics-office sources, PR Newswire (ISM), Bankier / Money.pl / Business Insider Polska /
Parkiet / PAP / Notes from Poland for Poland, CoinDesk / The Block for crypto, Stocktwits / 24/7 Wall St. / Yahoo Finance
for retail attention. Avoid autogenerated ticker spam (MarketBeat, Defense World, ETF Daily News …). At least **50
distinct headlines** per report (the wide China and Poland blocks alone carry many); one citation may be reused, but not more
than four times.

## Style rules
- Take a view. Stances are **Bullish / Bearish / Mixed**; use Mixed only when the evidence really is balanced.
- Every **Playbook** states an action with its trigger: what to own / avoid / hedge, and what would change the call. Keep
  Playbooks consistent across sections (an earnings Playbook must not contradict a catalyst; an invalidation must point the
  right way).
- Past events in past tense. No hindsight wording ("turned out", "subsequently", "retrospective"), no mention that this
  is a reconstruction.
- Copper is an asset (AI data-centre / grid capex metal), never a gauge of China or global growth; no gold/copper or
  oil/copper ratios. Read growth from PMIs, credit and housing.
- No Polish companies in the Sector Deep Dive (they belong in the Poland block).
- Company accuracy: describe a company's role exactly as the headline does; for M&A say what the target does.
- Plain text only (no HTML, no emoji); `&`, quotes and arrows are fine. The renderer adds flags, sector names and colours.

## Output: `specs/<date>.json`
```json
{
  "date": "2025-10-01",
  "geo": [
    {"key": "US", "stance": "Mixed", "label": "hold / data dependent",
     "parts": [["Macro Stance", "… [[n0123]]"], ["Rates & Curve", "… (US Treasury, prior close 2025-09-30)"],
               ["New / Most Important", "…"], ["Playbook ✓", "…"]]},
    {"key": "EU", …}, {"key": "CN", …}, {"key": "JP", …}, {"key": "AU", …}, {"key": "PL", …}
  ],
  "sectors": [
    {"key": "XLK", "stance": "Mixed", "parts": [["Narrative", "…"], ["Reported", "…"], ["EPS Upside Watch", "…"],
                                                ["⚡ Breaking Convention", "…"]]},
    … XLC, XLF, XLE, XLI, XLY, XLP, XLV, XLB, XLRE, XLU, SXAP, SOXX (exactly this order)
  ],
  "earnings_pattern": {"title": "…", "parts": [["Rewarded", "…"], ["Punished", "…"], ["Pattern", "…"],
                                                ["Attention into EPS", "…"], ["Playbook", "…"]]},
  "underowned": [{"title": "…", "parts": [["Attention Gap", "…"], ["Exposure & Risk", "…"], ["Trigger to Watch", "…"]]}, {…}, {…}, {…}],
  "crypto": {"title": "…", "parts": [["Market Context", "…"], ["New / Most Important", "…"], ["Playbook", "…"]]},
  "flows": {"title": "…", "parts": [["Global Liquidity", "…"], ["Rates & Dollar", "…"], ["Credit Check", "…"], ["Equity & Fund Flows", "…"], ["Portfolio Implication", "…"]]},
  "anticipatory": [{"title": "…", "parts": [["What Is Priced", "…"], ["Conditional Expression", "…"], ["Risk", "…"]]}, {…}, {…}, {…}],
  "catalysts": [{"title": "$NVDA — short thesis", "stance": "Bullish",
                 "parts": [["Catalyst & Thesis", "…"], ["Price Hurdle & Risk", "…"], ["Trade Expression", "…"]]}, {…}, {…}, {…}, {…}, {…}],
  "retail_intro": "One sentence naming the dominant popular-narrative trade and three or four earlier episodes it resembles (all before the report date).",
  "retail": [{"title": "Name / TICKER — the hook", "parts": [["Why Retail Is Here", "…"], ["What Is Driving It", "…"],
              ["The Social Signal", "…"], ["Historical Analog", "…"], ["Smart Money View", "…"],
              ["When the Narrative Breaks", "…"]]}, {"title": "…", "parts": [["Why Retail Is Here", "…"], ["Where It Breaks", "…"]]}, {…}, {…}]
}
```
Labels, keys, block counts and order are checked exactly. The Poland block uses these seven parts: Macro Stance · Markets ·
Fiscal & Politics · Corporate & Sectors · Geopolitics & Security · New / Most Important · Playbook ✓.

### Section guide — the whole report ≈ 9,500–11,000 words, block by block at the depth of the August 2026 pages
Word counts are per block (August medians in brackets). Do not pad: depth comes from specifics.

**🌍 Geographic Macro Overview** — six blocks, `label` = 2–6 word policy/stance tag (e.g. "hold / data dependent",
"easing bias / weak demand"). Each block closes with a **Playbook ✓**.
- **US** (400–500 words [407]): Macro Stance · Rates & Curve (2Y, 10Y, 10Y−2Y spread at the prior close, 20-observation bps
  changes, curve shape and move labels, plus S&P 500 / VIX / DXY context) · New / Most Important · Playbook ✓.
- **EU** (250–350 [224]): Macro Stance · Credit & Inflation (or Activity & Inflation) · New / Most Important · Playbook ✓.
- **CN** (800–950 [948], exactly these eight parts): Macro Stance · PMIs & Activity · Credit Impulse · Property ·
  Fiscal, Policy & Trade · Markets & Flows (Hang Seng / Shanghai / ASHR / KWEB / USD/CNY from the card) ·
  New / Most Important · Playbook ✓ (end with "⚠ Divergence: …" — the signal that contradicts the main story).
  If the feed has no fresh print for a part, say what the latest available print was (with its month) and what would
  confirm the view — without talking about the feed.
- **JP** (270–350 [288]): Macro Stance · Activity & Currency (USD/JPY, Nikkei from the card) · Playbook ✓.
- **AU** (200–300 [181]): Macro Stance · Demand & Financing (AUD/USD, ASX 200 from the card) · Playbook ✓.
- **PL** (850–1,050 [1,015]; the Polish reader's block — use the Polish-language headlines heavily and translate them in the
  sentence): **Macro Stance** (NBP / RPP decision and guidance, CPI, GDP, wages, retail sales, industry, PMI) · **Markets**
  (USD/PLN, EUR/PLN, EPOL, the WIG20TR ETF and named Polish stocks from the card, leadership rotation, POLGB / yield
  headlines, foreign flows) · **Fiscal & Politics** (budget and deficit, taxes, ratings, president / government) ·
  **Corporate & Sectors** (banks, energy and Orlen / PGE, KGHM / JSW, Dino / LPP / Allegro, CD Projekt, defence names, results
  and guidance as the headlines say) · **Geopolitics & Security** (Russia / Ukraine / NATO incidents, defence funding) ·
  **New / Most Important** (the one signal that matters, with what it means) · **Playbook ✓** (end with "⚠ Divergence: …").

**📊 Sector Deep Dive** — 13 blocks, 150–200 words each [164], four parts: **Narrative** (consensus + the driver that matters
now, may use the sector ETF's 20-session change from the card) · **Reported** (who reported in the feed window: beat /
miss, guidance, share reaction — only as the headline says) · **EPS Upside Watch** (who is set up for an earnings
surprise and why, from previews / estimate revisions / demand headlines) · **⚡ Breaking Convention** (the signal that
cuts against the consensus narrative). SXAP = European autos; SOXX = US–Asia semis incl. ASML / TSMC.

**🧮 Earnings Pattern — What the Market Pays For** — one block, 350–420 words [389], read from the last two weeks of Q3
results and share reactions: Rewarded · Punished · Pattern · Attention into EPS · Playbook.

**🔍 Underowned Themes** — four themes, 110–150 words each [125]: Attention Gap · Exposure & Risk (name instruments) ·
Trigger to Watch (the dated or observable event that would make the theme consensus). Do not claim measured
positioning data unless a headline gives it.

**₿ Crypto & Digital Assets** — 290–360 words [313]: Market Context (BTC / ETH / SOL closes and changes from the card, IBIT /
COIN / MSTR if useful) · New / Most Important · Playbook.

**💰 Capital Flows & Liquidity Framework** — 600–750 words [697], five parts: Global Liquidity (central-bank balance sheets,
policy stance, what the headlines show about liquidity) · Rates & Dollar (DXY, curve, HYG / LQD / TLT from the card) ·
Credit Check · Equity & Fund Flows (ETF / fund flow headlines, buybacks, positioning as the headline reports them) ·
Portfolio Implication.

**🔮 Anticipatory Positioning** — four scenarios the market is pricing (only events the feed shows as pending), 140–190
words each [159]: What Is Priced · Conditional Expression (the trade if it goes either way) · Risk.

**⚡ High-Conviction Stock Catalysts** — six single names with a stance, 100–140 words each [120]; title "$TICKER — short
thesis". Catalyst & Thesis (the dated catalyst from the feed + the thesis) · Price Hurdle & Risk (use the card's close /
20-session change if the ticker is there; otherwise no price) · Trade Expression (instrument, direction, what would
invalidate it).

## 🔥 What Retail Is Playing — the section the reader judges the page by
A narrative essay about the crowd, not a list of capsules. Four trades: one **lead** and three **smaller**. August depth: lead
650–850 words [792], each smaller trade 150–220 words [118 in August; yours are two-part], the section ≈ 1,200–1,350 words.

**Choose the trades first** (before writing a sentence):
1. Gather candidates from three places: (a) `tools/showcard.py` — the speculative / retail-favourite instruments with the
   biggest 5- and 20-session moves (single stocks, crypto and crypto equities, quantum / nuclear / space / AI-infrastructure
   names, leveraged and thematic ETFs, gold / silver); (b) `tools/digest.py <date> --topic retail --max 200` — what the
   attention headlines are about (Stocktwits, Reddit, Robinhood, retail-flow and dip-buying stories, most-active lists, meme
   names, options activity); (c) the sector, earnings, crypto and flows headlines about the names everyone is talking about.
2. The **lead** is the trade where price evidence and attention evidence coincide: something moving a lot (a surge, *or* a
   sharp drawdown the crowd is buying) **and** showing up in retail-attention headlines **and** carried by a simple story the
   crowd repeats. Pick it from that day's evidence — not for what you know happened afterwards. A trade can lead for several
   days in a row; the text must still be that day's.
3. The three smaller trades are **different narratives** (not three tickers of one basket); include a non-equity or
   non-AI trade when the evidence supports one.

**`retail_intro`** — one sentence in the August shape: the dominant popular-narrative trade capturing retail attention right
now, analogous to three or four named earlier episodes (all before the report date; for example Nvidia 2023, Tesla 2020,
GameStop 2021, Bitcoin 2020–21, the 1999 infrastructure trade, uranium or clean energy 2021, gold or Rheinmetall 2025).

**Lead trade** — six parts in this order, 650–850 words in total, vivid and concrete:
- **Why Retail Is Here** — the story retail tells itself, in the crowd's own words: the simple thesis, the emotional hook, why it
  feels obvious and unstoppable, the number or level the crowd anchors on (4–6 sentences).
- **What Is Driving It** — the hard evidence: the name's and its peers' moves from the card (prior session, five and 20
  sessions), the catalyst — earnings, guidance, a deal, a product — as cited headlines say, and the cross-asset backdrop
  (yields, dollar, Nasdaq, VIX) where it matters. The most numeric paragraph.
- **The Social Signal** — what attention looks like: Stocktwits sentiment pieces, Reddit / WallStreetBets threads, trending and
  most-active lists, Robinhood and brokerage flows, options-volume stories, influencer or platform headlines, and how the crowd
  reads institutional skepticism. Quote or closely paraphrase the actual headlines' language, name the outlet. When direct
  social evidence is thin, use the nearest real evidence (retail-flow and dip-buying data, broker data, ETF flows, volume,
  short interest) and write it as evidence — never as a gap.
- **Historical Analog** — one named earlier episode (before the report date) and the *mechanical* similarity: what happened
  first, what came second, why retail is in the second wave. Not surface vibes.
- **Smart Money View** — the institutional view, split honestly: what supports the trade (named banks, funds, analysts as the
  headlines say) and what institutions are hedging, trimming or warning about; say whether the disagreement is about direction
  or about pace.
- **When the Narrative Breaks** — specific, observable triggers: card levels (the 20-session reference close, round numbers),
  data prints, earnings, rate moves, dated events the headlines show as pending, and instrument risks (leverage, ETF
  premium / discount, liquidity).

**Three smaller trades** — two parts each, 150–220 words: **Why Retail Is Here** (one vivid paragraph on the attraction and the
crowd's story) · **Where It Breaks** (the trigger, with a card level or a pending event, and the instrument risk).

Title format for every item: **"Name / TICKER — the hook"**; the hook is what the crowd says, at most eight words, written
without quotes (the page prints it in quotes). Examples of the shape: "Palantir / PLTR — the AI operating system",
"Silver / SLV — is silver the new gold?". Only facts from the item's headlines and the card; interpretation (what retail
believes, what the crowd reads into a headline, how a narrative can break) is expected, in the plain voice above, with no
disclaimers about its status — but never invent social evidence (no made-up posts, replies, counts or flows).

## Procedure per date
```
cd /workspace/work/oct2025/code/corrections/2025-10
python3 -I tools/showcard.py <date>                       # market card as a table (--grep REGEX to filter)
python3 -I tools/digest.py <date>                          # prioritised headlines per topic
python3 -I tools/digest.py <date> --topic retail --max 200 # attention headlines for the retail section
python3 -I tools/digest.py <date> --grep "regex" --max 80  # search every item
python3 -I tools/verify.py <date>                          # fix every FAIL; review every WARN
python3 -I tools/render.py <date>                          # must render without error
```
1. Read the card and the digest (all topics; then `--grep` for what you need: earnings reactions, Polish items, Stocktwits,
   pending events). Decide the stances, the lead retail trade and the main stories **before** writing.
2. Write `specs/<date>.json` (valid JSON; escape quotes).
3. `verify.py` → fix every FAIL, review every WARN (fix it or be sure it is right). Re-read the retail section against the
   voice rules. `render.py`.
4. Before you finish, check: no narration about inputs; no fact without a headline or card number; no event after the cutoff; the
   retail lead is chosen on that day's evidence and every part is concrete; the Playbooks agree with each other; the whole
   report is ≈ 9,500–11,000 words.
5. Reply with a 3–5 line note: overall tone, the stances you chose, the lead retail trade and why, anything you deliberately
   excluded.


October additions: Include inline outlet attribution and [[nXXXX]] tokens on every concrete news fact, including translated Polish facts. The renderer preserves linked citations and provides a dated evidence ledger. Ignore later outcomes you may know. Do not read another report date's inputs. All output must be freshly written for that date. Later splits have been accounted for by the data pipeline; omit price levels if the card flags unreliable levels. Headlines alone do not verify full article details. Avoid any rolling/live article. Check for approximate RSS dates on Asian releases.


## Chronological retail selection

For a retrospective report, select from its own eligible dated evidence and earlier editorial history only. A persistent theme may remain when its catalyst, reaction or attention meaningfully changes. A new price or subtitle alone does not justify another full essay. Shorten unchanged carryovers. Do not impose ticker quotas or infer a measured retail ranking from price/news. Compare prior selections chronologically before publication; never use later-month popularity or performance to select an earlier report.

Use the shared corrections/retail-quality preflight and record specific evidence-bound dispositions. Review theme identity, company versus platform sentiment, direct versus indirect exposure and source-supported attention. The guard is diagnostic; an independent editor must verify the changed angle. Preserve live style references, including recurring themes that reflected ongoing live attention.
