"""Conservatively suppress latest-session/horizon metrics affected by raw vendor gaps.
No observations are filled or dates shifted. Cash-market calendars are independent
of Yahoo. Futures, crypto and DXY retain their separate vendor/candle conventions.
"""
from functools import lru_cache
import exchange_calendars as xc
SUFFIX={'.WA':'XWAR','.DE':'XETR','.PA':'XPAR','.CO':'XCSE','.L':'XLON','.SW':'XSWX','.T':'XTKS','.KS':'XKRX','.SS':'XSHG','.HK':'XHKG','.AX':'XASX'}
INDICES={'^VIX':'XCBF','^NDX':'XNAS','^SOX':'XNAS','^N225':'XTKS','^KS11':'XKRX','^TWII':'XTAI','000001.SS':'XSHG','^HSI':'XHKG','^AXJO':'XASX','^FTSE':'XLON','^GDAXI':'XETR','^FCHI':'XPAR','^STOXX':'XETR','^STOXX50E':'XETR'}
def calendar_code(t):
 if t.endswith(('=X','=F','-USD')) or t=='DX-Y.NYB':return None
 return INDICES.get(t) or next((v for k,v in SUFFIX.items() if t.endswith(k)),'XNYS')
@lru_cache(None)
def expected_sessions(code,start,end):return xc.get_calendar(code).sessions_in_range(start,end).strftime('%Y-%m-%d').tolist()
def sanitize(t,j,rows,x,date):
 code=calendar_code(t)
 if code is None:return x,None
 import datetime as dt
 lastday=(dt.date.fromisoformat(date)-dt.timedelta(days=1)).isoformat()
 expected=expected_sessions(code,j['rows'][0][0],lastday)
 if rows[-1][0]!=expected[-1]:return None,'Latest completed exchange session '+expected[-1]+' is missing from vendor history; stale substitute omitted'
 affected=[]
 for n in (1,5,20):
  expected_ref=expected[-n-1] if len(expected)>n else None
  actual_ref=rows[-n-1][0] if len(rows)>n else None
  if expected_ref!=actual_ref:
   x[f'chg_{n}s_pct']=None;x[f'ref_{n}s_session']=None;affected.append(n)
   if n==20:x['ref_20s_close']=None;x['reference_share_units_differ']=None;x['reference_level_note']=None
 if affected:
  x['vendor_gap_limitation']='Missing vendor observation inside requested '+', '.join(str(n) for n in affected)+'-session horizons; affected returns and references suppressed, not estimated'
  x['history_limitation']='; '.join(filter(None,[x.get('history_limitation'),x['vendor_gap_limitation']]))
 return x,None

