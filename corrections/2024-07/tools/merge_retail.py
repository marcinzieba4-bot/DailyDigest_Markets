"""Merge only current, independently accepted own-date components.

The merged candidate is validated in memory before any spec is replaced. No
writer script is executed and neither authored component is rewritten.
"""
from pathlib import Path
import argparse
import hashlib
import json
import verify

ROOT = Path(__file__).resolve().parent.parent
FIELDS = {'retail_intro', 'retail'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.merge.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    temp.replace(path)


def reviewed_candidate(date):
    verify.validate_date(date)
    paths = {
        'nonretail': ROOT/'nonretail_drafts'/f'{date}.json',
        'retail': ROOT/'retail_drafts'/f'{date}.json',
        'nonretail_review': ROOT/'audit'/f'independent_nonretail_{date}.json',
        'retail_review': ROOT/'audit'/f'independent_retail_{date}.json',
        'feed': ROOT/'feeds'/f'{date}.json.gz',
        'card': ROOT/'cards'/f'{date}.json',
        'exclusions': ROOT/'exclusions'/f'{date}.json',
    }
    missing = [str(path.relative_to(ROOT)) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError('Pending reviewed inputs: '+', '.join(missing))
    bound = {key: sha(path) for key, path in paths.items()}
    nr, retail = load(paths['nonretail']), load(paths['retail'])
    nreview, rreview = load(paths['nonretail_review']), load(paths['retail_review'])
    if set(nr) != verify.NONRETAIL_KEYS or set(retail) != verify.RETAIL_KEYS:
        raise ValueError('Component keys differ from their authoring scopes: '+date)
    if nr.get('date') != date or retail.get('date') != date:
        raise ValueError('Component date identity mismatch: '+date)
    for record in (nreview, rreview):
        if (record.get('date') != date
                or type(record.get('fatal_or_major_remaining')) is not int
                or record['fatal_or_major_remaining'] != 0
                or record.get('status') not in (None, 'accepted', 'passed')):
            raise ValueError('Independent component review is unresolved: '+date)
        if any(record.get(key+'_sha256') != bound[key] for key in ('feed', 'card')):
            raise ValueError('Independent component review binds stale sources: '+date)
    if nreview.get('nonretail_content_sha256') != digest(nr):
        raise ValueError('Nonretail component changed after independent review: '+date)
    if rreview.get('retail_draft_sha256', rreview.get('draft_sha256')) != bound['retail']:
        raise ValueError('Retail draft changed after independent review: '+date)
    candidate = {**nr, 'retail_intro': retail['retail_intro'], 'retail': retail['retail']}
    if digest({k:v for k,v in candidate.items() if k not in FIELDS}) != digest(nr):
        raise ValueError('Nonretail component was not preserved')
    return candidate, paths, bound


def merge(date):
    candidate, paths, bound = reviewed_candidate(date)
    failures, warnings, sources, words = verify.verify(date, spec_override=candidate)
    if failures:
        raise ValueError('Final validation rejected '+date+': '+'; '.join(failures))
    if any(sha(paths[key]) != value for key, value in bound.items()):
        raise ValueError('Reviewed inputs changed during staging: '+date)
    target = ROOT/'specs'/f'{date}.json'
    blob = (json.dumps(candidate, ensure_ascii=False, indent=2)+'\n').encode()
    if not target.is_file() or target.read_bytes() != blob:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix('.merge.tmp'); temp.write_bytes(blob); temp.replace(target)
    receipt = {'date': date, 'retail_source_sha256': bound['retail'],
               'spec_sha256': sha(target), 'nonretail_content_sha256': digest({k:v for k,v in candidate.items() if k not in FIELDS}),
               'nonretail_preserved': True, 'reviewed_input_sha256': bound,
               'words': words, 'sources': sources, 'failures': [], 'warnings': warnings}
    save(ROOT/'checks'/f'retail_merge_{date}.json', receipt)
    return receipt


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dates', nargs='+'); args=parser.parse_args(); bad=False
    for date in args.dates:
        try:
            row=merge(date); print(date, 'reviewed components merged;', row['words'], 'words;', len(row['warnings']), 'warnings')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print('FAIL', date, exc); bad=True
    raise SystemExit(1 if bad else 0)
