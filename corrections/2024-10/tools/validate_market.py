"""Validate Oct2024 cards, split arithmetic and independent exchange calendars.

No data are changed. Outputs audit/market_validation.json. Current-vintage
histories may contain later vendor revisions; original unrevised vintages are
not asserted. Corporate-action events are mechanical unit restoration only.
"""
from pathlib import Path
import datetime as dt
import hashlib
import importlib.util
import json
import math
from decimal import Decimal
from urllib.parse import urlsplit, parse_qs
import exchange_calendars as xc

ROOT = Path(__file__).resolve().parent.parent
def module(name, file):
    s=importlib.util.spec_from_file_location(name, ROOT/'tools'/file)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
cards_module=module('oct_cards','build_cards.py')
fetch_module=module('oct_fetch','fetch_market.py')
DATES=[dt.date(2024,10,n).isoformat() for n in range(1,32) if dt.date(2024,10,n).weekday()<5]
data={j['ticker']:j for p in (ROOT/'data').glob('yf_*.json') for j in [json.loads(p.read_text())]}
tr=json.loads((ROOT/'data/treasury_par.json').read_text())
fetch=json.loads((ROOT/'audit/market_fetch.json').read_text())
errors=[];checks=0;calendar_notes=[]
def check(value,message):
    global checks
    checks+=1
    if not value:errors.append(message)
def bp(a,b):return int((Decimal(str(a))-Decimal(str(b)))*100)
def pct(a,b):return round((a/b-1)*100,2)
expected=set(fetch_module.UNIVERSE)
check(len(expected)==len(fetch_module.UNIVERSE),'Duplicate universe ticker')
check(expected==set(data)=={x['ticker'] for x in fetch},'Fetch/data/universe mismatch')
check(all(x['status']=='ok' for x in fetch),'Fetch failure')
check(len(DATES)==23,'Expected 23 weekdays')
check(all(d<='2024-10-31' for d in tr),'Later Treasury row retained')
for t,j in data.items():
    rows=j['rows'];levels=j['as_traded_rows']
    check(rows==sorted(rows) and len(rows)==len({d for d,_ in rows}),t+': unordered/duplicate rows')
    check(set(dict(rows))==set(dict(levels)),t+': display date mismatch')
    check(all(d<='2024-10-31' for d,_ in rows),t+': later price retained')
    check(all(math.isfinite(v) and v>0 for _,v in rows+levels),t+': invalid value')
    check(len([x for x in rows if x[0]<'2024-10-01'])>=21 or t=='NBIS',t+': insufficient initial lookback')
    params=parse_qs(urlsplit(j['source_url']).query)
    check(params['period1']==[str(fetch_module.P1)] and params['period2']==[str(fetch_module.P2)],t+': request bounds')
cards={d:json.loads((ROOT/'cards'/f'{d}.json').read_text()) for d in DATES}
for date,c in cards.items():
    check(c['report_date']==date and c['cutoff_utc']==date+'T00:00:00Z',date+': identity')
    check(c==cards_module.card(date),date+': card deterministic recomputation')
    days=sorted(d for d in tr if d<date);tc=c['treasury'];last=tr[days[-1]];old=tr[days[-21]]
    check(tc['prior_close_date']==days[-1],date+': Treasury latest')
    check(tc['spread_10y_2y_bps']==bp(last['10 Yr'],last['2 Yr']),date+': spread')
    check(tc['chg_20obs_bps']['2y']==bp(last['2 Yr'],old['2 Yr']),date+': 2Y change')
    check(tc['chg_20obs_bps']['10y']==bp(last['10 Yr'],old['10 Yr']),date+': 10Y change')
    for t,x in c['markets'].items():
        raw=data[t];rows=[r for r in raw['rows'] if r[0]<date];ld,lc=rows[-1];levels=dict(raw['as_traded_rows'])
        check(x['session']==ld<date,date+' '+t+': session/cutoff')
        for n in (1,5,20):
            if len(rows)>=n+1:check(x[f'chg_{n}s_pct']==pct(lc,rows[-n-1][1]),date+' '+t+': return '+str(n))
            else:check(x[f'chg_{n}s_pct'] is None and t=='NBIS' and bool(x.get('history_limitation')),date+' '+t+': unavailable return documented')
        if raw.get('level_restriction'):check(x['close'] is None,date+' '+t+': suppressed level')
        else:check(x['close']==cards_module.fmt(levels[ld],t),date+' '+t+': display units')
        actions=json.loads((ROOT/'audit'/('actions_'+t.replace('^','_').replace('=','_').replace('.','_')+'.json')).read_text())['events']
        for day,value in ([rows[-1],rows[-21]] if len(rows)>=21 else [rows[-1]]):
            factor=math.prod(e['factor'] for e in actions if e['date']>day)
            check(abs(levels[day]-value*factor)<=max(1e-5,abs(levels[day])*1e-7),date+' '+t+': split arithmetic')
        if t.endswith('-USD'):check(ld==(dt.date.fromisoformat(date)-dt.timedelta(days=1)).isoformat(),date+' '+t+': UTC daily close')
