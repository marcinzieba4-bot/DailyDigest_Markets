"""Screen August 2024 own-date feeds after complete prefix/daily acquisition (headline-only, conservative).

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
Canonical publisher-date resolution was NOT performed for August 2024 (publisher article vintages remain an editorial limitation): no item is admitted on a resolved
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

DATES = [dt.date(2024, 8, n) for n in range(1, 32) if dt.date(2024, 8, n).weekday() < 5]

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
 ('China July Caixin manufacturing (1 Aug 01:45 UTC)', '2024-08-02', '2024-07-25', r'(?=.*(?:China|Chinese|Caixin))(?=.*(?:manufactur|factory|PMI))(?=.*(?:Caixin|private survey))'),
 ('Poland July PMI (1 Aug UTC day)', '2024-08-02', '2024-07-25', r'(?=.*(?:Poland|Polish|Polsk\w*))(?=.*(?:PMI|manufacturing|przemysł\w*))(?=.*(?:July|lipc\w*|PMI))'),
 ('US July ISM manufacturing (1 Aug 14:00 UTC)', '2024-08-02', '2024-07-25', r'(?=.*(?:ISM|Institute for Supply Management))(?=.*manufactur)'),
 ('Bank of England August decision (1 Aug 11:00 UTC)', '2024-08-02', '2024-07-25', r'(?=.*(?:Bank of England|BOE|British central bank))(?=.*(?:rates?|policy|cuts?|cut|lowers?|decision))'),
 ('US July payrolls (2 Aug 12:30 UTC)', '2024-08-05', '2024-07-26', r'(?=.*(?:US|U\.S\.|America|payroll|nonfarm))(?=.*(?:jobs report|payroll|nonfarm|employment report|unemployment rate))'),
 ('China July Caixin services (5 Aug 01:45 UTC)', '2024-08-06', '2024-07-29', r'(?=.*(?:China|Chinese|Caixin))(?=.*(?:services|service sector))(?=.*(?:Caixin|private survey))'),
 ('US July ISM services (5 Aug 14:00 UTC)', '2024-08-06', '2024-07-29', r'(?=.*(?:ISM|Institute for Supply Management))(?=.*(?:services|non.manufacturing))'),
 ('Nikkei 5 August crash magnitude', '2024-08-06', '2024-08-01', r'(?=.*(?:Nikkei|Japan|Japanese|Tokyo))(?=.*(?:12\.?4?%|12 per cent|12 percent|worst.*1987|biggest.*1987|largest.*points|Black Monday))'),
 ('RBA August decision (6 Aug 04:30 UTC)', '2024-08-07', '2024-07-30', r'(?=.*(?:RBA|Reserve Bank of Australia))(?=.*(?:rates?|policy|cash rate|decision))'),
 ('China July trade (7 Aug UTC day)', '2024-08-08', '2024-07-31', r'(?=.*(?:China|Chinese))(?=.*(?:exports|imports|trade surplus|trade data))(?=.*(?:July|trade data))'),
 ('China July CPI/PPI (9 Aug 01:30 UTC)', '2024-08-12', '2024-08-02', r'(?=.*(?:China|Chinese))(?=.*(?:CPI|PPI|consumer prices|producer prices|inflation|deflation))'),
 ('US July PPI (13 Aug 12:30 UTC)', '2024-08-14', '2024-08-06', r'(?=.*(?:US|U\.S\.|America|PPI))(?=.*(?:PPI|producer prices|producer inflation))'),
 ('US July CPI (14 Aug 12:30 UTC)', '2024-08-15', '2024-08-07', r'(?=.*(?:US|U\.S\.|America|CPI|consumer price))(?=.*(?:CPI|consumer prices|inflation))(?=.*(?:July|US|U\.S\.|America))'),
 ('Poland Q2 GDP flash (14 Aug UTC day)', '2024-08-15', '2024-08-07', r'(?=.*(?:Poland|Polish|Polsk\w*|PKB))(?=.*(?:GDP|PKB|economic growth|wzrost gospodarczy))(?=.*(?:Q2|second.quarter|II kwarta|kwartał|flash|wstępn\w*))'),
 ('Kishida withdrawal (14 Aug Japan UTC day)', '2024-08-15', '2024-08-07', r'(?=.*Kishida)(?=.*(?:step\w* down|resign\w*|will not|won.t|not seek|drop\w* out))'),
 ('China July activity (15 Aug UTC day)', '2024-08-16', '2024-08-08', r'(?=.*(?:China|Chinese))(?=.*(?:retail sales|industrial output|industrial production|fixed.asset|property investment|home prices|house prices))'),
 ('Japan Q2 GDP (14 Aug 23:50 UTC)', '2024-08-15', '2024-08-07', r'(?=.*(?:Japan|Japanese))(?=.*(?:GDP|gross domestic product|economic growth|economy))(?=.*(?:Q2|second.quarter|April.June|GDP|economic growth))'),
 ('Japan August flash PMI (22 Aug 00:30 UTC)', '2024-08-23', '2024-08-15', r'(?=.*(?:Japan|Japanese))(?=.*(?:PMI|purchasing managers|business activity))(?=.*(?:August|flash|preliminary))'),
 ('Japan July CPI (22 Aug 23:30 UTC)', '2024-08-23', '2024-08-15', r'(?=.*(?:Japan|Japanese))(?=.*(?:inflation|CPI|consumer prices))(?=.*(?:July|nationwide|national))'),
 ('Japan August Tokyo CPI (29 Aug 23:30 UTC)', '2024-08-30', '2024-08-22', r'(?=.*Tokyo)(?=.*(?:inflation|CPI|consumer prices))(?=.*(?:August|Tokyo))'),
 ('Japan July industrial and retail data (29 Aug 23:50 UTC)', '2024-08-30', '2024-08-22', r'(?=.*(?:Japan|Japanese))(?=.*(?:industrial output|industrial production|retail sales))(?=.*(?:July|monthly))'),
 ('Australia July jobs (15 Aug 01:30 UTC)', '2024-08-16', '2024-08-08', r'(?=.*(?:Australia|Australian))(?=.*(?:jobs|employment|unemployment|labour market|labor market))(?=.*(?:July|jobs|employment))'),
 ('US July retail sales (15 Aug 12:30 UTC)', '2024-08-16', '2024-08-08', r'(?=.*(?:US|U\.S\.|America))(?=.*retail sales)'),
 ('US July industrial output (15 Aug 13:15 UTC)', '2024-08-16', '2024-08-08', r'(?=.*(?:US|U\.S\.|America))(?=.*(?:industrial output|industrial production|factory output))'),
 ('China August LPR (20 Aug UTC day)', '2024-08-21', '2024-08-13', r'(?=.*(?:China|Chinese|PBOC))(?=.*(?:loan prime|LPR|benchmark lending))'),
 ('RBA August minutes (20 Aug 01:30 UTC)', '2024-08-21', '2024-08-13', r'(?=.*(?:RBA|Reserve Bank of Australia))(?=.*minutes)'),
 ('FOMC July minutes (21 Aug 18:00 UTC)', '2024-08-22', '2024-08-14', r'(?=.*(?:Fed|FOMC|Federal Reserve))(?=.*minutes)'),
 ('US payrolls annual benchmark (21 Aug 14:00 UTC)', '2024-08-22', '2024-08-14', r'(?=.*(?:US|U\.S\.|America|jobs|payroll))(?=.*(?:818,000|818000|benchmark|revis\w* jobs|jobs.*revis\w*|payroll.*revis\w*))'),
 ('August flash PMIs (22 Aug UTC day)', '2024-08-23', '2024-08-15', r'(?=.*(?:eurozone|Germany|German|France|French|US|U\.S\.))(?=.*(?:PMI|purchasing managers|business activity))(?=.*(?:August|flash|preliminary))'),
 ('Powell Jackson Hole speech (23 Aug 14:00 UTC)', '2024-08-26', '2024-08-16', r'(?=.*Powell)(?=.*(?:Jackson Hole|time has come|time to cut|policy adjust))'),
 ('Australia July CPI (28 Aug 01:30 UTC)', '2024-08-29', '2024-08-21', r'(?=.*(?:Australia|Australian))(?=.*(?:inflation|CPI|consumer prices))(?=.*(?:July|monthly))'),
 ('US Q2 GDP second estimate (29 Aug 12:30 UTC)', '2024-08-30', '2024-08-22', r'(?=.*(?:US|U\.S\.|America))(?=.*(?:GDP|gross domestic product|economic growth))(?=.*(?:revis\w*|second estimate|3\.0|3%|3 percent))'),
 ('US July PCE (30 Aug 12:30 UTC)', '2024-09-02', '2024-08-23', r'(?=.*(?:US|U\.S\.|America|PCE|Fed))(?=.*(?:PCE|personal consumption expenditures|preferred.*inflation|inflation.*preferred))'),
 ('Eurozone August CPI flash (30 Aug UTC day)', '2024-09-02', '2024-08-23', r'(?=.*(?:eurozone|euro zone|euro area))(?=.*(?:inflation|CPI|consumer prices))(?=.*(?:August|flash|preliminary|2\.2))'),
 ('Poland August CPI flash (30 Aug UTC day)', '2024-09-02', '2024-08-23', r'(?=.*(?:Poland|Polish|Polsk\w*|inflacja))(?=.*(?:CPI|inflation|inflacj\w*))(?=.*(?:August|sierpni\w*|flash|wstępn\w*))'),
 ('China August official PMI (31 Aug 01:30 UTC)', '2024-09-02', '2024-08-23', r'(?=.*(?:China|Chinese))(?=.*(?:manufactur|factory|PMI))(?=.*(?:August|official|NBS))'),
 ('Super Micro short seller report (27 Aug UTC day)', '2024-08-28', '2024-08-20', r'(?=.*(?:Super Micro|SMCI|Supermicro))(?=.*(?:Hindenburg|short.seller report))'),
 ('Super Micro annual filing delay (28 Aug UTC day)', '2024-08-29', '2024-08-21', r'(?=.*(?:Super Micro|SMCI|Supermicro))(?=.*(?:delay\w*|postpon\w*))(?=.*(?:filing|annual|10.K))'),
]

_RESULT = r'(?=.*(?:earnings|results|revenue|sales|profit|guidance|forecast|bookings))(?=.*(?:quarter|reports?|reported|beats?|beat|misses?|missed|raises?|raised|cuts?|cut|falls?|fell|jumps?|jumped|surges?|surged|slumps?|slumped|warns?|warning))'
for _label,_names,_eligible,_start in [
 ('Apple Amazon Intel',r'Apple|AAPL|Amazon|AMZN|Intel|INTC','2024-08-02','2024-07-25'),
 ('Palantir Hims',r'Palantir|PLTR|Hims','2024-08-06','2024-07-29'),
 ('Super Micro',r'Super Micro|SMCI|Supermicro','2024-08-07','2024-07-30'),
 ('Robinhood',r'Robinhood|HOOD','2024-08-08','2024-07-31'),
 ('Eli Lilly',r'Eli Lilly|LLY','2024-08-09','2024-08-01'),
 ('AST SpaceMobile',r'AST SpaceMobile|ASTS','2024-08-15','2024-08-07'),
 ('Walmart',r'Walmart|WMT','2024-08-16','2024-08-08'),
 ('Target',r'Target|TGT','2024-08-22','2024-08-14'),
 ('Nvidia Salesforce Chewy',r'Nvidia|NVDA|Salesforce|CRM|Chewy|CHWY','2024-08-29','2024-08-21'),
 ('Dell Lululemon',r'Dell|DELL|Lululemon|LULU','2024-08-30','2024-08-22'),
]:
 RELEASE_GUARDS.append((_label+' quarterly outcome guard',_eligible,_start,r'(?=.*(?:'+_names+r'))'+_RESULT))


# A modal in a second clause must not disguise a completed first clause.
COMPLETED = re.compile(r"\b(?:announced|unveiled|approved|confirmed|unchanged|reach|reaches|hit|hits|shrink|shrinks|contract|contracts|rebound|rebounds|rise|fall|surge|slump|jump|gain|gains|grow|grows|cool|cools|ease|eases|moderate|moderates|contraction|expansion|rattles?|rattled|dominates?|dominated|spars?|sparred|clash(?:es)?|clashed|defeats?|vows?|vowed|pledges?|pledged|urges?|urged|promises?|promised|won|elected|president-elect|conceded|defeated|lowered|held|kept|reported|surged|accelerated|slowed|beats|beat|misses|missed|tops|topped|rises|rose|falls|fell|jumps|jumped|slumps|slumped|raises|raised|cuts|cut|lowers|holds|keeps|expands|expanded|declines|declined|accelerates|slows|increases|increased|decreases|decreased|drops|dropped)\b|"
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
    r"approve|expand|decline|accelerate|slow|increase|decrease|drop|gain|grow|cool|ease|moderate|reach|hit|shrink|contract|rebound|rattle|dominate|spar|clash|defeat|vow|pledge|urge|promise|release|publish|decide|leave)\b",re.I)

def guard_hit(title, published, stamp):
    """Conservatively reject pre-release outcomes; mixed outcome/forecast headlines fail closed."""
    normalised = NEUTRALISE.sub("", title)
    for label, eligible, start, pattern in RELEASE_GUARDS:
        if stamp < eligible and start <= published < stamp and re.search(pattern, title, re.I):
            if label.startswith('Kishida withdrawal') and re.search(r"\b(?:announces?|announced|says?|said|declares?|declared|confirms?|confirmed)\b|\b(?:will not|won.t)\s+(?:run|seek|stand)\b|\b(?:not seeking|not running)\b",normalised,re.I):
                return label
            outcome_text=FORWARD_ACTION.sub("",normalised)
            if COMPLETED.search(outcome_text):
                return label
            if EXPLICIT_PREVIEW.search(normalised) or PREVIEW.search(normalised) or FORWARD.search(normalised):
                continue
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
               "canonical_screening": ("Not performed for August 2024: no canonical publisher-date resolution. "
                                       "RSS pubDate is used with release-timing guards; no article body is read."),
               "release_guards_version": "aug-2024-release-guards-v2"}
    target = ROOT / "feeds" / (stamp + ".json.gz")
    if persist:raise RuntimeError('Use finalize_sources.py: all-date physical candidate comparison is required')
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
