# Cutoff and fact audit of the non-retail sections: March 2025 edition

Your task message gives DATE and AUDIT (your folder, a copy of the edition). Work only inside AUDIT.

## Inputs
- specs/DATE.json: the draft. Audit ONLY these keys: geo, sectors, earnings_pattern, underowned, crypto, flows, anticipatory, catalysts. Do NOT edit retail_intro or retail (another process is editing them).
- feeds/DATE.json.gz: the only news source. Use it only through tools/digest.py and tools/cited_titles.py, not by reading the whole file.
- cards/DATE.json: the only market data. Read with python3 -I tools/showcard.py DATE.
- BRIEF.md: the rules you audit against.

## Procedure
1. Run python3 -I tools/cited_titles.py DATE > cited.txt. It lists every cited headline (id, published time, source, headline, first use). Read cited.txt.
2. Read the audited keys of specs/DATE.json. For each paragraph, check every factual sentence: an event, a print, a decision, an outcome, a price, a schedule, a company result or role. It must be supported by a headline cited in the same paragraph (and that headline must actually say it), or by the card (exact value, with the session date in the source tag).
3. Check every number and direction word against the card or the cited headline. Yields and spreads in basis points.
4. Cutoff: flag any statement of an outcome, decision or print that the cited headlines could not have known before 00:00 UTC on DATE, for example an outcome headlined before its release, a preview written as a completed result, or a date on or after DATE that is not supported.
5. Hindsight and outside knowledge: flag any name, number, event or cause that appears in neither a cited headline nor the card. Flag retrospective wording ("turned out", "later", "subsequently", "eventually", "in hindsight").
6. Narration: flag mentions inside the text of "the feed", "the card", "the brief", "the writer", "our sources".
7. Fix only the findings that are FATAL or MAJOR, with a short Python script that changes only the affected strings in the audited keys: reword to a cautious claim the cited headline supports, or delete the claim. Do not add facts. Keep the JSON structure. You may sample citations, but check every claim that contains a number or a dated event.
8. Run python3 -I tools/verify.py DATE in AUDIT. It must print PASS (warnings are acceptable; report them). Do not run git or spawn agents.

## Final reply
Reply with ONLY this JSON object, and no other text:
{"date": "DATE", "findings": [{"section": "...", "quote": "short exact quote", "problem": "...", "severity": "FATAL|MAJOR|MINOR", "action": "fixed|reworded|deleted|kept (why)"}], "fatal_or_major_remaining": 0, "verify": "PASS or FAIL: one-line summary", "words": 0}
