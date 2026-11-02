# Independent audit of the What Retail Is Playing section: March 2025 editions

Your task message gives you a list of DATES and a WORK root. For each date, your folder is WORK/<date>. Work only inside those folders. You are an auditor: check the retail text against its cited headlines and the card, not against your memory.

## Inputs per date (WORK/<date>)
- specs/<date>.json: the edition as it now stands. Edit ONLY the keys "retail_intro" and "retail". Do not touch any other key.
- feeds/<date>.json.gz: the only news source. Use it through tools/cited_titles.py and tools/digest.py with --grep, not by reading the whole file.
- cards/<date>.json: the only market data. Read with python3 -I tools/showcard.py <date> --grep REGEX.
- BRIEF.md: the rules (see "What Retail Is Playing" and "Chronological retail selection").
- tools/: verify.py, render.py, digest.py, showcard.py, cited_titles.py.

## What to check, item by item (retail_intro, then every retail item and each of its parts)
1. Citations: every [[nXXXX]] in the section must exist in the feed and must support the sentence it sits in (company, role, direction, number, date). Run python3 -I tools/cited_titles.py <date> and read only the lines whose first use is in retail[...] or retail_intro.
2. Attention evidence: any claim about posts, replies, mentions, counts, flows, rankings, "most-discussed", "retail is buying", or what the crowd believes must rest on a cited headline that says it. Invented social evidence must be removed or restated as a general tendency ("dip-buyers typically...").
3. Cutoff: nothing that happened on or after 00:00 UTC on the date; no outcome of a release, decision or result that the cited headlines do not show as already happened. A preview may not be written as a completed result.
4. Hindsight and outside knowledge: a concrete name, number, date, event or cause that is in neither a cited headline nor the card is UNSOURCED. General mechanisms (how a squeeze works, why leverage amplifies moves) are allowed. Retrospective wording ("turned out", "later", "subsequently", "eventually", "in hindsight") is not allowed.
5. Card numbers: each price or move must match the card for that instrument and its session (from showcard). Direction words must match the sign. Quoted prices carry the card currency.
6. Narration: no mention inside the text of "the feed", "the card", "the brief", "the writer", "our sources", or "the headlines show" as an input.
7. Consistency inside the section: the lead and the smaller trades must not contradict each other or the same edition's other sections where they share a fact.

## Then fix
For each FATAL or MAJOR finding, edit the retail keys with a short Python script (load specs/<date>.json, change only the affected strings, write back with ensure_ascii=False and indent=2): reword the claim to what the cited headline supports, cut the unsupported sentence, or move a claim to a general tendency. Do not add facts. Keep the structure: lead = six parts, each smaller trade = two parts, titles in "Name / TICKER - the hook" form. Do not edit other keys. After each date, run python3 -I tools/verify.py <date> in that date's folder; it must print PASS (warnings are acceptable).

## Final reply
Reply with ONLY this JSON, and no other text:
{"dates": {"<date>": {"findings": [{"item": "lead or smaller title", "quote": "short exact quote", "problem": "...", "severity": "FATAL|MAJOR|MINOR", "action": "fixed|reworded|deleted|kept (why)"}], "verify": "PASS or FAIL: one-line summary"}}, "fatal_or_major_remaining": 0}
