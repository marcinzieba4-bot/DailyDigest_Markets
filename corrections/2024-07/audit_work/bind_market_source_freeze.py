"""Bookkeeping-only binding of already accepted market inputs to the final July source freeze.
No card, observation, tool, report, source claim or prior accepted check is changed.
"""
from pathlib import Path
import json,hashlib,datetime as dt
ROOT=Path(__file__).resolve().parent.parent
DATES=[dt.date(2024,7,n).isoformat() for n in range(1,32) if dt.date(2024,7,n).weekday()<5]
sha=lambda blob:hashlib.sha256(blob).hexdigest()
def atomic(path,blob):
 tmp=path.with_suffix(path.suffix+'.binding.tmp');tmp.write_bytes(blob);tmp.replace(path)
def encoded(value):return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
def digest_map(value):return sha(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
def safe(relative):
 p=ROOT/relative
 if p.is_symlink() or not p.resolve().is_relative_to(ROOT) or not p.is_file():raise ValueError('Unsafe/missing accepted input '+relative)
 return p

def main():
 freeze_path=ROOT/'audit/source_freeze.json'
 if not freeze_path.is_file():
  print('READY: binding script prepared; final source_freeze.json is not present. No receipt changed.');return
 freeze_bytes=freeze_path.read_bytes();freeze_hash=sha(freeze_bytes);freeze=json.loads(freeze_bytes)
 if (freeze.get('status')!='all_23_ready' or [row.get('date') for row in freeze.get('dates',[])]!=DATES
      or freeze.get('frozen_feeds_immutable') is not True):raise ValueError('Final23-date immutable source freeze required')
 review_path=ROOT/'audit/independent_market_review.json';current_bytes=review_path.read_bytes();current=json.loads(current_bytes)
 if current.get('status')!='accepted' or current.get('passed') is not True or current.get('errors') or current.get('dates')!=DATES:raise ValueError('Original accepted23-date market review required')
 cards=current.get('card_sha256',{});inputs=current.get('input_sha256',{})
 if set(cards)!=set(DATES) or not inputs:raise ValueError('Complete accepted card/input maps required')
 for date,digest in cards.items():
  if sha(safe(f'cards/{date}.json').read_bytes())!=digest:raise ValueError('Accepted card changed '+date)
 for relative,digest in inputs.items():
  if sha(safe(relative).read_bytes())!=digest:raise ValueError('Accepted market input changed '+relative)
 # This checks the freeze transport/identity only; source factual acceptance belongs to its independent reviewer.
 for row in freeze['dates']:
  date=row['date'];declared=row.get('screened_sha256')
  if declared and sha(safe(f'feeds/{date}.json.gz').read_bytes())!=declared:raise ValueError('Frozen feed bytes changed '+date)
 backup=ROOT/'audit/review_history/independent_market_review_before_source_freeze.json';receipt_path=ROOT/'audit/market_source_freeze_binding.json'
 if current.get('source_freeze_sha256') is not None:
  if current['source_freeze_sha256']!=freeze_hash or not backup.is_file():raise ValueError('Different or unpreserved prior freeze binding')
  original_bytes=backup.read_bytes();original=json.loads(original_bytes);binding=current.get('source_freeze_binding',{})
  if binding.get('original_market_review_sha256')!=sha(original_bytes):raise ValueError('Original market provenance changed')
  if {k:v for k,v in current.items() if k not in {'source_freeze_sha256','source_freeze_binding'}}!=original:raise ValueError('Bound review changed pre-existing market claims')
  updated=current;updated_bytes=current_bytes
 else:
  original_bytes=current_bytes;original=current;backup.parent.mkdir(parents=True,exist_ok=True)
  if backup.exists():
   if backup.read_bytes()!=original_bytes:raise ValueError('Original receipt backup already differs')
  else:
   with backup.open('xb') as out:out.write(original_bytes)
  binding={'purpose':'Bookkeeping-only link to final source-freeze identity; all pre-existing market checks, numerical claims, limitations, card hashes and accepted input hashes are unchanged.','bound_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'original_market_review_path':str(backup.relative_to(ROOT)),'original_market_review_sha256':sha(original_bytes),'source_freeze_sha256':freeze_hash,'unchanged_card_map_sha256':digest_map(cards),'unchanged_market_input_map_sha256':digest_map(inputs),'binding_script_sha256':sha(Path(__file__).read_bytes()),'binding_receipt':'audit/market_source_freeze_binding.json'}
  updated={**current,'source_freeze_sha256':freeze_hash,'source_freeze_binding':binding};updated_bytes=encoded(updated)
  if {k:v for k,v in updated.items() if k not in {'source_freeze_sha256','source_freeze_binding'}}!=original:raise ValueError('Bookkeeping binding altered market content')
 if freeze_path.read_bytes()!=freeze_bytes:raise ValueError('Source freeze changed during binding checks')
 receipt={'status':'completed','bookkeeping_only':True,'bound_at_utc':binding['bound_at_utc'],'source_freeze_path':'audit/source_freeze.json','source_freeze_sha256':freeze_hash,'original_market_review_path':str(backup.relative_to(ROOT)),'original_market_review_sha256':sha(original_bytes),'updated_market_review_path':'audit/independent_market_review.json','updated_market_review_sha256':sha(updated_bytes),'dates':DATES,'unchanged_card_sha256':cards,'unchanged_market_input_sha256':inputs,'card_files_rechecked':len(cards),'market_input_files_rechecked':len(inputs),'preexisting_review_fields_unchanged':True,'binding_script_sha256':sha(Path(__file__).read_bytes()),'limits':['This adds source-freeze identity only; independent source replay/claim acceptance remains with the source reviewer.','No numerical value, market/card fact, report prose or acquisition/tool code was changed.']}
 if current_bytes!=updated_bytes:atomic(review_path,updated_bytes)
 readiness_path=ROOT/'audit/market_readiness.json'
 if readiness_path.is_file():
  ready_bytes=readiness_path.read_bytes();ready=json.loads(ready_bytes)
  if ready.get('card_sha256')!=cards or ready.get('market_review_sha256') not in {sha(original_bytes),sha(updated_bytes)}:raise ValueError('Unrelated or changed market readiness receipt')
  ready_backup=ROOT/'audit/review_history/market_readiness_before_source_freeze.json'
  if ready.get('market_review_sha256')==sha(original_bytes):
   if ready_backup.exists():
    if ready_backup.read_bytes()!=ready_bytes:raise ValueError('Readiness backup differs')
   else:
    with ready_backup.open('xb') as out:out.write(ready_bytes)
   ready={**ready,'market_review_sha256':sha(updated_bytes),'source_freeze_sha256':freeze_hash,'source_freeze_binding_receipt':'audit/market_source_freeze_binding.json','source_freeze_bound_at_utc':binding['bound_at_utc']};new_ready_bytes=encoded(ready)
  else:
   if not ready_backup.is_file() or ready.get('source_freeze_sha256')!=freeze_hash:raise ValueError('Unpreserved prior readiness binding')
   new_ready_bytes=ready_bytes
  receipt['readiness_original_path']=str(ready_backup.relative_to(ROOT));receipt['readiness_original_sha256']=sha(ready_backup.read_bytes());receipt['readiness_updated_sha256']=sha(new_ready_bytes)
  if ready_bytes!=new_ready_bytes:atomic(readiness_path,new_ready_bytes)
 if receipt_path.exists() and receipt_path.read_bytes()==encoded(receipt):
  print('ALREADY_BOUND',freeze_hash,sha(updated_bytes));return
 atomic(receipt_path,encoded(receipt))
 print('BOUND',len(cards),'cards',len(inputs),'unchangedinputs','freeze',freeze_hash,'marketreview',sha(updated_bytes))
if __name__=='__main__':main()
