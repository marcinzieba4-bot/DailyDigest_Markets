"""Screen July 2024 own-date feeds after complete prefix/daily acquisition (headline-only, conservative).

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
Canonical publisher-date resolution was NOT performed for July 2024 (publisher article vintages remain an editorial limitation): no item is admitted on a resolved
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

DATES = [dt.date(2024, 7, n) for n in range(1, 32) if dt.date(2024, 7, n).weekday() < 5]

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

# The schedule is a pre-authoring safety screen, never a factual report source.
SCHEDULE_PATH=ROOT/'audit_work/july_release_schedule.json'
SCHEDULE=read_json(SCHEDULE_PATH)
RELEASE_GUARDS=[(x['label'],x['eligible_edition'],x['earliest_pub_date'],x['pattern'])for x in SCHEDULE['guards']]
GUARD_META={x['label']:x for x in SCHEDULE['guards']}
NAMED_PATH=ROOT/'audit_work/july_named_source_exclusions.json'
NAMED=read_json(NAMED_PATH)['exclusions']
OBSERVED_COMPANY_PREVIEWS=frozenset([
 'Microsoft (MSFT) Analysis: Volatile Trading Day Signals Resistance, Await Earnings for Clarity - StockInvest.us',
 "The 'great rotation' faces its biggest test yet: earnings from Microsoft, Meta, Apple and Amazon - CNBC",
 'Microsoft’s earnings report will offer a new gauge for AI demand and cloud investments - GeekWire',
])
GUARD_VERSION='jul-2024-release-guards-v1'
SEMANTIC_GUARDS=[('rolling or live market page',re.compile(r'\b(?:live updates|live blog|live coverage|stock market (?:news )?today|markets today|stock market live|as it happened)\b|^LIVE:',re.I)),('advertisement or coupon page',re.compile(r'^Advertisement\b|sponsored content|advertorial|promo code|discount code|coupon code',re.I))]

# A modal in a second clause must not disguise a completed first clause.
COMPLETED = re.compile(r"\b(?:announced|unveiled|approved|confirmed|unchanged|reach|reaches|hit|hits|shrink|shrinks|contract|contracts|rebound|rebounds|rise|fall|surge|slump|jump|gain|gains|grow|grows|cool|cools|ease|eases|moderate|moderates|contraction|expansion|rattles?|rattled|dominates?|dominated|spars?|sparred|clash(?:es)?|clashed|defeats?|vows?|vowed|pledges?|pledged|urges?|urged|promises?|promised|won|elected|president-elect|conceded|defeated|shows|showed|wins|sweeps|swept|secures|secured|closes|closed|ends|ended|lowered|held|kept|reported|surged|accelerated|slowed|beats|beat|misses|missed|tops|topped|rises|rose|falls|fell|jumps|jumped|slumps|slumped|raises|raised|cuts|cut|lowers|holds|keeps|expands|expanded|declines|declined|accelerates|slows|increases|increased|decreases|decreased|drops|dropped)\b|"
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
    r"approve|expand|decline|accelerate|slow|increase|decrease|drop|gain|grow|cool|ease|moderate|reach|hit|shrink|contract|rebound|rattle|dominate|spar|clash|defeat|vow|pledge|urge|promise|release|publish|decide|leave|end|secure|sweep|close|show)\b",re.I)


FINANCIAL_OUTCOME=re.compile(r"\b(?:beats?|miss(?:es|ed)?|tops?|reports?|reported|posts?|posted|cuts?|raises?|lowers?)\b.{0,35}\b(?:earnings|revenue|sales|profit|EPS|guidance|forecasts?|bookings|deliveries|estimates|results)\b|\b(?:earnings|revenue|sales|profit|EPS|guidance|forecasts?|bookings|deliveries|results)\b.{0,35}\b(?:beats?|miss(?:es|ed)?|tops?|rose|fell|rises?|falls?|grows?|grew|surges?|jumps?|slumps?|drops?|declines?|doubles?|triples?|soars?|disappoints?|disappointed|record)\b",re.I)
MARKET_CLAUSE=re.compile(r"\b(?:stocks?|shares?|equities|bonds?|bond yields?|dollar|yen|yuan|gold|oil|markets?)\b[^,;.!?]{0,45}\b(?:rose|fell|rises?|falls?|gains?|jumps?|surges?|slumps?|drops?|declines?)\b",re.I)
POLICY_OUTCOME=re.compile(r"\b(?:Fed|FOMC|Federal Reserve|ECB|Lagarde|BOJ|Bank of Japan|Ueda|RBA|RBNZ|Bank of Canada|PBOC|NBP|RPP|Glapi\w*)\b.{0,45}\b(?:cuts?|hikes?|lifts?|lifted|raises?|holds?|held|keeps?|kept|leaves?|left|lowers?|lowered|unchanged|decides?|agrees?|agreed|announces?|announced)\b|\b(?:rates?|policy|bond.buying)\b.{0,30}\b(?:cut|held|unchanged|raised|hiked|reduced|kept|left)\b",re.I)
ADDITIONAL_FORWARD=re.compile(r'\b(?:before (?:the )?(?:earnings|results|report|decision)|earnings expectations|earnings estimates|looms?|considers?|mulls?|weighs?|could|would|may|might)\b',re.I)

FUTURE_RATE_NOUN=re.compile(r'\b(?:(?:likelihood|chances?|prospect|probability|odds|hopes|expectations|bets) of (?:a |another |the )?|(?:a|an|another|next|possible|potential|expected) )(?:Fed )?(?:rate )?(?:cut|hike)\b',re.I)
SETTLED_UK=re.compile(r'\b(?:is named|was named|has been named|named prime minister|sworn in|has conceded|concedes (?:defeat|the election)|conceded (?:defeat|the election)|appointed prime minister|becomes? (?:Britain[’\']s |the )?prime minister|enters? Downing Street|takes office|takes power)\b',re.I)


MODAL_SUBJECT_ACTION=re.compile(r'\b(?:will|could|would|can|might|may|should)\s+(?:the\s+)?(?:Fed|FOMC|ECB|BOJ|RBA|PBOC|it|they|he|she)\s+(?:rate\s+)?(?:cuts?|hikes?|raises?|holds?|keeps?|reports?|beats?|misses?|tops?|grows?)\b',re.I)
PENDING_POLICY_ACTION=re.compile(r'\b(?:to weigh|to debate|to discuss|to consider|weighs?|considers?|debates?|discusses?|mulls?)\s+(?:(?:an?|the|another)\s+)?(?:rate\s+)?(?:hike|cut|increase|reduction)\b|\b(?:possible|potential|expected|likely|prospective|anticipated)\s+(?:(?:Fed|BOJ|ECB|PBOC)\s+)?(?:rate\s+)?(?:hike|cut|increase|reduction)\b|\b(?:opens?|opening|opened)\s+(?:the\s+)?door\s+to\s+(?:rate\s+)?cuts?\b',re.I)
PENDING_FINANCIAL_CLAUSE=re.compile(r'\b(?:set for|poised for|on track for)\b[^,;.!?]{0,100}\b(?:decline|rise|fall|growth|increase|decrease)\b',re.I)
FINANCIAL_COMPLETION_HINT=re.compile(r'\b(?:earnings|results|revenue|sales|profits?|EPS)\b.{0,30}\b(?:were|was|came in|surprise|surprises|surprised|beat|beats|miss|misses|rose|fell|soars?|doubles?|disappoints?)\b',re.I)

def guard_hit(title,published,stamp):
    """Reject a premature outcome without making a later-clause modal an escape."""
    if title in OBSERVED_COMPANY_PREVIEWS:return None
    normalised=NEUTRALISE.sub('',title)
    for label,eligible,start,pattern in RELEASE_GUARDS:
        if not(stamp<eligible and start<=published<stamp and re.search(pattern,title,re.I)):continue
        kind=GUARD_META[label]['kind']
        if kind=='uk_settled_result':
            future_masked=re.sub(r'\b(?:will|could|may|might|would)\s+(?:be|become)\s+(?:named|sworn in|appointed|prime minister)\b','',title,flags=re.I)
            if SETTLED_UK.search(future_masked):return label
            if stamp>='2024-07-05' and re.search(r'exit.poll|projection|projected',title,re.I) and not re.search(r'official|confirmed|appointed|becomes? prime minister|resigns?',title,re.I):continue
        if kind=='biden_withdrawal':
            if re.search(r'\b(?:not|won.t|will not)\s+(?:drop out|withdraw|quit)|stay(?:ing|s)? in (?:the )?race',title,re.I):continue
            demanded=re.search(r'\b(?:urges?|calls?|pressures?|asks?|wants?|demands?)\b.*Biden.*(?:withdraw|drop|quit|stand|step)',title,re.I)
            declared=re.search(r'Biden\s+(?:(?:has|just|now)\s+)?(?:withdraws|withdrew|withdrawn|drops out|dropped out|quits|ends|steps aside|stands down|announces|announced)|Biden.{0,30}(?:says|said).{0,20}(?:will not seek|won.t seek)|Biden\s+(?:will not seek|won.t seek)',title,re.I)
            if demanded and not declared:continue
            if declared:return label
        if kind=='exit_poll':
            if re.search(r'what to expect|ahead of|will (?:be |show|predict)|due|expected to|to be released',title,re.I)and not re.search(r'exit.poll (?:shows?|predicts?|projects?|forecasts?)',title,re.I):continue
            return label
        if kind=='event':
            question=re.match(r'^\s*(?:Could|Would|Can|Might|May)\b[^?;.!]+\?',title,re.I)
            if question and not COMPLETED.search(title[question.end():]):continue
            if re.search(r'risk of|could cause|may cause|would cause|potential outage|stress test|simulation',title,re.I)and not re.search(r'outage (?:hits?|hit|causes?|caused)|crashes|crashed',title,re.I):continue
            return label
        # Mask only directly governed future actions. Do not erase a completed
        # first clause because another clause forecasts something else.
        outcome_text=FUTURE_RATE_NOUN.sub('',PENDING_FINANCIAL_CLAUSE.sub('',PENDING_POLICY_ACTION.sub('',MODAL_SUBJECT_ACTION.sub('',FORWARD_ACTION.sub('',normalised)))))
        direct_forward=outcome_text!=normalised
        if re.match(r'^\s*(?:what\s+)?if\b',normalised,re.I):
            first=re.split(r'[?;.!]',normalised,maxsplit=1)[0]
            outcome_text=outcome_text.replace(first,'',1)
            direct_forward=True
        calendar_notice=bool(re.search(r'announc\w*.*(?:webcast|conference call|date|schedule)|sets? (?:the )?date|date for .*results',normalised,re.I))
        clear_preview=bool(direct_forward or calendar_notice or EXPLICIT_PREVIEW.search(normalised) or PREVIEW.search(normalised) or ADDITIONAL_FORWARD.search(normalised) or re.search(r'Outlook for|optimism about|before (?:Q[1-4] |quarterly )?(?:earnings|results)|nears? (?:the )?earnings|earnings to (?:reflect|show|test|reveal|shed)|here.s what you need to know|meeting started|(?:earnings|profits?|revenue|sales) (?:seen|expected|forecast) [a-z]+',normalised,re.I))
        if label.startswith('China Q2 GDP')and re.search(r'Penfolds|\bMay\b',title,re.I):continue
        if label.startswith('US Q2 GDP')and re.search(r'largest economies|GDP \(PPP\)',title,re.I):continue
        if label.startswith('US June retail sales') and re.search(r'^Porsche reports',title,re.I):continue
        if kind in{'company_result','company_operation'}:
            # A stock move before earnings is eligible news; it does not report
            # the financial outcome. Actual cuts/beats in another clause fail.
            # Preserve observed separate disclosures/issuer roles, not a future
            # parent-company result: Westlife franchisee, industry EV sales and
            # litigation about streaming-revenue taxation are different events.
            if re.search(r'McDonald',label,re.I)and re.search(r'Westlife|franchisee|India (?:operator|franchise)',title,re.I):continue
            if re.search(r'Tesla Alphabet',label)and re.search(r'EV Sales|electric.vehicle sales',title,re.I)and not re.search(r'earnings|profits?|EPS|guidance|revenue',title,re.I):continue
            if FINANCIAL_COMPLETION_HINT.search(MARKET_CLAUSE.sub('',outcome_text))or FINANCIAL_OUTCOME.search(MARKET_CLAUSE.sub('',outcome_text)):return label
            if re.search(r'court|lawsuit|appeal|tax',title,re.I)and not re.search(r'earnings|results|profits?|EPS|quarter',title,re.I):continue
            if clear_preview:continue
            return label
        if kind=='policy':
            if POLICY_OUTCOME.search(outcome_text):return label
            if clear_preview or FORWARD.search(normalised):continue
            return label
        if COMPLETED.search(MARKET_CLAUSE.sub('',outcome_text)):return label
        if clear_preview or FORWARD.search(normalised):continue
        return label
    return None


def screen(date,raw=None,persist=True):
    stamp=date.isoformat();cutoff=dt.datetime.combine(date,dt.time(),UTC)
    if raw is None:raw=read_json(ROOT/'work/unreviewed_feeds'/(stamp+'.json.gz'))
    assert raw['date']==stamp and dt.datetime.fromisoformat(raw['cutoff_utc'])==cutoff
    assert raw['query_upper_bound_enforced']and not raw['fails'],'harvest incomplete for '+stamp
    ready=[];excluded=[];annotations=[];tightenings=[]
    named={x['id']:x for x in NAMED if x['date']==stamp}
    by_id={x['id']:x for x in raw['items']}
    for n,x in named.items():
        assert n in by_id and all(by_id[n][key]==x[key]for key in['title','published_at','src']),('Named exclusion identity mismatch',stamp,n)
    for item in raw['items']:
        pub=dt.datetime.fromisoformat(item['published_at']);assert cutoff-dt.timedelta(days=WIN[item['cat']])<=pub<cutoff,item['id']
        if item['title']in OBSERVED_COMPANY_PREVIEWS:
            if pub<cutoff-dt.timedelta(days=WIN['news']):
                excluded.append({k:item[k]for k in['id','published_at','src','title']}|dict(guard='Observed pending company preview older than seven days',screen_kind='semantic_age'));continue
            if item['cat']!='news':
                tightenings.append(dict(id=item['id'],from_category=item['cat'],to_category='news',reason='Exact observed pending company preview; semantic seven-day window'))
                item={**item,'cat':'news'}
        if item['id']in named:
            excluded.append(named[item['id']]);continue
        semantic=next((label for label,pattern in SEMANTIC_GUARDS if pattern.search(item['title'])),None)
        label=semantic or guard_hit(item['title'],pub.date().isoformat(),stamp)
        if label:
            excluded.append({k:item[k]for k in['id','published_at','src','title']}|{'guard':label,'screen_kind':'semantic'if semantic else'timing'});continue
        if stamp=='2024-07-05' and re.search(r'exit.poll|projection|projected',item['title'],re.I)and re.search(r'Labour|Starmer|Britain|British|UK',item['title'],re.I):annotations.append(dict(id=item['id'],status='projection wording only; not a settled Friday result or PM appointment'))
        ready.append(item)
    payload={**raw,'items':ready,'canonical_screening':'Canonical publisher vintages not resolved. Exact RSS headlines/pubDate use finite July release-timing guards; no article body is read.','release_guards_version':GUARD_VERSION,'release_schedule_sha256':hashlib.sha256(SCHEDULE_PATH.read_bytes()).hexdigest(),'named_exclusions_sha256':hashlib.sha256(NAMED_PATH.read_bytes()).hexdigest()}
    target=ROOT/'feeds'/(stamp+'.json.gz')
    receipt=dict(date=stamp,status='ready',input_items=len(raw['items']),ready_items=len(ready),excluded_items=len(excluded),excluded_by_guard=dict(Counter(x['guard']for x in excluded)),excluded=excluded,eligible_status_annotations=annotations,category_tightenings=tightenings,ready_path=str(target.relative_to(ROOT)),ready_sha256=hashlib.sha256(json_bytes(payload,True)).hexdigest(),unreviewed_sha256=hashlib.sha256(json_bytes(raw,True)).hexdigest(),release_guards_version=GUARD_VERSION,release_schedule_sha256=hashlib.sha256(SCHEDULE_PATH.read_bytes()).hexdigest(),named_exclusions_sha256=hashlib.sha256(NAMED_PATH.read_bytes()).hexdigest())
    if persist:raise RuntimeError('Use finalize_sources.py: complete request plan, semantic review and all-date physical candidate comparison required')
    receipt['_payload']=payload;return receipt

def main():
    raise SystemExit('Use finalize_sources.py --stage-only, then finalize only after semantic review; ready_feeds never freezes independently')
if __name__=='__main__':main()
