import csv, datetime as dt, os
D='/tmp/claude-0/-home-user/01233cf7-f758-5bad-b280-d38226412ca9/scratchpad/work/data'
def load_fred(sid):
    out={}
    for r in csv.DictReader(open(f'{D}/{sid}.csv')):
        v=r[sid]
        if v not in ('','.'): out[r['observation_date']]=float(v)
    return out
def load_yf(sym):
    out={}
    for r in csv.DictReader(open(f'{D}/yf_{sym}.csv')):
        out[r['Date']]=float(r['Close'])
    return out
F={s:load_fred(s) for s in ['DGS3MO','DGS2','DGS5','DGS10','DGS30','T10Y2Y','DFF']}
Y={s:load_yf(s) for s in ['TNX','IRX','FVX','TYX','GSPC','VIX','GC_F','CL_F','HG_F','BTC-USD','RUT','NDX']}
def asof(series, date, strict=False):
    """last observation on or before date (strict: before date). returns (date,value)"""
    d=dt.date.fromisoformat(date) if isinstance(date,str) else date
    keys=sorted(series)
    best=None
    for k in keys:
        kd=dt.date.fromisoformat(k)
        if kd<d or (kd==d and not strict): best=k
        else: break
    return best, (series[best] if best else None)
def weeks_ago(series, date, n_td=20, strict=False):
    """value ~n trading days before the as-of observation"""
    k,_=asof(series,date,strict)
    keys=sorted(series); i=keys.index(k); j=max(0,i-n_td)
    return keys[j], series[keys[j]]
