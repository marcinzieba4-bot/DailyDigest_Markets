"""Offline preflight by default; --go resumes only final-cutoff collection.

No catalogue, URL, context, cache parser, cap policy or source ID rule changes.
Refuses execution while any other collector exists, including a paused process.
"""
from __future__ import annotations
import argparse,datetime as dt,fcntl,json,os
from pathlib import Path
from fetch_news import ROOT,atomic_json
from expand_capped_news import PLAN,sha,prepare_final_cutoff_resume,harvest

def collectors():
    found=[]
    for p in Path('/proc').glob('[0-9]*'):
        try:
            pid=int(p.name)
            if pid==os.getpid():continue
            args=(p/'cmdline').read_bytes().decode(errors='replace').split('\0')
            scripts=[Path(a).name for a in args if a and '\n'not in a and len(a)<500]
            inline_fetch=any('fetch_news' in a and ('import fetch' in a or 'fetch_news.fetch' in a)for a in args)
            targeted_script=any('targeted' in a and ('news' in a or 'repair' in a)and a.endswith('.py')for a in scripts)
            if any(a in {'expand_capped_news.py','resume_final_cutoff.py'}for a in scripts)or inline_fetch or targeted_script:
                found.append({'pid':pid,'args':args[:-1]})
        except (OSError,ValueError):continue
    return found

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--go',action='store_true');parser.add_argument('--workers',type=int,default=2)
    a=parser.parse_args();assert 1<=a.workers<=4,'Recovery concurrency must remain at most four'
    active=collectors()
    if a.go and active:raise SystemExit('Another collector exists; no requests sent: '+json.dumps(active))
    _,_,_,_,note=prepare_final_cutoff_resume()
    record={**note,'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'active_collectors':active,'requests_sent':False,'proposed_workers':a.workers,'resume_helper_sha256':sha(Path(__file__))}
    atomic_json(ROOT/'audit_work/final_cutoff_resume_preflight.json',record)
    print(json.dumps({k:v for k,v in record.items()if k!='earlier_source_bindings'},indent=2),flush=True)
    if not a.go:return
    lockpath=ROOT/'audit/final_cutoff_resume.lock';lockpath.parent.mkdir(parents=True,exist_ok=True)
    with lockpath.open('a')as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        active=collectors()
        if active:raise SystemExit('Collector appeared during preflight; no requests sent: '+json.dumps(active))
        assert sha(PLAN)==note['prior_plan_sha256'],'Plan changed during preflight; rerun'
        harvest(a.workers,resume_final=True)
if __name__=='__main__':main()
