# posthoc — NOT for the writers

`tripwire.py` lists major November 2025 events with the first report date on which each may appear, and scans the written
specs for outcome wording that shows up earlier (a candidate hindsight leak). It encodes what happened *after* each cutoff, so
**no writer or critic may read this folder** (the brief only allows `BRIEF.md`, `CRITIC.md`, `tools/` and `reference/`).
Run it yourself after writing: `python3 posthoc/tripwire.py [dates]`; review every hit by hand against that date's feed
(hits can be false positives: a conditional preview, or "Meta" matching inside "metal").
