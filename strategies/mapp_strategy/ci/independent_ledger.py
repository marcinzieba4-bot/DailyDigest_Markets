"""Independent current-vintage accounting/recovery auditor.
No production engine imports. Input preflight and run authorization remain caller duties.
Source SPY positions and source shorts are supported; only the conceptual hedge is short-only.
"""
import csv,datetime as dt,hashlib,json,math,statistics
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results';NY=ZoneInfo('America/New_York')
def read(p):
    with p.open(newline='') as f:r=list(csv.DictReader(f))
    return [] if not r or list(r[0])==['empty_ledger'] else r
def near(a,b,tol=1e-10):assert abs(float(a)-float(b))<tol,(a,b)
def truth(v):return v is True or str(v).lower()=='true'
def time(day,h,m=0):return dt.datetime.combine(dt.date.fromisoformat(day),dt.time(h,m),NY)
def load_cohorts(corpus):
    paths=[ROOT/'inputs'/f'main_{corpus}_prepared.json',ROOT/'inputs'/f'{corpus}_prepared.json',ROOT/'engine/inputs'/f'main_{corpus}_prepared.json']
    path=next(p for p in paths if p.exists());prepared=json.loads(path.read_text())
    rows=prepared.get('reference_cohorts',prepared.get('cohorts',{}).get('etf_own'))
    assert rows is not None
    return {b['basket_id']:b for b in rows}
prices={}
def configure(root):
    global ROOT,OUT,prices,DAYS,INDEX,BETA_CACHE
    ROOT=Path(root).resolve();OUT=ROOT/'results'
    prices={(r['symbol'],r['session_date']):r for r in read(ROOT/'prices.csv')}
    DAYS=sorted(d for s,d in prices if s=='SPY');INDEX={d:i for i,d in enumerate(DAYS)};BETA_CACHE={}
    assert DAYS

def price(s,day,kind='open'):
    value=float(prices[s,day]['adjusted_open' if kind=='open' else 'adjclose']);assert math.isfinite(value) and value>0;return value
