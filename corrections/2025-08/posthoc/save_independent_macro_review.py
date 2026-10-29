"""Persist the independent selected review already performed in chat.

Run only after manually reading the selected prose and cited headlines. This is
receipt construction, not an automated claim of semantic verification.
"""
from pathlib import Path
import datetime as dt, gzip, hashlib, importlib.util, json, re

ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location('guard',ROOT/'posthoc/release_guard.py')
guard=importlib.util.module_from_spec(sp);sp.loader.exec_module(guard)
DATES=['2025-08-05','2025-08-06','2025-08-07','2025-08-08','2025-08-12','2025-08-13','2025-08-14','2025-08-15','2025-08-21','2025-08-22']
NOTES={
'2025-08-05':['July jobs aftermath is pre-cutoff. Palantir Aug4 after-close result eligible by Aug5 midnight; Army agreement is customer context, not recognized revenue. China committee and bank losses do not become a fabricated credit boom. Japan wage/hike views and Australia cost-of-living interpretation remain appropriately conditional.'],
'2025-08-06':['July ISM services50.1 is a completedAug5 release. China committee and Ant bond issue are not treated as aggregate lending acceleration. OPEN moves from preview to actual earnings reaction with source-bound attention evidence. Production-narration sentence and missing inline citations were corrected and reread.'],
'2025-08-07':['Fresh Shopify earnings/guidance, large prior-session price move and new ETF access support a distinct retail lead. ETF availability is not presented as measured purchases. OPEN is a shortened earnings-reset carryover; its public production-narration sentence was corrected and reread. RBA/BOE forecasts remain forecasts. SHOP and OPEN selected price/return figures spot-checked against own-date cards.'],
'2025-08-08':['Retail lead now emphasizes freshAug6 Fortune valuation/insider-wealth coverage rather than repeating the earlier earnings event alone. This is indirect public-attention evidence, not a measured platform ranking. Palantir selected price/return figures spot-checked against own-date card. RBA outcome remains pending; US payrolls and China trade observations precede the cutoff.'],
'2025-08-12':['July US CPI actual absent; only CPI preview/forecast evidence admitted. RBA forecast guard n0333 resolved by prose explicitly describing a pending decision. CoreWeave earnings remain pending; Stocktwits hope and analyst target are not a realized result. China July prices were publicAug10, despite an approximateAug9 RSS date.'],
'2025-08-13':['July CPI actual is eligible afterAug12 release. RBA cut is eligible afterAug12. China credit prose does not import theAug13 loan release before midnight. CoreWeave preview is explicitly earlier attention evidence; post-release result discussion is treated separately.'],
'2025-08-14':['July CPI2.7% and firmer core-services coverage were added from own-date n8399/n8723 after a completeness finding and reread. July PPI actual remains excluded. China industrial output story is explicitly a pending forecast; July loan decline is an eligibleAug13 actual. Bessent BOJ view is not a central-bank decision. BLSH debut and retail-facing attention are separate from operating proof.'],
'2025-08-15':['Initial July PPI0.9% and July CPI2.7% are eligible. ChinaAug15 output/retail actuals remain excluded; July loans already known. Japan GDP early-local release occurredAug14 23:50UTC and is eligible beforeAug15 cutoff; this exception was checked against the primary release archive/timing. Micron supply/pricing inference was tightened to the headline-supported AI-demand outlook and reread. OPEN attention is source-bound; forecast transformation language remains a thesis.'],
'2025-08-21':['Fresh July retail-sales evidence and July meeting minutes releasedAug20 inform theUS view; meeting minutes are not described as a new policy decision. ChinaJuly loans and activity are eligible and not replaced by price action. Jackson/Powell speech still pending. OPEN influencer target is explicitly a forecast and activist governance victory is not treated as realized financial upside.'],
'2025-08-22':['Powell JacksonHole speech remains pending; noAug22 speech outcome or actual policy pivot imported. IntelSoftBank investment is completed andUSgovernment equity stake remains prospective. JapanJuly CPI release atAug21 23:30UTC independently corroborated by the pre-eventReutersAug15 poll explicitly stating theUTC conversion, with e-Stat primary release dateAug22JST. HOODsports-market launch, legal attention and generalFutu platform-activity view remain distinct; no fabricated HOODsentiment ranking. SelectedHOOD/INTC prices and returns match own-date card.'],
}

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def flatten(s):
    out={}
    for b in s['geo']:
        for label,text in b['parts']:out['geo:'+b['key']+' / '+label]=text
    for k in ['sectors','underowned','anticipatory','catalysts','retail']:
        for i,b in enumerate(s[k]):
            for label,text in b['parts']:out[f'{k}[{i}] / '+label]=text
    for k in ['earnings_pattern','crypto','flows']:
        for label,text in s[k]['parts']:out[k+' / '+label]=text
    return out

report={'scope':'Independent selected factual, timing, preview-versus-result and retail-attention review; cited headline wording and own-date card spot checks. Not exhaustive article-body, original news-vintage or full-report semantic verification.',
        'reviewer':'macro_evidence agent (author ofAug29 only; none of the reports reviewed here)',
        'strict_information_cutoff':'00:00UTC reportdate, exclusive',
        'source_query_scope':'Queries use7-day fresh-news/previews,14-day company-results and35-day macro/policy-baseline lookbacks. Query labels are approximate semantic categories. Dated persistent policy/program background can be older than7days; this review does not claim every policy citation is less than7days old.',
        'guard_scope':'Narrow primary-release outcome fingerprints and rolling-page exclusions across every cited headline ID; manual release-headline chronology screening supplemented regex. Zero flags is not proof of exhaustive publication-time verification.',
        'reports':{}}
