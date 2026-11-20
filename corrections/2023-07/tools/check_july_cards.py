"""Verify all 21 dated historical cards, write one isolated plain-text digest per edition."""
from pathlib import Path
from datetime import date,timedelta
import hashlib,json,sys
root=Path(sys.argv[1]); out=root/'daily_summary'; out.mkdir(exist_ok=True)
audit=root/'audit'; audit.mkdir(exist_ok=True)
reference=[["2023-07-03","06/30",4.87,3.81,54,20],["2023-07-04","07/03",4.94,3.86,44,17],["2023-07-05","07/03",4.94,3.86,44,17],["2023-07-06","07/05",4.94,3.95,48,26],["2023-07-07","07/06",4.99,4.05,48,35],["2023-07-10","07/07",4.94,4.06,38,27],["2023-07-11","07/10",4.85,4.01,33,28],["2023-07-12","07/11",4.88,3.99,29,24],["2023-07-13","07/12",4.72,3.86,17,13],["2023-07-14","07/13",4.59,3.76,-8,-8],["2023-07-17","07/14",4.74,3.83,0,0],["2023-07-18","07/17",4.74,3.81,12,9],["2023-07-19","07/18",4.74,3.8,4,3],["2023-07-20","07/19",4.74,3.75,6,1],["2023-07-21","07/20",4.8,3.85,12,13],["2023-07-24","07/21",4.82,3.84,5,4],["2023-07-25","07/24",4.81,3.86,10,12],["2023-07-26","07/25",4.85,3.91,20,19],["2023-07-27","07/26",4.82,3.86,8,9],["2023-07-28","07/27",4.91,4.01,20,30],["2023-07-31","07/28",4.87,3.96,0,11]]
sectors='XLK XLC XLF XLE XLI XLY XLP XLV XLB XLRE XLU EXV5.DE SOXX'.split()
proxies='^GSPC ^NDX ^IXIC ^VIX ^RUT DX-Y.NYB CL=F BZ=F GC=F HG=F HYG LQD TLT IWM KRE ^N225 ^HSI 000001.SS KWEB ^AXJO ETFBW20TR.WA EPOL BTC-USD ETH-USD XRP-USD'.split()
retail='TSLA NVDA RIVN COIN META PLTR AI MSFT GOOGL AMD TQQQ CVNA AMC ROKU MAT SOFI BYND TUPBQ NKLAQ SPY QQQ CAVA INTC UPST GME SIRI LCID'.split()
previously_issued=set()
checks=[]
for ds,session,y2,y10,delta2,delta10 in reference:
 card_file=root/'cards'/f'{ds}.json'; card=json.loads(card_file.read_text()); m=card['markets']; curve=card['treasury']; cutoff=date.fromisoformat(ds); prev=cutoff-timedelta(days=1)
 assert card['cutoff_utc']==ds+'T00:00:00Z' and card['report_date']==ds and cutoff.weekday()<5
 assert curve['prior_close_date']==f'2023-{session.replace("/", "-")}'
 assert float(curve['prior_close_pct']['2y'].rstrip('%'))==y2 and float(curve['prior_close_pct']['10y'].rstrip('%'))==y10
 assert curve['chg_20obs_bps']['2y']==delta2 and curve['chg_20obs_bps']['10y']==delta10 and curve['spread_10y_2y_bps']==round((y10-y2)*100)
 assert not [t for t in m if t.endswith('=X')]
 assert all(v['session']<ds and all(v.get(f'ref_{n}s_session','') is None or v[f'ref_{n}s_session']<v['session'] for n in (1,5,20)) for v in m.values())
 assert all(v['session']==prev.isoformat() for t,v in m.items() if t.endswith('-USD'))
 for t in ['^GSPC','SPY','TSLA','NVDA']:
  if t in m: assert m[t]['session']==curve['prior_close_date'], (ds,t,m[t]['session'],curve['prior_close_date'])
 if ds=='2023-07-18':
  for t in ('^N225','^HSI','0700.HK','9988.HK'):
   if t in m: assert m[t]['session']=='2023-07-14'
 if ds=='2023-07-31':
  for t,target in [('^GSPC',4582.23),('^IXIC',14316.66),('^VIX',13.33)]:
   if t in m: assert abs(float(m[t]['close'].replace(',',''))-target)<0.015,(t,m[t]['close'],target)
  if 'NVDA' in m: assert 400<float(m['NVDA']['close'].replace(',',''))<500, m['NVDA']
 lines=[f'{ds} | prior completed sessions only', f'Treasury {curve["prior_close_date"]} | 2Y {y2:.2f}% | 10Y {y10:.2f}% | 10Y−2Y {curve["spread_10y_2y_bps"]:+d}bp | 20 observations {delta2:+d}bp / {delta10:+d}bp', 'Ticker | session | close | unit | 1 / 5 / 20 session price returns (%)']
 for title,tickers in [('Markets',proxies),('Sectors',sectors),('Retail candidates',retail)]:
  lines.append(title)
  for t in tickers:
   if t not in m: continue
   x=m[t]; pct=' / '.join(f'{v:+.2f}' if v is not None else '—' for v in [x['chg_1s_pct'],x['chg_5s_pct'],x['chg_20s_pct']]); lines.append(f"{t} | {x['session']} | {x['close'] or '—'} | {x['level_unit']} | {pct}")
 (out/(ds+'.txt')).write_text('\n'.join(lines)+'\n');checks.append({'report_date':ds,'market_count':len(m),'card_sha256':hashlib.sha256(card_file.read_bytes()).hexdigest(),'sector_missing':[t for t in sectors if t not in m],'unavailable_or_excluded':sorted(set(card['unavailable_symbols'])|set(card['excluded_instruments']))})
assert len(checks)==21
(audit/'market_cards_verified.json').write_text(json.dumps({'provenance':'Independent June/July 2023 US Treasury published-table cross-checks for all dates. Prior-session US benchmark prices cross-checked to July 28 daily press/market tables. Hashes bind final cards. Missing vendor instruments retained as unavailable.','verification':checks},indent=2)+'\n'); print(f'Verified {len(checks)} cards; daily market coverage {min(d["market_count"] for d in checks)}–{max(d["market_count"] for d in checks)} instruments.')
