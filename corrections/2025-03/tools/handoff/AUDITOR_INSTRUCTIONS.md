# Independent cutoff and fact audit: March 2025 edition

Your task message gives DATE and AUDIT (absolute folder: a fresh copy of the edition with its final spec). Work only inside AUDIT. You are an auditor, not the writer: you did not write this edition and must check it against its sources, not against your own memory.

## Inputs in AUDIT
- specs/DATE.json: the edition's final text (retail_intro and retail are the chronologically edited retail section).
- feeds/DATE.json.gz: the ONLY news source. Read it fully with python3 -I tools/digest.py DATE --max 400 for each topic, and with --grep for specific names. Each item's published_at is strictly before the 00:00 UTC cutoff.
- cards/DATE.json: the ONLY market data. Read with python3 -I tools/showcard.py DATE.
- BRIEF.md: the rules you audit against.
- tools/verify.py: run it first and note its output.

## What to check, claim by claim
1. Citations: every [[nXXXX]] must exist in the feed and must actually support the sentence it sits in (company, role, direction, number, date, outlet). Flag wrong attribution, overstatement, or a headline that does not say what the text says.
2. Cutoff: every event, print, decision, outcome, price or schedule the text states must be knowable from headlines published before the cutoff. Flag: an outcome of a release or decision that had not happened by the cutoff; a preview written as a completed result; a calendar claim with no supporting preview headline; any mention of a later price, decision or event.
3. Hindsight and outside knowledge: any name, date, number, event or causal claim that appears in neither a cited headline nor the card is UNSOURCED. General economic mechanisms are allowed; concrete facts are not. Flag retrospective wording ("turned out", "later", "subsequently", "in hindsight", "would go on to", "eventually").
4. Numbers: each figure must match the card (the exact value and the session date printed in the tag), or be in a headline cited in the same paragraph. Direction words must match the sign. Yields and spreads in basis points. Source tags must match the card's session dates.
5. Retail section: attention claims must rest on cited headlines. Flag invented posts, replies, counts, inflows or rankings. Flag any claim that a retail ranking was measured.
6. Narration: flag any mention inside the text of "the feed", "the card", "the brief", "the writer", "our sources", "not a reported fact", or similar.
7. Consistency: Playbooks must agree with stances and with each other; no sentence should contradict another.

## Then fix
For each FATAL or MAJOR finding, edit specs/DATE.json with a short Python script that changes only the affected string: reword an unsupported claim into a cautious statement the cited headlines support, or delete it. Keep JSON structure, labels, block counts and citation markers. Do not add new facts. Then run python3 -I tools/verify.py DATE until it reports PASS, and run python3 -I tools/render.py DATE. Minor findings may be fixed if trivial.

## Final reply
Reply with ONLY this JSON object, and no other text:
{"date": "DATE", "findings": [{"section": "...", "quote": "short exact quote", "problem": "...", "severity": "FATAL|MAJOR|MINOR", "action": "fixed|reworded|deleted|kept (why)"}], "fatal_or_major_remaining": 0, "verify": "PASS or FAIL: one-line summary", "words": 0}
