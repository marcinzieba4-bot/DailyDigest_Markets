import urllib.request, urllib.parse, xml.etree.ElementTree as ET, json, os, time, datetime as dt, email.utils, glob, concurrent.futures as cf, random
H={'User-Agent':'Mozilla/5.0'}
OUT='/tmp/claude-0/-home-user/01233cf7-f758-5bad-b280-d38226412ca9/scratchpad/work/pl/feeds'
PL=[('nbp','NBP RPP stopy procentowe'),('cpi','inflacja GUS ceny'),('data','GUS PKB sprzedaż detaliczna produkcja przemysłowa wynagrodzenia'),
    ('gpw','GPW WIG20 sesja giełda'),('pln','złoty kurs EUR/PLN dolar'),('bonds','obligacje skarbowe rentowność Polska'),
    ('fiscal','budżet deficyt dług publiczny Ministerstwo Finansów Domański'),('policy','rząd Tusk ustawa podatki KPO Sejm'),
    ('corp','Orlen PGE PKO BP Pekao Allegro Dino wyniki'),('energy','ceny energii gaz atom Polska energetyka'),
    ('housing','mieszkania kredyt hipoteczny ceny mieszkań'),('geo','Polska Ukraina granica bezpieczeństwo wojsko'),('banks','banki kredyty WIBOR frankowicze')]
EN=[('en_econ','Poland economy'),('en_mkt','Poland zloty NBP rates bonds'),('en_stocks','Polish stocks Warsaw WIG'),('en_geo','Poland Ukraine Russia NATO')]
def rss(q, pl=True):
    hl,gl,ceid=('pl','PL','PL:pl') if pl else ('en-US','US','US:en')
    url=f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl={hl}&gl={gl}&ceid={ceid}"
    for attempt in range(4):
        try:
            raw=urllib.request.urlopen(urllib.request.Request(url,headers=H),timeout=25).read()
            root=ET.fromstring(raw); out=[]
            for it in root.findall('.//item'):
                pd=email.utils.parsedate_to_datetime(it.findtext('pubDate'))
                out.append({'t':pd.astimezone(dt.timezone.utc).strftime('%Y-%m-%d %H:%M'),'src':(it.find('source').text if it.find('source') is not None else ''),'title':it.findtext('title')})
            return out
        except Exception as e:
            time.sleep(2*(attempt+1)+random.random())
    return None
def one(d):
    fn=f'{OUT}/{d}.json'
    if os.path.exists(fn): return d,'cached'
    D=dt.date.fromisoformat(d); after=(D-dt.timedelta(days=8)).isoformat(); before=(D+dt.timedelta(days=1)).isoformat()
    cutoff=f'{d} 17:00'; res={}; fails=[]
    for key,q in PL+EN:
        items=rss(f'{q} after:{after} before:{before}', pl=(key in dict(PL)))
        if items is None: fails.append(key); continue
        items=[x for x in items if x['t']<=cutoff and x['t']>=(D-dt.timedelta(days=7)).isoformat()]
        items.sort(key=lambda x:x['t'],reverse=True)
        res[key]=items
        time.sleep(0.3)
    json.dump({'date':d,'cutoff_utc':cutoff,'fails':fails,'feeds':res},open(fn,'w'),ensure_ascii=False,indent=1)
    return d, f'{sum(len(v) for v in res.values())} items, fails={fails}'
dates=sorted(os.path.basename(f)[:-5] for f in glob.glob('/tmp/claude-0/-home-user/01233cf7-f758-5bad-b280-d38226412ca9/scratchpad/work/edited/*.html'))
with cf.ThreadPoolExecutor(4) as ex:
    for d,msg in ex.map(one,dates): print(d,msg,flush=True)
