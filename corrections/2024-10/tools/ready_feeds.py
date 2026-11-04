"""Screen October 2024 own-date feeds after complete prefix/daily acquisition (headline-only, conservative).

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
Canonical publisher-date resolution was NOT performed for October 2024 (see README.md): no item is admitted on a resolved
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

DATES = [dt.date(2024, 10, n) for n in range(1, 32) if dt.date(2024, 10, n).weekday() < 5]

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
    ("US ISM manufacturing September (1 Oct 14:00 UTC)","2024-10-02","2024-09-24",r"(?=.*(?:ISM|Institute for Supply Management))(?=.*manufactur)(?=.*(?:September|Sept?\b))"),
    ("US JOLTS August (1 Oct 14:00 UTC)","2024-10-02","2024-09-24",r"(?=.*(?:JOLTS|job openings))(?=.*(?:August|Aug\b))"),
    ("Euro-area September flash inflation (1 Oct 09:00 UTC)","2024-10-02","2024-09-24",r"(?=.*(?:eurozone|euro.zone|euro.area))(?=.*(?:CPI|HICP|inflation|consumer prices))(?=.*(?:September|Sept?\b))"),
    ("US dockworkers strike begins (1 Oct 04:01 UTC)","2024-10-02","2024-09-24",r"(?=.*(?:ports?|dockworkers?|longshoremen))(?=.*(?:strike begins|strike starts|go on strike|walk out|walkout begins|strike shuts|strike halts))"),
    ("China October NDRC stimulus briefing (8 Oct UTC morning)","2024-10-09","2024-10-01",r"(?=.*(?:China|Chinese|NDRC))(?=.*(?:briefing|stimulus|economic planner|development and reform))(?=.*(?:disappoint|underwhelm|no new|little new|falls short|lack of|failed to|unveils?|announces?|pledges?))"),
    ("NBP/RPP October decision (2 Oct UTC day)","2024-10-03","2024-09-25",r"(?=.*(?:NBP|RPP|Polish central bank|Poland central bank|Glapi\w*))(?=.*(?:holds?|held|keeps?|kept|unchanged|bez zmian|utrzyma\w*|decyzj\w*))"),
    ("US ADP September employment (2 Oct 12:15 UTC)","2024-10-03","2024-09-25",r"(?=.*ADP)(?=.*(?:September|Sept?\b|private payroll|private employment))"),
    ("US ISM services September (3 Oct 14:00 UTC)","2024-10-04","2024-09-26",r"(?=.*(?:ISM|Institute for Supply Management))(?=.*(?:services|non.manufacturing))(?=.*(?:September|Sept?\b))"),
    ("US payrolls September (4 Oct 12:30 UTC)","2024-10-07","2024-09-27",r"(?=.*(?:US|U\.S\.|America|payroll|nonfarm))(?=.*(?:jobs|payroll|nonfarm|employment|unemployment))(?=.*(?:September|Sept?\b))"),
    ("RBNZ October decision (9 Oct 01:00 UTC)","2024-10-10","2024-10-02",r"(?=.*(?:RBNZ|Reserve Bank of New Zealand|New Zealand central bank))(?=.*(?:cuts?|cut|lowers?|lowered|holds?|held|keeps?|kept|decision|unchanged))(?=.*(?:rate|policy|decision))"),
    ("Fed September meeting minutes (9 Oct 18:00 UTC)","2024-10-10","2024-10-02",r"(?=.*(?:Fed|FOMC|Federal Reserve))(?=.*minutes)(?=.*(?:September|Sept?\b|divided|debated|officials favored|officials favoured))"),
    ("US CPI September (10 Oct 12:30 UTC)","2024-10-11","2024-10-03",r"(?=.*(?:US|U\.S\.|America|CPI|consumer price))(?=.*(?:CPI|consumer prices|inflation))(?=.*(?:September|Sept?\b))"),
    ("US PPI September (11 Oct 12:30 UTC)","2024-10-14","2024-10-04",r"(?=.*(?:US|U\.S\.|PPI|producer prices|wholesale prices))(?=.*(?:PPI|producer prices|wholesale prices))(?=.*(?:September|Sept?\b))"),
    ("China MOF fiscal briefing (12 Oct 02:00 UTC)","2024-10-14","2024-10-05",r"(?=.*(?:China|Chinese|Lan Fo|finance minist|MOF))(?=.*(?:fiscal|debt|stimulus|property|briefing))(?=.*(?:briefing|vows?|pledges?|unveils?|announces?|lukewarm|disappoint|details|debt ceiling|local government))"),
    ("China September CPI/PPI (13 Oct 01:30 UTC)","2024-10-14","2024-10-06",r"(?=.*(?:China|Chinese))(?=.*(?:CPI|PPI|consumer prices|producer prices|inflation|deflation))(?=.*(?:September|Sept?\b))"),
    ("China September trade (14 Oct UTC day)","2024-10-15","2024-10-07",r"(?=.*(?:China|Chinese))(?=.*(?:exports|imports|trade surplus|trade data))(?=.*(?:September|Sept?\b))"),
    ("China September credit (14 Oct UTC day; conservative)","2024-10-15","2024-10-07",r"(?=.*(?:China|Chinese|PBOC))(?=.*(?:new loans|bank lending|credit data|total social financing|money supply|M2))(?=.*(?:September|Sept?\b))"),
    ("ECB October decision (17 Oct 12:15 UTC)","2024-10-18","2024-10-10",r"(?=.*(?:ECB|European Central Bank))(?=.*(?:cuts?|cut|lowers?|lowered|decision|eases?|eased|reduces?|reduced))(?=.*(?:rates?|policy|deposit|quarter.point|25 basis|25.basis))"),
    ("US September retail sales (17 Oct 12:30 UTC)","2024-10-18","2024-10-10",r"(?=.*retail sales)(?=.*(?:US|U\.S\.|America))(?=.*(?:September|Sept?\b))"),
    ("Australia September employment (17 Oct 00:30 UTC)","2024-10-18","2024-10-10",r"(?=.*(?:Australia|Australian))(?=.*(?:employment|jobs|unemployment))(?=.*(?:September|Sept?\b))"),
    ("China housing-support briefing (17 Oct 02:00 UTC)","2024-10-18","2024-10-10",r"(?=.*(?:China|Chinese))(?=.*(?:housing|property|home sales|homebuyers))(?=.*(?:briefing|whitelist|white.list|4 trillion|four trillion|doubles?|doubled|loans to))"),
    ("China Q3 GDP and September activity (18 Oct 02:00 UTC)","2024-10-21","2024-10-11",r"(?=.*(?:China|Chinese))(?=.*(?:GDP|industrial output|industrial production|retail sales|fixed.asset|urban unemployment|home prices|property investment))(?=.*(?:September|Sept?\b|Q3|third.quarter|July.September))"),
    ("China October loan prime rates (21 Oct 01:00 UTC)","2024-10-22","2024-10-14",r"(?=.*(?:China|Chinese|PBOC))(?=.*(?:loan prime rate|LPR|benchmark lending))(?=.*(?:cuts?|cut|lowers?|lowered|reduces?|reduced|holds?|held|unchanged|decision))"),
    ("Bank of Canada October decision (23 Oct 13:45 UTC)","2024-10-24","2024-10-16",r"(?=.*(?:Bank of Canada|BOC|Canada.s central bank))(?=.*(?:cuts?|cut|lowers?|lowered|reduces?|reduced|decision|holds?|held))(?=.*(?:rates?|policy|half.point|50 basis|50.basis))"),
    ("October flash PMIs (24 Oct UTC day)","2024-10-25","2024-10-17",r"(?=.*(?:PMI|purchasing managers))(?=.*flash)(?=.*(?:October|Oct\b))"),
    ("Japan October general election (27 Oct JST)","2024-10-28","2024-10-20",r"(?=.*(?:Japan|Japanese|Ishiba|LDP|ruling coalition))(?=.*(?:election|majority|vote))(?=.*(?:loses?|lost|wins?|won|defeat|failed|falls short|short of majority))"),
    ("US Q3 GDP advance estimate (30 Oct 12:30 UTC)","2024-10-31","2024-10-23",r"(?=.*(?:US|U\.S\.|America))(?=.*(?:GDP|gross domestic product|economy))(?=.*(?:Q3|third.quarter|July.September))"),
    ("US ADP October employment (30 Oct 12:15 UTC)","2024-10-31","2024-10-23",r"(?=.*ADP)(?=.*(?:October|Oct\b|private payroll|private employment))"),
    ("Australia Q3/September CPI (30 Oct 00:30 UTC)","2024-10-31","2024-10-23",r"(?=.*(?:Australia|Australian))(?=.*(?:CPI|inflation|consumer prices))(?=.*(?:September|Sept?\b|Q3|third.quarter))"),
    ("Japan September national CPI (17 Oct 23:30 UTC)","2024-10-18","2024-10-10",r"(?=.*(?:Japan|Japanese))(?=.*(?:CPI|consumer prices|inflation))(?=.*(?:September|Sept?\b))"),
    ("Japan October Tokyo CPI (24 Oct 23:30 UTC)","2024-10-25","2024-10-17",r"(?=.*Tokyo)(?=.*(?:CPI|consumer prices|inflation))(?=.*(?:October|Oct\b))"),
    ("Japan September trade (16 Oct 23:50 UTC)","2024-10-17","2024-10-09",r"(?=.*(?:Japan|Japanese))(?=.*(?:trade|exports|imports))(?=.*(?:September|Sept?\b))"),
    ("Japan September industrial production and retail (30 Oct 23:50 UTC)","2024-10-31","2024-10-23",r"(?=.*(?:Japan|Japanese))(?=.*(?:industrial production|industrial output|factory output|production rises|retail sales))(?=.*(?:September|Sept?\b))"),
    ("China October official PMI (31 Oct 01:30 UTC)","2024-11-01","2024-10-24",r"(?=.*(?:China|Chinese))(?=.*(?:PMI|manufacturing activity|factory activity|purchasing managers))(?=.*(?:October|Oct\b|expands|expansion|six months))"),
    ("BOJ October decision (31 Oct UTC morning)","2024-11-01","2024-10-24",r"(?=.*(?:BOJ|Bank of Japan|Ueda))(?=.*(?:holds?|held|keeps?|kept|leaves?|left|decision|unchanged|raises?|raised|cuts?|cut|outlook report))(?=.*(?:rates?|policy|decision|outlook))"),
    ("Euro-area October inflation (31 Oct 10:00 UTC)","2024-11-01","2024-10-24",r"(?=.*(?:eurozone|euro.zone|euro.area))(?=.*(?:CPI|HICP|inflation|consumer prices))(?=.*(?:October|Oct\b))"),
    ("US September PCE (31 Oct 12:30 UTC)","2024-11-01","2024-10-24",r"(?=.*(?:PCE|personal consumption expenditure|Fed.s (?:preferred|favou?rite) inflation))(?=.*(?:September|Sept?\b))"),
    ("Poland October flash inflation (31 Oct UTC day)","2024-11-01","2024-10-24",r"(?=.*(?:Poland|Polish|Polsk\w*|GUS|inflacj\w*))(?=.*(?:CPI|inflation|consumer prices|inflacj\w*))(?=.*(?:October|Oct\b|październik\w*))"),
    ("US October payrolls (1 Nov 12:30 UTC)","2024-11-04","2024-10-24",r"(?=.*(?:US|U\.S\.|America|payroll|nonfarm))(?=.*(?:jobs|payroll|nonfarm|employment|unemployment))(?=.*(?:October|Oct\b))"),
    ("China October Caixin manufacturing (1 Nov 01:45 UTC)","2024-11-04","2024-10-24",r"(?=.*(?:China|Chinese|Caixin))(?=.*(?:PMI|manufacturing))(?=.*(?:Caixin|private survey))(?=.*(?:October|Oct\b))"),
    ("US October ISM manufacturing (1 Nov 14:00 UTC)","2024-11-04","2024-10-24",r"(?=.*(?:ISM|Institute for Supply Management))(?=.*manufactur)(?=.*(?:October|Oct\b))"),
    ("US national presidential election outcome (5 Nov election)","2024-11-07","2024-10-01",r"(?=.*(?:Trump|Harris|Republican))(?=.*(?:wins election|won election|election victory|elected president|president.elect|defeats? Harris|Harris concedes?|Republican sweep|red sweep))"),
    ('Nike Q3/quarterly outcome guard','2024-10-02','2024-09-24',r'(?=.*(?:Nike))(?=.*(?:earnings|results|revenue|sales|profit|guidance|forecast|bookings))(?=.*(?:Q3|third.quarter|quarter|reports?|reported|beats?|beat|misses?|missed|raises?|raised|cuts?|cut|falls?|fell|jumps?|jumped|surges?|surged|slumps?|slumped|warns?|warning))'),
    ('PepsiCo Q3/quarterly outcome guard','2024-10-09','2024-10-01',r'(?=.*(?:PepsiCo|Pepsi))(?=.*(?:earnings|results|revenue|sales|profit|guidance|forecast|bookings))(?=.*(?:Q3|third.quarter|quarter|reports?|reported|beats?|beat|misses?|missed|raises?|raised|cuts?|cut|falls?|fell|jumps?|jumped|surges?|surged|slumps?|slumped|warns?|warning))'),
    ('JPMorgan and Wells Fargo Q3/quarterly outcome guard','2024-10-14','2024-10-04',r'(?=.*(?:JPMorgan|JP Morgan|Wells Fargo))(?=.*(?:earnings|results|revenue|sales|profit|guidance|forecast|bookings))(?=.*(?:Q3|third.quarter|quarter|reports?|reported|beats?|beat|misses?|missed|raises?|raised|cuts?|cut|falls?|fell|jumps?|jumped|surges?|surged|slumps?|slumped|warns?|warning))'),
    ('Goldman Sachs, Bank of America, Citigroup Q3/quarterly outcome guard','2024-10-16','2024-10-08',r'(?=.*(?:Goldman Sachs|Bank of America|Citigroup|Citi\b))(?=.*(?:earnings|results|revenue|sales|profit|guidance|forecast|bookings))(?=.*(?:Q3|third.quarter|quarter|reports?|reported|beats?|beat|misses?|missed|raises?|raised|cuts?|cut|falls?|fell|jumps?|jumped|surges?|surged|slumps?|slumped|warns?|warning))'),
    ('ASML early Q3 release (15 Oct) Q3/quarterly outcome guard','2024-10-16','2024-10-08',r'(?=.*(?:ASML))(?=.*(?:earnings|results|revenue|sales|profit|guidance|forecast|bookings))(?=.*(?:Q3|third.quarter|quarter|reports?|reported|beats?|beat|misses?|missed|raises?|raised|cuts?|cut|falls?|fell|jumps?|jumped|surges?|surged|slumps?|slumped|warns?|warning))'),
    ('Morgan Stanley Q3/quarterly outcome guard','2024-10-17','2024-10-09',r'(?=.*(?:Morgan Stanley))(?=.*(?:earnings|results|revenue|sales|profit|guidance|forecast|bookings))(?=.*(?:Q3|third.quarter|quarter|reports?|reported|beats?|beat|misses?|missed|raises?|raised|cuts?|cut|falls?|fell|jumps?|jumped|surges?|surged|slumps?|slumped|warns?|warning))'),
    ('Netflix and TSMC Q3/quarterly outcome guard','2024-10-18','2024-10-10',r'(?=.*(?:Netflix|TSMC|Taiwan Semiconductor))(?=.*(?:earnings|results|revenue|sales|profit|guidance|forecast|bookings))(?=.*(?:Q3|third.quarter|quarter|reports?|reported|beats?|beat|misses?|missed|raises?|raised|cuts?|cut|falls?|fell|jumps?|jumped|surges?|surged|slumps?|slumped|warns?|warning))'),
    ('Tesla Q3/quarterly outcome guard','2024-10-24','2024-10-16',r'(?=.*(?:Tesla))(?=.*(?:earnings|results|revenue|sales|profit|guidance|forecast|bookings))(?=.*(?:Q3|third.quarter|quarter|reports?|reported|beats?|beat|misses?|missed|raises?|raised|cuts?|cut|falls?|fell|jumps?|jumped|surges?|surged|slumps?|slumped|warns?|warning))'),
    ('UPS and Honeywell Q3/quarterly outcome guard','2024-10-25','2024-10-17',r'(?=.*(?:UPS\b|United Parcel|Honeywell))(?=.*(?:earnings|results|revenue|sales|profit|guidance|forecast|bookings))(?=.*(?:Q3|third.quarter|quarter|reports?|reported|beats?|beat|misses?|missed|raises?|raised|cuts?|cut|falls?|fell|jumps?|jumped|surges?|surged|slumps?|slumped|warns?|warning))'),
    ('Alphabet and AMD Q3/quarterly outcome guard','2024-10-30','2024-10-22',r'(?=.*(?:Alphabet|Google|AMD|Advanced Micro Devices))(?=.*(?:earnings|results|revenue|sales|profit|guidance|forecast|bookings))(?=.*(?:Q3|third.quarter|quarter|reports?|reported|beats?|beat|misses?|missed|raises?|raised|cuts?|cut|falls?|fell|jumps?|jumped|surges?|surged|slumps?|slumped|warns?|warning))'),
    ('Microsoft and Meta Q3/quarterly outcome guard','2024-10-31','2024-10-23',r'(?=.*(?:Microsoft|Meta|Facebook))(?=.*(?:earnings|results|revenue|sales|profit|guidance|forecast|bookings))(?=.*(?:Q3|third.quarter|quarter|reports?|reported|beats?|beat|misses?|missed|raises?|raised|cuts?|cut|falls?|fell|jumps?|jumped|surges?|surged|slumps?|slumped|warns?|warning))'),
    ('Eli Lilly and Caterpillar Q3/quarterly outcome guard','2024-10-31','2024-10-23',r'(?=.*(?:Eli Lilly|Caterpillar))(?=.*(?:earnings|results|revenue|sales|profit|guidance|forecast|bookings))(?=.*(?:Q3|third.quarter|quarter|reports?|reported|beats?|beat|misses?|missed|raises?|raised|cuts?|cut|falls?|fell|jumps?|jumped|surges?|surged|slumps?|slumped|warns?|warning))'),
    ('Apple, Amazon, Uber, Merck and Intel Q3/quarterly outcome guard','2024-11-01','2024-10-24',r'(?=.*(?:Apple|Amazon|Uber|Merck|Intel))(?=.*(?:earnings|results|revenue|sales|profit|guidance|forecast|bookings))(?=.*(?:Q3|third.quarter|quarter|reports?|reported|beats?|beat|misses?|missed|raises?|raised|cuts?|cut|falls?|fell|jumps?|jumped|surges?|surged|slumps?|slumped|warns?|warning))'),
]


# A modal in a second clause must not disguise a completed first clause.
COMPLETED = re.compile(r"\b(?:announced|unveiled|approved|won|elected|president-elect|conceded|defeated|lowered|held|kept|reported|surged|accelerated|slowed|beats|beat|misses|missed|tops|topped|rises|rose|falls|fell|jumps|jumped|slumps|slumped|raises|raised|cuts|cut|lowers|holds|keeps|expands|expanded|declines|declined|accelerates|slows|increases|increased|decreases|decreased|drops|dropped)\b|"
                       r"(?:Trump|Harris|Fed|FOMC|Federal Reserve|BOE|Bank of England|RBA|Reserve Bank of Australia|RBNZ|Bank of Canada|ECB|BOJ|NBP|RPP|China|Nvidia)"
                       r".{0,35}\b(?:wins|cuts|cut|lowers|holds|keeps|expands|expanded|declines|declined|accelerates|slows|increases|increased|decreases|decreased|drops|dropped|leaves|reports|beats|beat|misses|missed|unveils|approves|announces)\b",re.I)
EXPLICIT_PREVIEW = re.compile(r"\b(?:preview|ahead of|what to expect|set to report|earnings calendar)\b|"
                              r"\b(?:expected|forecast|likely|seen|set|poised|due) to (?:win|cut|hold|keep|report|beat|announce|unveil|release)\b|"
                              r"\b(?:will|could|would|may|might) (?:win|cut|hold|keep|report|beat|announce|unveil|release)\b",re.I)

# Mask only an outcome verb governed directly by a forward phrase. A pending
# second clause cannot erase a completed verb in the first clause.
FORWARD_ACTION = re.compile(
    r"\b(?:(?:will|could|would|may|might|should)(?:\s+(?:also|still|soon|now|again|further))?|"
    r"(?:expected|forecast|likely|seen|set|poised|due)\s+to|plans?\s+to|to)\s+"
    r"(?:win|cut|hold|keep|report|beat|miss|top|rise|fall|jump|surge|slump|raise|lower|announce|unveil|"
    r"approve|expand|decline|accelerate|slow|increase|decrease|drop|release|publish|decide|leave)\b",re.I)

def guard_hit(title, published, stamp):
    """Conservatively reject pre-release outcomes; mixed outcome/forecast headlines fail closed."""
    normalised = NEUTRALISE.sub("", title)
    for label, eligible, start, pattern in RELEASE_GUARDS:
        if stamp < eligible and start <= published < stamp and re.search(pattern, title, re.I):
            outcome_text=FORWARD_ACTION.sub("",normalised)
            if COMPLETED.search(outcome_text):
                return label
            if EXPLICIT_PREVIEW.search(normalised) or PREVIEW.search(normalised) or FORWARD.search(normalised):
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
               "canonical_screening": ("Not performed for October 2024: no canonical publisher-date resolution. "
                                       "RSS pubDate is used with release-timing guards; no article body is read."),
               "release_guards_version": "oct-2024-release-guards-v1"}
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
