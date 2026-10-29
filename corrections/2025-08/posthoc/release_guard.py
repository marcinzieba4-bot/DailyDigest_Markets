"""Reviewer-only primary-release guards for misdated August2025 news.

These guards use narrow outcome fingerprints. They do not certify article bodies,
and they do not reject a clearly labelled preview solely for naming a release.
The full timeline must not be made available to an earlier-date report writer.

Callable API: screen_item(item, cutoff_utc) -> {exclude: [], review: []}.
CLI: python posthoc/release_guard.py --feed feeds/2025-08-01.json.gz.
The command writes no source feed. --out saves a reviewer audit JSON.
"""
from __future__ import annotations
import argparse, datetime as dt, gzip, json, re
from functools import lru_cache
from pathlib import Path

ROOT=Path(__file__).resolve().parent
PREVIEW=re.compile(r'\b(preview|expects?|expected|forecast(?:s|ed)?|prediction|predicts?|consensus|estimate[sd]?|ahead of|awaits?|due (?:on|this|next|at)|set to|to (?:extend|cut|report)|poll|likely|what to (?:watch|expect)|could|may|might)\b',re.I)
DONE=re.compile(r'\b(reports?|reported|shows?|showed|rose|rises?|falls?|fell|grew|grows?|slows?|slowed|holds?|held|cuts?|cut|confirms?|confirmed|unchanged|revised|revises|adds?|added|says?|said|signals?|signalled|announces?|announced|beats?|misses?|hits?|hits|comes in|came in)\b',re.I)

# A rule only matches when *all* patterns match. Explicit numeric fingerprints
# avoid confusing a preview with a result or a different reference month.
RULES=[
 ('us-july-employment',[r'\b(?:july|jul\.?|payrolls?|jobs?)\b',r'\b73[,.]?000\b|\b73k\b'], 'July employment initial result'),
 ('us-july-employment',[r'\b(?:jobs?|payrolls?|employment)\b',r'\b258[,.]?000\b|\b258k\b',r'\brevis'], 'May/June employment revision'),
 ('ism-july-manufacturing',[r'\bISM\b',r'\bmanufactur',r'\b48(?:\.0)?\b'], 'July ISM manufacturing result'),
 ('ism-july-services',[r'\bISM\b',r'\bservices?\b',r'\b50\.1\b'], 'July ISM services result'),
 ('boe-august-cut',[r'\b(?:BOE|Bank of England)\b',r'\b(?:cuts?|cut|reduces?|reduced)\b',r'\b4(?:\.0+)?\s*%|\b4 per cent'], 'August BOE decision'),
 ('rba-august-cut',[r'\b(?:RBA|Reserve Bank of Australia)\b',r'\b(?:cuts?|cut|reduces?|reduced)\b',r'\b3\.6(?:0)?\b'], 'August RBA decision'),
 ('us-july-cpi',[r'\b(?:US|U\.S\.|United States|American)\b',r'\b(?:July|Jul\.?)\b',r'\b(?:CPI|consumer pric|inflation)'], 'July US CPI realized claim'),
 ('us-july-ppi',[r'\b(?:US|U\.S\.|United States|American)\b',r'\b(?:July|Jul\.?)\b',r'\b(?:PPI|producer pric)',r'\b0\.9\b|\b3\.3\b'], 'July US PPI result'),
 ('china-july-cpi',[r'\bChin',r'\bJuly\b',r'\b(?:CPI|consumer pric|inflation)',r'\b(?:flat|unchanged|zero|0\.0)\b'], 'July China CPI result'),
 ('poland-q2-gdp-flash',[r'\bPol(?:and|ish)\b',r'\bGDP\b|\beconom',r'\b3\.4\b',r'\b(?:Q2|second quarter)\b'], 'Poland Q2 GDP flash result'),
 ('japan-q2-gdp-first',[r'\bJapan',r'\bGDP\b|\beconom',r'\b1\.0\b|\b0\.3\b',r'\b(?:Q2|second quarter)\b'], 'Japan Q2 GDP first result'),
 ('china-july-activity',[r'\bChin',r'\bJuly\b',r'\b(?:output|industrial|retail)\b',r'\b5\.7\b|\b3\.7\b'], 'China July activity result'),
 ('us-july-retail',[r'\b(?:US|U\.S\.|United States|American)\b',r'\bJuly\b',r'\bretail\b',r'\b0\.5\b'], 'US July retail result'),
 ('us-q2-gdp-second',[r'\b(?:US|U\.S\.|United States|American)\b',r'\bGDP\b|\beconom',r'\b3\.3\b',r'\b(?:Q2|second quarter)\b'], 'US Q2 GDP second result'),
 ('nvidia-q2-results',[r'\bNvidia\b|\bNVDA\b',r'\b46\.7\b|\b41\.1\b|\bno H20 sales\b'], 'Nvidia Q2 FY26 results'),
 ('palantir-q2-results',[r'\bPalantir\b|\bPLTR\b',r'\b93\s*%|\b48\s*%|\bfirst billion\b|\b1 billion\b',r'\b(?:revenue|sales|quarter)\b'], 'Palantir Q2 results'),
 ('walmart-q2-results',[r'\bWalmart\b|\bWMT\b',r'\b177\.4\b|\b2\.52\b|\b2\.62\b'], 'Walmart Q2 FY26 results'),
 ('poland-august-cpi-flash',[r'\bPol(?:and|ish)\b',r'\bAugust\b',r'\b(?:CPI|inflation|consumer pric)',r'\b2\.8\b'], 'Poland August CPI flash result'),
 ('china-truce-extension',[r'\bChin',r'\b(?:truce|tariff|trade)\b',r'\b(?:extends?|extended|extension|agrees?|agreed|signs?|signed)\b',r'\b90.day|\bNovember 10\b'], 'US-China truce extension'),
]