def audit(m):
    corpus,family,policy=m['corpus'],m.get('family','etf_own'),m['policy'];scope=m.get('scope','main');cohorts=load_cohorts(corpus)
    scope_out=OUT;ledgers={k:read(scope_out/m[k+'_path']) for k in ['daily','orders','borrow','baskets','source_trades','exante']};daily,orders,borrow,baskets,source,diag=[ledgers[k] for k in ['daily','orders','borrow','baskets','source_trades','exante']]
    assert len(baskets)==len(cohorts)==int(m['baskets']);assert [d['date'] for d in daily]==[d for s,d in prices if s=='SPY' and m['start']<=d<=m['end']]
    source_ids=defaultdict(list)
    for l in source:source_ids[l['basket_id']].append(l)
    for b in baskets:
        c=cohorts[b['basket_id']];ls=source_ids[b['basket_id']];assert len(ls)==len(c['legs'])
        for k in ['entry_date','exit_date','exit_kind','report_date']:assert b[k]==c[k]
        assert truth(b['terminal_censored'])==truth(c['terminal_censored']);assert b['exit_reason']==('terminal_mark_and_liquidation' if truth(c['terminal_censored']) else 'time_limit')
        for l in ls:
            ref=next(t for t in c['legs'] if t['symbol']==l['symbol']);assert int(l['direction'])==ref['direction']
            for k in ['entry_date','exit_date','exit_kind','report_date']:assert l[k]==b[k]
            near(l['entry_notional'],float(b['entry_nav'])*.25*ref['weight']/1.001);near(l['qty'],int(l['direction'])*float(l['entry_notional'])/price(l['symbol'],l['entry_date']))
            near(l['entry_price'],price(l['symbol'],l['entry_date']));near(l['exit_price'],price(l['symbol'],l['exit_date'],l['exit_kind']));near(l['gross_pnl'],float(l['qty'])*(float(l['exit_price'])-float(l['entry_price'])))
        near(b['source_entry_notional'],sum(float(l['entry_notional']) for l in ls))
        assert float(b['source_entry_notional'])*1.001<=float(b['entry_nav'])*.25+1e-10
    cash=1.;last_when=None;last_marks={};positions={};active=None;previous_nav=1.;navs=[1.];expected_borrow=[];seen_orders=[];opens=[];closes=[];signed=[];cash_values=[];cash_fractions=[]
    def accrue(day,now,stage):
        nonlocal cash,last_when
        if active is not None and last_when is not None:
            seconds=(now-last_when).total_seconds();assert seconds>=0
            for s,q in positions.items():
                if q<0:
                    charge=abs(q)*last_marks[s]*.03*seconds/(365*86400);cash-=charge
                    expected_borrow.append(dict(date=day,stage=stage,basket_id=active,symbol=s,qty=q,mark=last_marks[s],seconds=seconds,borrow_cost=charge,from_time=last_when.isoformat(),to_time=now.isoformat()))
        last_when=now
    def transact(day,kind):
        nonlocal cash
        os=[o for o in orders if o['date']==day and o['kind']==kind]
        assert len({o['symbol'] for o in os})==len(os)
        for o in os:
            s=o['symbol'];q=float(o['delta_qty']);p=price(s,day,kind)
            near(o['price'],p);near(o['qty_before'],positions.get(s,0));near(o['qty_after'],positions.get(s,0)+q);near(q,float(o['source_delta_qty'])+float(o['hedge_delta_qty']))
            near(o['notional'],abs(q*p));near(o['fee'],abs(q*p)*.001);cash-=q*p+float(o['fee']);positions[s]=positions.get(s,0)+q
            if abs(positions[s])<1e-14:positions.pop(s)
            if s!='SPY':near(o['hedge_delta_qty'],0.)
            seen_orders.append(o)
        return os
    for d in daily:
        day=d['date'];old_pos=dict(positions);had=bool(positions);first_br=len(expected_borrow);accrue(day,time(day,9,30),'overnight')
        entering=[b for b in baskets if b['entry_date']==day];exiting=[b for b in baskets if b['exit_date']==day and b['exit_kind']=='open']
        assert len(entering)<=1 and len(exiting)<=1 and not(entering and exiting)
        if entering:assert active is None and not positions;near(entering[0]['entry_nav'],cash)
        os=transact(day,'open')
        if exiting:assert active==exiting[0]['basket_id'];active=None
        if entering:active=entering[0]['basket_id']
        expected_source={l['symbol']:float(l['qty']) for l in source if l['entry_date']<=day and (l['exit_date']>day or l['exit_date']==day and l['exit_kind']=='close')}
        for s,q in positions.items():
            if s!='SPY':assert s in expected_source;near(q,expected_source[s])
        assert {s for s in expected_source if s!='SPY'}=={s for s in positions if s!='SPY'}
        assert positions.get('SPY',0.)-expected_source.get('SPY',0.)<=1e-14
        for o in os:
            source_delta=sum(float(l['qty']) for l in source if l['symbol']==o['symbol'] and l['entry_date']==day)-sum(float(l['qty']) for l in source if l['symbol']==o['symbol'] and l['exit_date']==day and l['exit_kind']=='open')
            near(o['source_delta_qty'],source_delta)
        had_open_positions=bool(positions)
        open_nav=cash+sum(q*price(s,day) for s,q in positions.items());gopen=sum(abs(q)*price(s,day) for s,q in positions.items())/open_nav;nopen=sum(q*price(s,day) for s,q in positions.items())/open_nav
        opening_diagnostics=[r for r in diag if r['date']==day]
        assert len(opening_diagnostics)==(1 if active is not None else 0)
        if opening_diagnostics:
            assert opening_diagnostics[0]['basket_id']==active
            near(opening_diagnostics[0]['opening_nav'],open_nav)
        near(gopen,d['gross_exposure_open']);near(nopen,d['signed_exposure_open']);opens.append(gopen);signed.append(abs(nopen))
        last_marks={s:price(s,day) for s in positions};accrue(day,time(day,16),'intraday')
        cs=transact(day,'close');final=[b for b in baskets if b['exit_date']==day and b['exit_kind']=='close']
        if final:assert day==m['end'] and active==final[0]['basket_id'] and not positions and truth(final[0]['terminal_censored']);active=None
        else:assert not cs
        for o in cs:near(o['source_delta_qty'],-sum(float(l['qty']) for l in source if l['symbol']==o['symbol'] and l['exit_date']==day and l['exit_kind']=='close'))
        close_nav=cash+sum(q*price(s,day,'close') for s,q in positions.items());near(close_nav,d['nav']);near(cash,d['cash']);near(close_nav/previous_nav-1,d['daily_return']);navs.append(close_nav)
        gclose=sum(abs(q)*price(s,day,'close') for s,q in positions.items())/close_nav;nclose=sum(q*price(s,day,'close') for s,q in positions.items())/close_nav
        near(gclose,d['gross_exposure_close']);near(nclose,d['signed_exposure_close']);near(cash/close_nav,d['cash_fraction_close']);closes.append(gclose);signed.append(abs(nclose));cash_values.append(cash);cash_fractions.append(cash/close_nav)
        near(sum(float(o['fee']) for o in os+cs),d['transaction_cost']);near(sum(b['borrow_cost'] for b in expected_borrow[first_br:]),d['borrow_cost'])
        assert truth(d['active_day'])==(had or had_open_positions or bool(entering))
        last_marks={s:price(s,day,'close') for s in positions};previous_nav=close_nav
    assert active is None and not positions and len(seen_orders)==len(orders) and len(expected_borrow)==len(borrow)
    for a,b in zip(expected_borrow,borrow):
        for k in ['date','stage','basket_id','symbol','from_time','to_time']:assert str(a[k])==b[k],(k,a,b)
        for k in ['qty','mark','seconds','borrow_cost']:near(a[k],b[k])
    for b in baskets:
        os=[o for o in orders if o['basket_id']==b['basket_id']];bs=[x for x in borrow if x['basket_id']==b['basket_id']];sg=sum(float(l['gross_pnl']) for l in source_ids[b['basket_id']]);hg=-sum(float(o['delta_qty'])*float(o['price']) for o in os)-sg;fees=sum(float(o['fee']) for o in os);br=sum(float(x['borrow_cost']) for x in bs)
        near(sg,b['source_gross_pnl']);near(hg,b['hedge_gross_pnl']);near(fees,b['transaction_cost']);near(br,b['borrow_cost']);near(sg+hg-fees-br,b['net_pnl'])
    near(navs[-1]-1,m['total_return']);peak=1.;dd=0.
    for v in navs:peak=max(peak,v);dd=min(dd,v/peak-1)
    near(dd,m['max_drawdown']);near(statistics.mean(opens),m['average_gross_exposure']);near(max(opens+closes),m['max_gross_exposure']);near(max(signed),m['max_abs_net_exposure']);near(min(cash_values),m['min_cash']);near(min(cash_fractions),m['min_cash_fraction']);near(sum(float(o['fee']) for o in orders),m['transaction_cost']);near(sum(float(b['borrow_cost']) for b in borrow),m['borrow_cost']);near(sum(float(b['net_pnl']) for b in baskets),m['total_return'])
    return dict(scope=scope,corpus=corpus,family=family,policy=policy,status='passed',daily_rows=len(daily),baskets=len(baskets),source_legs=len(source),orders=len(orders),borrow_rows=len(borrow))

