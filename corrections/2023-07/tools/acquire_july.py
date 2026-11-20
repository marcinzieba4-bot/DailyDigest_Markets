#!/usr/bin/env python3
"""July 2023 own-cutoff historical headline acquisition. Python 3 standard library.
Run: python acquire_july.py --root /workspace/work/july-2023-editions/news --workers 18
All times UTC. Source is the headline, not an article body. Every report is presented with coverage diagnostics.
"""
from __future__ import annotations
import argparse, concurrent.futures as cf, datetime as dt, email.utils, gzip, hashlib, html, json, os, re, sys, threading, time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

UTC=dt.timezone.utc
DATE=dt.date.fromisoformat
DATES=[dt.date(2023,7,d) for d in range(1,32) if dt.date(2023,7,d).weekday()<5]
WINDOW={'news':7,'result':14,'monthly':35}
# Queries use names and themes that were known before July; independent of winners during the month.
CATALOGUE={
'us_macro|news': ['US stocks bond yields','Wall Street stock market closes','Treasury yields dollar US economy','Federal Reserve inflation interest rates','S&P 500 Nasdaq earnings','US stock market breadth small caps'],
'us_macro|monthly': ['US June economic data ISM PMI manufacturing','Federal Reserve interest rates Powell','US inflation CPI PCE','US payrolls unemployment labor market','US GDP consumer spending housing retail sales'],
'europe|news': ['European stocks ECB inflation','Europe STOXX 600 Germany euro economy','Europe banks credit lending energy crisis'],
'europe|monthly': ['ECB interest rates bank lending survey','eurozone inflation PMI GDP Germany Ifo'],
'china|news': ['China economy stimulus consumption Beijing','China property developers Evergrande Country Garden','China stocks CSI 300 Hang Seng yuan','PBOC China credit loans', 'China trade exports semiconductor policy'],
'china|monthly': ['China GDP industrial production retail sales','China Caixin PMI manufacturing services PMI','China new yuan loans credit property investment','China exports imports inflation PPI CPI'],
'japan|news': ['Japan stocks Nikkei yen Bank of Japan','Japan yields yield curve control wages'],
'japan|monthly':['Japan industrial production retail sales Tankan','Japan inflation CPI Bank of Japan'],
'australia|news':['Australian economy Reserve Bank Australian dollar','ASX miners iron ore Australia bank'],
'australia|monthly':['Australia CPI inflation employment RBA cash rate'],
'poland_pl|news':['GPW WIG20 sesja giełda','polska gospodarka złoty obligacje','RPP NBP stopy procentowe inflacja Polska','Sejm budżet wybory KPO Polska','Polska Ukraina bezpieczeństwo zboże','GPW spółki wyniki banki kredyty','PKO Pekao mBank Santander Polska','KGHM Orlen PGE JSW','Kęty LPP Allegro CD Projekt'],
'poland_pl|monthly':['GUS inflacja produkcja przemysłowa sprzedaż detaliczna','Polska PMI przemysł inflacja bazowa NBP'],
'poland_en|news':['Poland economy stocks zloty Poland Ukraine'],
'earnings|result':['companies quarterly earnings revenue profit','company quarterly earnings banking financial results','technology earnings semiconductor chip quarterly results','quarterly earnings autos industrial manufacturers','consumer retail quarterly earnings results','pharmaceutical health quarterly earnings results','energy oil earnings quarterly results'],
'sectors|news':['technology stocks chipmakers Nvidia Microsoft AI','communications media advertising Disney Alphabet Meta','financial sector stocks banks credit earnings','oil prices OPEC energy stocks Exxon Chevron','industrial stocks airlines Boeing GE Caterpillar','consumer discretionary Tesla GM Ford homebuilders','consumer staples stocks food prices Procter Gamble','healthcare stocks drugs hospitals insurance','materials stocks copper chemicals steel miners','real estate REITs mortgage rates commercial property','utilities stocks electric power demand','European autos Volkswagen BMW Stellantis Renault','semiconductors ASML TSMC Intel Samsung'],
'capital_flows|news':['fund flows equities bonds money markets Lipper EPFR','investment grade high yield credit spreads Treasury yields','US Treasury auction dollar funding liquidity','ETF inflows ETF outflows fund investors'],
'crypto|news':['Bitcoin cryptocurrency market Ether altcoins','crypto exchange regulation Coinbase SEC XRP Ripple','bitcoin ETF crypto trading volumes stablecoin'],
'retail|news':['retail traders most traded stocks retail investors','meme stocks retail investors short interest trading','WallStreetBets most mentioned stocks Stocktwits','Fidelity most traded stocks retail buy sell orders','options volume unusual options activity Cboe stocks','US individual stock movers short squeeze','Robinhood retail investors most-active stocks'],
'geopolitics|news':['Russia Ukraine grain Black Sea energy exports','US China export controls technology trade','NATO EU Poland Ukraine security'],
'calendar|news':['economic calendar week ahead Federal Reserve ECB BoJ','stock market upcoming earnings week ahead']
}
CATALOGUE={k:v for k,v in CATALOGUE.items()}
STOCKS={'technology':['Apple','Microsoft','Amazon','Alphabet','Meta Platforms','Nvidia','Intel','AMD','ASML','TSMC','Texas Instruments','Qualcomm','Netflix'],
'financial':['JPMorgan','Wells Fargo','Bank of America','Citigroup','Goldman Sachs','BlackRock','American Express','Visa','Mastercard'],
'cyclical':['Tesla','General Motors','Ford','Boeing','General Electric','Honeywell','Union Pacific','Delta Air Lines','United Airlines','Southwest Airlines','RTX','3M'],
'consumer_health':['Coca-Cola','PepsiCo','McDonald’s','Procter & Gamble','Nike','Johnson & Johnson','UnitedHealth','AbbVie','Bristol Myers'],
'international':['LVMH','Volkswagen','BMW','Stellantis','Adidas','Shell','TotalEnergies','Barclays','Deutsche Bank','UBS']}
for key,names in STOCKS.items():
    for lo in range(0,len(names),3):
        CATALOGUE.setdefault('earnings_'+key+'|result',[]).append('('+' OR '.join('"'+n+'"' for n in names[lo:lo+3])+') (results OR earnings OR profit)')
