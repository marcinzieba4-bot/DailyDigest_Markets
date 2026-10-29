"""Reviewer-only hindsight tripwire; root inferred from this file, never hard-coded.

Reads specs without changing them. Outcome regex matches are candidates only:
previews and descriptions of older releases can match. Review wording, date,
and citations before deciding. Calendar metadata must never enter writer feeds.
"""
from pathlib import Path
import argparse,json,re
ROOT=Path(__file__).resolve().parent.parent
CITE=re.compile(r'\s*\[\[n\d{4,6}\]\]')
def strings(obj,path='$'):
 if isinstance(obj,str):yield path,CITE.sub('',obj)
 elif isinstance(obj,list):
  for i,x in enumerate(obj):yield from strings(x,f'{path}[{i}]')
 elif isinstance(obj,dict):
  for k,x in obj.items():yield from strings(x,f'{path}.{k}')
def scan(report_date,spec,events):
 out=[]
 for e in events:
  rx=e.get('outcome_regex')
  if not rx or report_date>=e['first_eligible_weekday_report']:continue
  for path,text in strings(spec):
   if re.search(rx,text,re.I|re.S):out.append({'date':report_date,'rule':e['id'],'event':e['event'],'first_eligible_report':e['first_eligible_weekday_report'],'where':path,'text':text,'disposition':'unreviewed candidate; verify actual claim and own-date citation'})
 return out
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('dates',nargs='*');p.add_argument('--spec-dir',type=Path,default=ROOT/'specs');p.add_argument('--output',type=Path,default=ROOT/'checks'/'release_guard_flags.json');p.add_argument('--fail-on-flags',action='store_true');a=p.parse_args()
 events=json.loads((ROOT/'posthoc'/'release_chronology.json').read_text())['events']
 files=[a.spec_dir/f'{d}.json' for d in a.dates] if a.dates else sorted(a.spec_dir.glob('2025-09-*.json'))
 flags=[]
 for f in files:flags+=scan(f.stem,json.loads(f.read_text()),events)
 out={'purpose':'Reviewer only; heuristic candidates requiring disposition. Do not supply later calendar knowledge to writers.','spec_dir':str(a.spec_dir.resolve()),'reports_checked':len(files),'method':'Compare report dates to first eligible weekday release boundaries, then search outcome wording. Exact release times may be schedule-derived.','flags':flags}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2))
 print(len(files),'reports;',len(flags),'release-boundary candidates;',a.output)
 if flags and a.fail_on_flags:raise SystemExit(1)
if __name__=='__main__':main()
