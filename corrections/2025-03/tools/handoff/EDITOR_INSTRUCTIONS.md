# Retail chronology editor: March 2025 edition

Your task message gives DATE (report date, cutoff 00:00 UTC) and EDIT (absolute folder, your sandbox). First run this setup exactly, once:
  mkdir -p EDIT && cp -r SANDBOX/. EDIT/ && python3 SCRATCH/make_earlier.py DATE EDIT/earlier/retail_before.json
(SANDBOX, SCRATCH and DATE are given in your task message. Use the EDIT copy for everything below.)

## What is in EDIT
- specs/DATE.json: the writer's draft edition. You may change ONLY the keys "retail_intro" and "retail".
- notes/DATE.json: the writer's retail selection record. Update it to match any change.
- earlier/retail_before.json: the final retail sections and selection records of STRICTLY EARLIER March 2025 editions. There is nothing later in your folder.
- feeds/DATE.json.gz: this edition's news, the only evidence you may use. Cite only ids present in it.
- cards/DATE.json: this edition's market card.
- BRIEF.md (see "Chronological retail selection" and "What Retail Is Playing") and tools/ (digest.py, showcard.py, verify.py, render.py).

## The task
Chronological editorial review of the What Retail Is Playing section. Nobody should repeat an earlier edition's angle without a changed story. A persistent theme may remain when its catalyst, reaction or attention changed. A changed price alone does not justify a full repeat essay.
1. Shortlist candidates from THIS day's evidence: concrete catalysts and actual attention evidence (retail, Stocktwits, Reddit, brokerage flows, most-active lists, options activity). Include reversals and failed narratives, not only strong performers.
2. Compare each candidate with its appearances in earlier/retail_before.json, in date order. For any repeat, state what changed: a result, a product or customer event, a regulatory development, a reversal, or a dated attention observation in THIS feed. A new subtitle, a new price or a new wrapper is not a new story.
3. The lead: keep the draft lead only if it is still the best-supported lead today AND it is new since earlier leads, or today's new evidence warrants a repeat. Otherwise replace it with the best-supported distinct narrative from today's evidence. An unchanged theme may remain only as a shortened carryover among the smaller trades, never as a full lead essay again.
4. The three smaller trades must be three distinct narratives. Do not reuse an earlier smaller trade unless its story changed.
5. Keep the BRIEF structure: lead = six parts in the BRIEF order, about 650 to 850 words in total; each smaller trade = two parts, about 150 to 220 words (a shortened carryover may be shorter, but verify.py must still pass). Title format "Name / TICKER - the hook".
6. Evidence and numbers: every number must come from this card or a headline cited in the same paragraph; no hindsight; no event after the cutoff; no invented social posts, counts or flows.
7. Edit with a short Python script: load specs/DATE.json, replace only "retail_intro" and "retail", and write it back with ensure_ascii=False and indent=2. Update notes/DATE.json the same way (lead, smaller, why_lead, why_smaller, evidence_ids, considered_not_chosen). If nothing needs to change, change nothing.
8. Run: cd EDIT && python3 -I tools/verify.py DATE. Fix every FAIL until it reports PASS. Then run python3 -I tools/render.py DATE, which must render cleanly.
9. Do not run git, do not browse, do not spawn agents, do not read any file outside EDIT.

## Final reply
Reply with ONLY this JSON object, and no other text:
{"date": "DATE", "changed": true, "lead_before": "...", "lead_after": "...", "smaller_before": "...; ...; ...", "smaller_after": "...; ...; ...", "change_reason": "one or two sentences naming the evidence that justified each change, or why nothing changed", "verify": "PASS or FAIL: one-line summary"}