ROLL=re.compile(r'\b(?:live updates?|live blog|as it happened|stocks? market today|stock market today|markets today|prices? today|sponsored content|press release distribution|stocks to buy (?:in|now)|price prediction for|forex signals)\b',re.I)
PREVIEW=re.compile(r'\b(?:preview|next week|week ahead|what to expect|to report|set to (?:report|release|announce)|will report|earnings calendar|ahead of|expected to (?:report|increase|raise|fall))\b',re.I)
OUTCOME=re.compile(r'\b(?:reported|rose|fell|increased|raised|cut|jumped|declined|announced|beat|missed|held|surged|spiked|unveiled|approved|unchanged|slowed|eased|soared|dropp?ed|grew|expands?|raises?|launches?|rallies|jumps?|cuts|slumps?|falls?|agrees?|rules?|wins?|wyniosł|spadł|wzro[sś])',re.I)
# Only outcome signatures for identifiable July releases. Dates are the *first admissible UTC calendar day*.
# Generic mixtures and unchecked release references require author inspection even if this screen passes.
GUARDS=[
 ('2023-07-03',r'Tesla',r'(466[,.]?140|record.{0,24}deliveries|deliveries.{0,35}record)'),
 ('2023-07-04',r'Rivian',r'(12[,.]?640|13[,.]?992|deliveries.{0,36}(?:beat|jump|record|surge))'),
 ('2023-07-05',r'(RBA|Reserve Bank of Australia)',r'(?:(?:holds?|keeps?|pauses?).{0,32}(?:July|4\.10)|(?:July|4\.10).{0,20}(?:hold|pause))'),
 ('2023-07-07',r'(ADP|private payrolls)',r'497[,.]?000|497k'),
 ('2023-07-08',r'(nonfarm|payrolls|jobs report|US jobs)',r'209[,.]?000|209k'),
 ('2023-07-13',r'(CPI|inflation|consumer prices)',r'(June.{0,75}3(?:\.0)?%|3(?:\.0)?%.{0,75}June|two.year low.{0,40}June)'),
 ('2023-07-14',r'(Ripple|XRP)',r'(judge.{0,40}(rules|sides|rejects)|court.{0,35}(win|victory|ruling)|relist|not a security|partial victory)'),
 ('2023-07-15',r'(JPMorgan|Wells Fargo|Citigroup)',r'(?:earnings|profit|revenue|results).{0,25}(?:beat|jump|top|surge)|(?:beat|top).{0,18}estimate'),
 ('2023-07-18',r'(China|Chinese)',r'(6\.3%|0\.8%).{0,60}(?:GDP|growth|quarter)|(?:GDP|growth|quarter).{0,60}(6\.3%|0\.8%)'),
 ('2023-07-20',r'(Carvana|CVNA)',r'(debt (?:deal|restructur|exchange)|bondholder.{0,24}deal|restructur.{0,12}debt)'),
 ('2023-07-20',r'(Tesla|Netflix)',r'(Q2|second.quarter|quarterly).{0,60}(earnings|margin|beat|report|subscriber)|(?:earnings|margin|subscriber).{0,60}(Q2|second.quarter)'),
 ('2023-07-22',r'(AMC|APE units)',r'(judge.{0,28}(blocks|rejects)|settlement.{0,20}(rejected|blocked))'),
 ('2023-07-25',r'(China|Chinese|Politburo)',r'(Politburo.{0,60}(pledges|vows|signals)|property.{0,25}policy.{0,28}(pledge|eases))'),
 ('2023-07-26',r'(Alphabet|Microsoft)',r'(quarterly|second.quarter|Q2|fiscal fourth.quarter).{0,40}(profits?|revenue|earnings|results).{0,25}(beat|top|r[i o]se|jump)'),
 ('2023-07-27',r'(Federal Reserve|FOMC|\bFed\b)',r'5\.(?:25.{0,10}5\.50|5(?:0)?%)|(?:July|22.year high).{0,42}(?:hikes?|raises?)|(?:hikes?|raises?).{0,42}(?:July|22.year high)'),
 ('2023-07-27',r'(Volkswagen|VW|XPeng|Xpeng|XPEV)',r'(700 million|\$700m|stake in XPeng|invest.{0,30}XPeng|Volkswagen.{0,36}(buys|stake))'),
 ('2023-07-27',r'(Australia|Australian)',r'(6\.0%|6 per cent).{0,45}(?:June quarter|inflation)|(?:June quarter|inflation).{0,45}(6\.0%|6 per cent)'),
 ('2023-07-28',r'(US|U\.S\.|American|GDP|economy)',r'(?:Q2|second.quarter|GDP).{0,45}2\.4%|2\.4%.{0,45}(?:Q2|second.quarter|GDP)'),
 ('2023-07-28',r'(ECB|European Central Bank)',r'(?:July|3\.75%|deposit rate).{0,45}(hikes?|raises?)|(?:hikes?|raises?).{0,45}3\.75%'),
 ('2023-07-28',r'(Intel|Enphase|Ford)',r'(Q2|second.quarter).{0,35}(results|earnings).{0,30}(beat|miss|jump|drop)|unexpected profit'),
 ('2023-07-29',r'(Bank of Japan|BOJ|Ueda)',r'(loosens|tweaks|relaxes|flexib).{0,40}(yield|curve|cap)|(yield|curve|cap).{0,40}(flexib|loosens|tweaks|relaxes)'),
 ('2023-07-29',r'(PCE|US inflation|personal consumption)',r'(?:June|PCE).{0,45}(3\.0%|4\.1%)|(?:3\.0%|4\.1%).{0,45}(?:June|PCE)'),
]
GUARDS=[(DATE(d),re.compile(a,re.I),re.compile(b,re.I)) for d,a,b in GUARDS]
# A report may be indexed with an earlier datestamp than the event it describes.
# Anchor unscheduled effects and colloquial variants in addition to named release clocks.
JULY_MORE=[
 ('2023-07-04',r'(US|U\.S\.|ISM)',r'(ISM|factory activity|manufacturing).{0,45}(46\.0|eight.month contraction)|46\.0.{0,45}(ISM|manufacturing)'),
 ('2023-07-06',r'(Federal Reserve|FOMC|\bFed\b)',r'(June|meeting).{0,30}minutes.{0,25}(show|reveal|signal|indicate)|minutes.{0,30}(show|reveal).{0,35}(June|hike|rate)'),
 ('2023-07-06',r'(Meta|Zuckerberg|Threads)',r'(Threads.{0,45}(launches|downloads|sign.?ups|million users)|(?:launches|releases).{0,15}Threads)'),
 ('2023-07-10',r'(Nasdaq|Nasdaq.100)',r'(special rebalanc.{0,40}(announce|cut|reduce)|announc.{0,45}special rebalanc)'),
 ('2023-07-13',r'(Bank of Canada|BoC)',r'(hikes?|raises?|increases?).{0,30}5%|5%.{0,28}(hike|raise)'),
 ('2023-07-14',r'(US|U\.S\.|producer prices|PPI)',r'(producer prices|PPI).{0,45}(0\.1%|0\.1 percent).{0,28}June|June.{0,35}(PPI|producer prices).{0,40}0\.1%'),
 ('2023-07-18',r'(Black Sea|grain deal|grain export)',r'(Russia|Moscow|Kremlin).{0,40}(exits|ends|pulls out|suspends|withdraws|halts).{0,35}(deal|pact|agreement)'),
 ('2023-07-19',r'(Bank of America|Morgan Stanley|Lockheed Martin)',r'(second.quarter|quarterly|Q2).{0,60}(profit|earnings|revenue).{0,25}(beat|jump|rise|grew|fall|fell|top)|(?:profit|earnings|revenue).{0,30}beats?.{0,10}estimate'),
 ('2023-07-20',r'(UK|British|Britain)',r'(CPI|inflation).{0,40}(7\.9%|7\.9 per cent)|7\.9%.{0,28}(CPI|inflation)'),
 ('2023-07-21',r'(TSMC|Taiwan Semiconductor|Johnson & Johnson)',r'(cuts.{0,25}(?:forecast|outlook|guidance)|(?:Q2|second.quarter).{0,50}(?:profit|earnings).{0,30}(?:fell|beat|rise|drop))'),
 ('2023-07-24',r'(Barbie|Oppenheimer|Barbenheimer)',r'(opening|open).{0,45}(?:\$15[0-9]|\$8[0-9]|box.office record)|(?:\$15[0-9]|\$8[0-9]).{0,38}(opening|box office)'),
 ('2023-07-25',r'(AMC|APEs?)',r'(narrowed release.{0,40}(objection|class)|resume.{0,30}settlement review)'),
 ('2023-07-26',r'(IMF|International Monetary Fund)',r'(raises?|upgrades?).{0,30}(?:2023|growth).{0,30}(3\.0|3%)'),
 ('2023-07-27',r'(Meta|Facebook)',r'(second.quarter|Q2|quarterly).{0,55}(earnings|revenue|profit).{0,30}(beat|rise|jump|grow|surge)|(?:earnings|sales|revenue).{0,15}beat.{0,20}estimate'),
 ('2023-07-28',r'(Japan|Japanese|Tokyo)',r'(Tokyo.{0,60}(?:3\.0%|3 percent).{0,35}July|July.{0,45}Tokyo.{0,55}3\.0%)'),
 ('2023-07-31',r'(Japan|Japanese|METI)',r'(industrial (?:production|output).{0,55}(2\.0%|2 percent|2%)|(?:2\.0%|2 percent).{0,45}industrial (?:production|output)).{0,45}June|June.{0,75}industrial (?:production|output).{0,45}(2\.0%|2 percent|2%)'),
 ('2023-08-01',r'(Poland|GUS|Polska|inflacja)',r'(Polish|Poland|GUS|inflacja).{0,60}(10\.8%|10,8 proc)|(?:10\.8%|10,8 proc).{0,40}(July|lipc)'),
 ('2023-08-01',r'(euro.?zone|euro area|Eurostat)',r'(5\.3%).{0,30}(July|inflation)|(?:July|inflation).{0,45}5\.3%'),
]
GUARDS+= [(DATE(d),re.compile(a,re.I),re.compile(b,re.I)) for d,a,b in JULY_MORE]

