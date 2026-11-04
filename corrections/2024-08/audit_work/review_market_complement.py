from pathlib import Path
import json,hashlib,datetime as dt
R=Path('/workspace/work/august2024')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
validation=read(R/'audit/market_validation.json')
assert validation['passed'] and not validation['errors']
raw={j['ticker']:j for p in (R/'data').glob('yf_*.json') for j in [read(p)]}
errors=[];checks=0

def ck(ok,msg):
 global checks
 checks+=1
 if not ok:errors.append(msg)

def movement(a,b):
 if abs(a)<4 and abs(b)<4:return 'little changed'
 if a==b:return 'parallel rally (both down equally; spread unchanged)' if a<0 else 'parallel selloff (both up equally; spread unchanged)'
 if a>0 and b>0:return 'bear steepening (both up, 10Y up more)' if b>a else 'bear flattening (both up, 2Y up more)'
 if a<0 and b<0:return 'bull steepening (both down, 2Y down more)' if b>a else 'bull flattening (both down, 10Y down more)'
 if b>0:return 'steepening (10Y up, 2Y down/flat)'
 if a>0:return 'flattening (2Y up, 10Y down/flat)'
 if b<0:return 'flattening (10Y down, 2Y up/flat)'
 return 'steepening (2Y down, 10Y up/flat)'

for date in validation['dates']:
 p=R/'cards'/f'{date}.json';c=read(p)
 ck(sha(p)==validation['card_sha256'][date],date+' frozen card hash')
 for ticker,x in c['markets'].items():
  j=raw[ticker]
  ck(x['currency']==j['currency'] and x['tz']==j['tz'],date+' '+ticker+' currency/timezone')
  ck(x['source_url']==j['source_url'] and x['return_unit']=='%',date+' '+ticker+' source/return unit')
  if ticker.startswith('^') or ticker in {'DX-Y.NYB','000001.SS'}:ck(x['level_unit']=='index points',date+' '+ticker+' index unit')
 z=c['treasury'];ck(z['curve_move_20obs']==movement(z['chg_20obs_bps']['2y'],z['chg_20obs_bps']['10y']),date+' curve movement label')
 dates=sorted(k for k in read(R/'data/treasury_par.json') if k<date)
 ck(z['prior_5obs_date']==dates[-6],date+' Treasury five-observation date')
result={'status':'accepted' if not errors else 'failed','passed':not errors,'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'dates':validation['dates'],'errors':errors,'assertions':validation['assertions']+checks,'root_complement_assertions':checks,'infrastructure_receipt_sha256':sha(R/'audit/market_validation.json'),'root_replay_log_sha256':sha(R/'audit_work/market_replay.log'),'source_freeze_sha256':sha(R/'audit/source_freeze.json'),'card_sha256':validation['card_sha256'],'tool_sha256':{'validate_market.py':sha(R/'tools/validate_market.py'),'review_market_complement.py':sha(Path(__file__))},'scope':'Root inspected and reran the independent bounded-input/session/calendar/split/Treasury preflight, then independently checked currency, timezone, index units, return units, source identity, Treasury reference dates and curve-move wording against frozen raw inputs. This accepts infrastructure only; report claims require separate editorial review.','limitations':validation['limitations']}
(R/'audit/independent_market_review.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['status','assertions','root_complement_assertions','errors']}))
raise SystemExit(bool(errors))
