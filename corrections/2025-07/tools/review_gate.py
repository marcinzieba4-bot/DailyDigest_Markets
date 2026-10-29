"""Require current chronology and independent selected-claim review receipts."""
import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATES = [dt.date(2025, 7, n).isoformat() for n in range(1, 32)
         if dt.date(2025, 7, n).weekday() < 5]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_review():
    chronology = json.loads((ROOT/'audit/cited_source_dates.json').read_text())
    if (chronology.get('date_screen_passed') is not True
            or sorted(chronology.get('spec_sha256', {})) != DATES):
        raise ValueError('Complete passing cited-source date screen required')
    if (chronology.get('timing_exceptions_sha256') != sha(ROOT/'audit/canonical_source_exceptions.json')
            or chronology.get('auditor_sha256') != sha(ROOT/'tools/audit_source_dates.py')):
        raise ValueError('Timing exceptions or source auditor changed after screening')
    exceptions = json.loads((ROOT/'audit/canonical_source_exceptions.json').read_text())['exceptions']
    approved = {(x['date'], x['id']): x for x in exceptions}
    for used in chronology.get('timing_exceptions_used', []):
        row = approved.get((used['date'], used['id']))
        proof = (ROOT/row.get('timing_proof_file', '')).resolve() if row else None
        if (not proof or not proof.is_relative_to(ROOT) or not proof.is_file()
                or sha(proof) != row.get('timing_proof_sha256')):
            raise ValueError('Timing proof changed after source screening: '+str(used))
    independent = json.loads((ROOT/'checks/independent_selected_review.json').read_text())
    if sorted(independent.get('reports', {})) != DATES:
        raise ValueError('Independent selected-claim review required for all 23 dates')
    for date in DATES:
        spec_hash = sha(ROOT/'specs'/f'{date}.json')
        feed_hash = sha(ROOT/'feeds'/f'{date}.json.gz')
        card_hash = sha(ROOT/'cards'/f'{date}.json')
        row = independent['reports'][date]
        if (chronology['spec_sha256'].get(date) != spec_hash
                or chronology.get('feed_sha256', {}).get(date) != feed_hash
                or row.get('spec_sha256') != spec_hash
                or row.get('feed_sha256') != feed_hash
                or row.get('card_sha256') != card_hash):
            raise ValueError(date+' changed after source or independent review')
        if (row.get('selected_review_passed') is not True
                or not row.get('reviewer') or not row.get('notes')):
            raise ValueError(date+' incomplete independent review')
    return {'dates': DATES, 'chronology_sha256': sha(ROOT/'audit/cited_source_dates.json'),
            'selected_review_sha256': sha(ROOT/'checks/independent_selected_review.json')}


if __name__ == '__main__':
    print(json.dumps(require_review(), indent=2))
