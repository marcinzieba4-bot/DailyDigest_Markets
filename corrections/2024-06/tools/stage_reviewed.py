"""Validate and stage accepted June components; never stage an invalid candidate."""
from pathlib import Path
import argparse
import json
import merge_retail
import verify

ROOT=Path(__file__).resolve().parent.parent
DATES=verify.DATES


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dates',nargs='*');args=parser.parse_args()
    dates=args.dates or DATES
    if len(dates)!=len(set(dates)):parser.error('Duplicate report dates')
    for date in dates:verify.validate_date(date)
    ready=[];pending=[];errors=[]
    for date in dates:
        try:
            row=merge_retail.merge(date);ready.append(row)
        except FileNotFoundError as exc:
            pending.append(date)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            errors.append({'date':date,'error':str(exc)})
    report={'requested_dates':dates,'ready':ready,'pending':pending,'errors':errors,
            'ready_count':len(ready),'all_20_ready':set(dates)==set(DATES) and len(ready)==20 and not pending and not errors,
            'total_words':sum(x['words'] for x in ready)}
    merge_retail.save(ROOT/'checks/staged_reviewed.json',report)
    print(json.dumps({'ready':len(ready),'all_20_ready':report['all_20_ready'],'pending':pending,'errors':errors,
                      'warnings':{x['date']:x['warnings'] for x in ready if x['warnings']},'total_words':report['total_words']},ensure_ascii=False,indent=2))
    return 1 if errors else 2 if pending else 0


if __name__=='__main__':
    raise SystemExit(main())
