"""Screen November 2024 own-date feeds after complete prefix/daily acquisition (headline-only, conservative).

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
Canonical publisher-date resolution was NOT performed for November 2024 (see README.md): no item is admitted on a resolved
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

from fetch_news import ROOT, WIN, UTC, PREVIEW, atomic_json, json_bytes


def read_json(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)

DATES = [dt.date(2024, 11, n) for n in range(1, 31) if dt.date(2024, 11, n).weekday() < 5]

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
    ("US payrolls for October (1 Nov 12:30 UTC)","2024-11-04","2024-10-24",r"(?=.*(?:US|U\.S\.|America|payrolls|nonfarm))(?=.*(?:jobs|payrolls|nonfarm|employment|unemployment))(?=.*(?:October|Oct\b|12,000|12000|hurricane))"),
    ("US ISM manufacturing for October (1 Nov 14:00 UTC)","2024-11-04","2024-10-24",r"(?=.*(?:ISM|Institute for Supply Management))(?=.*manufactur)(?=.*(?:October|Oct\b|46\.5))"),
    ("China Caixin manufacturing PMI for October (1 Nov 01:45 UTC)","2024-11-04","2024-10-24",r"(?=.*(?:China|Chinese|Caixin))(?=.*(?:PMI|manufacturing))(?=.*(?:Caixin|private survey))(?=.*(?:October|Oct\b|50\.3))"),
    ("US ISM services for October (5 Nov 15:00 UTC)","2024-11-06","2024-10-29",r"(?=.*(?:ISM|Institute for Supply Management))(?=.*(?:services|non-manufacturing))(?=.*(?:October|Oct\b|56\.0))"),
    ("China Caixin services PMI for October (5 Nov 01:45 UTC)","2024-11-06","2024-10-29",r"(?=.*(?:China|Chinese|Caixin))(?=.*(?:PMI|services))(?=.*(?:Caixin|private survey))(?=.*(?:October|Oct\b|52\.0))"),
    ("RBA decision (5 Nov 03:30 UTC)","2024-11-06","2024-10-29",r"(?=.*(?:RBA|Reserve Bank of Australia))(?=.*(?:holds?|held|keeps?|kept|leaves?|left|cuts?|cut|raises?|unchanged|steady|decision))(?=.*(?:rates?|policy|decision))"),
    ("US presidential election national outcome (called 6 Nov UTC morning)","2024-11-07","2024-10-29",r"(?=.*(?:Trump|Harris|Republican))(?=.*(?:wins?|won|victory|elected|president-elect|defeats? Harris|concedes?|conceded|White House return|Republican sweep|red sweep|Republicans win))"),
    ("Fed FOMC decision (7 Nov 19:00 UTC)","2024-11-08","2024-11-01",r"(?=.*(?:Fed|FOMC|Federal Reserve))(?=.*(?:cuts?|cut|lowers?|lowered|decision|statement|eases?|eased))(?=.*(?:rates?|policy|quarter.point|25 basis|25-basis|FOMC))"),
    ("Bank of England decision (7 Nov 12:00 UTC)","2024-11-08","2024-10-31",r"(?=.*(?:BOE|Bank of England))(?=.*(?:cuts?|cut|lowers?|lowered|decision|eases?|eased))(?=.*(?:rates?|policy|quarter.point|25 basis))"),
    ("NBP/RPP November decision (6 Nov)","2024-11-07","2024-11-01",r"(?=.*(?:NBP|RPP|Polish central bank|Poland central bank|Glapi\w*))(?=.*(?:holds?|held|keeps?|kept|unchanged|bez zmian|utrzyma\w*|decyzj\w*))"),
    ("China trade data for October (7 Nov)","2024-11-08","2024-10-31",r"(?=.*(?:China|Chinese))(?=.*(?:exports|imports|trade surplus|trade data))(?=.*(?:October|Oct\b|12\.7))"),
    ("China NPC fiscal/debt-swap announcement (8 Nov UTC day)","2024-11-11","2024-11-01",r"(?=.*(?:China|Chinese))(?=.*(?:debt.swap|debt swap|debt package|10 trillion|10-trillion|6 trillion|6-trillion|1.4 trillion|fiscal package|stimulus package|NPC))(?=.*(?:approves?|approved|unveils?|unveiled|announces?|announced|reveals?|revealed|passes?|passed|clears?|cleared|10 trillion|6 trillion))"),
    ("China CPI/PPI for October (9 Nov)","2024-11-11","2024-11-01",r"(?=.*(?:China|Chinese))(?=.*(?:CPI|PPI|consumer prices|producer prices|inflation|deflation))(?=.*(?:October|Oct\b|0\.3%|2\.9%))"),
    ("US CPI for October (13 Nov 13:30 UTC)","2024-11-14","2024-11-06",r"(?=.*(?:US|U\.S\.|America|CPI|consumer price))(?=.*(?:CPI|consumer prices|inflation))(?=.*(?:October|Oct\b|2\.6%))"),
    ("US PPI for October (14 Nov 13:30 UTC)","2024-11-15","2024-11-07",r"(?=.*(?:PPI|producer prices|wholesale prices))(?=.*(?:October|Oct\b))"),
    ("US retail sales for October (15 Nov 13:30 UTC)","2024-11-18","2024-11-08",r"(?=.*retail sales)(?=.*(?:October|Oct\b))"),
    ("China activity/property data for October (15 Nov 02:00 UTC)","2024-11-18","2024-11-08",r"(?=.*(?:China|Chinese))(?=.*(?:industrial output|industrial production|retail sales|fixed.asset|urban unemployment|home prices|property investment))(?=.*(?:October|Oct\b))"),
    ("Poland preliminary Q3 GDP (14 Nov)","2024-11-15","2024-11-07",r"(?=.*(?:Poland|Polish|Polsk\w*|GUS|PKB))(?=.*(?:GDP|PKB))(?=.*(?:Q3|third.quarter|trzec\w* kwart|III kwart|2\.7))"),
    ("Japan Q3 GDP (14 Nov 23:50 UTC; valid Nov15)","2024-11-15","2024-11-07",r"(?=.*(?:Japan|Japanese))(?=.*(?:GDP|gross domestic product))(?=.*(?:Q3|third.quarter|July.September))"),
    ("China November loan prime rates (20 Nov 01:00 UTC)","2024-11-21","2024-11-13",r"(?=.*(?:China|Chinese|PBOC))(?=.*(?:loan prime rate|LPR|benchmark lending))(?=.*(?:unchanged|holds?|held|keeps?|kept|steady))"),
    ("Nvidia quarterly results (20 Nov after US close)","2024-11-21","2024-11-13",r"(?=.*Nvidia)(?=.*(?:earnings|results|revenue|sales|profit|guidance|forecast))(?=.*(?:reports?|reported|beats?|beat|misses?|missed|doubles?|doubled|rises?|rose|94%|35\.1 billion|37\.5 billion|fourth.quarter|Q4))"),
    ("Japan national CPI for October (21 Nov 23:30 UTC; valid Nov22)","2024-11-22","2024-11-14",r"(?=.*(?:Japan|Japanese))(?=.*(?:CPI|consumer prices|inflation))(?=.*(?:October|Oct\b))"),
    ("November flash PMIs (22 Nov UTC day)","2024-11-25","2024-11-15",r"(?=.*(?:PMI|purchasing managers))(?=.*flash)(?=.*(?:November|Nov\b))"),
    ("US PCE inflation for October (27 Nov 15:00 UTC)","2024-11-28","2024-11-20",r"(?=.*(?:PCE|personal consumption expenditure|Fed.s (?:preferred|favou?rite) inflation))(?=.*(?:October|Oct\b))"),
    ("US Q3 GDP second estimate (27 Nov 13:30 UTC)","2024-11-28","2024-11-20",r"(?=.*(?:US|U\.S\.|America))(?=.*(?:GDP|gross domestic product))(?=.*(?:second estimate|revised|revision|unchanged|2\.8%))"),
    ("Australia monthly CPI for October (27 Nov 00:30 UTC)","2024-11-28","2024-11-20",r"(?=.*(?:Australia|Australian))(?=.*(?:CPI|inflation|consumer prices))(?=.*(?:October|Oct\b))"),
    ("Poland November flash CPI (29 Nov)","2024-12-02","2024-11-22",r"(?=.*(?:Poland|Polish|Polsk\w*|GUS|inflacj\w*))(?=.*(?:CPI|inflation|consumer prices|inflacj\w*))(?=.*(?:November|Nov\b|listopad\w*))"),
    ("Euro-area November flash inflation (29 Nov)","2024-12-02","2024-11-22",r"(?=.*(?:inflation|HICP|consumer prices|CPI))(?=.*(?:euro zone|eurozone|euro area))(?=.*(?:November|Nov\b))"),
    ("China November official PMI (30 Nov 01:30 UTC)","2024-12-02","2024-11-22",r"(?=.*(?:PMI|purchasing managers))(?=.*(?:China|Chinese))(?=.*(?:November|Nov\b))"),
]


# A modal in a second clause must not disguise a completed first clause.
COMPLETED = re.compile(r"\b(?:announced|unveiled|approved|won|elected|president-elect|conceded|defeated|lowered|held|kept|reported|surged|accelerated|slowed)\b|"
                       r"(?:Trump|Harris|Fed|FOMC|Federal Reserve|BOE|Bank of England|RBA|Reserve Bank of Australia|NBP|RPP|China|Nvidia)"
                       r".{0,35}\b(?:wins|cuts|cut|lowers|holds|keeps|leaves|reports|beats|beat|misses|missed|unveils|approves|announces)\b",re.I)
EXPLICIT_PREVIEW = re.compile(r"\b(?:preview|ahead of|what to expect|set to report|earnings calendar)\b|"
                              r"\b(?:expected|forecast|likely|seen|set|poised|due) to (?:win|cut|hold|keep|report|beat|announce|unveil|release)\b|"
                              r"\b(?:will|could|would|may|might) (?:win|cut|hold|keep|report|beat|announce|unveil|release)\b",re.I)

def guard_hit(title, published, stamp):
    """Conservatively reject pre-release outcomes; mixed outcome/forecast headlines fail closed."""
    normalised = NEUTRALISE.sub("", title)
    for label, eligible, start, pattern in RELEASE_GUARDS:
        if stamp < eligible and start <= published < stamp and re.search(pattern, title, re.I):
            if EXPLICIT_PREVIEW.search(normalised):
                return None
            if COMPLETED.search(normalised):
                return label
            if PREVIEW.search(normalised) or FORWARD.search(normalised):
                return None
            return label
    return None


def screen(date, raw=None, persist=True):
    stamp = date.isoformat()
    cutoff = dt.datetime.combine(date, dt.time(), UTC)
    if raw is None:raw = read_json(ROOT / "work" / "unreviewed_feeds" / (stamp + ".json.gz"))
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
               "canonical_screening": ("Not performed for November 2024: no canonical publisher-date resolution. "
                                       "RSS pubDate is used with release-timing guards; no article body is read."),
               "release_guards_version": "nov-2024-release-guards-v1"}
    target = ROOT / "feeds" / (stamp + ".json.gz")
    if persist:atomic_json(target, payload, True)
    receipt = {"date": stamp, "status": "ready", "input_items": len(raw["items"]), "ready_items": len(ready),
               "excluded_items": len(excluded), "excluded_by_guard": dict(Counter(x["guard"] for x in excluded)),
               "excluded": excluded, "ready_path": str(target.relative_to(ROOT)),
               "ready_sha256": hashlib.sha256(json_bytes(payload,True)).hexdigest(),
               "unreviewed_sha256": hashlib.sha256(json_bytes(raw,True)).hexdigest()}
    if persist:atomic_json(ROOT / "audit" / ("news_ready_" + stamp + ".json"), receipt)
    else:receipt["_payload"]=payload
    return receipt


def main():
    for date in DATES:
        r = screen(date)
        print(r["date"], "ready", r["ready_items"], "excluded", r["excluded_items"], dict(r["excluded_by_guard"]), flush=True)


if __name__ == "__main__":
    main()
