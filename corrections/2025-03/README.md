# March 2025 retrospective briefings

Request read as **March 2025**, not March 2005. The series here is built backward month by month (June to April 2025 already exist), and the repository holds no 2005 material.

Scope: 21 weekday editions, 3-31 March 2025. Each edition is as it would have stood at 00:00 UTC on its report date, in the wide nine-section layout, with a "What Retail Is Playing" section. Outputs: `specs/` (the text), `notes/` (retail selection records), `html/` and `json/` (rendered editions), `retail/What_Retail_Is_Playing_2025-03.html` (the retail sections on one page).

## Status

- **Drafts:** all 21 editions. Each passes `tools/verify.py` with 0 failures (warnings remain; see below).
- **Non-retail sections:** each edition was checked by a separate auditor against its cited headlines and the market card. Unsupported claims were reworded or deleted. Early-release items were removed, for example China's industrial profits and home-price prints released early on their report date (3/17, 3/27), a Canadian steel-tariff halt dated before the cutoff (3/18), and Abercrombie & Fitch results (3/6).
- **Retail sections:** a sequential chronology pass ran one editor per edition in date order. Each editor saw only earlier retail selections. Leads changed on 18 of 21 editions; repeated Tesla leads were replaced where the evidence supported a change. A separate retail audit then removed crowd-behaviour claims that no cited headline supported, and named historical analogues that had no source.

## Method

- **Feeds:** Google News RSS harvest from `tools/expand_capped_news.py` (445 queries, 15 topics, weekly windows with cutoff-prefix and daily-refinement requests). `tools/ready_feeds.py` keeps 8,269-13,091 headlines per edition and drops 0-10 per edition with release-timing guards.
- **Cutoff:** a headline counts only if its RSS date is strictly before 00:00 UTC on the report date. Feeds are gitignored; rebuild them with the commands below.
- **Market data:** Yahoo Finance completed closes and the US Treasury daily par curve, 288 instruments (`cards/`, `data/`). SCCO is omitted because Yahoo returned no history for it between December 2024 and April 2025.
- **Writers:** one isolated sandbox per edition, holding only that date's feed, card, brief and tools.

## Limitations (read before relying on this)

1. **No publisher-date verification.** The April method resolved Google News links to publisher dates. That step was not reproduced for March. Timing relies on RSS dates and the release guards in `ready_feeds.py`, so a misdated headline can still get through.
2. **Model-based checks, not human review.** The audits are AI agents checking text against the cited headlines and the card. They are thorough but not exhaustive, and they can miss errors. Treat each edition as a reconstruction, not a verified archive.
3. **Feed gaps.** Some expected releases are absent from the feed (for example China's factory PMI and some credit prints). Where that happened the text says so, or leaves the item out.
4. **Verify warnings remain.** Some editions run above the word target (3/10, 3/18 and others), a few citations are reused more than four times, a few calendar phrases need dated headlines, and some market sentences lack the source tag the brief asks for. These are warnings, not failures.
5. **Notes for 3/10, 3/12 and 3/18** were regenerated from the saved specs, because the writers' original records were not saved. They are marked `regenerated_from_spec`.
6. **Not published.** Nothing was sent to S3, CloudFront, Lambda, email or Telegram.

## Tooling changes versus April

- `verify.py` and `render.py`: the April-only month check (`month != 4`) now tests March.
- `expand_capped_news.py`: tolerates the hash of the April-only `posthoc/` file being absent.
- `fetch_market.py`: SCCO removed from the universe.
- `build_retail_page.py`: new; builds the retail page from the editions.
- `cited_titles.py`: new; lists the headline behind each citation in an edition.

## Reproduce

From `corrections/2025-03`, after the feeds and cards have been built:

```bash
python3 -I tools/verify.py 2025-03-03 2025-03-04 2025-03-05 2025-03-06 2025-03-07 2025-03-10 2025-03-11 2025-03-12 2025-03-13 2025-03-14 2025-03-17 2025-03-18 2025-03-19 2025-03-20 2025-03-21 2025-03-24 2025-03-25 2025-03-26 2025-03-27 2025-03-28 2025-03-31
python3 -I tools/render.py 2025-03-03 2025-03-04 2025-03-05 2025-03-06 2025-03-07 2025-03-10 2025-03-11 2025-03-12 2025-03-13 2025-03-14 2025-03-17 2025-03-18 2025-03-19 2025-03-20 2025-03-21 2025-03-24 2025-03-25 2025-03-26 2025-03-27 2025-03-28 2025-03-31
python3 -I tools/build_retail_page.py
```

To rebuild the feeds from scratch:

```bash
python3 -u tools/fetch_market.py --resume
python3 tools/build_cards.py
python3 -u tools/expand_capped_news.py --workers 12
python3 tools/ready_feeds.py
```

`tools/handoff/` holds the writer, chronology-editor, non-retail auditor and retail-auditor instructions, plus the sandbox and earlier-edition helpers. Those helpers were written for a scratch folder, so adjust their paths before reuse.
