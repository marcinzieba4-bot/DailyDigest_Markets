"""Package exact frozen acquisition inputs and replay code without acquiring or changing evidence."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parent.parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
 temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');temp.replace(path)
def main():
 source=json.loads((ROOT/'audit/independent_source_review.json').read_text())
 market=json.loads((ROOT/'audit/independent_market_review.json').read_text())
 if not source['passed'] or not market['passed']:raise ValueError('Accepted source and market inputs required')
 paths=set()
 for folder in ['cache/news','cache/rss_raw','audit/news_provenance','work/source_candidates','work/unreviewed_feeds','exclusions','source_supplements','audit/source_amendments','audit/review_history','work/withdrawn_aug14_retail']:
  paths.update(p for p in (ROOT/folder).rglob('*') if p.is_file())
 paths.update((ROOT/'audit').glob('*.csv'))
 paths.update((ROOT/'audit_work').glob('*.py'))
 for name in ['review_sources.py','review_market_complement.py','amend_retail_sources.py','independent_source_amendment_review.py','independent_artifact_delivery_tool_review.py','physical_source_inventory.json','source_review_draft.json','market_replay.log','source_replay.log']:
  path=ROOT/'audit_work'/name
  if path.is_file():paths.add(path)
 for name in ['newest_lambda_function.py','code_provenance.json','checks/code_discovery.json']:
  paths.add(ROOT/name)
 rows=[]
 for path in sorted(paths):
  if path.is_symlink() or not path.resolve().is_relative_to(ROOT) or not path.is_file():raise ValueError('Unsafe packaging path')
  rows.append({'path':str(path.relative_to(ROOT)),'sha256':sha(path),'bytes':path.stat().st_size})
 if len({r['path'] for r in rows})!=len(rows):raise ValueError('Duplicate packaging input')
 result={'status':'frozen_inputs_hash_bound','files':rows,'file_count':len(rows),'source_acceptance_sha256':sha(ROOT/'audit/independent_source_review.json'),'market_acceptance_sha256':sha(ROOT/'audit/independent_market_review.json'),'scope':'Exact raw RSS responses, parsed request cache, per-headline physical provenance, staged and final raw feed proof, independent replay code/results, bounded market Treasury CSV, and latest code discovery. Writer-facing feeds, cards, specifications, reviews and final tooling are included separately by the artifact builder. No earlier attempts, other-month factual reports, credentials or original full Lambda deployment archive are included.'}
 write(ROOT/'audit/news_replay_inventory.json',result)
 print(json.dumps({'files':len(rows),'bytes':sum(r['bytes'] for r in rows),'inventory_sha256':sha(ROOT/'audit/news_replay_inventory.json')}))
if __name__=='__main__':main()