def rejected(title, cutoff, published):
    if ROLL.search(title): return 'rolling_or_promotion'
    for eligible,subject,outcome in GUARDS:
        if cutoff<eligible and subject.search(title) and outcome.search(title):
            if PREVIEW.search(title) and not OUTCOME.search(title): continue
            return 'premature_outcome_'+eligible.isoformat()
    return None
def pack(obj):
    return gzip.compress(json.dumps(obj,ensure_ascii=False,separators=(',',':'),sort_keys=True).encode(),mtime=0)
def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+str(os.getpid())+'.'+str(threading.get_ident())+'.tmp')
    temp.write_bytes(data); os.replace(temp,path)
def parse_date(value):
    try: return email.utils.parsedate_to_datetime(value).astimezone(UTC)
    except (ValueError,TypeError,OverflowError,AttributeError): return None
def request(topic,query,cat,d,lo,hi,root):
    lang,gl,ceid=('pl','PL','PL:pl') if topic=='poland_pl' else ('en-US','US','US:en')
    args={'q':query+' after:'+(lo-dt.timedelta(days=1)).isoformat()+' before:'+hi.isoformat(),'hl':lang,'gl':gl,'ceid':ceid}
    url='https://news.google.com/rss/search?'+urlencode(args)
    sig=hashlib.sha256(url.encode()).hexdigest()
    path=root/'rss_cache'/sig[:2]/(sig+'.xml.gz')
    from_cache=path.exists(); errors=[]
    tree=None
    for attempt in range(3):
        try:
            if from_cache: raw=gzip.decompress(path.read_bytes())
            else:
                req=Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; historical research RSS client)','Accept':'application/rss+xml, application/xml, text/xml'})
                with urlopen(req,timeout=12) as response: raw=response.read()
            tree=ET.fromstring(raw)
            if tree.tag!='rss' or tree.find('channel') is None: raise ValueError('non-RSS response')
            if not from_cache: write(path,gzip.compress(raw,mtime=0))
            break
        except Exception as exc:
            errors.append(f'{type(exc).__name__}: {str(exc)[:170]}')
            if from_cache: from_cache=False
            if attempt<2: time.sleep(.4*(attempt+1))
    rows=[]
    if tree is not None and tree.tag=='rss' and tree.find('channel') is not None:
        for n in tree.findall('./channel/item'):
            source=n.find('source'); pub=parse_date(n.findtext('pubDate')); link=(n.findtext('link') or '').strip()
            original=html.unescape(n.findtext('title') or '').strip()
            name=(source.text or '').strip() if source is not None else ''
            sourceurl=source.get('url','') if source is not None else ''
            if not name or not link.startswith(('https://','http://')) or not pub or not original: continue
            title=original.removesuffix(' - '+name).strip()
            if not lo<=pub.date()<hi: continue
            rows.append(dict(title=title,src=name,source_url=sourceurl,domain=urlparse(sourceurl).hostname or '',url=link,published_at=pub.isoformat(),lang=lang,cat=cat,topics=[topic],q=query,queries=[query],signatures=[sig]))
        raw_count=len(tree.findall('./channel/item'))
        return rows,dict(signature=sig,topic=topic,query=query,category=cat,lo=str(lo),hi=str(hi),raw=raw_count,eligible=len(rows),status='fetched',errors=errors,source=url)
    return [],dict(signature=sig,topic=topic,query=query,category=cat,lo=str(lo),hi=str(hi),raw=0,eligible=0,status='failed',errors=errors,source=url)
