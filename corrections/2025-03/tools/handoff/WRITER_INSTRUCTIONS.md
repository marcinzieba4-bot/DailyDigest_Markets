# Writer instructions: March 2025 retrospective edition

Your task message gives you DATE (the report date; the information cutoff is 00:00 UTC on that date) and SANDBOX (an absolute folder). Work only inside SANDBOX. Do not list, read or search any other folder under the scratchpad or the repository.

## What is in SANDBOX
- BRIEF.md: the complete writing brief. Read all of it before writing. Ignore its workspace paths; SANDBOX is your folder.
- reference/retail_voice_A_stock_lead.txt and reference/retail_voice_B_macro_lead.txt: voice and depth reference only. Read once; carry over no facts, numbers, names or phrases.
- feeds/DATE.json.gz: your only news source. Publication-timestamped headlines, all strictly before the cutoff.
- cards/DATE.json: your only market data. Completed closes and the Treasury curve before the cutoff.
- tools/: digest.py, showcard.py, verify.py, render.py. Run them from SANDBOX, for example: cd SANDBOX && python3 -I tools/digest.py DATE --topic retail --max 200

## Absolute rules
1. Sources are the feed headlines (cite them as [[nXXXX]] ids) and the card, and nothing else. No web access, no git, no installs. Do not edit feeds/, cards/ or tools/. No other date's data exists in your sandbox; do not look for it. Do not spawn further agents.
2. No hindsight. You may know much about 2025 and 2026 from training. None of it may enter the edition: no later outcome, price, data print, decision, tariff result, court ruling or "what happened next", and no retrospective phrasing. If you notice yourself knowing how something turned out, drop it. Choose stances, the lead trade and the stories only from what the feed and card show on DATE.
3. No narration. Never mention the feed, the card, the brief, the writer or the sources inside the report text (see the BRIEF voice section).
4. Numbers: every number in the text must come from the card or from a headline cited in the same paragraph. verify.py enforces this.
5. Write two files:
   a) specs/DATE.json: valid JSON with the exact structure in the BRIEF "Output" section.
   b) notes/DATE.json: your retail selection record, valid JSON with keys: "date", "lead" (Name / TICKER - the hook), "smaller" (three titles), "why_lead" (2-3 sentences from this date's evidence only), "why_smaller" (one sentence each), "evidence_ids" (the nXXXX ids you relied on), "considered_not_chosen" (hot topics you passed over and why, from this date's evidence only).
6. Procedure: read the BRIEF; run showcard; run digest for every topic and for --topic retail --max 200; use --grep for earnings reactions, Polish items, Stocktwits and pending events; decide stances, the lead trade and the main stories BEFORE writing; write the spec; run "python3 -I tools/verify.py DATE" and fix EVERY FAIL and review every WARN until it reports PASS; run "python3 -I tools/render.py DATE", which must render cleanly. Then check the BRIEF's final checklist: no narration, no unsupported fact, no post-cutoff content, Playbooks consistent, roughly 9,500 to 11,000 words, at least 50 distinct cited headlines, no citation reused more than four times.
7. Your final reply must be ONLY this JSON object, with no other text:
   {"date": "DATE", "verify": "PASS or FAIL: one-line summary", "words": 0, "cited_headlines": 0, "stances": "US ..., EU ..., CN ..., JP ..., AU ..., PL ...", "lead": "...", "smaller": "...; ...; ...", "notes_written": true, "open_issues": "..."}
