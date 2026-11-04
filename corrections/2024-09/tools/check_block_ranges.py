"""Check all September nonretail block ranges against the reviewed components."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
DATES = [dt.date(2024, 9, n).isoformat() for n in range(1, 31)
         if dt.date(2024, 9, n).weekday() < 5]
CITE = re.compile(r'\[\[n\d+\]\]')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def main():
    reports, violations, pending = [], [], []
    for date in DATES:
        spec = json.loads((ROOT/'specs'/(date+'.json')).read_text())
        nr = {key: value for key, value in spec.items()
              if key not in {'retail', 'retail_intro'}}
        component_hash = digest(nr)
        review_path = ROOT/'audit'/('independent_nonretail_'+date+'.json')
        review = json.loads(review_path.read_text()) if review_path.exists() else {}
        accepted = (review.get('fatal_or_major_remaining') == 0
                    and review.get('nonretail_content_sha256') == component_hash)
        if not accepted:
            pending.append(date)
        rows = []

        def add(component, name, bounds, block):
            words = sum(len(CITE.sub('', text).split()) for _, text in block['parts'])
            low, high = bounds
            row = dict(component=component, block=name, words=words,
                       minimum=low, maximum=high, in_range=low <= words <= high)
            rows.append(row)
            if not row['in_range']:
                violations.append(dict(date=date, **row))

        geo_bounds = [(400, 500), (250, 350), (800, 950), (270, 350),
                      (200, 300), (850, 1050)]
        for block, bounds in zip(spec['geo'], geo_bounds):
            add('geo', block['key'], bounds, block)
        for block in spec['sectors']:
            add('sectors', block['key'], (150, 200), block)
        for component, bounds in [('earnings_pattern', (350, 420)),
                                  ('crypto', (290, 360)), ('flows', (600, 750))]:
            add(component, spec[component]['title'], bounds, spec[component])
        for component, bounds in [('underowned', (110, 150)),
                                  ('anticipatory', (140, 190)), ('catalysts', (100, 140))]:
            for i, block in enumerate(spec[component]):
                add(component, str(i+1)+': '+block['title'], bounds, block)
        if len(rows) != 36:
            raise ValueError('Expected 36 nonretail blocks: '+date)
        reports.append(dict(date=date, nonretail_content_sha256=component_hash,
                            review_status='independently_reviewed' if accepted else 'pending',
                            blocks_checked=len(rows),
                            actual_nonretail_body_words=sum(row['words'] for row in rows),
                            out_of_range_count=sum(not row['in_range'] for row in rows), blocks=rows))
    result = dict(review_type='actual_nonretail_block_word_ranges',
                  generated_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  method='Whitespace words in paragraph bodies after canonical citation removal; includes ordinary source tags, excludes titles, labels and retail.',
                  all_dates=len(reports), total_blocks_checked=sum(r['blocks_checked'] for r in reports),
                  out_of_range_count=len(violations), provisional_dates=pending,
                  reports=reports, out_of_range=violations,
                  limitations=['Word-range and current independent-component binding check only; financial claim review is recorded separately.'])
    (ROOT/'checks/block_word_range_review.json').write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps({key: result[key] for key in
                      ['all_dates', 'total_blocks_checked', 'out_of_range_count', 'provisional_dates']}))
    if violations or pending:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