def regression(y,x):
    if len(y)<2:return dict(observations=len(y),beta=None,correlation=None,intercept=None)
    mx,my=statistics.mean(x),statistics.mean(y)
    xx=sum((v-mx)**2 for v in x);yy=sum((v-my)**2 for v in y)
    xy=sum((a-mx)*(b-my) for a,b in zip(x,y));beta=xy/xx if xx>0 else None
    return dict(observations=len(y),beta=beta,correlation=xy/math.sqrt(xx*yy) if xx>0 and yy>0 else None,
                intercept=my-beta*mx if beta is not None else None)

DAYS=sorted(d for s,d in prices if s=='SPY');INDEX={d:i for i,d in enumerate(DAYS)};BETA_CACHE={}
def beta(symbol,day):
    key=symbol,day
    if key not in BETA_CACHE:
        i=INDEX[day];past=DAYS[max(0,i-41):i]
        series=[[prices.get((s,d)) for d in past] for s in [symbol,'SPY']]
        if i<41 or len(past)!=41 or any(r is None for rows in series for r in rows):BETA_CACHE[key]=None
        else:
            closes=[[float(r['adjclose']) for r in rows] for rows in series]
            assert len(closes[0])==len(closes[1])==41 and past[-1]<day
            if any(not math.isfinite(v) or v<=0 for rows in closes for v in rows):BETA_CACHE[key]=None
            else:
                y,x=[[b/a-1 for a,b in zip(values,values[1:])] for values in closes]
                assert len(y)==len(x)==40;BETA_CACHE[key]=regression(y,x)['beta']
    return BETA_CACHE[key]