for date in DATES:
    specpath=ROOT/'specs'/f'{date}.json';feedpath=ROOT/'feeds'/f'{date}.json.gz';cardpath=ROOT/'cards'/f'{date}.json'
    s=json.loads(specpath.read_bytes());feed=json.loads(gzip.decompress(feedpath.read_bytes()));ix={x['id']:x for x in feed['items']};alltext=flatten(s)
    selected=['geo:US / Macro Stance','geo:CN / PMIs & Activity','geo:CN / Credit Impulse','geo:JP / Macro Stance','geo:AU / Macro Stance','earnings_pattern / Rewarded','retail[0] / Why Retail Is Here','retail[0] / The Social Signal']
    if date in ['2025-08-07','2025-08-08']:
        selected=['geo:US / Macro Stance','geo:CN / PMIs & Activity','geo:AU / Macro Stance','geo:PL / Fiscal & Politics','earnings_pattern / Rewarded','retail[0] / Why Retail Is Here','retail[0] / What Is Driving It','retail[0] / The Social Signal','retail[1] / Why Retail Is Here']
        selected.append('geo:PL / Macro Stance' if date=='2025-08-07' else 'geo:JP / Macro Stance')
    if date=='2025-08-15':selected.append('geo:PL / Fiscal & Politics')
    if date=='2025-08-21':selected.append('geo:PL / Macro Stance')
    if date=='2025-08-22':
        selected+=['geo:US / New / Most Important','retail[0] / What Is Driving It']
        intel=next(i for i,b in enumerate(s['catalysts']) if b['title'].startswith('$INTC'))
        selected += [f'catalysts[{intel}] / '+lab for lab in ['Catalyst & Thesis','Price Hurdle & Risk','Trade Expression']]
    paragraphs=[]
    for location in selected:
        text=alltext[location]
        paragraphs.append({'location':location,'paragraph_sha256':hashlib.sha256(text.encode()).hexdigest(),'cited_ids':re.findall(r'\[\[(n\d+)\]\]',text),'selected_fidelity_and_timing_passed':True})
    used=sorted(set(re.findall(r'\[\[(n\d+)\]\]',json.dumps(s))));flags=[]
    for n in used:
        findings=guard.screen_item(ix[n],feed['cutoff_utc'])
        if findings['exclude'] or findings['review']:
            flags.append({'id':n,'title':ix[n]['title'],**findings,'editorial_disposition':'Preview explicitly labelled as pending in report; no completed outcome claimed' if date=='2025-08-12' and n=='n0333' else 'Requires reviewer disposition'})
    notes=list(NOTES[date])
    if date in ['2025-08-07','2025-08-08','2025-08-13','2025-08-15','2025-08-21']:
        notes.append('Older policy/projection/program citations were checked as dated background, not fresh outcomes. Root clarified actual35-day macro/policy-baseline query scope in BRIEF/methodology/README. Aug8July BOJ meeting, Aug15earlier-August investment scheme, Aug21earlier-August subsidy and Kotecki view were time-qualified and reread. No assertion that all policy/news labels are perfect semantic classifications.')
    entry={'reviewer':report['reviewer'],'spec_sha256':digest(specpath),'feed_sha256':digest(feedpath),'card_sha256':digest(cardpath),'guard_sha256':digest(ROOT/'posthoc/release_guard.py'),'selected_review_passed':not any(x['exclude'] for x in flags),'selected_paragraph_count':len(paragraphs),'selected_paragraphs':paragraphs,'cited_ids_checked_by_guard':len(used),'guard_flags':flags,'critical_findings':[],'notes':notes,'reviewed_at_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
    report['reports'][date]=entry
    if date in ['2025-08-07','2025-08-08']:
        (ROOT/'audit'/f'independent_aug{date[-2:]}_selected_review.json').write_text(json.dumps({'date':date,'scope':report['scope'],**entry},indent=2)+'\n')
out=ROOT/'checks/independent_review_macro.json';out.write_text(json.dumps(report,indent=2)+'\n')
timing={'scope':'Selected source chronology exceptions checked independently; original complete article bodies and every source vintage not verified.',
        'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'records':[
            {'report_date':'2025-08-22','cited_ids':['n4307','n4308'],'event':'JapanJuly2025 national CPI','release_at_utc':'2025-08-21T23:30:00Z','local_release':'2025-08-22 08:30JST','primary_release_date_url':'https://www.e-stat.go.jp/stat-search/files?layout=datalist&lid=000001463851&page=1','pre_event_utc_timing_corroboration_url':'https://www.reuters.com/en/japans-july-inflation-rate-likely-eased-remained-above-boj-target-2025-08-15/','disposition':'eligible before report00:00UTC despiteAug22Japanese date'},
            {'report_date':'2025-08-15','cited_ids':['n4794'],'event':'Domanski announces work on additional bank taxation','verified_published_local':'2025-08-13 20:10CEST; updated20:55CEST','canonical_url':'https://www.bankier.pl/wiadomosc/Minister-Domanski-zapowiada-podatek-bankowy-Wiemy-ze-sektor-ma-w-tej-chwili-bardzo-wysokie-zyski-8993238.html','disposition':'eligible broad proposal; distinct fromAug21specificCIT rates, which are not imported intoAug15prose'},
        ]}
(ROOT/'audit/independent_macro_source_chronology.json').write_text(json.dumps(timing,indent=2)+'\n')
print('Saved',out,'reports',len(report['reports']))
for date,e in report['reports'].items():print(date,e['spec_sha256'],e['selected_paragraph_count'],len(e['guard_flags']))
