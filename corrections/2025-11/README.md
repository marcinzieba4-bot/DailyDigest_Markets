# November 2025 — retrospective briefings for the 20 weekdays (2025-11-03 … 2025-11-28) — IN PROGRESS: 2 of 20 written

Same pipeline as `corrections/2025-12` and `corrections/2026-02` (information cutoff 00:00 UTC on each report date, Google News
feeds bounded by date, Yahoo / US Treasury cards, pages in the August 2026 layout). Stopped by the owner on 2026-10-28 because of
cost (see "Cost"); nothing from this folder is on S3 yet.

## Status
| Piece | State |
|---|---|
| `tools/` (fetch, cards, digest, showcard, verify, render, summary, upload) | done, tested |
| `BRIEF.md` (writers) and `CRITIC.md` (reviewers) | done; block sizes taken from the 31 August 2026 pages |
| `data/`, `cards/` (20 cards, 292 instruments) | done — **see Known issues 1 (split-adjusted levels)** |
| `feeds/*.json.gz` (20 dates, ~8,000 headlines each, 0 failed queries, 0 items at/after a cutoff) | done |
| `specs/` + `html/` + `json/` | **2025-11-04 and 2025-11-06 written** (verify PASS, 0 fail / 0 warn, hindsight tripwire clean) |
| the other 18 dates | **not written**: 11-03, 05, 07, 10, 11, 12, 13, 14, 17, 18, 19, 20, 21, 24, 25, 26, 27, 28 |
| critic pass (`CRITIC.md`) | not run on any date |
| upload to S3 + CloudFront invalidation | **not done** — see Known issues 2 |

The two written pages: 11-04 = 9,946 words / 402 cited headlines; 11-06 = 10,407 words / 421 (August median 10,132). Lead retail
trades: 11-04 bitcoin miners as AI landlords (IREN, CIFR; smaller: Palantir, bitcoin dip-buying, quantum), 11-06 Palantir
"Burry is wrong, buy the dip" (smaller: IREN / Cipher, Bitcoin / IBIT, IonQ). Neither has had an independent review.

## Resume (cheap path)
```
cd /home/user/DailyDigest_Markets/corrections/2025-11
python3 -I tools/showcard.py <date>                       # market card as a table (~9k tokens)
python3 -I tools/digest.py <date> --max 40                # smaller digest than the default (default is ~65k tokens)
python3 -I tools/digest.py <date> --topic retail --max 80
python3 -I tools/digest.py <date> --grep "regex" --max 60
python3 -I tools/verify.py <date>                          # 0 FAIL required
python3 -I tools/render.py <date>                          # writes html/<date>.html and json/<date>_Market_Intelligence.json
python3 -I tools/summary.py                                # all written dates vs the August medians
python3 posthoc/tripwire.py                                # hindsight tripwire (keep it away from writers)
```
Writer prompt that worked (one date per agent; scratch only in `work/w<YYYYMMDD>/`, which is git-ignored): "Read BRIEF.md
completely, then write specs/<date>.json from feeds/<date>.json.gz (via tools/digest.py) and cards/<date>.json (via
tools/showcard.py) only; verify.py 0 FAIL, render.py clean; re-read the retail section against reference/retail_voice_*.txt;
no git, no web; reply with a 3-5 line note." Critic prompt: "Read CRITIC.md and BRIEF.md, review specs/<date>.json, repair in
place, re-run verify and render."

## Cost (why it was stopped)
Each Opus writer took about 40 minutes and 100–116 tool calls and used **690,400 and 758,141 tokens** (the two finished
writers). Most of it is reading: the default digest is ~1,800 lines (~65k tokens), plus dozens of greps and verify iterations that
re-read context. Twenty writers plus twenty critics at that rate is on the order of 15–25 million tokens. Ways to make the rest
much cheaper: a smaller model for writers; `digest.py --max 40` instead of the default caps; two or three dates per session
instead of a parallel fan-out; critics only where verify or the tripwire shows something (the two finished pages needed none).

## Known issues
1. **Split-adjusted price levels in the cards.** Yahoo returns split-adjusted history, so the card's `close` and `ref_20s_close`
   are not what traded in November 2025 for: NFLX (card 110.01; traded ~1,100 before its 10-for-1 split), NOW, TQQQ, ETHA, CRWD,
   KLAC, CVNA, CMCSA, BYND (reverse split, level scaled up) and the XLK / XLY / XLE / XLB / XLU sector ETFs, possibly more.
   **Percentage changes are unaffected.** Until fixed, write only percentages for those names (the 11-04 writer did) and never
   quote a level or a 20-session reference level for them. Fix: in `fetch_market.py` request `events=div,splits`, multiply each
   close by the product of the split ratios dated after it, rebuild the cards (`build_cards.py`); spin-off adjustments (CMCSA)
   are not in the split events, so drop its level. The December and February cards probably carry the same problem for
   ETFs/stocks that split after those dates.
2. **AWS credentials.** In the cloud session `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` are 14-character proxy placeholders
   that AWS rejects (`InvalidAccessKeyId`); earlier sessions published with the real key stored as `AWS_Key` / `AWS_Pass` in the
   environment settings (not set in the 2026-10-28 session). `tools/upload.py` maps those two names itself and runs a pre-flight
   (STS + HeadBucket) that stops before any write. Set them in the environment settings (never paste a key into chat), start
   a new session, then: `python3 corrections/2025-11/tools/upload.py 2025-11-04 2025-11-06` (dry run), add `--go` to publish.
   It backs up anything it overwrites to `reports/_retrospective_backup/november-weekdays/<stamp>/`, adds the index rows,
   leaves `reports/latest.html` alone, and invalidates only the written paths on CloudFront. `--no-aws` builds the HTML, JSON and
   PDFs in memory without touching AWS (tested).
3. `CLAUDE.md` on the report-scope branch contains a Telegram bot token in plain text — worth rotating.

## What changed against the December set (and why)
Measured on the 31 August 2026 pages (median 10,132 words; Retail 1,232): the December pages averaged ~18 mentions of "the feed",
~19 of "the writer" and ~3 "not a reported fact" disclaimers per report (August: ~3, 0, 0), a thin Social Signal, Poland ~400
words (August ~1,000, eight parts) and Flows / Geo shorter than August. So: `BRIEF.md` forbids narration about the inputs and
invented social evidence, gives August block sizes (Poland seven parts ~850–1,050, China ~800–950, Flows 600–750), spells out
how to choose and write the retail lead, and `verify.py` fails narration, caps "the feed", requires ≥ 8,500 words and the
Poland structure; the news harvest has 440 queries per date (61 on retail attention) instead of 217; the cards carry ~290
instruments including the names retail was trading.

## Layout
`BRIEF.md`, `CRITIC.md` · `reference/` (two August 2026 retail sections as voice references) · `tools/` · `data/` (Yahoo closes and
the Treasury par curve, stopped at the 2025-11-28 close) · `cards/<date>.json` · `feeds/<date>.json.gz` · `specs/<date>.json` ·
`html/<date>.html`, `json/<date>_Market_Intelligence.json` · `posthoc/` (not for writers) · `work/` (git-ignored scratch).