def audit_beta(m):
    daily,orders,source,diag=[read(OUT/m[k+'_path']) for k in ['daily','orders','source_trades','exante']]
    baskets={b['basket_id']:b for b in read(OUT/m['baskets_path'])}
    cohorts=load_cohorts(m['corpus'])
    expected_keys=[(day,str(c['basket_id'])) for day in DAYS if m['start']<=day<=m['end'] for c in cohorts.values() if c['entry_date']<=day and (day<c['exit_date'] or day==c['exit_date'] and c['exit_kind']=='close')]
    observed_keys=[(r['date'],str(r['basket_id'])) for r in diag]
    assert len(observed_keys)==len(set(observed_keys)) and observed_keys==expected_keys
    assert all(r['phase']=='after_open_orders' for r in diag)
    previous={};hedges=[];unknown_rows=constrained_rows=0;max_unknown=max_residual=max_dollar=0.
    for r in diag:
        day,bid=r['date'],r['basket_id'];own=[l for l in source if l['basket_id']==bid];assert own
        assert all(l['entry_date']<=day and (day<l['exit_date'] or day==l['exit_date'] and l['exit_kind']=='close') for l in own)
        source_value=sum(float(l['qty'])*price(l['symbol'],day) for l in own)
        bs={l['symbol']:beta(l['symbol'],day) for l in own}
        observed=json.loads(r['beta40']);assert set(observed)==set(bs)
        for symbol,b in bs.items():
            if b is None:assert observed[symbol] is None
            else:near(b,observed[symbol])
        known=sum(float(l['qty'])*price(l['symbol'],day)*bs[l['symbol']] for l in own if bs[l['symbol']] is not None)
        unknown_symbols=[l['symbol'] for l in own if bs[l['symbol']] is None]
        unknown=sum(abs(float(l['qty'])*price(l['symbol'],day)) for l in own if bs[l['symbol']] is None)
        assert json.loads(r['unknown_beta_symbols'])==unknown_symbols
        physical_spy=sum(float(o['delta_qty']) for o in orders if o['basket_id']==bid and o['symbol']=='SPY' and (o['date']<day or o['date']==day and o['kind']=='open'))
        conceptual_source_spy=sum(float(l['qty']) for l in own if l['symbol']=='SPY');hedge=physical_spy-conceptual_source_spy
        assert hedge<=1e-14;hedges.append(hedge);hv=hedge*price('SPY',day);nv=float(r['opening_nav'])
        for key,value in [('source_net_dollars',source_value),('source_beta_dollars',known),('unknown_beta_exposure_dollars',unknown),('hedge_spy_qty',hedge),('hedge_spy_dollars',hv),('residual_beta_dollars',known+hv),('residual_beta_per_nav',(known+hv)/nv),('residual_dollar_dollars',source_value+hv),('residual_dollar_per_nav',(source_value+hv)/nv),('unknown_beta_exposure_per_nav',unknown/nv)]:near(value,r[key])
        if m['policy']=='beta40_daily_short25':
            near(hedge,-max(0.,known)/price('SPY',day));near(known+hv,min(known,0.));constrained=known<0
        elif m['policy']=='unhedged25':
            near(hedge,0.);near(hv,0.);constrained=False
        else:
            assert m['policy'] in ['baseline25','dollar_short25']
            if day==baskets[bid]['entry_date']:near(hedge,-max(0.,source_value)/price('SPY',day))
            else:near(hedge,previous[bid])
            constrained=False
        assert truth(r['short_only_constraint_prevents_full_beta_hedge'])==constrained
        previous[bid]=hedge;constrained_rows+=constrained;unknown_rows+=unknown>0
        max_unknown=max(max_unknown,unknown/nv);max_residual=max(max_residual,abs((known+hv)/nv));max_dollar=max(max_dollar,abs((source_value+hv)/nv))
    for key,value in [('max_abs_opening_estimated_beta',max_residual),('max_abs_opening_dollar_residual',max_dollar),('unknown_beta_active_openings',unknown_rows),('max_unknown_beta_exposure_per_nav',max_unknown),('short_only_beta_constrained_openings',constrained_rows),('minimum_hedge_spy_qty',min(hedges,default=0)),('maximum_hedge_spy_qty',max(hedges,default=0))]:near(value,m[key])
    for group in ['all','active']:
        subset=daily if group=='all' else [r for r in daily if truth(r['active_day'])]
        xs=[];ys=[]
        for r in subset:
            day=r['date'];i=INDEX[day];x=price('SPY',day,'close')/price('SPY',DAYS[i-1],'close')-1
            near(x,r['spy_daily_return']);xs.append(x);ys.append(float(r['daily_return']))
        expected=regression(ys,xs);assert m['realized_'+group]['observations']==expected['observations']
        for k in ['beta','correlation','intercept']:
            if expected[k] is None:assert m['realized_'+group][k] is None
            else:near(expected[k],m['realized_'+group][k])
    return dict(status='passed',corpus=m['corpus'],policy=m['policy'],exante_rows=len(diag),unknown_beta_rows=unknown_rows,
                negative_known_beta_short_only_constraint_rows=constrained_rows,max_abs_opening_estimated_beta=max_residual,
                min_hedge_qty=min(hedges,default=0),max_hedge_qty=max(hedges,default=0))

