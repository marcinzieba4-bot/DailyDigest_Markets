"""Bind all 23 final July reports to current accepted sources and component reviews.

No network calls, author-script execution or automatic editorial dispositions.
"""
from pathlib import Path
import datetime as dt
import json
import re
import merge_retail
import retail_quality_snapshot
import verify

ROOT=Path(__file__).resolve().parent.parent
DATES=verify.DATES
CITE=verify.CITE


def load(path):return json.loads(path.read_text())
def sha(path):return merge_retail.sha(path)
def save(path,value):return merge_retail.save(path,value)
def component(spec):return merge_retail.digest({k:v for k,v in spec.items() if k not in {'retail','retail_intro'}})


def reviewed_warnings(warnings,records,cited):
    """A receipt must name the actual diagnostic, its evidence and rationale."""
    decisions=[entry for record in records for entry in record.get('reviewed_validation_warnings',[])]
    errors=[];accepted=[]
    for warning in warnings:
        matches=[entry for entry in decisions if entry.get('warning')==warning]
        valid=[entry for entry in matches if len(entry.get('rationale','').strip())>=40
               and entry.get('evidence_ids') and set(entry['evidence_ids'])<=cited]
        if not valid:errors.append('Unresolved validation warning: '+warning)
        else:accepted.append(valid[0])
    return errors,accepted


def frozen_source_exclusions(source, source_rows):
    """Read either reviewed schema without inventing an empty exclusion map."""
    names=('known_semantic_exclusions','known_timing_exclusions')
    if any(name in source for name in names):
        if not all(name in source for name in names):
            raise ValueError('Incomplete legacy source exclusion records')
        records=[source[name]['by_date'] for name in names]
        if any(set(record)!=set(DATES) for record in records):
            raise ValueError('Expected all23 own-date source exclusion records')
        for date in DATES:
            if any(record[date].get('feed_sha256')!=source_rows[date]['feed_sha256'] for record in records):
                raise ValueError('Legacy exclusion record binds a stale feed: '+date)
        return {date:{row['id'] for record in records for row in record[date]['exclusions']}
                for date in DATES},{}
    bindings=source.get('input_bindings',{})
    excluded={};stable={}
    for date in DATES:
        path=ROOT/'audit'/f'news_ready_{date}.json'
        digest=sha(path);ready=load(path);relative=path.relative_to(ROOT).as_posix()
        if (bindings.get(relative)!=digest or source_rows[date].get('ready_receipt_sha256')!=digest
                or ready.get('date')!=date or ready.get('status')!='ready'
                or ready.get('ready_sha256')!=source_rows[date]['feed_sha256']):
            raise ValueError('Current source screening receipt is missing or stale: '+date)
        rows=ready.get('excluded')
        if not isinstance(rows,list) or ready.get('excluded_items')!=len(rows):
            raise ValueError('Source screening exclusion list/count mismatch: '+date)
        ids=[row['id'] for row in rows]
        if len(ids)!=len(set(ids)):raise ValueError('Duplicate screened exclusion ID: '+date)
        excluded[date]=set(ids);stable[path]=digest
    return excluded,stable