def parse(value):
    if isinstance(value,dt.datetime):return value.astimezone(dt.timezone.utc)
    return dt.datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(dt.timezone.utc)

@lru_cache(maxsize=1)
def timeline_by_id():
    return {f['id']:f for f in json.loads((ROOT/'macro_evidence.json').read_text())['facts']}

def screen_item(item,cutoff_utc):
    """Narrow pre-release exclusions; ambiguous fingerprints are review flags.

    Date-only conservative primary releases are safe for the nextUTC date.
    All evidence stays in reviewer-only output; writers see surviving IDs only.
    """
    cutoff=parse(cutoff_utc);title=item.get('title','')
    timeline=timeline_by_id()
    result={'exclude':[],'review':[]}
    rolling=re.search(r'\b(?:live updates|as it happened|stock market today|markets today|live stock (?:price|market)|real.time (?:stock|sentiment)|sentiment (?:score|tracker|dashboard)|(?:stock|share) price today)\b',title,re.I)
    if rolling:
        result['exclude'].append({'event_id':'rolling-page','reason':'Rolling instrument/market/sentiment page cannot establish original headline vintage','matched':rolling.group(0)})
    if re.search(r'\b(?:stock|share) price (?:prediction|forecast)\b',title,re.I):
        result['review'].append({'event_id':'price-forecast-page','reason':'Check whether this is a dated static forecast or a rolling instrument page; never treat target as observed price'})
    if re.search(r'\b(?:Palantir|PLTR)\b',title,re.I) and re.search(r'\bQ3\b',title,re.I) and re.search(r'\b(?:earnings|results)\b',title,re.I) and re.search(r'\b(?:next week|today|tomorrow|this week)\b',title,re.I) and cutoff.month==8:
        result['exclude'].append({'event_id':'inconsistent-reporting-quarter','reason':'Near-term PalantirQ3 earnings claim conflicts with AugustQ2 reporting cycle; original publication date unverified'})
    for event,patterns,label in RULES:
        fact=timeline[event]
        if parse(fact['available_at'])<cutoff:continue
        if not all(re.search(p,title,re.I) for p in patterns):continue
        finding={'event_id':event,'reason':label+' precedes verified release','release_at':fact['available_at'],'primary_source':fact['source_url']}
        # A preview stays eligible, but cannot be used as a realized observation.
        if PREVIEW.search(title):
            finding['reason']+='; explicit preview/forecast language requires editorial treatment'
            result['review'].append(finding)
        elif DONE.search(title) or event in {'us-july-employment','us-july-ppi','ism-july-manufacturing','ism-july-services','nvidia-q2-results'}:
            result['exclude'].append(finding)
        else:result['review'].append(finding)
    # July PCE numerical estimates were public inPowell'sAug22 speech. They
    # cannot be treated as officialBEA data beforeAug29.
    if (re.search(r'\bJuly\b',title,re.I) and re.search(r'\bPCE\b',title,re.I) and re.search(r'\b2\.9\b|\b2\.6\b',title)):
        estimate=timeline['powell-jackson-hole'];official=timeline['us-july-pce-official']
        if parse(estimate['available_at'])>=cutoff:
            finding={'event_id':'powell-jackson-hole','reason':'July PCE estimate fingerprint before verified public Fed estimate','release_at':estimate['available_at'],'primary_source':estimate['source_url']}
            result['review' if PREVIEW.search(title) else 'exclude'].append(finding)
        elif parse(official['available_at'])>=cutoff and not re.search(r'\b(?:Powell|Fed|estimate|forecast)\b',title,re.I):
            result['review'].append({'event_id':'us-july-pce-official','reason':'Only Fed estimates were public; officialBEA July PCE release later','release_at':official['available_at'],'primary_source':official['source_url']})
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--feed',type=Path);ap.add_argument('--out',type=Path);ap.add_argument('--self-test',action='store_true');a=ap.parse_args()
    if a.self_test:
        # The purpose is release-time behavior, not regex implementation parity.
        assert screen_item({'title':'US July payrolls rose 73,000'},'2025-08-01T00:00:00Z')['exclude']
        assert not screen_item({'title':'US July payrolls rose 73,000'},'2025-08-04T00:00:00Z')['exclude']
        assert not screen_item({'title':'US July CPI preview: economists expect core inflation 3.1%'},'2025-08-12T00:00:00Z')['exclude']
        assert screen_item({'title':'US July CPI rose 0.2%, inflation held 2.7%'},'2025-08-12T00:00:00Z')['exclude']
        assert not screen_item({'title':'Fed holds rates 4.25–4.50% at July 30 meeting'},'2025-08-01T00:00:00Z')['exclude']
        assert not screen_item({'title':'China, US to extend tariff pause at Sweden talks by another 90 days, SCMP reports'},'2025-08-01T00:00:00Z')['exclude']
        assert not screen_item({'title':'RBA set to cut rates 25bps to 3.60% on August 12: Reuters poll'},'2025-08-12T00:00:00Z')['exclude']
        assert screen_item({'title':'Nvidia reports revenue of 46.7 billion'},'2025-08-27T00:00:00Z')['exclude']
        assert not screen_item({'title':'Nvidia reports revenue of 46.7 billion'},'2025-08-28T00:00:00Z')['exclude']
        print('Release guard behavior checks passed')
    if a.feed:
        raw=a.feed.read_bytes();feed=json.loads(gzip.decompress(raw) if a.feed.suffix=='.gz' else raw)
        flagged=[]
        for item in feed['items']:
            result=screen_item(item,feed['cutoff_utc'])
            if result['exclude'] or result['review']:flagged.append({'id':item['id'],'title':item['title'],**result})
        report={'date':feed['date'],'cutoff_utc':feed['cutoff_utc'],'items_checked':len(feed['items']),'flagged':flagged,'exclude_count':sum(bool(x['exclude']) for x in flagged),'review_count':sum(bool(x['review']) for x in flagged)}
        if a.out:a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
if __name__=='__main__':main()