def point(rows,i):
    if i is None:return None
    v=float(rows[i]['nav']);return dict(date=rows[i]['date'],index=i,nav=v,nav_usd=100000*v,pnl_usd=100000*(v-1))
def recovery(rows,target,start=0):
    values=[float(r['nav']) for r in rows]
    under=next((i for i in range(start,len(rows)) if values[i]<target),None)
    first=next((i for i in range(under+1,len(rows)) if values[i]>=target),None) if under is not None else None
    last=max((i for i in range(start,len(rows)) if values[i]<target),default=None)
    durable=last+1 if last is not None and last+1<len(rows) else None
    state='never_below_target' if under is None else 'unrecovered' if first is None else 'recovered'
    result=dict(anchor_nav=target,anchor_usd=target*100000,state=state,first_under=point(rows,under),first_recovery=point(rows,first),durable_recovery_in_observed_sample=point(rows,durable),strict_underwater_closes_before_first_recovery=sum(v<target for v in values[start:first if first is not None else len(rows)]))
    if under is not None and first is not None:
        result['first_under_to_first_recovery_session_intervals']=first-under
        result['first_under_to_first_recovery_calendar_days']=(dt.date.fromisoformat(rows[first]['date'])-dt.date.fromisoformat(rows[under]['date'])).days
    return result

