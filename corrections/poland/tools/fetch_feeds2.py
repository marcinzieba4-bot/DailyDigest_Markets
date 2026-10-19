import urllib.request, urllib.parse, xml.etree.ElementTree as ET, json, os, time, datetime as dt, email.utils, glob, concurrent.futures as cf, random
H={'User-Agent':'Mozilla/5.0'}
OUT='/tmp/claude-0/-home-user/01233cf7-f758-5bad-b280-d38226412ca9/scratchpad/work/pl/feeds'
PL=[('data_gdp','PKB GUS'),('data_retail','sprzedaż detaliczna'),('data_industry','produkcja przemysłowa'),('data_wages','wynagrodzenia GUS'),
    ('fiscal_deficit','deficyt budżetu'),('fiscal_debt','dług publiczny'),('fiscal_mf','Ministerstwo Finansów'),
    ('banks_credit','banki kredyty'),('wibor','WIBOR'),('chf','frankowicze'),
    ('corp_orlen','Orlen'),('corp_pko','PKO BP'),('corp_kghm','KGHM'),('corp_pge','PGE'),('corp_allegro','Allegro'),('corp_cdp','CD Projekt'),('corp_dino','Dino'),('corp_lpp','LPP'),
    ('energy_prices','ceny energii'),('energy_nuclear','elektrownia jądrowa')]
EN=[('en_zloty','Poland zloty'),('en_bonds','Poland bonds'),('en_wig','Polish stocks')]
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
        except Exception: time.sleep(2*(attempt+1)+random.random())
    return None
def one(d):
    fn=f'{OUT}/{d}.json'; j=json.load(open(fn))
    if 'corp_orlen' in j['feeds']: return d,'cached'
    D=dt.date.fromisoformat(d); after=(D-dt.timedelta(days=8)).isoformat(); before=(D+dt.timedelta(days=1)).isoformat()
    cutoff=j['cutoff_utc']; fails=[]
    for key,q in PL+EN:
        items=rss(f'{q} after:{after} before:{before}', pl=(key in dict(PL)))
        if items is None: fails.append(key); continue
        items=[x for x in items if x['t']<=cutoff and x['t']>=(D-dt.timedelta(days=7)).isoformat()]
        items.sort(key=lambda x:x['t'],reverse=True); j['feeds'][key]=items[:25]
        time.sleep(0.25)
    j['fails']=j.get('fails',[])+fails
    json.dump(j,open(fn,'w'),ensure_ascii=False,indent=1)
    return d, f"{sum(len(j['feeds'][k]) for k,_ in PL+EN if k in j['feeds'])} new items, fails={fails}"
dates=sorted(os.path.basename(f)[:-5] for f in glob.glob(f'{OUT}/*.json'))
with cf.ThreadPoolExecutor(4) as ex:
    for d,msg in ex.map(one,dates): print(d,msg,flush=True)
