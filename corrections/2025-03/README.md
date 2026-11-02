# March 2025 retrospective briefings: PARTIAL, saved for handoff

Request read as **March 2025**, not March 2005. The series here is built backward month by month (June to April 2025 already exist), and the repository holds no 2005 material. Target: 21 weekday editions, 3-31 March 2025, cutoff 00:00 UTC on each report date, nine-section wide layout, with a "What Retail Is Playing" section.

## What is saved
- **News feeds**: Google News RSS harvest from `tools/expand_capped_news.py` (445 queries, 15 topics, weekly windows, cutoff-prefix and daily refinement requests, about 9,650 base requests). `tools/ready_feeds.py` keeps 8,269-13,091 headlines per edition and excludes 0-10 per edition with release-timing guards. Feeds are gitignored; rebuild them with the two commands above.
- **Market cards**: `cards/` (288 instruments) and `data/` (Yahoo Finance daily closes and US Treasury par curve). SCCO is omitted because Yahoo returned no December 2024 to April 2025 history for it.
- **Drafts**: `specs/` and `notes/` for 19 of 21 editions.
- **Verification**: `verify.py` (with the April-only month check corrected to March) passes 17 editions. Rendered HTML/JSON exists for those 17.
- **Retail page**: `retail/What_Retail_Is_Playing_2025-03.html` shows the 19 retail sections. Hover a source number to see its headline.
- **Handoff prompts**: `tools/handoff/` holds the writer, editor and auditor instructions, plus `make_sandboxes.py` and `make_earlier.py`. The two scripts were written for a scratch folder, so adjust their paths before reuse.

## Known gaps: do not treat as final
1. **No chronological retail pass.** Tesla is the lead in 11 editions (3/4, 3/5, 3/6, 3/11, 3/12, 3/14, 3/20, 3/24, 3/25, 3/28, 3/31). D-Wave/QBTS leads 3/17-3/19. The brief requires each lead to be checked against strictly earlier editions.
2. **Two verify FAILs.** 3/10 uses "corrected" in a catalyst paragraph, which the hindsight rule forbids. 3/18 has a Playbook that names "March 19" with no citing headline.
3. **Missing drafts.** 3/21 and 3/26 have no spec (writers stopped). Notes are missing for 3/10, 3/12 and 3/18.
4. **No independent cutoff audit** of the claims against their cited headlines. Only `verify.py` (citations, numbers, narration, hindsight words) has run.
5. **No `retail_quality.py` preflight** run for the month.
6. **No canonical publisher-date resolution.** The April step (resolving Google News links to publisher dates) was not reproduced. Timing relies on RSS dates plus the release guards, so a misdated headline can still get through.
7. **Feed gaps.** Several drafts state that a print is absent from the feed (for example China factory PMI and fresh China credit data).
8. **Renderer boilerplate.** Every page carries "Prepared retrospectively; later outcomes are excluded." Check the wording before any publication.

## Tooling changes versus April
- `verify.py` and `render.py`: the April month check (`month != 4`) now tests March.
- `expand_capped_news.py`: the hash of the April-only `posthoc/` file is tolerated when missing.
- `fetch_market.py`: SCCO removed from the universe.
- `build_retail_page.py`: new; skips editions without a spec.

Not published anywhere: no S3, CloudFront, Lambda, email or Telegram.

## To finish
Run from `corrections/2025-03`:

```bash
python3 -I tools/verify.py 2025-03-03 2025-03-04 2025-03-05 2025-03-06 2025-03-07 2025-03-10 2025-03-11 2025-03-12 2025-03-13 2025-03-14 2025-03-17 2025-03-18 2025-03-19 2025-03-20 2025-03-21 2025-03-24 2025-03-25 2025-03-26 2025-03-27 2025-03-28 2025-03-31
python3 -I tools/build_retail_page.py
```

Then complete the chronological retail editor pass (`tools/handoff/EDITOR_INSTRUCTIONS.md`, one date at a time, earlier editions only), the cutoff audit (`tools/handoff/AUDITOR_INSTRUCTIONS.md`), the `retail_quality.py` preflight from the repository root, and the drafts for 3/10, 3/18, 3/21 and 3/26.
