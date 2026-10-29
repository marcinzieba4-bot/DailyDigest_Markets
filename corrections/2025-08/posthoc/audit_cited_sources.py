"""Offline canonical-date screen. Path dates are evidence, not body-vintage proof."""
from pathlib import Path
import datetime as dt
import gzip
import hashlib
import json
import re
import urllib.parse

ROOT = Path(__file__).resolve().parent.parent
MONTHS = {v.lower(): i for i, v in enumerate(
    ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], 1)}

def path_dates(url):
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path)
    values = re.findall(r'(?<!\d)(20\d{2})[-/](\d{1,2})[-/](\d{1,2})(?!\d)', path)
    values += re.findall(r'(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)', path)
    for year, month, day in re.findall(r'/(20\d{2})/([a-z]{3})/(\d{1,2})(?:/|$)', path, re.I):
        if month.lower() in MONTHS:
            values.append((year, str(MONTHS[month.lower()]), day))
    dates = set()
    for year, month, day in values:
        try:
            dates.add(dt.date(int(year), int(month), int(day)).isoformat())
        except ValueError:
            pass
    return sorted(dates)

def main():
    cache = json.loads((ROOT/'audit/canonical_all_cited_urls.json').read_text())
    exceptions = json.loads((ROOT/'audit/canonical_source_exceptions.json').read_text())['exceptions']
    approved = {(x['date'], x['id']): x for x in exceptions}
    rows, conflicts, missing, used_exceptions, hashes = [], [], [], [], {}
    for path in sorted((ROOT/'specs').glob('2025-08-*.json')):
        date = path.stem
        hashes[date] = hashlib.sha256(path.read_bytes()).hexdigest()
        feed = {x['id']: x for x in json.load(gzip.open(ROOT/'feeds'/f'{date}.json.gz', 'rt'))['items']}
        cutoff = dt.datetime.fromisoformat(date).replace(tzinfo=dt.timezone.utc)
        for key in sorted(set(re.findall(r'\[\[(n\d{4,6})\]\]', path.read_text()))):
            item = feed[key]
            metadata = cache.get(item['url'], {})
            canonical = metadata.get('canonical_url', item['url'])
            dates = path_dates(canonical)
            row = {'date': date, 'id': key, 'source': item['src'], 'title': item['title'],
                   'indexed_at': item['published_at'], 'canonical_url': canonical,
                   'path_dates': dates, 'publisher_body_vintage_verified': False}
            if item['url'].startswith('https://news.google.com/') and not metadata.get('canonical_url'):
                missing.append(row)
            if any(day >= date for day in dates):
                exception = approved.get((date, key))
                valid = exception and exception['canonical_url'] == canonical
                if valid:
                    known = dt.datetime.fromisoformat(exception['known_before_utc'].replace('Z', '+00:00'))
                    valid = known < cutoff
                if valid:
                    row['timing_exception'] = exception
                    used_exceptions.append({'date': date, 'id': key})
                else:
                    conflicts.append(row)
            rows.append(row)
    result = {'scope': 'All cited canonical URL metadata and parsed path dates, with documented UTC exceptions.',
              'date_screen_passed': not conflicts and not missing and len(hashes) == 21,
              'reports': len(hashes), 'cited_occurrences': len(rows),
              'unique_canonical_urls': len({x['canonical_url'] for x in rows}),
              'missing_canonical_urls': missing, 'unresolved_path_date_conflicts': conflicts,
              'timing_exceptions_used': used_exceptions, 'spec_sha256': hashes, 'records': rows,
              'limitation': 'Metadata does not establish original intraday publication time or complete article-body vintage. Release exceptions establish availability of official data, not every subsequent article detail.'}
    (ROOT/'audit/cited_source_dates.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({k: result[k] for k in ['reports', 'cited_occurrences', 'unique_canonical_urls',
                                            'timing_exceptions_used', 'date_screen_passed']}))
    for row in conflicts + missing:
        print(json.dumps(row, ensure_ascii=False))
    raise SystemExit(0 if result['date_screen_passed'] else 1)

if __name__ == '__main__':
    main()
