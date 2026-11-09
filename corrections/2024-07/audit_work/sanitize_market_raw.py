"""Remove live Yahoo metadata from bounded-history audit payloads, retaining exact historical arrays.
Original network bytes are hashed in fetch provenance but deliberately not retained because their
meta object embeds current prices outside the historical scope. No observation is filled or changed.
"""
from pathlib import Path
import json,gzip,hashlib,datetime as dt
R=Path(__file__).resolve().parent.parent
KEEP_META={'currency','symbol','exchangeName','fullExchangeName','instrumentType','timezone','exchangeTimezoneName','firstTradeDate'}
ledger=[]
for p in sorted((R/'audit/market_raw').glob('*.json.gz')):
 original=gzip.decompress(p.read_bytes());full=json.loads(original)
 # Main fetch originally stores the API chart envelope.
 if 'chart' not in full:raise ValueError('Unexpected source envelope '+str(p))
 result=full['chart']['result'][0];removed=sorted(set(result['meta'])-KEEP_META)
 keep={'meta':{k:v for k,v in result['meta'].items() if k in KEEP_META},'timestamp':result.get('timestamp',[]),'indicators':{'quote':[{'close':result['indicators']['quote'][0]['close']}]},'events':{'splits':result.get('events',{}).get('splits',{})}}
 ticker=keep['meta']['symbol'];data_path=R/'data'/('yf_'+ticker.replace('^','_').replace('=','_').replace('.','_')+'.json');j=json.loads(data_path.read_text());rawhash=hashlib.sha256(original).hexdigest();assert rawhash==j['source_response_sha256'],ticker
 retained=json.dumps({'chart':{'result':[keep],'error':None}},ensure_ascii=False,separators=(',',':')).encode();p.write_bytes(gzip.compress(retained,mtime=0))
 ledger.append({'ticker':ticker,'path':str(p.relative_to(R)),'original_network_response_sha256':rawhash,'retained_uncompressed_sha256':hashlib.sha256(retained).hexdigest(),'retained_gzip_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'removed_meta_fields':removed,'historical_timestamp_and_close_arrays_unchanged':True,'retained_meta_fields':sorted(keep['meta'])})
 j['retained_source_path']=str(p.relative_to(R));j['retained_source_sha256']=hashlib.sha256(retained).hexdigest();data_path.write_text(json.dumps(j))
(R/'audit/market_raw_retention.json').write_text(json.dumps({'purpose':'Exact historical quote arrays retained for independent replay; live quote metadata discarded so no later price survives. Original response hashes identify network provenance; sanitized retained bytes have separate explicit hashes.','created_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'sources':ledger},ensure_ascii=False,indent=2)+'\n');print('Sanitized',len(ledger),'bounded responses; no live-market meta retained')
