"""Screen March 2025 own-date feeds after complete prefix/daily acquisition (headline-only, conservative).

Input : work/unreviewed_feeds/<date>.json.gz from expand_capped_news.py. Every item's RSS pubDate is strictly
        before the report date's 00:00 UTC cutoff and inside its 7 / 14 / 35-day category window, and no query
        window failed.
Screens applied to every item of every own-date feed:
  1. Release-timing guard. A headline that reports the OUTCOME of a scheduled release, policy decision or tariff
     action is excluded from any edition whose 00:00 UTC cutoff precedes that release, because at that cutoff the
     outcome did not exist (the RSS date is then early or the headline is misdated). Previews and forecasts pass.
     The eligible date is the first weekday edition whose cutoff follows the release; where a release time is
     uncertain the eligible date is set late, which is the conservative direction.
  2. Cutoff and category-window assertions.
Canonical publisher-date resolution was NOT performed for March (see README.md): no item is admitted on a resolved
canonical date, and nothing here reads article bodies.

Output: feeds/<date>.json.gz (the writers' only news input) and audit/news_ready_<date>.json (receipt listing every
excluded item with its guard, for the independent audit).
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import re
from collections import Counter

from fetch_news import ROOT, WIN, UTC, PREVIEW, atomic_json


def read_json(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)

DATES = [dt.date(2025, 3, n) for n in range(1, 32) if dt.date(2025, 3, n).weekday() < 5]

# Forward-looking language: a headline with it describes something pending, not a completed outcome.
FORWARD = re.compile(
    r"(?:\bexpect(?:ed|s)?\b|\bforecasts?\b|\bforecasting\b|\bwill\b|\bwould\b|\bcould\b|\bmay\b|\bmight\b|"
    r"\bset to\b|\bdue\b|\bpoised\b|\blikely\b|\bseen\b|\bconsensus\b|\bestimates?\b|\bpreview\b|\bahead\b|"
    r"\bawait\w*\b|\bto (?:unveil|announce|impose|set|sign|cut|raise|hold|keep|release|publish|report|decide|"
    r"review|meet|be)\b|\bplans? to\b|\bweighs?\b|\bcalendar\b|\bthis week\b|\bnext week\b|"
    r"\bon (?:monday|tuesday|wednesday|thursday|friday)\b|\bdue (?:on|out)\b|\bprognoz|\boczekuj|\boczekiw|"
    r"\bspodziew|\bzapowied|\bszacuj)",
    re.I,
)
NEUTRALISE = re.compile(
    r"\b(?:better|worse|more|less|higher|lower|stronger|weaker|faster|slower|above|below|in line)\s+than\s+"
    r"(?:expected|forecast|estimates?|predicted|anticipated)\b|\bas\s+(?:expected|forecast|anticipated)\b",
    re.I,
)

# (label, eligible edition date, earliest publication date checked, outcome pattern)
RELEASE_GUARDS = [
    ("US ISM manufacturing (Feb; 3 Mar 15:00 UTC)", "2025-03-04", "2025-02-24",
     r"(?=.*(?:ISM|Institute for Supply Management))(?=.*(?:February|Feb\b))"),
    ("US JOLTS (Jan; 4 Mar 15:00 UTC)", "2025-03-05", "2025-02-25",
     r"(?=.*(?:JOLTS|job openings))(?=.*(?:January|Jan\b))"),
    ("US ADP (Feb; 5 Mar)", "2025-03-06", "2025-02-25",
     r"(?=.*\bADP\b)(?=.*(?:February|Feb\b|private payrolls|private-sector))"),
    ("US ISM services (Feb; 5 Mar 15:00 UTC)", "2025-03-06", "2025-02-25",
     r"(?=.*(?:ISM|Institute for Supply Management))(?=.*(?:services|non-manufacturing))(?=.*(?:February|Feb\b))"),
    ("ECB rate decision (6 Mar 12:15 UTC)", "2025-03-07", "2025-02-25",
     r"(?=.*(?:ECB|European Central Bank))(?=.*(?:cuts?|cut|holds?|held|keeps?|kept|leaves?|left|lowers?|lowered|"
     r"unchanged|on hold|decision|decided))"),
    ("US payrolls (Feb; 7 Mar 13:30 UTC)", "2025-03-10", "2025-03-01",
     r"(?=.*(?:payrolls|nonfarm|jobs report|employment report|jobs data|unemployment rate|jobs added|jobs lost))"
     r"(?=.*(?:February|Feb\b|Friday))"),
    ("China trade data (Jan-Feb; 7 Mar)", "2025-03-10", "2025-03-01",
     r"(?=.*(?:China|Chinese))(?=.*(?:exports|imports|trade surplus|trade data|trade deficit))"
     r"(?=.*(?:February|Feb\b|January-February|first two months))"),
    ("China CPI and PPI (Feb; 9 Mar 01:30 UTC)", "2025-03-10", "2025-03-01",
     r"(?=.*(?:China|Chinese))(?=.*(?:CPI|PPI|consumer prices|producer prices|inflation|deflation))"
     r"(?=.*(?:February|Feb\b|January-February))"),
    ("US CPI (Feb; 12 Mar 13:30 UTC)", "2025-03-13", "2025-03-05",
     r"(?=.*(?:CPI|consumer prices|inflation))(?=.*(?:February|Feb\b))"),
    ("US PPI (Feb; 13 Mar 13:30 UTC)", "2025-03-14", "2025-03-06",
     r"(?=.*(?:PPI|producer prices|wholesale prices))(?=.*(?:February|Feb\b))"),
    ("US retail sales (Feb; 14 Mar 13:30 UTC)", "2025-03-17", "2025-03-07",
     r"(?=.*retail sales)(?=.*(?:February|Feb\b))"),
    ("China activity data (Jan-Feb; 17 Mar 02:00 UTC)", "2025-03-18", "2025-03-10",
     r"(?=.*(?:China|Chinese))(?=.*(?:industrial output|industrial production|retail sales|fixed-asset|"
     r"fixed asset|urban unemployment|home prices|property investment))"
     r"(?=.*(?:February|Feb\b|January-February|first two months))"),
    ("RBA rate decision (18 Mar 03:30 UTC)", "2025-03-19", "2025-03-10",
     r"(?=.*(?:RBA|Reserve Bank of Australia))(?=.*(?:holds?|held|keeps?|kept|leaves?|left|cuts?|cut|raises?|"
     r"raised|unchanged|steady|on hold|decision|decided))"),
    ("FOMC decision (19 Mar 18:00 UTC)", "2025-03-20", "2025-03-12",
     r"(?=.*(?:Fed|FOMC|Federal Reserve))(?=.*(?:holds?|held|keeps?|kept|leaves?|left|cuts?|cut|unchanged|steady|"
     r"on hold|dot plot|projections|statement))(?=.*(?:rates?|policy|decision|FOMC))"),
    ("BOJ policy decision (19 Mar)", "2025-03-20", "2025-03-12",
     r"(?=.*(?:BOJ|Bank of Japan))(?=.*(?:holds?|held|keeps?|kept|maintains?|maintained|leaves?|left|raises?|"
     r"raised|decision|unchanged|policy rate))"),
    ("China loan prime rate (20 Mar 01:00 UTC)", "2025-03-21", "2025-03-12",
     r"(?=.*(?:loan prime rate|LPR))(?=.*(?:unchanged|holds?|held|keeps?|kept|cuts?|cut|lowers?|lowered))"),
    ("Japan national CPI (Feb; 20 Mar 23:30 UTC)", "2025-03-21", "2025-03-14",
     r"(?=.*(?:Japan|Japanese|Tokyo))(?=.*(?:CPI|consumer prices|inflation))(?=.*(?:February|Feb\b))"),
    ("Flash PMIs (March; 21 Mar)", "2025-03-24", "2025-03-14",
     r"(?=.*(?:PMI|purchasing managers))(?=.*flash)(?=.*(?:March|Mar\b))"),
    ("US GDP third estimate (Q4; 27 Mar 13:30 UTC)", "2025-03-28", "2025-03-20",
     r"(?=.*(?:GDP|gross domestic product))(?=.*(?:fourth.quarter|Q4|final estimate|third estimate|revised))"),
    ("US PCE inflation (Feb; 28 Mar 13:30 UTC)", "2025-03-31", "2025-03-21",
     r"(?=.*(?:PCE|personal consumption expenditure|core inflation))(?=.*(?:February|Feb\b))"),
    ("Euro-area and German flash inflation (March; 31 Mar)", "2025-04-01", "2025-03-25",
     r"(?=.*(?:inflation|HICP|consumer prices|CPI))(?=.*(?:euro zone|eurozone|euro area|Germany|German|France|"
     r"French|Spain|Spanish|Italy|Italian))(?=.*(?:March|Mar\b|flash))"),
    ("China official PMI (March; 31 Mar 01:30 UTC)", "2025-04-01", "2025-03-25",
     r"(?=.*(?:PMI|purchasing managers))(?=.*(?:China|Chinese))(?=.*(?:March|Mar\b))"),
    ("Poland NBP rate decision (Mar; 5 Mar, uncertain time)", "2025-03-07", "2025-02-25",
     r"(?=.*(?:NBP|RPP|Polish central bank|Poland central bank|Glapi\w*))"
     r"(?=.*(?:holds?|held|keeps?|kept|cuts?|cut|unchanged|bez zmian|utrzyma\w*|obni\w*))"),
    ("Poland CPI final (Feb; mid-March)", "2025-03-17", "2025-03-07",
     r"(?=.*(?:Poland|Polish|Polsk\w*|GUS|inflacj\w*))(?=.*(?:CPI|inflation|consumer prices|inflacj\w*))"
     r"(?=.*(?:February|Feb\b|lutego|lutym))"),
    ("Poland wages, industry and retail (Feb; 19-24 Mar)", "2025-03-25", "2025-03-14",
     r"(?=.*(?:Poland|Polish|Polsk\w*|GUS))(?=.*(?:wages|salaries|employment|industrial|industry|retail sales|"
     r"wynagrodz\w*|zatrudn\w*|produkcj\w*|sprzeda\w*))(?=.*(?:February|Feb\b|lutego|lutym))"),
    ("US auto tariffs proclamation (26 Mar)", "2025-03-27", "2025-03-18",
     r"(?=.*tariff)(?=.*(?:auto|autos|car|cars|vehicle|vehicles))"
     r"(?=.*(?:25%|25 percent|imposes?|imposed|announces?|announced|signs?|signed|proclamation|effective))"),
    ("US reciprocal tariffs announcement (2 Apr)", "2025-04-01", "2025-03-20",
     r"(?=.*(?:reciprocal tariff|Liberation Day))(?=.*(?:unveil\w*|announce\w*|announced|imposes?|imposed|sets?|set|"
     r"baseline|34%|10%))"),
]


def guard_hit(title, published, stamp):
    """Return the guard label when this headline is an early outcome for the edition dated `stamp`."""
    normalised = NEUTRALISE.sub("", title)
    preview = bool(PREVIEW.search(normalised) or FORWARD.search(normalised))
    for label, eligible, start, pattern in RELEASE_GUARDS:
        if stamp < eligible and start <= published < stamp and re.search(pattern, title, re.I):
            if preview:
                return None
            return label
    return None


def screen(date):
    stamp = date.isoformat()
    cutoff = dt.datetime.combine(date, dt.time(), UTC)
    raw = read_json(ROOT / "work" / "unreviewed_feeds" / (stamp + ".json.gz"))
    assert raw["date"] == stamp and dt.datetime.fromisoformat(raw["cutoff_utc"]) == cutoff
    assert raw["query_upper_bound_enforced"] and not raw["fails"], "harvest incomplete for " + stamp
    ready, excluded = [], []
    for item in raw["items"]:
        pub = dt.datetime.fromisoformat(item["published_at"])
        assert cutoff - dt.timedelta(days=WIN[item["cat"]]) <= pub < cutoff, item["id"]
        label = guard_hit(item["title"], pub.date().isoformat(), stamp)
        if label:
            excluded.append({"id": item["id"], "published_at": item["published_at"], "src": item["src"],
                             "title": item["title"], "guard": label})
            continue
        ready.append(item)
    payload = {**raw, "items": ready,
               "canonical_screening": ("Not performed for March 2025: no canonical publisher-date resolution. "
                                       "RSS pubDate is used with release-timing guards; no article body is read."),
               "release_guards_version": "mar-2025-release-guards-v1"}
    target = ROOT / "feeds" / (stamp + ".json.gz")
    atomic_json(target, payload, True)
    receipt = {"date": stamp, "status": "ready", "input_items": len(raw["items"]), "ready_items": len(ready),
               "excluded_items": len(excluded), "excluded_by_guard": dict(Counter(x["guard"] for x in excluded)),
               "excluded": excluded, "ready_path": str(target.relative_to(ROOT)),
               "ready_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
               "unreviewed_sha256": hashlib.sha256((ROOT / "work" / "unreviewed_feeds" / (stamp + ".json.gz")).read_bytes()).hexdigest()}
    atomic_json(ROOT / "audit" / ("news_ready_" + stamp + ".json"), receipt)
    return receipt


def main():
    for date in DATES:
        r = screen(date)
        print(r["date"], "ready", r["ready_items"], "excluded", r["excluded_items"], dict(r["excluded_by_guard"]), flush=True)


if __name__ == "__main__":
    main()
