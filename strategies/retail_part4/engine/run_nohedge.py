"""Compare no SPY hedge with the two unchanged extended-history SPY controls."""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,json,math
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
from data import Data,MissingHeldPrice
ROOT=Path(__file__).resolve().parents[1];INPUT=ROOT/'inputs';OUT=ROOT/'results';NY=ZoneInfo('America/New_York')
POLICIES=['dollar_short25','beta40_daily_short25','unhedged25'];FAMILIES=['etf_own'];CORPORA=['archive_replay'];FEE=.001;BORROW=.03
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    with Path(p).open(newline='') as f:return list(csv.DictReader(f))


def dump(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False))


def write(p,rows):
    if not rows:Path(p).write_text('empty_ledger\n');return
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with Path(p).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def time(day,hour,minute=0):return dt.datetime.combine(dt.date.fromisoformat(day),dt.time(hour,minute),NY)


def truth(x):return x is True or str(x).lower()=='true'


def regress(y,x):
    if len(y)<2:return dict(observations=len(y),beta=None,correlation=None,intercept=None)
    y=np.array(y);x=np.array(x);xc=x-x.mean();yc=y-y.mean();den=float(xc@xc);vy=float(yc@yc)
    return dict(observations=len(y),beta=float(xc@yc/den) if den>0 else None,
        correlation=float(xc@yc/math.sqrt(den*vy)) if den>0 and vy>0 else None,
        intercept=float(y.mean()-(xc@yc/den)*x.mean()) if den>0 else None)