def collect(job,root):
    topic,query,cat,d=job
    # Each final report uses only its own bounded root requests or their subdivisions.
    lo=d-dt.timedelta(days=WINDOW[cat]); batches=[]; receipts=[]
    todo=[(lo,d)]
    while todo:
        start,end=todo.pop()
        items,receipt=request(topic,query,cat,d,start,end,root)
        receipts.append(receipt); batches.extend(items)
        if receipt['raw']>=100:
            if (end-start).days>1:
                mid=start+(end-start)//2
                todo.extend([(start,mid),(mid,end)])
            else: receipt['unresolved_cap']=True
    return batches,receipts
def publish(d,root,rows,receipts,expected):
    records={};excluded=Counter();cut=dt.datetime.combine(d,dt.time(),UTC)
    for item in rows:
        pub=dt.datetime.fromisoformat(item['published_at'])
        cat=item['cat']; t=item['title']
        if PREVIEW.search(t):cat='news'
        if cat=='result' and not re.search(r'\b(?:earnings|results|quarter|quarterly|profit|revenue|sales|income|EPS|margin|subscriber|deliveries|Q[1-4]|reported)\b',t,re.I):cat='news'
        if cat=='monthly' and not re.search(r'GDP|PMI|CPI|PCE|ISM|GUS|inflation|inflacja|employment|payroll|bezrob|unemploy|rates|loans|lending|sales|production|manufactur|retail|trade|exports|imports|produkc|sprzeda|Tankan|industrial|credit|consumer|housing',t,re.I):cat='news'
        if not cut-dt.timedelta(days=WINDOW[cat])<=pub<cut: excluded['semantic_age']+=1;continue
        reason=rejected(t,d,pub)
        if reason:excluded[reason]+=1;continue
        key=(item['src'].casefold(),t.casefold(),item['published_at'])
        if key in records:
            o=records[key]
            for k in ('topics','queries','signatures'):o[k]=sorted(set(o[k]+item[k]))
            if WINDOW[cat]<WINDOW[o['cat']]:o['cat']=cat
        else: records[key]={**item,'cat':cat}
    items=sorted(records.values(),key=lambda x:(x['published_at'],x['src'],x['title']))
    for n,x in enumerate(items,1):
        x['id']=f'n{n:04d}'
    domains=sorted(set(x['domain'] for x in items if x['domain']))
    fails=[r for r in receipts if r['status']!='fetched']
    caps=[r for r in receipts if r.get('unresolved_cap')]
    status=('screened_own_cutoff' if len(items)>=50 and not fails else 'partial_acquisition')
    data=dict(date=d.isoformat(),cutoff_utc=cut.isoformat(),items=items,source_domains=domains,status=status,
              headline_only=True,query_upper_bound_enforced=True,release_screen='known July outcome signatures; remaining items require own-date editorial review',
              acquisition_limits={'failed_requests':len(fails),'unresolved_caps':len(caps),'expected_root_queries':expected})
    if caps and status=='screened_own_cutoff': data['status']='screened_with_unresolved_caps'
    audit=dict(date=d.isoformat(),cutoff_utc=cut.isoformat(),items=len(items),domains=len(domains),publishers=len({r['src'] for r in items}),counts_by_topic=dict(Counter(t for x in items for t in x['topics'])),exclusions=dict(excluded),requests=receipts,status=data['status'])
    out=pack(data)
    audit['feed_sha256']=hashlib.sha256(out).hexdigest()
    # Only label an edition frozen if a checked repeat is byte-identical. A configurable
    # working profile has its own output root so it cannot overwrite a completed profile.
    dest=root/'feeds'/(str(d)+'.json.gz')
    if dest.exists() and dest.read_bytes()!=out:
        prior=json.loads(gzip.decompress(dest.read_bytes()))
        if prior.get('status')!='partial_acquisition': raise ValueError(f'refusing to replace stable feed for {d}')
    write(dest,out)
    write(root/'audit'/(str(d)+'.json.gz'),pack(audit))
    index=[{k:x[k] for k in ('id','published_at','src','domain','title','url','topics','cat')} for x in items]
    write(root/'headlines'/(str(d)+'.json.gz'),pack(index))
    print(f'{d} {data["status"]}: {len(items)} headlines, {len(domains)} domains, {len(fails)} failed, {len(caps)} unresolved caps',flush=True)
