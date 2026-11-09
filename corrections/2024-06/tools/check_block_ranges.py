"""Check all 720 June nonretail block ranges and current independent bindings."""
import argparse
import datetime as dt
import json
from pathlib import Path
import merge_retail
import verify

ROOT=Path(__file__).resolve().parent.parent
DATES=verify.DATES


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dates',nargs='*');parser.add_argument('--drafts',action='store_true',help='Read nonretail_drafts instead of merged specs')
    args=parser.parse_args();dates=args.dates or DATES
    if len(dates)!=len(set(dates)):parser.error('Duplicate report dates')
    reports=[];violations=[];pending=[]
    for date in dates:
        verify.validate_date(date)
        path=ROOT/('nonretail_drafts' if args.drafts else 'specs')/(date+'.json')
        if not path.is_file():pending.append(date);continue
        spec=json.loads(path.read_text())
        nr={key:value for key,value in spec.items() if key not in {'retail','retail_intro'}}
        component_hash=merge_retail.digest(nr)
        review_path=ROOT/'audit'/('independent_nonretail_'+date+'.json')
        review=json.loads(review_path.read_text()) if review_path.is_file() else {}
        accepted=(type(review.get('fatal_or_major_remaining')) is int and review['fatal_or_major_remaining']==0
                  and review.get('nonretail_content_sha256')==component_hash and review.get('date')==date
                  and review.get('status') in ('accepted','passed'))
        for key,folder,suffix in [('feed','feeds','.json.gz'),('card','cards','.json'),('exclusions','exclusions','.json')]:
            artifact=ROOT/folder/(date+suffix)
            accepted=accepted and artifact.is_file() and review.get(key+'_sha256')==merge_retail.sha(artifact)
        if not accepted:pending.append(date)
        rows=verify.block_ranges(nr,include_retail=False)
        if len(rows)!=36:violations.append({'date':date,'error':'Expected exactly 36 nonretail blocks','actual':len(rows)})
        violations.extend({'date':date,**row} for row in rows if not row['in_range'])
        reports.append({'date':date,'nonretail_content_sha256':component_hash,
                        'review_status':'independently_reviewed' if accepted else 'pending',
                        'blocks_checked':len(rows),'actual_nonretail_body_words':sum(row['words'] for row in rows),
                        'out_of_range_count':sum(not row['in_range'] for row in rows),'blocks':rows})
    result={'review_type':'actual_nonretail_block_word_ranges','generated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'method':'Whitespace words in paragraph bodies after citation removal; includes source tags, excludes titles, labels and retail.',
            'expected_dates':len(dates),'expected_blocks':36*len(dates),'all_dates':len(reports),
            'total_blocks_checked':sum(r['blocks_checked'] for r in reports),'out_of_range_count':len(violations),
            'provisional_dates':pending,'reports':reports,'out_of_range':violations,
            'limitations':['Exact word ranges and current independent component/source hashes only; claim semantics are reviewed separately.']}
    merge_retail.save(ROOT/'checks/block_word_range_review.json',result)
    print(json.dumps({key:result[key] for key in ['expected_dates','expected_blocks','all_dates','total_blocks_checked','out_of_range_count','provisional_dates']}))
    return 1 if violations else 2 if pending else 0


if __name__=='__main__':
    raise SystemExit(main())