def simulate(data,corpus,policy,family,scope='main'):
    prepared=json.loads((INPUT/f'{scope}_{corpus}_prepared.json').read_text())
    days=[d for d in data.days if prepared['start']<=d<=prepared['end']]
    cohorts=prepared['cohorts'][family]
    entries={r['entry_date']:r for r in cohorts}
    assert len(entries)==len(cohorts)
    allocation=.25
    hedge_mode='dollar' if policy in ['dollar_short25','dollar_daily_short25'] else 'beta' if policy=='beta40_daily_short25' else 'none'
    daily_rebalance=policy in ['beta40_daily_short25','dollar_daily_short25']
    cash=1.;previous_nav=1.;active=None;hedge_qty=0.;last_when=None;last_marks={}
    fee_total=0.;borrow_total=0.;daily=[];orders=[];borrow_ledger=[];baskets=[];source_trades=[];diagnostics=[]
    def physical():
        pos=defaultdict(float)
        if active:
            for leg in active['legs']:pos[leg['symbol']]+=leg['qty']
        pos['SPY']+=hedge_qty
        return {s:q for s,q in pos.items() if abs(q)>1e-14}
    def nav(day,kind):return cash+sum(q*data.p(s,day,kind) for s,q in physical().items())
    def accrue(day,when,stage):
        nonlocal cash,borrow_total,last_when
        if last_when is not None and active:
            seconds=(when-last_when).total_seconds();assert seconds>=0
            for s,q in physical().items():
                if q>=0:continue
                charge=abs(q)*last_marks[s]*BORROW*seconds/(365*86400)
                cash-=charge;borrow_total+=charge;active['borrow_cost']+=charge
                borrow_ledger.append(dict(date=day,stage=stage,basket_id=active['basket_id'],symbol=s,
                    qty=q,mark=last_marks[s],seconds=seconds,borrow_cost=charge,from_time=last_when.isoformat(),to_time=when.isoformat()))
        last_when=when
    def transact(day,kind,old,new,reason,source_changes=None,hedge_change=0.):
        nonlocal cash,fee_total
        source_changes=source_changes or {}
        for s in sorted(set(old)|set(new)):
            delta=new.get(s,0.)-old.get(s,0.)
            if abs(delta)<1e-14:continue
            price=data.p(s,day,kind);fee=abs(delta*price)*FEE
            cash-=delta*price+fee;fee_total+=fee;active['transaction_cost']+=fee
            orders.append(dict(date=day,kind=kind,reason=reason,basket_id=active['basket_id'],symbol=s,
                qty_before=old.get(s,0.),qty_after=new.get(s,0.),delta_qty=delta,price=price,notional=abs(delta*price),
                fee=fee,source_delta_qty=source_changes.get(s,0.),hedge_delta_qty=hedge_change if s=='SPY' else 0.))
    def hedge_target(day):
        if hedge_mode=='none':return 0.
        numerator=0.
        for leg in active['legs']:
            coefficient=data.beta(leg['symbol'],day) if hedge_mode=='beta' else 1.
            if coefficient is not None:numerator+=leg['qty']*data.p(leg['symbol'],day)*coefficient
        return -max(0.,numerator)/data.p('SPY',day)
    def record_diagnostic(day,phase):
        source_value=sum(l['qty']*data.p(l['symbol'],day) for l in active['legs'])
        betas={l['symbol']:data.beta(l['symbol'],day) for l in active['legs']}
        source_beta=sum(l['qty']*data.p(l['symbol'],day)*betas[l['symbol']] for l in active['legs'] if betas[l['symbol']] is not None)
        unknown=sum(abs(l['qty']*data.p(l['symbol'],day)) for l in active['legs'] if betas[l['symbol']] is None)
        hv=hedge_qty*data.p('SPY',day);current_nav=nav(day,'open')
        assert hedge_qty<=1e-14,'A hedge must never hold long SPY'
        diagnostics.append(dict(date=day,phase=phase,basket_id=active['basket_id'],source_net_dollars=source_value,
            source_beta_dollars=source_beta,hedge_spy_qty=hedge_qty,hedge_spy_dollars=hv,residual_beta_dollars=source_beta+hv,
            residual_beta_per_nav=(source_beta+hv)/current_nav,opening_nav=current_nav,
            residual_dollar_dollars=source_value+hv,residual_dollar_per_nav=(source_value+hv)/current_nav,
            unknown_beta_exposure_dollars=unknown,unknown_beta_exposure_per_nav=unknown/current_nav,
            unknown_beta_symbols=json.dumps([s for s,b in betas.items() if b is None]),beta40=json.dumps(betas),
            short_only_constraint_prevents_full_beta_hedge=hedge_mode=='beta' and source_beta<0.))
    def close(day,kind,reason):
        nonlocal active,hedge_qty
        old=physical();source_changes={l['symbol']:-l['qty'] for l in active['legs']};old_hedge=hedge_qty
        # Clear conceptual positions only after recording virtual sourcePnL.
        gross_source=0.
        for l in active['legs']:
            price=data.p(l['symbol'],day,kind);pnl=l['qty']*(price-l['entry_price']);gross_source+=pnl
            source_trades.append(dict(basket_id=active['basket_id'],report_date=active['report_date'],symbol=l['symbol'],
                direction=l['direction'],entry_date=active['entry_date'],entry_price=l['entry_price'],qty=l['qty'],entry_notional=l['entry_notional'],
                exit_date=day,exit_kind=kind,exit_price=price,gross_pnl=pnl,terminal_censored=reason=='terminal_mark_and_liquidation'))
        active['hedge_cashflow']+=old_hedge*data.p('SPY',day,kind)
        transact(day,kind,old,{},reason,source_changes,-old_hedge)
        record=dict(basket_id=active['basket_id'],report_date=active['report_date'],entry_date=active['entry_date'],exit_date=day,
            exit_kind=kind,exit_reason=reason,entry_nav=active['entry_nav'],source_entry_notional=active['source_entry_notional'],
            symbols='|'.join(l['symbol'] for l in active['legs']),source_gross_pnl=gross_source,hedge_gross_pnl=active['hedge_cashflow'],
            transaction_cost=active['transaction_cost'],borrow_cost=active['borrow_cost'],
            net_pnl=gross_source+active['hedge_cashflow']-active['transaction_cost']-active['borrow_cost'],
            terminal_censored=reason=='terminal_mark_and_liquidation')
        baskets.append(record);active=None;hedge_qty=0.
    for day in days:
        had_exposure=bool(physical());fees_before=fee_total;borrow_before=borrow_total
        accrue(day,time(day,9,30),'overnight')
        if active and active['exit_date']==day and active['exit_kind']=='open':close(day,'open','time_limit')
        if day in entries:
            assert active is None
            cohort=entries[day];opening_nav=nav(day,'open');assert opening_nav>0
            sourcelegs=cohort['legs'];legs=[]
            for ref in sourcelegs:
                symbol=ref['symbol'];direction=int(ref['direction']);price=data.p(symbol,day)
                original_weight=float(ref['weight'])
                notional=opening_nav*allocation*original_weight/(1+FEE)
                legs.append(dict(symbol=symbol,direction=direction,qty=direction*notional/price,entry_price=price,entry_notional=notional))
            active=dict(basket_id=cohort['basket_id'],report_date=cohort['report_date'],entry_date=day,
                exit_date=cohort['exit_date'],exit_kind=cohort['exit_kind'],entry_nav=opening_nav,legs=legs,
                source_entry_notional=sum(l['entry_notional'] for l in legs),transaction_cost=0.,borrow_cost=0.,hedge_cashflow=0.)
            old={};hedge_qty=hedge_target(day);active['hedge_cashflow']-=hedge_qty*data.p('SPY',day)
            transact(day,'open',old,physical(),'source_entry_and_initial_hedge',{l['symbol']:l['qty'] for l in legs},hedge_qty)
        elif active and daily_rebalance:
            old=physical();old_hedge=hedge_qty;hedge_qty=hedge_target(day);change=hedge_qty-old_hedge
            active['hedge_cashflow']-=change*data.p('SPY',day)
            transact(day,'open',old,physical(),'daily_hedge_rebalance',{},change)
        if active:record_diagnostic(day,'after_open_orders')
        pos_open=physical();open_nav=nav(day,'open')
        gross_open=sum(abs(q*data.p(s,day)) for s,q in pos_open.items());net_open=sum(q*data.p(s,day) for s,q in pos_open.items())
        last_marks={s:data.p(s,day) for s in pos_open}
        accrue(day,time(day,16),'intraday')
        if active and active['exit_date']==day and active['exit_kind']=='close':close(day,'close','terminal_mark_and_liquidation')
        close_nav=nav(day,'close');pos_close=physical()
        gross_close=sum(abs(q*data.p(s,day,'close')) for s,q in pos_close.items());net_close=sum(q*data.p(s,day,'close') for s,q in pos_close.items())
        i=data.index[day];spy_ret=data.p('SPY',day,'close')/data.p('SPY',data.days[i-1],'close')-1
        daily.append(dict(date=day,nav=close_nav,daily_return=close_nav/previous_nav-1,cash=cash,
            cash_fraction_close=cash/close_nav,gross_exposure_open=gross_open/open_nav,signed_exposure_open=net_open/open_nav,
            gross_exposure_close=gross_close/close_nav,signed_exposure_close=net_close/close_nav,
            transaction_cost=fee_total-fees_before,borrow_cost=borrow_total-borrow_before,spy_daily_return=spy_ret,
            active_day=had_exposure or bool(pos_open) or day in entries))
        last_marks={s:data.p(s,day,'close') for s in pos_close};previous_nav=close_nav
    assert active is None
    values=np.array([1.]+[r['nav'] for r in daily]);total=float(values[-1]-1)
    assert abs(sum(r['net_pnl'] for r in baskets)-total)<1e-10
    assert abs(sum(r['fee'] for r in orders)-fee_total)<1e-10
    active_days=[r for r in daily if r['active_day']]
    metric=dict(status='ok',scope=scope,corpus=corpus,family=family,policy=policy,start=days[0],end=days[-1],total_return=total,
        max_drawdown=float(min(values/np.maximum.accumulate(values)-1)),baskets=len(baskets),
        completed_baskets=sum(not b['terminal_censored'] for b in baskets),
        transaction_cost=fee_total,borrow_cost=borrow_total,hedge_orders=sum(abs(r['hedge_delta_qty'])>1e-14 for r in orders),
        average_gross_exposure=float(np.mean([r['gross_exposure_open'] for r in daily])),
        max_gross_exposure=max(max(r['gross_exposure_open'],r['gross_exposure_close']) for r in daily),
        min_cash=min(r['cash'] for r in daily),min_cash_fraction=min(r['cash_fraction_close'] for r in daily),
        max_abs_net_exposure=max(max(abs(r['signed_exposure_open']),abs(r['signed_exposure_close'])) for r in daily),
        max_abs_opening_estimated_beta=max((abs(r['residual_beta_per_nav']) for r in diagnostics),default=0.),
        max_abs_opening_dollar_residual=max((abs(r['residual_dollar_per_nav']) for r in diagnostics),default=0.),
        unknown_beta_active_openings=sum(r['unknown_beta_exposure_dollars']>0 for r in diagnostics),
        max_unknown_beta_exposure_per_nav=max((r['unknown_beta_exposure_per_nav'] for r in diagnostics),default=0.),
        short_only_beta_constrained_openings=sum(r['short_only_constraint_prevents_full_beta_hedge'] for r in diagnostics),
        minimum_hedge_spy_qty=min((r['hedge_spy_qty'] for r in diagnostics),default=0.),
        maximum_hedge_spy_qty=max((r['hedge_spy_qty'] for r in diagnostics),default=0.),
        realized_all=regress([r['daily_return'] for r in daily],[r['spy_daily_return'] for r in daily]),
        realized_active=regress([r['daily_return'] for r in active_days],[r['spy_daily_return'] for r in active_days]))
    return dict(metric=metric,daily=daily,orders=orders,borrow=borrow_ledger,baskets=baskets,source_trades=source_trades,exante=diagnostics)