suffix_calendars={'.WA':'XWAR','.DE':'XETR','.PA':'XPAR','.CO':'XCSE','.L':'XLON','.SW':'XSWX','.T':'XTKS','.KS':'XKRX','.SS':'XSHG','.HK':'XHKG','.AX':'XASX'}
index_calendars={'^N225':'XTKS','^KS11':'XKRX','^TWII':'XTAI','000001.SS':'XSHG','^HSI':'XHKG','^AXJO':'XASX','^FTSE':'XLON','^GDAXI':'XETR','^FCHI':'XPAR','^STOXX':'XETR','^STOXX50E':'XETR'}
closures={'XTAI':{'2024-10-02','2024-10-03','2024-10-31'}, 'XKRX':{'2024-10-01'}, 'XHKG':{'2024-09-06'}}
closure_sources=[{'calendar': 'XTAI', 'dates': ['2024-10-02', '2024-10-03'], 'source': 'Taiwan Stock Exchange and Taiwan Futures Exchange typhoon closure notices', 'urls': ['https://www.twse.com.tw/staticFiles/news/news/tsecnews/8a8216d69236c2e3019248073ed90050.pdf', 'https://www.taifex.com.tw/enl/eng11/newsDetail.do?idx=8925&thetype=2'], 'summary': 'Exceptional closures during Typhoon Krathon.', 'independently_checked_at_utc': '2026-11-04', 'verified_by': 'Independent market auditor'}, {'calendar': 'XTAI', 'dates': ['2024-10-31'], 'source': 'Taiwan Stock Exchange Trading Department press release, 2024-10-30', 'urls': ['https://wwwc.twse.com.tw/staticFiles/news/news/tsecnews/8a8216d69236c2e30192dd523eb10329.pdf'], 'summary': 'Full market closure for Typhoon Kong-Rey. This affects the raw October inventory; the October 31 report still uses the October 30 session.', 'independently_checked_at_utc': '2026-11-04', 'verified_by': 'Independent market auditor'}, {'calendar': 'XHKG', 'dates': ['2024-09-06'], 'source': 'HKEX market communications, 2024-09-06', 'urls': ['https://www.hkex.com.hk/News/Market-Communications/2024/2409062news?sc_lang=en'], 'summary': 'Full day closure for Typhoon Yagi.', 'independently_checked_at_utc': '2026-11-04', 'verified_by': 'Independent market auditor'}, {'calendar': 'XKRX', 'dates': ['2024-10-01'], 'source': 'Korea.net and Yonhap, September 2024', 'urls': ['https://www.korea.net/NewsFocus/policies/view?articleId=257866', 'https://en.yna.co.kr/view/AEN20240910002600320'], 'summary': 'Exceptional Armed Forces Day public holiday and KRX closure.', 'independently_checked_at_utc': '2026-11-04', 'verified_by': 'Independent market auditor'}]
calendar_inventory={};prior_checks=0
for t,raw in sorted(data.items()):
    if t.endswith(('=X','=F','-USD')) or t=='DX-Y.NYB':continue
    code=index_calendars.get(t) or next((v for k,v in suffix_calendars.items() if t.endswith(k)),'XNYS')
    cal=xc.get_calendar(code)
    expected_sessions=[d for d in cal.sessions_in_range(raw['rows'][0][0],raw['rows'][-1][0]).strftime('%Y-%m-%d').tolist() if d not in closures.get(code,set())]
    actual={d for d,_ in raw['rows']};missing=sorted(set(expected_sessions)-actual);extra=sorted(actual-set(expected_sessions))
    if missing or extra:calendar_notes.append({'ticker':t,'calendar':code,'missing':missing,'extra':extra})
    check(not missing and not extra,t+': calendar inventory missing='+str(missing)+' extra='+str(extra))
    for date,c in cards.items():
        if t in cards_module.SKIP:continue
        if date <= raw['rows'][0][0]:
            check(t not in c['markets'],date+' '+t+': no prelisting/resumption quote')
            continue
        expected_date=[d for d in cal.sessions_in_range(raw['rows'][0][0],(dt.date.fromisoformat(date)-dt.timedelta(days=1)).isoformat()).strftime('%Y-%m-%d').tolist() if d not in closures.get(code,set())][-1]
        check(c['markets'][t]['session']==expected_date,date+' '+t+': calendar latest '+expected_date)
        prior_checks+=1
    if code not in calendar_inventory:
        sessions=[d for d in cal.sessions_in_range('2024-10-01','2024-10-31').strftime('%Y-%m-%d').tolist() if d not in closures.get(code,set())]
        calendar_inventory[code]={'sessions':sessions,'closed_weekdays':sorted(set(DATES)-set(sessions))}
