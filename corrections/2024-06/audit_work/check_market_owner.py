"""Owner checks and exact input manifests; not an independent approval."""
from pathlib import Path
from zoneinfo import ZoneInfo
import csv,datetime as dt,gzip,hashlib,json,math
R=Path(__file__).resolve().parent.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text())
checks=0;errors=[]
def ck(value,message):
 global checks
 checks+=1
 if not value:errors.append(message)
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
raw={j['ticker']:(p,j) for p in sorted((R/'data').glob('yf_*.json')) for j in [load(p)]}
retention=load(R/'audit/market_raw_retention.json');trimmed=[]
for rr in retention['sources']:
 t=rr['ticker'];p,j=raw[t];zone=ZoneInfo(j['tz']);a=load(R/'audit'/('actions_'+p.stem[3:]+'.json'))
 exact=a['exact_action_inputs'];ck(len(exact)==len(a['requests'])==2,t+' two exact action inputs')
 merged={}
 for x,request in zip(exact,a['requests']):
  ck(x['request']==request,t+' exact action request identity')
  ck(set(x['retained_identity_meta'])<={'currency','symbol','exchangeName','fullExchangeName','instrumentType','timezone','exchangeTimezoneName','firstTradeDate'},t+' no live action metadata')
  ck(not {'rows','prices','timestamp','indicators'}&set(x),t+' action-only payload')
  merged.update(x['retained_exact_split_events'])
 events=sorted([{'date':dt.datetime.fromtimestamp(e['date'],zone).date().isoformat(),'factor':float(e['numerator'])/float(e['denominator']),'ratio':e.get('splitRatio')} for e in merged.values()],key=lambda x:x['date'])
 ck(events==a['events'],t+' exact original split metadata replay')
 ck(len(rr['removed_out_of_scope_observations'])==rr['removed_out_of_scope_observation_count'],t+' exact trim count')
 ck(all(not '2024-04-01'<=x['exchange_local_date']<='2024-06-27' for x in rr['removed_out_of_scope_observations']),t+' trims out of scope only')
 source=json.loads(gzip.decompress((R/rr['path']).read_bytes()))['chart']['result'][0]
 ck(all('2024-04-01'<=dt.datetime.fromtimestamp(e['date'],zone).date().isoformat()<='2024-06-27' for e in source.get('events',{}).get('splits',{}).values()),t+' raw split metadata bounded')
 if rr['removed_out_of_scope_observation_count']:trimmed.append({'ticker':t,'removed':rr['removed_out_of_scope_observations']})
tr=load(R/'data/treasury_par.json');receipt=load(R/'audit/treasury_source.json');csvpath=R/'audit/treasury_retained.csv'
ck(receipt['retained_csv_sha256']==sha(csvpath),'Treasury exact retained CSV bytes')
rows=list(csv.DictReader(csvpath.open()));replay={dt.datetime.strptime(r['Date'],'%m/%d/%Y').date().isoformat():{k:float(v) for k,v in r.items() if k!='Date' and v} for r in rows}
ck(replay==tr,'Treasury exact retained cell strings replay')
ck(min(tr)>='2024-04-01' and max(tr)=='2024-06-27','Treasury retained range')
ck(len(rows)==receipt['retained_row_count'] and len(rows)+len(receipt['removed_out_of_scope_dates'])==receipt['original_source_row_count'],'Treasury exact trim inventory')
files=[*sorted((R/'data').glob('*.json')),*sorted((R/'audit').glob('actions_*.json')),*sorted((R/'audit/market_raw').glob('*')),R/'audit/market_raw_retention.json',R/'audit/market_fetch.json',csvpath,R/'audit/treasury_source.json',*[R/'tools'/n for n in ['fetch_market.py','build_cards.py','validate_market.py','market_calendar_policy.py']]]
manifest={'scope':'Exact owner inputs for June market cards. Full source histories are bounded Apr1–Jun27; every eligible slice is strict own-cutoff. Action ledgers include only later metadata for mechanical quote-unit reconstruction. This is not independent approval.','input_sha256':{str(p.relative_to(R)):sha(p) for p in files},'cards':{}}
for p in sorted((R/'cards').glob('2024-06-*.json')):
 c=load(p);d=c['report_date'];eligible={t:digest({'rows':[x for x in j['rows'] if x[0]<d],'as_traded_rows':[x for x in j['as_traded_rows'] if x[0]<d]}) for t,(f,j) in raw.items() if t in c['markets']}
 manifest['cards'][d]={'path':str(p.relative_to(R)),'sha256':sha(p),'cutoff_utc':c['cutoff_utc'],'used_symbols':sorted(eligible),'eligible_normalized_history_sha256':eligible,'eligible_treasury_history_sha256':digest({k:v for k,v in tr.items() if k<d})}
ck(len(manifest['cards'])==20,'Twenty card manifests')
mp=R/'audit/market_card_inputs.json';mp.write_text(json.dumps(manifest,indent=2)+'\n')
validation=load(R/'audit/market_validation.json');ck(validation['passed'] is True and not validation['errors'],'Owner market validation passed')
ck(validation['card_sha256']=={d:x['sha256'] for d,x in manifest['cards'].items()},'Current validation card hashes')
ck(validation['source_retention_sha256']==sha(R/'audit/market_raw_retention.json'),'Current validation retention hash')
result={'passed':not errors,'review_type':'owner checks only; independent acceptance pending','created_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'assertions':checks,'errors':errors,'cards':20,'raw_symbols':len(raw),'first_retained_inclusive':'2024-04-01','final_retained_inclusive':'2024-06-27','removed_future_observations_count':sum(len(x['removed']) for x in trimmed),'removed_future_observations':trimmed,'market_validation_sha256':sha(R/'audit/market_validation.json'),'market_card_inputs_sha256':sha(mp),'market_raw_retention_sha256':sha(R/'audit/market_raw_retention.json'),'owner_check_source_sha256':sha(Path(__file__)),'news_source_freeze_binding':'pending accepted news source freeze; no binding written'}
(R/'audit/market_owner_checks.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='removed_future_observations'},indent=2));raise SystemExit(bool(errors))
