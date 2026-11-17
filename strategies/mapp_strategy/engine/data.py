"""Source/entry-only preparation for the fixed April-history extension.

Only report fields, entry-opening prices, and completed prior bars are read for
qualification. This module calculates no portfolio returns. The opportunity
reservation clock is formed before the SMA20 gate, separately for stocks/ETFs.
"""
from __future__ import annotations
import csv, datetime as dt, json, math
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
ROOT=Path(__file__).resolve().parent.parent
INPUT=ROOT/'engine/inputs';NY=ZoneInfo('America/New_York')
STOCK_EXCHANGES={'NYQ','NMS','NGM','NCM','ASE'}
ETF_EXCHANGES=STOCK_EXCHANGES|{'PCX','BTS','BATS','CBOE','NYSEArca','NasdaqGM','NasdaqGS','NasdaqCM'}
NON_STOCK_TYPES={'ETF','MUTUALFUND','INDEX','CURRENCY','CRYPTOCURRENCY','FUTURE'}
def read(p):
    with Path(p).open(newline='') as f:return list(csv.DictReader(f))
def stamp(s):return dt.datetime.fromisoformat(s.replace('Z','+00:00'))
def opening(day):return dt.datetime.combine(dt.date.fromisoformat(day),dt.time(9,30),NY)
class MissingHeldPrice(ValueError):pass
class Data:
    def __init__(self,root=None):
        root=Path(root) if root is not None else ROOT
        self.rows=defaultdict(dict)
        for r in read(root/'prices.csv'):
            assert r['session_date'] not in self.rows[r['symbol']],f'Duplicate price {r["symbol"]} {r["session_date"]}'
            self.rows[r['symbol']][r['session_date']]={k:float(r[k]) for k in ['open','close','adjusted_open','adjclose','volume']}
        self.days=sorted(self.rows['SPY']);self.index={d:i for i,d in enumerate(self.days)};self.cache={}
        self.meta={r['symbol']:r for r in json.loads((root/'market_manifest.json').read_text())['series']}
    def maybe(self,s,day,kind='open'):
        row=self.rows.get(s,{}).get(day);v=row.get('adjusted_open' if kind=='open' else 'adjclose') if row else None
        return v if v is not None and math.isfinite(v) and v>0 else None
    def p(self,s,day,kind='open'):
        value=self.maybe(s,day,kind)
        if value is None:raise MissingHeldPrice(f'Missing held mark: {s} {day} {kind}; no carry-forward or future screening')
        return value
    def eligible(self,s,day,asset='stock'):
        m=self.meta.get(s,{})
        if m.get('status') not in ['ok','cached','success']:return False,'history_unavailable'
        types={'EQUITY'} if asset=='stock' else {'ETF','EQUITY'}
        exchanges=STOCK_EXCHANGES if asset=='stock' else ETF_EXCHANGES
        if m.get('quote_type') not in types:return False,'not_equity' if asset=='stock' else 'not_equity_or_etf'
        if m.get('currency')!='USD' or m.get('exchange_timezone')!='America/New_York':return False,'not_usd_us_session'
        if m.get('exchange') not in exchanges:return False,'not_nyse_nasdaq_amex' if asset=='stock' else 'unapproved_exchange_or_otc'
        if self.maybe(s,day) is None:return False,'missing_entry_open'
        i=self.index[day];past=[self.rows.get(s,{}).get(d) for d in self.days[max(0,i-20):i]]
        if len(past)<20 or any(r is None for r in past):return False,'fewer_than_20_prior_sessions'
        dv=[r['close']*r['volume'] for r in past]
        if not all(math.isfinite(v) and v>=0 for v in dv):return False,'invalid_prior_dollar_volume'
        return (False,'prior_median_dollar_volume_below_10m') if float(np.median(dv))<10_000_000 else (True,'eligible')
    def sma(self,s,day,direction):
        i=self.index[day];past=[self.maybe(s,d,'close') for d in self.days[max(0,i-20):i]]
        valid=len(past)==20 and all(v is not None for v in past)
        average=sum(past)/20 if valid else None;latest=past[-1] if valid else None
        okay=bool(valid and (latest>average if direction>0 else latest<average))
        return okay,latest,average
    def beta(self,s,day):
        key=(s,day)
        if key not in self.cache:
            i=self.index[day]
            values=[[self.maybe(symbol,d,'close') for d in self.days[max(0,i-41):i]] for symbol in [s,'SPY']]
            if i<41 or any(len(v)!=41 or any(x is None for x in v) for v in values):self.cache[key]=None
            else:
                prices=np.array(values);r=prices[:,1:]/prices[:,:-1]-1;x=r[1]-r[1].mean();y=r[0]-r[0].mean();den=float(x@x)
                self.cache[key]=float(x@y/den) if den>0 else None
        return self.cache[key]
def load_items(data,corpus,asset,source_min):
    stem='archival_replay' if corpus=='archive_replay' else 'original'
    items=[];exclusions=[]
    for source in read(ROOT/'inputs'/f'{stem}_{asset}_items.csv'):
        if int(source['slot'])!=4 or source['report_date']<source_min:continue
        row=dict(source);kept=[]
        for t in json.loads(row['targets']):
            symbol=t['symbol'];direction=int(t['direction']);meta=data.meta.get(symbol,{})
            assert direction in [-1,1]
            if asset=='stock' and meta.get('quote_type') in NON_STOCK_TYPES:
                exclusions.append(dict(corpus=corpus,report_date=row['report_date'],symbol=symbol,quote_type=meta['quote_type'],reason='metadata_confirms_non_stock_excluded_before_named_stock_weights'))
            else:
                kept.append(dict(symbol=symbol,direction=direction,source_eligible=t.get('source_eligible',True),source_eligibility_reason=t.get('source_eligibility_reason','literal_candidate' if asset=='stock' else 'fixed17_etf_mapping')))
        assert len({t['symbol'] for t in kept})==len(kept)
        row['legs']=kept;items.append(row)
    assert len({r['report_date'] for r in items})==len(items)
    return sorted(items,key=lambda r:r['report_date']),exclusions