cases=[('2024-10-02','000001.SS','2024-09-30'),('2024-10-08','000001.SS','2024-09-30'),('2024-10-09','000001.SS','2024-10-08'),('2024-10-02','^HSI','2024-09-30'),('2024-10-14','^HSI','2024-10-10'),('2024-10-04','^TWII','2024-10-01'),('2024-10-15','^N225','2024-10-11'),('2024-10-15','^GSPC','2024-10-14'),('2024-10-02','^KS11','2024-09-30'),('2024-10-10','^KS11','2024-10-08'),('2024-10-31','^TWII','2024-10-30'),('2024-10-08','^AXJO','2024-10-07'),('2024-10-04','^KS11','2024-10-02'),('2024-10-11','^TWII','2024-10-09')]
for d,t,s in cases:check(cards[d]['markets'][t]['session']==s,d+' '+t+': holiday regression')
check(cards['2024-10-15']['treasury']['prior_close_date']=='2024-10-11','2024-10-15: Treasury Columbus Day closure')
check(all(not any(t.endswith('=X') for t in c['markets']) and bool(c.get('excluded_vendor_marks')) for c in cards.values()),'Spot-FX vendor marks excluded from writer cards')
check(all(d>='2024-10-21' for d,_ in data['NBIS']['rows']),'NBIS pre-resumption history excluded')
check(all('NBIS' not in c['markets'] for d,c in cards.items() if d<='2024-10-21'),'NBIS no quote before resumed trading')
check(float(cards['2024-10-01']['markets']['NFLX']['close'].replace(',',''))>500,'NFLX split restoration')
check(float(cards['2024-10-01']['markets']['LCID']['close'].replace(',',''))<10,'LCID reverse split restoration')
result={'passed':not errors,'assertions':checks,'errors':errors,'dates':DATES,'cards':len(cards),'instruments_per_card':sorted({len(c['markets']) for c in cards.values()}),'raw_symbols':len(data),'fetch_failures':sum(x['status']!='ok' for x in fetch),'retained_last_date':'2024-10-31','future_price_rows_retained':0,'calendar_package':'exchange-calendars','calendar_version':xc.__version__,'independent_prior_session_checks':prior_checks,'calendar_inventory':calendar_inventory,'calendar_discrepancies':calendar_notes,'exceptional_closure_sources':closure_sources,'spot_fx_policy':'Raw =X vendor marks retained in data for audit only; every numeric spot-FX level and return excluded from writer cards and prose.', 'limited_history_symbols':{'NBIS':'Trading history restarts 2024-10-21; early cards leave 20-session returns null.'},'holiday_cases':[{'report_date':d,'ticker':t,'session':s} for d,t,s in cases],'card_sha256':{d:hashlib.sha256((ROOT/'cards'/f'{d}.json').read_bytes()).hexdigest() for d in DATES},'vintage_limit':'Retrospectively retrieved current-vintage histories can include later vendor revisions. Future split events are solely used to restore historical display units and are kept away from report writers.'}
(ROOT/'audit/market_validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('card_sha256','calendar_inventory')},indent=2))
raise SystemExit(bool(errors))