def write_csv(path,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def drawdown_episode(rows):
    vals=[1.]+[float(r['nav']) for r in rows];peak=1.;peak_i=0;worst=0.;episode=(0,0)
    for i,v in enumerate(vals):
        if v>peak:peak=v;peak_i=i
        loss=v/peak-1
        if loss<worst:worst=loss;episode=(peak_i,i)
    pi,ti=episode;target=vals[pi]
    # Include a synthetic initial mark only if it is the actual peak anchor.
    anchor=dict(date='initial_capital',index=-1,nav=1.,nav_usd=100000.,pnl_usd=0.) if pi==0 else point(rows,pi-1)
    result=recovery(rows,target,max(0,pi));result.update(peak=anchor,trough=point(rows,ti-1) if ti else anchor,drawdown=worst)
    first=result['first_recovery']
    if pi and first:
        result['peak_to_first_recovery_session_intervals']=first['index']-(pi-1)
        result['peak_to_first_recovery_calendar_days']=(dt.date.fromisoformat(first['date'])-dt.date.fromisoformat(anchor['date'])).days
    return result

def subperiods(rows):
    result=[];previous=1.;current=None;start=None
    for r in rows:
        year=r['date'][:4]
        if year!=current:
            if current is not None:result.append(dict(year=current,start=start,end=last['date'],starting_nav=base,ending_nav=float(last['nav']),return_value=float(last['nav'])/base-1))
            current=year;start=r['date'];base=previous
        previous=float(r['nav']);last=r
    if current is not None:result.append(dict(year=current,start=start,end=last['date'],starting_nav=base,ending_nav=float(last['nav']),return_value=float(last['nav'])/base-1))
    product=math.prod(1+r['return_value'] for r in result);near(product,previous)
    return result

def case_metrics(m):
    rows=read(OUT/m['daily_path']);baskets=read(OUT/m['baskets_path'])
    result={k:m[k] for k in ['scope','family','corpus','policy','start','end','total_return','max_drawdown','baskets','completed_baskets','max_gross_exposure','average_gross_exposure','transaction_cost','borrow_cost','realized_all','realized_active','max_abs_opening_estimated_beta','short_only_beta_constrained_openings','unknown_beta_active_openings']}
    result.update(ending_nav_usd=100000*float(rows[-1]['nav']),initial_capital_recovery=recovery(rows,1.),maximum_drawdown_episode=drawdown_episode(rows),calendar_year_returns=subperiods(rows))
    near(result['maximum_drawdown_episode']['drawdown'],m['max_drawdown'])
    result['lowest_observed_nav_close']=point(rows,min(range(len(rows)),key=lambda i:float(rows[i]['nav'])))
    gross=max(rows,key=lambda r:max(float(r['gross_exposure_open']),float(r['gross_exposure_close'])))
    result['peak_gross_observation']=dict(date=gross['date'],kind='open' if float(gross['gross_exposure_open'])>=float(gross['gross_exposure_close']) else 'close',gross_exposure=max(float(gross['gross_exposure_open']),float(gross['gross_exposure_close'])))
    result['closed_trade_attribution']={k+'_usd':100000*sum(float(b[k]) for b in baskets) for k in ['source_gross_pnl','hedge_gross_pnl','transaction_cost','borrow_cost','net_pnl']}
    if rows[0]['date']<'2025-04-01' and rows[-1]['date']>='2025-04-01':
        early=[r for r in rows if r['date']<'2025-04-01'];assert early and early[-1]['date']=='2025-03-31'
        recent=[r for r in rows if r['date']>='2025-04-01'];assert recent
        first_nav=float(early[-1]['nav']);result['pre_april_2025_return']=first_nav-1
        result['continuous_april_onward_return']=float(rows[-1]['nav'])/first_nav-1
        near((1+result['pre_april_2025_return'])*(1+result['continuous_april_onward_return']),1+m['total_return'])
        result['pre_april_2025_filled_baskets']=sum(b['entry_date']<'2025-04-01' for b in baskets)
        for label,selected in [('pre_april_2025_closed',[b for b in baskets if b['exit_date']<'2025-04-01']),('calendar_2025_closed',[b for b in baskets if '2025-01-01'<=b['exit_date']<'2026-01-01'])]:
            result[label]={k+'_usd':100000*sum(float(b[k]) for b in selected) for k in ['source_gross_pnl','hedge_gross_pnl','transaction_cost','borrow_cost','net_pnl']};result[label]['baskets']=len(selected)
    if rows[0]['date']<='2024-08-30' and rows[-1]['date']>'2024-08-30':
        early=[r for r in rows if r['date']<='2024-08-30'];assert early[-1]['date']=='2024-08-30'
        split_nav=float(early[-1]['nav'])
        result['pre_september_2024_return']=split_nav-1
        result['continuous_september_2024_onward_return']=float(rows[-1]['nav'])/split_nav-1
        result['pre_september_2024_filled_baskets']=sum(b['entry_date']<='2024-08-30' for b in baskets)
        near((1+result['pre_september_2024_return'])*(1+result['continuous_september_2024_onward_return']),1+m['total_return'])
    return result

def predeclared_anchor(rows,cutoff='2025-04-04'):
    selected=[i for i,r in enumerate(rows) if r['date']<=cutoff];assert selected
    i=max(selected,key=lambda i:float(rows[i]['nav']))
    if float(rows[i]['nav'])<1.:return dict(date='initial_capital',index=-1,nav=1.,nav_usd=100000.,pnl_usd=0.)
    return point(rows,i)

def recovery_from_cutoff(rows,anchor,cutoff='2025-04-04'):
    start=next(i for i,r in enumerate(rows) if r['date']>cutoff)
    result=recovery(rows,anchor['nav'],start);result['peak']=anchor;result['cutoff']=cutoff
    first=result['first_recovery']
    if first and anchor['date']!='initial_capital':
        result['peak_to_first_recovery_calendar_days']=(dt.date.fromisoformat(first['date'])-dt.date.fromisoformat(anchor['date'])).days
        result['peak_to_first_recovery_session_intervals']=first['index']-anchor['index']
    return result

def _configured_corpora(freeze):
    cfg=freeze['case_config']
    if isinstance(cfg,dict):
        for key in ['cases','windows']:
            if key in cfg:
                cfg=cfg[key]
                break
    if isinstance(cfg,dict):
        names=set(cfg)
    elif isinstance(cfg,list):
        names={str(r if isinstance(r,str) else r.get('corpus',r.get('case',r.get('name')))) for r in cfg}
    else:
        raise AssertionError('Unrecognized frozen case_config schema')
    allowed={'november_continuous','september_current','september_recorded_fixture'}
    assert names and names<=allowed,('Unexpected frozen case names',sorted(names))
    return names

def run(root,expected_cases=None):
    configure(root)
    summaries=json.loads((OUT/'summary.json').read_text())
    freeze_path=ROOT/'research_freeze.json';freeze=json.loads(freeze_path.read_text())
    review=json.loads((ROOT/'audit/prefreeze_review.json').read_text())
    assert review['status']=='passed'
    assert review['input_freeze_sha256']==hashlib.sha256(freeze_path.read_bytes()).hexdigest()
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['sha256'].items())
    policies={'dollar_short25','beta40_daily_short25','unhedged25'}
    actual={(m['corpus'],m['policy']) for m in summaries};corpora={m['corpus'] for m in summaries}
    assert len(actual)==len(summaries) and all(m['status']=='ok' for m in summaries)
    assert corpora==_configured_corpora(freeze)
    expected={(c,p) for c in corpora for p in policies}
    assert actual==expected
    if expected_cases is not None:
        if isinstance(expected_cases,int):assert len(actual)==expected_cases
        else:assert actual=={tuple(x) for x in expected_cases}
    ledgers=[audit(m) for m in summaries];betas=[audit_beta(m) for m in summaries];metrics=[case_metrics(m) for m in summaries]
    source_flags=[];deltas=[]
    for corpus in sorted(corpora):
        chosen=[m for m in summaries if m['corpus']==corpus]
        fixed=next(m for m in chosen if m['policy']=='dollar_short25')
        common=predeclared_anchor(read(OUT/fixed['daily_path']))
        signatures={}
        for m in chosen:
            row=next(r for r in metrics if r['corpus']==corpus and r['policy']==m['policy'])
            daily=read(OUT/m['daily_path']);source=read(OUT/m['source_trades_path']);orders=read(OUT/m['orders_path']);diag=read(OUT/m['exante_path'])
            row['own_hwm_through_april4_recovery']=recovery_from_cutoff(daily,predeclared_anchor(daily))
            row['common_baseline_hwm_through_april4_recovery']=recovery_from_cutoff(daily,common)
            signatures[m['policy']]=[(b['basket_id'],b['report_date'],b['entry_date'],b['exit_date'],b['exit_kind'],b['symbols']) for b in read(OUT/m['baskets_path'])]
            flags=dict(corpus=corpus,policy=m['policy'],source_legs=len(source),source_long_legs=sum(int(l['direction'])>0 for l in source),source_short_legs=sum(int(l['direction'])<0 for l in source),source_spy_legs=sum(l['symbol']=='SPY' for l in source),physical_spy_orders=sum(o['symbol']=='SPY' for o in orders))
            if m['policy']=='unhedged25':
                assert int(m['hedge_orders'])==0
                assert all(float(o['hedge_delta_qty'])==0 for o in orders)
                assert all(float(d['hedge_spy_qty'])==0 for d in diag)
                flags['zero_conceptual_hedge_verified']=True
            source_flags.append(flags)
        assert all(v==signatures['unhedged25'] for v in signatures.values())
        un=next(r for r in metrics if r['corpus']==corpus and r['policy']=='unhedged25')['closed_trade_attribution']
        for policy in ['dollar_short25','beta40_daily_short25']:
            ref=next(r for r in metrics if r['corpus']==corpus and r['policy']==policy)['closed_trade_attribution']
            d=dict(corpus=corpus,against=policy,source_gross_difference=un['source_gross_pnl_usd']-ref['source_gross_pnl_usd'],hedge_gross_difference=un['hedge_gross_pnl_usd']-ref['hedge_gross_pnl_usd'],total_order_fees_saved=ref['transaction_cost_usd']-un['transaction_cost_usd'],borrow_saved=ref['borrow_cost_usd']-un['borrow_cost_usd'],net_difference=un['net_pnl_usd']-ref['net_pnl_usd'])
            near(d['source_gross_difference']+d['hedge_gross_difference']+d['total_order_fees_saved']+d['borrow_saved'],d['net_difference'],1e-7);deltas.append(d)
    flat=[];trades=[];years=[]
    for r in metrics:
        row={k:v for k,v in r.items() if not isinstance(v,(dict,list))}
        row.update(all_day_realized_beta=r['realized_all']['beta'],active_day_realized_beta=r['realized_active']['beta'])
        for prefix,key in [('initial','initial_capital_recovery'),('max_dd','maximum_drawdown_episode'),('own_apr4','own_hwm_through_april4_recovery'),('common_apr4','common_baseline_hwm_through_april4_recovery')]:
            a=r.get(key,{});row[prefix+'_anchor_usd']=a.get('anchor_usd','');row[prefix+'_state']=a.get('state','')
            for suffix,key2 in [('first_under','first_under'),('first_recovery','first_recovery'),('durable_recovery','durable_recovery_in_observed_sample')]:row[prefix+'_'+suffix]=(a.get(key2) or {}).get('date','')
        flat.append(row);years.extend(dict(corpus=r['corpus'],policy=r['policy'],**yr) for yr in r['calendar_year_returns'])
    for m in summaries:
        for b in read(OUT/m['baskets_path']):
            r=dict(corpus=m['corpus'],policy=m['policy'],**b)
            for k in ['entry_nav','source_entry_notional','source_gross_pnl','hedge_gross_pnl','transaction_cost','borrow_cost','net_pnl']:r[k+'_usd']=float(b[k])*100000
            trades.append(r)
    result=dict(status='passed',reviewed_utc=dt.datetime.now(dt.timezone.utc).isoformat(),cases=len(summaries),method='No production engine import: independent saved physical orders, netted positions, virtual source/hedge attribution, ACT365 borrow, cash/NAV, sampled open-close exposures, raw40-return beta, complete conceptual held-opening diagnostics and recovery scans.',frozen_input_hashes_unchanged=True,input_freeze_sha256=hashlib.sha256(freeze_path.read_bytes()).hexdigest(),prior_price_vintage_identity_claimed=False,unique_beta_estimates=len(BETA_CACHE),missing_beta_estimates=sum(v is None for v in BETA_CACHE.values()),ledger_audits=ledgers,beta_audits=betas,source_flags=source_flags,same_source_signatures_within_each_corpus=True,metrics=metrics,unhedged_attribution_vs_controls=deltas,recovery_definition='Exact daily-close scans. First recross after falling below target; sustained recross has no later observed close below target through saved sample end. Own running HWM through Apr4 and per-corpus fixed-dollar common HWM are distinct; initial capital and full maximum drawdown episode separately labeled. Sustained recovery is retrospective, never an entry signal.')
    dest=ROOT/'diagnosis';dest.mkdir(exist_ok=True)
    (dest/'independent_results.json').write_text(json.dumps(result,indent=2)+'\n')
    write_csv(dest/'metrics.csv',flat);write_csv(dest/'trade_attribution.csv',trades);write_csv(dest/'calendar_year_returns.csv',years);write_csv(dest/'unhedged_attribution_vs_controls.csv',deltas);write_csv(dest/'source_flags.csv',source_flags)
    public_summary=[{k:r[k] for k in ['corpus','policy','start','end','total_return','max_drawdown','baskets','completed_baskets','max_gross_exposure','transaction_cost','borrow_cost','all_day_realized_beta','active_day_realized_beta']} for r in flat]
    print(json.dumps(dict(status='passed',cases=len(summaries),orders=sum(a['orders'] for a in ledgers),borrow_rows=sum(a['borrow_rows'] for a in ledgers),exante_rows=sum(a['exante_rows'] for a in betas),metrics=public_summary),indent=2))
    return result

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path.cwd());p.add_argument('--expected-cases',type=int);args=p.parse_args()
    run(args.root,args.expected_cases)