def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--workers',type=int,default=16);p.add_argument('--dates',nargs='*');p.add_argument('--profile',choices=['full','quick'],default='full');p.add_argument('--unrefined',action='store_true',help='Explicit exploratory profile: report every capped root as unresolved for early source discovery. Use a separate output root.');args=p.parse_args()
    ds=[DATE(x) for x in args.dates] if args.dates else DATES
    if any(d not in DATES for d in ds):p.error('choose a July 2023 weekday')
    for d in ds:
        jobs=[]
        for key,queries in CATALOGUE.items():
            topic,cat=key.split('|')
            for q in (queries if args.profile=='full' else queries[:(3 if topic in {'poland_pl','china','retail','sectors'} else 2)]):
                jobs.append((topic,q,cat,d))
        if args.unrefined:
            def runner(j):
                t,q,c,d=j;items,r=request(t,q,c,d,d-dt.timedelta(days=WINDOW[c]),d,args.root)
                if r['raw']>=100:r['unresolved_cap']=True
                return items,[r]
        else:
            def runner(j):return collect(j,args.root)
        rows=[];receipts=[]
        with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
            for batch,rr in pool.map(runner,jobs):rows.extend(batch);receipts.extend(rr)
        publish(d,args.root,rows,receipts,len(jobs))
if __name__=='__main__':main()