def main():
    required=[ROOT/'audit'/name for name in ['independent_source_review.json','independent_market_review.json']]
    required += [ROOT/folder/name for date in DATES for folder,name in
                 [('specs',date+'.json'),('nonretail_drafts',date+'.json'),('retail_drafts',date+'.json'),
                  ('audit','independent_nonretail_'+date+'.json'),('audit','independent_retail_'+date+'.json')]]
    missing=[str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        print('Pending reviewed inputs:',*missing,sep='\n');return 2
    source_path=ROOT/'audit/independent_source_review.json';market_path=ROOT/'audit/independent_market_review.json'
    source,market=load(source_path),load(market_path)
    if source.get('passed') is not True or market.get('passed') is not True or source.get('errors') or market.get('errors'):
        raise ValueError('Current independent source and market acceptance required')
    source_rows={row['date']:row for row in source.get('dates',[])}
    if set(source_rows)!=set(DATES) or len(source.get('dates',[]))!=23:
        raise ValueError('Source acceptance must cover exactly all 23 July weekdays')
    if set(market.get('dates',[]))!=set(DATES) or len(market.get('dates',[]))!=23:
        raise ValueError('Market acceptance must cover exactly all 23 July weekdays')
    excluded,screening_bindings=frozen_source_exclusions(source,source_rows)
    extra_path=ROOT/'audit/additional_release_exclusions.json'
    if extra_path.is_file():
        for row in load(extra_path)['exclusions']:
            verify.validate_date(row['date']);excluded[row['date']].add(row['id'])
    rows=[];warnings={};warning_decisions={};errors=[];stable={path:sha(path) for path in (source_path,market_path)}
    stable.update(screening_bindings)
    if extra_path.is_file():stable[extra_path]=sha(extra_path)
    for date in DATES:
        path=ROOT/'specs'/(date+'.json');data=load(path)
        candidate,paths,bound=merge_retail.reviewed_candidate(date)
        if candidate!=data:errors.append(date+': final spec differs from current independently reviewed drafts')
        fp,cp=paths['feed'],paths['card'];feed_hash,card_hash=bound['feed'],bound['card']
        if source_rows[date].get('feed_sha256')!=feed_hash:
            errors.append(date+': accepted source feed hash is stale')
        for label,record in [('source',source),('market',market)]:
            if record.get('card_sha256',{}).get(date)!=card_hash:errors.append(date+': '+label+' acceptance card hash is stale')
        failures,diagnostics,count,words=verify.verify(date,spec_override=data)
        errors.extend(date+': '+message for message in failures)
        prose=' '.join(text for _,_,text in verify.paragraphs(data))
        cited=set(CITE.findall(prose));bad=cited & excluded[date]
        if bad:errors.append(date+': known late/stale/ambiguous source used '+repr(sorted(bad)))
        nreview,rreview=load(paths['nonretail_review']),load(paths['retail_review'])
        unresolved,decisions=reviewed_warnings(diagnostics,[nreview,rreview],cited)
        errors.extend(date+': '+message for message in unresolved)
        warnings[date]=diagnostics;warning_decisions[date]=decisions
        nr_ranges=verify.block_ranges(data,include_retail=False)
        if len(nr_ranges)!=36:errors.append(date+': expected 36 nonretail blocks')
        row={'date':date,'spec_sha256':sha(path),'nonretail_content_sha256':component(data),
             'nonretail_draft_sha256':bound['nonretail'],'retail_draft_sha256':bound['retail'],
             'feed_sha256':feed_hash,'card_sha256':card_hash,'exclusions_sha256':bound['exclusions'],
             'nonretail_review_sha256':bound['nonretail_review'],'retail_review_sha256':bound['retail_review'],
             'words':words,'distinct_sources':count,'warnings':diagnostics,'nonretail_blocks_checked':len(nr_ranges)}
        rows.append(row);stable[path]=row['spec_sha256']
        stable.update({paths[key]:value for key,value in bound.items()})
    if sum(row['nonretail_blocks_checked'] for row in rows)!=828:errors.append('Expected all 828 nonretail blocks')
    if errors:
        print(*errors,sep='\n');return 1
    retail=retail_quality_snapshot.require_review(ROOT)
    if retail.get('reports_checked')!=23:raise ValueError('Complete July retail chronology review required')
    changed=[str(path.relative_to(ROOT)) for path,value in stable.items() if sha(path)!=value]
    if changed:raise ValueError('Reviewed inputs changed during final binding: '+repr(changed))
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    save(ROOT/'audit/final_editorial_review.json',{'checked_at_utc':now,'dates':DATES,'reports':rows,
         'fatal_or_major_remaining':0,'all_23_ready':True,'nonretail_blocks_checked':828,
         'scope':'Current final components bind their independent AI reviews and accepted own-date sources; headline-level review does not establish original article-body vintages.'})
    save(ROOT/'audit/final_precision_review.json',{'checked_at_utc':now,'passed':True,'dates':DATES,
         'spec_sha256':{row['date']:row['spec_sha256'] for row in rows},
         'additional_release_exclusions_sha256':sha(extra_path) if extra_path.is_file() else None,
         'source_acceptance_sha256':sha(source_path),'market_acceptance_sha256':sha(market_path),
         'retail_quality_july_sha256':sha(ROOT/'checks/retail_quality_july.json'),
         'scope':'Exact schema/ranges/citations, current independent component/source/exclusion hashes, explicit numeric FX exclusion and independently recorded warning dispositions. Instrument identity and claim meaning remain in component receipts.'})
    save(ROOT/'checks/validation_warning_review.json',{'dates':DATES,'warnings':warnings,
         'reviewed_decisions':warning_decisions,
         'disposition':'Every emitted diagnostic is explicitly reviewed in a bound independent component receipt; no blanket calendar-warning clearance.'})
    print('Final editorial and precision bindings passed:',len(rows),'reports,',sum(row['words'] for row in rows),'words; 828 nonretail blocks')
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print('FAIL final review:',exc);raise SystemExit(1)