def compare(a,b):
    if a is None or b is None:assert a is b,(a,b);return
    if isinstance(a,dict):
        assert a.keys()==b.keys(),(a.keys(),b.keys())
        for k in a:compare(a[k],b[k])
        return
    try:x,y=float(a),float(b)
    except (TypeError,ValueError):assert a==b,(a,b)
    else:assert math.isclose(x,y,rel_tol=1e-10,abs_tol=1e-12),(x,y)


def check_baselines(summary):
    refs=json.loads((INPUT/'baseline_reference/summary.json').read_text());checks=[]
    for old in refs:
        now=next(m for m in summary if m['corpus']==old['corpus'] and m['policy']==old['policy'])
        for k in old:
            if k.endswith('_path'):continue
            compare(old[k],now[k])
        rows={}
        for kind in ['daily','orders','borrow','baskets','source_trades','exante']:
            a=read(INPUT/'baseline_reference'/Path(old[kind+'_path']).name);b=read(OUT/now[kind+'_path'])
            assert len(a)==len(b)
            for x,y in zip(a,b):
                assert x.keys()==y.keys()
                for k in x:compare(x[k],y[k])
            rows[kind]=len(a)
        checks.append(dict(corpus=old['corpus'],policy=old['policy'],status='passed',rows=rows))
    result=dict(status='passed',controls=2,checks=checks);dump(OUT/'baseline_identity.json',result);return result


