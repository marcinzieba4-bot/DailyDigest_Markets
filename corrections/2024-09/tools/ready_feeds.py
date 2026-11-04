"""Screen September 2024 own-date feeds after complete prefix/daily acquisition (headline-only, conservative).

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
Canonical publisher-date resolution was NOT performed for September 2024 (publisher article vintages remain an editorial limitation): no item is admitted on a resolved
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

DATES = [dt.date(2024, 9, n) for n in range(1, 31) if dt.date(2024, 9, n).weekday() < 5]

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
    ('China August Caixin manufacturing (2 Sep 01:45 UTC)', '2024-09-03', '2024-08-26', r'(?=.*(?:China|Chinese|Caixin))(?=.*(?:manufactur|factory|PMI))(?=.*(?:Caixin|private survey))'),
    ('Poland August manufacturing PMI (2 Sep UTC day)', '2024-09-03', '2024-08-26', r'(?=.*(?:Poland|Polish|Polsk\w*))(?=.*(?:PMI|manufacturing|przemysł\w*))(?=.*(?:August|Aug\b|sierpni\w*|PMI))'),
    ('US August ISM manufacturing (3 Sep 14:00 UTC)', '2024-09-04', '2024-08-27', r'(?=.*(?:ISM|Institute for Supply Management))(?=.*manufactur)'),
    ('China August Caixin services (4 Sep 01:45 UTC)', '2024-09-05', '2024-08-28', r'(?=.*(?:China|Chinese|Caixin))(?=.*(?:services|service sector))(?=.*(?:Caixin|private survey))'),
    ('US July JOLTS (4 Sep 14:00 UTC)', '2024-09-05', '2024-08-28', r'(?=.*(?:JOLTS|job openings))(?=.*(?:US|U\.S\.|America|JOLTS|July|job openings))'),
    ('NBP/RPP September decision (4 Sep UTC day)', '2024-09-05', '2024-08-28', r'(?=.*(?:NBP|RPP|Polish central bank|Poland central bank|Glapi\w*))(?=.*(?:holds?|held|keeps?|kept|unchanged|bez zmian|utrzyma\w*|decyzj\w*))'),
    ('Bank of Canada September decision (4 Sep 13:45 UTC)', '2024-09-05', '2024-08-28', r'(?=.*(?:Bank of Canada|BOC|Canada.s central bank))(?=.*(?:cuts?|cut|lowers?|lowered|reduces?|reduced|decision|holds?|held|unchanged))(?=.*(?:rates?|policy))'),
    ('Australia Q2 GDP (4 Sep 01:30 UTC)', '2024-09-05', '2024-08-28', r'(?=.*(?:Australia|Australian))(?=.*(?:GDP|gross domestic product|economic growth))(?=.*(?:Q2|second.quarter|June.quarter|April.June|economy))'),
    ('US August ADP (5 Sep 12:15 UTC)', '2024-09-06', '2024-08-29', r'(?=.*ADP)(?=.*(?:August|Aug\b|private payroll|private employment|jobs))'),
    ('US August ISM services (5 Sep 14:00 UTC)', '2024-09-06', '2024-08-29', r'(?=.*(?:ISM|Institute for Supply Management))(?=.*(?:services|non.manufacturing))'),
    ('US August payrolls (6 Sep 12:30 UTC)', '2024-09-09', '2024-08-30', r'(?=.*(?:US|U\.S\.|America|payroll|nonfarm))(?=.*(?:jobs report|payroll|nonfarm|employment report|unemployment rate))'),
    ('China August CPI/PPI (9 Sep 01:30 UTC)', '2024-09-10', '2024-09-02', r'(?=.*(?:China|Chinese))(?=.*(?:CPI|PPI|consumer prices|producer prices|inflation|deflation))'),
    ('China August trade (10 Sep UTC day)', '2024-09-11', '2024-09-03', r'(?=.*(?:China|Chinese))(?=.*(?:exports|imports|trade surplus|trade data))'),
    ('US presidential debate (11 Sep 01:00 UTC)', '2024-09-12', '2024-09-04', r'(?=.*(?:Trump|Harris|presidential))(?=.*debate)'),
    ('US August CPI (11 Sep 12:30 UTC)', '2024-09-12', '2024-09-04', r'(?=.*(?:US|U\.S\.|America|CPI|consumer price))(?=.*(?:CPI|consumer prices|inflation))(?=.*(?:August|Aug\b|US|U\.S\.|America))'),
    ('UK July GDP (11 Sep UTC morning)', '2024-09-12', '2024-09-04', r'(?=.*(?:UK|U\.K\.|Britain|British))(?=.*(?:GDP|economy|economic growth))(?=.*(?:July|monthly))'),
    ('US August PPI (12 Sep 12:30 UTC)', '2024-09-13', '2024-09-05', r'(?=.*(?:US|U\.S\.|PPI|producer prices|wholesale prices))(?=.*(?:PPI|producer prices|wholesale prices))'),
    ('ECB September decision (12 Sep 12:15 UTC)', '2024-09-13', '2024-09-05', r'(?=.*(?:ECB|European Central Bank))(?=.*(?:cuts?|cut|lowers?|lowered|decision|eases?|eased|reduces?|reduced|holds?|held))(?=.*(?:rates?|policy|deposit))'),
    ('China August credit (13 Sep UTC day; conservative)', '2024-09-16', '2024-09-06', r'(?=.*(?:China|Chinese|PBOC))(?=.*(?:new loans|bank lending|credit data|total social financing|money supply|M2))'),
    ('US preliminary September Michigan sentiment (13 Sep 14:00 UTC)', '2024-09-16', '2024-09-06', r'(?=.*(?:Michigan|US consumer sentiment|U\.S\. consumer sentiment))(?=.*(?:sentiment|expectations))(?=.*(?:September|Sept?\b|preliminary))'),
    ('China August activity/housing (14 Sep 02:00 UTC)', '2024-09-16', '2024-09-07', r'(?=.*(?:China|Chinese))(?=.*(?:industrial output|industrial production|retail sales|fixed.asset|urban unemployment|home prices|property investment))'),
    ('Poland final August CPI (13 Sep UTC day)', '2024-09-16', '2024-09-06', r'(?=.*(?:Poland|Polish|Polsk\w*|GUS))(?=.*(?:CPI|inflation|inflacj\w*))(?=.*(?:final|ostatecz\w*|confirmed|potwierdz\w*))(?=.*(?:August|Aug\b|sierpni\w*))'),
    ('US August retail sales (17 Sep 12:30 UTC)', '2024-09-18', '2024-09-10', r'(?=.*retail sales)(?=.*(?:US|U\.S\.|America))'),
    ('US August industrial production (17 Sep 13:15 UTC)', '2024-09-18', '2024-09-10', r'(?=.*(?:US|U\.S\.|America))(?=.*(?:industrial production|industrial output|factory output))'),
    ('Fed September decision (18 Sep 18:00 UTC)', '2024-09-19', '2024-09-11', r'(?=.*(?:Fed|FOMC|Federal Reserve|Powell))(?=.*(?:cuts?|cut|lowers?|lowered|decision|eases?|eased|reduces?|reduced|holds?|held|half.point|50.basis|50 basis|jumbo))(?=.*(?:rates?|policy|easing|cut))'),
    ('UK August CPI (18 Sep UTC morning)', '2024-09-19', '2024-09-11', r'(?=.*(?:UK|U\.K\.|Britain|British))(?=.*(?:CPI|inflation|consumer prices))'),
    ('Euro-area final August CPI (18 Sep 09:00 UTC)', '2024-09-19', '2024-09-11', r'(?=.*(?:eurozone|euro.zone|euro.area))(?=.*(?:CPI|HICP|inflation|consumer prices))(?=.*(?:final|confirmed|August|Aug\b))'),
    ('US August housing starts (18 Sep 12:30 UTC)', '2024-09-19', '2024-09-11', r'(?=.*(?:US|U\.S\.|America))(?=.*(?:housing starts|building permits))'),
    ('Bank of England September decision (19 Sep 11:00 UTC)', '2024-09-20', '2024-09-12', r'(?=.*(?:Bank of England|BOE|BoE))(?=.*(?:cuts?|cut|lowers?|lowered|decision|holds?|held|keeps?|kept|unchanged|leaves?|left))(?=.*(?:rates?|policy))'),
    ('Australia August jobs (19 Sep 01:30 UTC)', '2024-09-20', '2024-09-12', r'(?=.*(?:Australia|Australian))(?=.*(?:employment|jobs|unemployment))'),
    ('Poland August industry/wages/employment (19 Sep UTC day)', '2024-09-20', '2024-09-12', r'(?=.*(?:Poland|Polish|Polsk\w*|GUS))(?=.*(?:industrial production|industrial output|produkcj\w* przemysł\w*|wages|wynagrodz\w*|employment|zatrudni\w*))(?=.*(?:August|Aug\b|sierpni\w*))'),
    ('US August existing-home sales (19 Sep 14:00 UTC)', '2024-09-20', '2024-09-12', r'(?=.*(?:US|U\.S\.|America))(?=.*(?:existing.home sales|existing homes))'),
    ('Japan August national CPI (19 Sep 23:30 UTC)', '2024-09-20', '2024-09-12', r'(?=.*(?:Japan|Japanese))(?=.*(?:CPI|consumer prices|inflation))(?=.*(?:August|Aug\b|national))'),
    ('BOJ September decision (20 Sep UTC morning)', '2024-09-23', '2024-09-13', r'(?=.*(?:BOJ|Bank of Japan|Ueda))(?=.*(?:holds?|held|keeps?|kept|leaves?|left|decision|unchanged|raises?|raised|cuts?|cut))(?=.*(?:rates?|policy|decision))'),
    ('China September loan prime rates (20 Sep 01:00 UTC)', '2024-09-23', '2024-09-13', r'(?=.*(?:China|Chinese|PBOC))(?=.*(?:loan prime rate|LPR|benchmark lending))'),
    ('UK August retail sales (20 Sep UTC morning)', '2024-09-23', '2024-09-13', r'(?=.*(?:UK|U\.K\.|Britain|British))(?=.*retail sales)'),
    ('Europe/US September flash PMIs (23 Sep UTC day)', '2024-09-24', '2024-09-16', r'^(?!.*(?:Australia|Australian|Japan|Japanese))(?=.*(?:PMI|purchasing managers))(?=.*(?:flash|September|Sept?\b))'),
    ('Australia September flash PMI (22 Sep 23:00 UTC)', '2024-09-23', '2024-09-16', r'(?=.*(?:Australia|Australian))(?=.*(?:PMI|purchasing managers))(?=.*(?:flash|September|Sept?\b))'),
    ('Japan September flash PMI (24 Sep 00:30 UTC)', '2024-09-25', '2024-09-17', r'(?=.*(?:Japan|Japanese))(?=.*(?:PMI|purchasing managers))(?=.*(?:flash|September|Sept?\b))'),
    ('Poland August retail sales (23 Sep UTC day)', '2024-09-24', '2024-09-16', r'(?=.*(?:Poland|Polish|Polsk\w*|GUS))(?=.*(?:retail sales|sprzedaż detaliczn\w*))(?=.*(?:August|Aug\b|sierpni\w*))'),
    ('RBA September decision (24 Sep 04:30 UTC)', '2024-09-25', '2024-09-17', r'(?=.*(?:RBA|Reserve Bank of Australia|Australia.s central bank))(?=.*(?:holds?|held|keeps?|kept|leaves?|left|decision|unchanged|raises?|raised|cuts?|cut))(?=.*(?:rates?|policy|decision))'),
    ('PBOC September stimulus announcement (24 Sep UTC morning)', '2024-09-25', '2024-09-17', r'(?=.*(?:China|Chinese|PBOC|Pan Gongsheng))(?=.*(?:stimulus|reserve requirement|RRR|mortgage rates?|stock.market support|swap facility|lending facility|policy rates?))(?=.*(?:announc|unveil|cuts?|cut|lowers?|lowered|reduces?|reduced|launch|rolls? out|package|eases?|eased))'),
    ('US September Conference Board confidence (24 Sep 14:00 UTC)', '2024-09-25', '2024-09-17', r'(?=.*(?:US|U\.S\.|America|Conference Board))(?=.*consumer confidence)'),
    ('Australia August monthly CPI (25 Sep 01:30 UTC)', '2024-09-26', '2024-09-18', r'(?=.*(?:Australia|Australian))(?=.*(?:CPI|inflation|consumer prices))'),
    ('US August new-home sales (25 Sep 14:00 UTC)', '2024-09-26', '2024-09-18', r'(?=.*(?:US|U\.S\.|America))(?=.*(?:new.home sales|new homes))'),
    ('China September Politburo meeting (26 Sep UTC day)', '2024-09-27', '2024-09-19', r'(?=.*(?:China|Chinese|Xi|Politburo))(?=.*(?:Politburo|top leaders|top leadership))(?=.*(?:pledge|vows?|urges?|calls? for|steps?|support|stimulus|fiscal|property|housing))'),
    ('US Q2 GDP third estimate (26 Sep 12:30 UTC)', '2024-09-27', '2024-09-19', r'(?=.*(?:US|U\.S\.|America))(?=.*(?:GDP|gross domestic product))(?=.*(?:final|third estimate|revised|revision))'),
    ('US August durable goods (26 Sep 12:30 UTC)', '2024-09-27', '2024-09-19', r'(?=.*(?:US|U\.S\.|America))(?=.*durable.goods)'),
    ('Japan September Tokyo CPI (26 Sep 23:30 UTC)', '2024-09-27', '2024-09-19', r'(?=.*Tokyo)(?=.*(?:CPI|consumer prices|inflation))(?=.*(?:September|Sept?\b))'),
    ('China August industrial profits (27 Sep 01:30 UTC)', '2024-09-30', '2024-09-20', r'(?=.*(?:China|Chinese))(?=.*industrial profits)'),
    ('US August PCE (27 Sep 12:30 UTC)', '2024-09-30', '2024-09-20', r'(?=.*(?:PCE|personal consumption expenditure|Fed.s (?:preferred|favou?rite) inflation))'),
    ('US final September Michigan sentiment (27 Sep 14:00 UTC)', '2024-09-30', '2024-09-20', r'(?=.*(?:Michigan|US consumer sentiment|U\.S\. consumer sentiment))(?=.*(?:sentiment|expectations))(?=.*(?:final|revised|revision))'),
    ('Japan LDP leadership result (27 Sep UTC day)', '2024-09-30', '2024-09-20', r'(?=.*(?:Ishiba|Takaichi|Koizumi|Japan|Japanese|LDP))(?=.*(?:leadership|leader|prime minister|premier|LDP election))(?=.*(?:wins?|won|elected|becomes?|victory|defeats?|defeated|loses?|lost))'),
    ('Japan August industrial production/retail (29 Sep 23:50 UTC)', '2024-09-30', '2024-09-22', r'(?=.*(?:Japan|Japanese))(?=.*(?:industrial production|industrial output|factory output|retail sales))(?=.*(?:August|Aug\b))'),
    ('China September official/Caixin PMIs (30 Sep UTC morning)', '2024-10-01', '2024-09-23', r'(?=.*(?:China|Chinese|Caixin))(?=.*(?:PMI|manufacturing activity|factory activity|purchasing managers|services activity))(?=.*(?:September|Sept?\b))'),
    ('Poland September flash CPI (30 Sep UTC day)', '2024-10-01', '2024-09-23', r'(?=.*(?:Poland|Polish|Polsk\w*|GUS|inflacj\w*))(?=.*(?:CPI|inflation|inflacj\w*))(?=.*(?:September|Sept?\b|wrześni\w*))'),
    ('China 30 September session outcome (after final cutoff)', '2024-10-01', '2024-09-29', r'(?=.*(?:China|Chinese|CSI 300|Shanghai|Hang Seng))(?=.*(?:September 30|Sept\.? 30|30 September|Monday))(?=.*(?:stocks|shares|index|indices|market))(?=.*(?:rall|surge|jump|soar|leap|gain|rise|rose|close|record|best))'),
    ('Japan 30 September session outcome (after final cutoff)', '2024-10-01', '2024-09-29', r'(?=.*(?:Nikkei|Japan|Japanese))(?=.*(?:September 30|Sept\.? 30|30 September|Monday|Ishiba))(?=.*(?:stocks|shares|index|market|Nikkei))(?=.*(?:sell.off|plung|sink|tumble|slump|drop|fell|fall|loss|close))'),
    ('US dockworkers strike begins (1 Oct 04:01 UTC)', '2024-10-02', '2024-09-24', r'(?=.*(?:ports?|dockworkers?|longshoremen))(?=.*(?:strike begins|strike starts|go on strike|walk out|walkout begins|strike shuts|strike halts))'),
    ('Any October central-bank decision is future to September', '2024-10-02', '2024-09-01', r'(?=.*(?:Fed|FOMC|Federal Reserve|ECB|Bank of England|BOE|BOJ|Bank of Japan|RBA|RBNZ|NBP|RPP|Bank of Canada))(?=.*October)(?=.*(?:decision|cuts?|cut|holds?|held|raises?|raised|unchanged|keeps?|kept))'),
]
RELEASE_GUARDS.append(('US national presidential election outcome is future', '2024-11-07', '2024-09-01', r'(?=.*(?:Trump|Harris|Republican))(?=.*(?:wins election|won election|election victory|elected president|president.elect|defeats? Harris|Harris concedes?|Republican sweep|red sweep))'))

RELEASE_GUARDS.extend([
 ('GameStop September results/share offering (10 Sep US evening)', '2024-09-11', '2024-09-03', r'(?=.*(?:GameStop|GME\b))(?=.*(?:earnings|quarterly|results|revenue|sales|profit|offering|sell.*shares|share.*sale))'),
 ('Roaring Kitty September social return (6 Sep US day)', '2024-09-09', '2024-08-30', r'(?=.*(?:Roaring Kitty|Keith Gill))(?=.*(?:returns?|returned|posts?|posted|tweets?|tweeted|breaks? silence|Toy Story|Chewy))'),
 ('Constellation Microsoft Three Mile Island restart agreement (20 Sep US day)', '2024-09-23', '2024-09-13', r'(?=.*(?:Constellation|Microsoft|Three Mile Island|Crane Clean Energy))(?=.*(?:nuclear|Three Mile Island|reactor|power plant))(?=.*(?:agreement|deal|restart|reopen|revive|reboot|power))'),
])


_RESULT = r'(?=.*(?:earnings|results|revenue|sales|profit|guidance|forecast|bookings))(?=.*(?:quarter|reports?|reported|beats?|beat|misses?|missed|raises?|raised|cuts?|cut|falls?|fell|jumps?|jumped|surges?|surged|slumps?|slumped|warns?|warning))'
for _label, _names, _eligible, _start in [
    ('Broadcom', r'Broadcom|AVGO', '2024-09-06', '2024-08-29'),
    ('Oracle', r'Oracle|ORCL', '2024-09-10', '2024-09-02'),
    ('Adobe', r'Adobe|ADBE', '2024-09-13', '2024-09-05'),
    ('FedEx', r'FedEx|FDX', '2024-09-20', '2024-09-12'),
    ('Micron', r'Micron|MU\b', '2024-09-26', '2024-09-18'),
    ('Costco, Accenture and H&M', r'Costco|Accenture|H\s*&\s*M|Hennes.*Mauritz', '2024-09-27', '2024-09-19'),
    ('Nike future October release', r'Nike|NKE', '2024-10-02', '2024-09-24'),
]:
    RELEASE_GUARDS.append((_label+' quarterly outcome guard', _eligible, _start, r'(?=.*(?:'+_names+r'))'+_RESULT))



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
               "canonical_screening": ("Not performed for September 2024: no canonical publisher-date resolution. "
                                       "RSS pubDate is used with release-timing guards; no article body is read."),
               "release_guards_version": "sep-2024-release-guards-v2"}
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
