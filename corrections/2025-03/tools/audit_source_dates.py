"""Screen cited source metadata and UTC boundaries without changing writer inputs.

Canonical paths can expose a misdated RSS item, but do not establish the original
article body's vintage or intraday publication time. Any same-day exception must
have independently documented earlier UTC availability and an exact source URL.
"""
from pathlib import Path
import argparse
import concurrent.futures as cf
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
import re
import time
import urllib.parse

ROOT = Path(__file__).resolve().parent.parent
DATES = [dt.date(2025, 4, n).isoformat() for n in range(1, 31)
         if dt.date(2025, 4, n).weekday() < 5]
CITE = re.compile(r'\[\[(n\d{4,6})\]\]')
MONTHS = {v.lower(): i for i, v in enumerate(
    ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], 1)}


def atomic(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    tmp.replace(path)


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


def valid_publisher_url(value):
    parsed = urllib.parse.urlsplit(value or '')
    host = (parsed.hostname or '').lower()
    return (parsed.scheme in ('http', 'https') and bool(host)
            and host not in {'google.com', 'www.google.com', 'news.google.com',
                             'accounts.google.com', 'consent.google.com'}
            and '/sorry/' not in parsed.path.lower())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('dates', nargs='*')
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--offline', action='store_true')
    args = ap.parse_args()
    dates = args.dates or [d for d in DATES if (ROOT/'specs'/f'{d}.json').exists()]
    if not dates or any(d not in DATES for d in dates):
        raise ValueError('Expected April 2025 weekday specs')
    cache_path = ROOT/'audit/canonical_all_cited_urls.json'
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    priority_path = ROOT/'audit/canonical_reuters_urls.json'
    if priority_path.exists():
        for url, value in json.loads(priority_path.read_text()).items():
            if valid_publisher_url(value.get('canonical_url')) and not valid_publisher_url(cache.get(url, {}).get('canonical_url')):
                cache[url] = value
    refs = []
    hashes = {}
    feed_hashes = {}
    for date in dates:
        sp = ROOT/'specs'/f'{date}.json'
        fp = ROOT/'feeds'/f'{date}.json.gz'
        hashes[date] = hashlib.sha256(sp.read_bytes()).hexdigest()
        feed_hashes[date] = hashlib.sha256(fp.read_bytes()).hexdigest()
        feed = {x['id']: x for x in json.loads(gzip.decompress(fp.read_bytes()))['items']}
        cutoff = dt.datetime.fromisoformat(date).replace(tzinfo=dt.timezone.utc)
        for key in sorted(set(CITE.findall(sp.read_text()))):
            item = feed[key]
            pub = dt.datetime.fromisoformat(item['published_at'].replace('Z', '+00:00'))
            window = {'news': 7, 'result': 14, 'monthly': 35}[item['cat']]
            if pub.tzinfo is None or not cutoff-dt.timedelta(days=window) <= pub < cutoff:
                raise ValueError(date+' invalid indexed boundary '+key)
            refs.append({'date': date, 'id': key, 'source': item['src'], 'title': item['title'],
                         'indexed_at': item['published_at'], 'url': item['url']})
    need = sorted({r['url'] for r in refs if r['url'].startswith('https://news.google.com/')
                   and not valid_publisher_url(cache.get(r['url'], {}).get('canonical_url'))})
    print(len(refs), 'cited records;', len(need), 'metadata lookups', flush=True)
    if need and not args.offline:
        path = ROOT/'posthoc/resolve_news_url.py'
        spec = importlib.util.spec_from_file_location('source_url_resolver', path)
        resolver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(resolver)

        def fetch(url):
            for attempt in range(3):
                try:
                    return url, {'canonical_url': resolver.resolve(url),
                                 'observed_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                                 'publisher_body_fetched': False}
                except Exception as exc:
                    error = {'error_type': type(exc).__name__, 'error': str(exc)[:200],
                             'publisher_body_fetched': False}
                    if attempt < 2:
                        time.sleep(attempt+1)
            return url, error
        with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
            for i, (url, result) in enumerate(pool.map(fetch, need), 1):
                cache[url] = result
                if i % 25 == 0:
                    atomic(cache_path, cache)
                    print('Metadata', i, '/', len(need), flush=True)
    atomic(cache_path, cache)
    ep = ROOT/'audit/canonical_source_exceptions.json'
    exceptions = json.loads(ep.read_text()).get('exceptions', []) if ep.exists() else []
    approved = {(x['date'], x['id']): x for x in exceptions}
    conflicts, missing, used = [], [], []
    for row in refs:
        metadata = cache.get(row['url'], {})
        canonical = metadata.get('canonical_url', row['url'])
        row.update(canonical_url=canonical, path_dates=path_dates(canonical),
                   publisher_body_vintage_verified=False)
        if row['url'].startswith('https://news.google.com/') and not valid_publisher_url(metadata.get('canonical_url')):
            missing.append(row)
        if any(day >= row['date'] for day in row['path_dates']):
            ex = approved.get((row['date'], row['id']))
            valid = ex and ex.get('canonical_url') == canonical and ex.get('evidence_url') and ex.get('reason')
            if valid:
                proof = (ROOT/ex.get('timing_proof_file', '')).resolve()
                valid = (proof.is_relative_to(ROOT) and proof.is_file()
                         and ex.get('timing_proof_sha256') == hashlib.sha256(proof.read_bytes()).hexdigest()
                         and bool(ex.get('reviewer')))
            if valid:
                known = dt.datetime.fromisoformat(ex['known_before_utc'].replace('Z', '+00:00'))
                cutoff = dt.datetime.fromisoformat(row['date']).replace(tzinfo=dt.timezone.utc)
                valid = known.tzinfo is not None and known < cutoff
            if valid:
                row['timing_exception'] = ex
                used.append({'date': row['date'], 'id': row['id']})
            else:
                conflicts.append(row)
    complete = sorted(dates) == DATES
    result = {'scope': 'All cited canonical URL metadata and parsed path dates, with explicit UTC exceptions.',
              'date_screen_passed': complete and not conflicts and not missing,
              'checked_dates_passed': not conflicts and not missing, 'complete_month': complete,
              'reports': len(dates), 'cited_occurrences': len(refs),
              'unique_canonical_urls': len({r['canonical_url'] for r in refs}),
              'missing_canonical_urls': missing, 'unresolved_path_date_conflicts': conflicts,
              'timing_exceptions_used': used, 'spec_sha256': hashes, 'feed_sha256': feed_hashes,
              'timing_exceptions_sha256': hashlib.sha256(ep.read_bytes()).hexdigest(),
              'auditor_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'records': refs,
              'limitation': 'Canonical metadata and path dates do not prove original article-body vintage or intraday publication. Independent review covers selected factual and release-timing claims.'}
    atomic(ROOT/'audit/cited_source_dates.json', result)
    print(json.dumps({k: result[k] for k in ['reports', 'cited_occurrences', 'unique_canonical_urls',
                                           'complete_month', 'checked_dates_passed', 'date_screen_passed']}))
    for row in conflicts+missing:
        print(json.dumps(row, ensure_ascii=False))
    raise SystemExit(0 if result['checked_dates_passed'] else 1)


if __name__ == '__main__':
    main()