def freeze():
    path=ROOT/'research_freeze.json';assert not path.exists()
    files=[ROOT/'protocol.json',ROOT/'prices.csv',ROOT/'market_manifest.json']
    files+=sorted(p for sub in ['engine','inputs'] for p in (ROOT/sub).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    dump(path,dict(frozen_utc=dt.datetime.now(dt.timezone.utc).isoformat(),status='Before newly calculated no-SPY-hedge outcome. Prior two hedged outcomes already known; no policy tuning.',
        cases=3,sha256={str(p.relative_to(ROOT)):sha(p) for p in files}))
    print('Frozen three unchanged-rule comparison books.')


def run():
    frozen=json.loads((ROOT/'research_freeze.json').read_text());assert all(sha(ROOT/p)==h for p,h in frozen['sha256'].items())
    OUT.mkdir(exist_ok=True);summary=[];data=Data()
    for corpus in CORPORA:
        for policy in POLICIES:
            result=simulate(data,corpus,policy,'etf_own');metric=result['metric'];prefix=corpus+'_'+policy
            if policy=='unhedged25':
                assert metric['hedge_orders']==0 and metric['minimum_hedge_spy_qty']==0 and metric['maximum_hedge_spy_qty']==0
                assert not result['borrow'] and all(r['symbol']!='SPY' for r in result['orders'])
                assert all(r['hedge_gross_pnl']==0 and r['borrow_cost']==0 for r in result['baskets'])
            for kind,rows in result.items():
                if kind=='metric':continue
                filename=prefix+'_'+kind+'.csv';write(OUT/filename,rows);metric[kind+'_path']=filename
            summary.append(metric)
    assert len(summary)==3
    dump(OUT/'summary.json',summary)
    write(OUT/'metrics.csv',[{k:json.dumps(v) if isinstance(v,dict) else v for k,v in m.items()} for m in summary])
    check_baselines(summary)
    dump(OUT/'run_manifest.json',dict(completed_utc=dt.datetime.now(dt.timezone.utc).isoformat(),cases=3,failed_cases=0,freeze_sha256=sha(ROOT/'research_freeze.json')))
    print(json.dumps(dict(cases=3,failed_cases=0)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');args=p.parse_args()
    freeze() if args.freeze else run()