def expiry(data,day,end):
    i=data.index[day];target=i+10;deadline=dt.date.fromisoformat(day)+dt.timedelta(days=21)
    if target<len(data.days):
        while dt.date.fromisoformat(data.days[target])>deadline:target-=1
    if target>=len(data.days) or data.days[target]>end:return end,'close',True
    return data.days[target],'open',False
def qualify(data,row,day,clock_id,asset):
    n=len(row['legs']);legs=[];audit=[]
    for t in row['legs']:
        symbol=t['symbol'];direction=int(t['direction']);okay,reason=data.eligible(symbol,day,asset)
        if t.get('source_eligible') is False:okay,reason=False,t.get('source_eligibility_reason','source_ineligible_foreign_listing')
        aligned,latest,average=data.sma(symbol,day,direction)
        if okay and not aligned:okay,reason=False,'crowd_direction_not_sma20_aligned'
        weight=1/n
        audit.append(dict(clock_id=clock_id,date=day,report_date=row['report_date'],symbol=symbol,direction=direction,
            original_weight=weight,eligible=okay,reason=reason,prior_close=latest,prior_sma20=average,
            beta40=data.beta(symbol,day),available_at=row['available_at'],source_sha256=row['source_sha256']))
        if okay:legs.append(dict(symbol=symbol,direction=direction,weight=weight))
    return legs,audit
def clock(data,items,start,end,asset):
    """Latest ready report, before-gate FOLLOW reservations, complete flat cooldown."""
    events=defaultdict(list)
    for row in items:
        first=next((d for d in data.days if d>row['report_date'] and opening(d)>stamp(row['available_at'])),None)
        if first:events[first].append(row)
    opportunities=[];cohorts=[];audit=[];latest=None;reserved_until=None;last_exit=-1000;last_report=None
    for day in [d for d in data.days if d<=end]:
        i=data.index[day]
        for row in events.get(day,[]):
            if latest is None or row['report_date']>latest['report_date']:latest=row
        if day<start:continue
        if reserved_until is not None and i>=reserved_until:reserved_until=None;last_exit=i
        if reserved_until is not None or i<=last_exit+1 or latest is None or latest['report_date']==last_report:continue
        age=(dt.date.fromisoformat(day)-dt.date.fromisoformat(latest['report_date'])).days
        if age>4 or not latest['legs'] or not any(t.get('source_eligible') is not False and data.eligible(t['symbol'],day,asset)[0] for t in latest['legs']):continue
        ident=len(opportunities)+1;exit_day,kind,censored=expiry(data,day,end)
        opportunities.append(dict(clock_id=ident,date=day,report_date=latest['report_date'],source_sha256=latest['source_sha256'],
            source_version_id=latest['source_version_id'],available_at=latest['available_at'],targets=json.dumps(latest['legs']),scheduled_exit=exit_day,exit_kind=kind))
        legs,records=qualify(data,latest,day,ident,asset);audit+=records
        if legs:cohorts.append(dict(basket_id=str(ident),entry_date=day,exit_date=exit_day,exit_kind=kind,
            report_date=latest['report_date'],heading=latest['heading'],source_sha256=latest['source_sha256'],terminal_censored=censored,legs=legs))
        last_report=latest['report_date'];reserved_until=data.index[exit_day] if not censored else len(data.days)+1
    return opportunities,cohorts,audit
def prepare(data,corpus,scope='main'):
    config=json.loads((ROOT/'engine/design_config.json').read_text())
    window=config['windows'][scope][corpus];start,end,source_min=window['start'],window['end'],window['source_min']
    if start=='first_original_open':
        original_rows=read(ROOT/'inputs/original_stock_items.csv')
        available=[d for row in original_rows if row['report_date']>=source_min for d in data.days if d>row['report_date'] and opening(d)>stamp(row['available_at'])]
        start=max('2025-04-01',min(available))
    assert start<=end and end in data.index
    stocks,exclusions=load_items(data,corpus,'stock',source_min);etfs,_=load_items(data,corpus,'etf',source_min)
    assert [(r['report_date'],r['source_sha256']) for r in stocks]==[(r['report_date'],r['source_sha256']) for r in etfs]
    stock_opp,stock_cohorts,stock_audit=clock(data,stocks,start,end,'stock')
    etf_opp,etf_cohorts,etf_audit=clock(data,etfs,start,end,'etf')
    bydate={r['report_date']:r for r in stocks};paired=[];paired_audit=[]
    for ident,ref in enumerate(etf_opp,1):
        day=ref['date'];row=bydate[ref['report_date']];assert row['source_sha256']==ref['source_sha256']
        legs,records=qualify(data,row,day,ident,'stock');paired_audit+=records
        if legs:
            exit_day,kind,censored=expiry(data,day,end)
            paired.append(dict(basket_id=str(ident),entry_date=day,exit_date=exit_day,exit_kind=kind,
                report_date=row['report_date'],heading=row['heading'],source_sha256=row['source_sha256'],terminal_censored=censored,legs=legs))
    return dict(scope=scope,start=start,end=end,source_min=source_min,cohorts=dict(stock_own=stock_cohorts,stock_paired=paired,etf_own=etf_cohorts),
        stock_opportunities=stock_opp,etf_opportunities=etf_opp,stock_qualification=stock_audit,etf_qualification=etf_audit,
        paired_qualification=paired_audit,metadata_exclusions=exclusions)
