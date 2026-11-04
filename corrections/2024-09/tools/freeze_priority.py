"""Compatibility entry point: September permits only complete full-month finalization."""
from __future__ import annotations
import argparse,datetime as dt
from expand_capped_news import ROOT,COVERAGE,DATES,read
from finalize_sources import main
if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('date');ap.add_argument('--workers',type=int,default=24);a=ap.parse_args()
 assert dt.date.fromisoformat(a.date)in DATES,'Not an September weekday edition'
 assert COVERAGE.exists(),'Complete full-month acquisition is required before any freeze'
 proof=read(COVERAGE)
 assert proof['report_dates']==21 and proof['failed_requests']==0,'Complete successful full-month acquisition required'
 main()
