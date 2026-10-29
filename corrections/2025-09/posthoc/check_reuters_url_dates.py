"""Cache canonical URL dates for cited Reuters stories and flag RSS date conflicts.

These are rejection candidates, not proof of original article body vintage. Only
Google News metadata is queried. Exact intraday timestamps remain unverified.
"""
from pathlib import Path
import concurrent.futures as cf
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
import re
import sys
import time
import urllib.parse
ROOT = Path(__file__).resolve().parent.parent
m_spec = importlib.util.spec_from_file_location('resolver', ROOT/'posthoc/resolve_news_url.py')
resolver = importlib.util.module_from_spec(m_spec); m_spec.loader.exec_module(resolver)
CITE = re.compile(r'\[\[(n\d{4,6})\]\]')

def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)

def main():
    dates = sys.argv[1:]
    if not dates:
        raise SystemExit('Pass completed report dates explicitly')
    # Keep cited-review mutations separate from the concurrently running feed screen.
    cache_path = ROOT/'audit/canonical_cited_urls.json'
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    seed_path = ROOT/'audit/canonical_reuters_urls.json'
    if seed_path.exists():
        seed = json.loads(seed_path.read_text())
        for url, result in seed.items():
            if url not in cache or (cache[url].get('error') and not result.get('error')):
                cache[url] = result
    refs = {}
    report_hashes = {}
    for date in dates:
        raw = (ROOT/'specs'/f'{date}.json').read_bytes()
        report_hashes[date] = hashlib.sha256(raw).hexdigest()
        cited = set(CITE.findall(raw.decode()))
        feed = json.load(gzip.open(ROOT/'feeds'/f'{date}.json.gz', 'rt'))
        for item in feed['items']:
            if item['id'] in cited and ('reuters' in item['src'].lower() or item['title'].lower().endswith(' - reuters')):
                refs.setdefault(item['url'], []).append({'report_date': date, 'id': item['id'], 'indexed_at': item['published_at'], 'title': item['title']})
    missing = [url for url in refs if url not in cache or cache[url].get('error')]
    print(f'{len(dates)} reports, {len(refs)} unique cited Reuters links, {len(missing)} metadata lookups needed', flush=True)
    def fetch(url):
        last_error = ''
        for attempt in range(3):
            try:
                canonical = resolver.resolve(url)
                parsed = urllib.parse.urlparse(canonical)
                match = re.search(r'(\d{4}-\d{2}-\d{2})/?$', parsed.path)
                return url, {'canonical_url': canonical, 'canonical_date': match.group(1) if match else None, 'observed_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'publisher_body_fetched': False}
            except Exception as error:
                last_error = str(error)
                if attempt < 2: time.sleep(attempt + 1)
        return url, {'error': last_error, 'publisher_body_fetched': False}
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        for n, (url, result) in enumerate(pool.map(fetch, missing), 1):
            cache[url] = result
            if n % 20 == 0:
                save(cache_path, cache)
                print(f'{n}/{len(missing)} metadata lookups complete', flush=True)
    save(cache_path, cache)
    candidates = []
    for url, citations in refs.items():
        result = cache[url]
        day = result.get('canonical_date')
        if not day: continue
        for citation in citations:
            if day >= citation['report_date']:
                candidates.append({**citation, **result, 'indexed_url': url})
    exception_path = ROOT/'checks/canonical_timing_exceptions.json'
    timing = json.loads(exception_path.read_text())['exceptions'] if exception_path.exists() else []
    accepted = []
    unresolved = []
    for item in candidates:
        match = next((x for x in timing if (x['report_date'], x['id'], x['canonical_url']) == (item['report_date'], item['id'], item['canonical_url'])), None)
        if match and dt.datetime.fromisoformat(match['scheduled_release_utc'].replace('Z','+00:00')) < dt.datetime.fromisoformat(match['report_cutoff_utc'].replace('Z','+00:00')):
            accepted.append(match)
        else:
            unresolved.append(item)
    receipt = {'purpose': 'Reject-candidate check using canonical Reuters URL dates; not original-body or intraday timestamp verification.', 'dates': dates, 'spec_sha256': report_hashes, 'unique_cited_links': len(refs), 'lookup_failures': sum(bool(cache[url].get('error')) for url in refs), 'date_candidates': candidates, 'documented_timing_exceptions': accepted, 'unresolved_candidates': unresolved, 'passed': not unresolved and not any(cache[url].get('error') for url in refs)}
    save(ROOT/'checks/canonical_reuters_date_review.json', receipt)
    for item in candidates:
        print(item['report_date'], item['id'], item['canonical_date'], item['title'], flush=True)
    print(f'{len(candidates)} raw date candidates; {len(accepted)} documented timing exceptions; {len(unresolved)} unresolved', flush=True)

if __name__ == '__main__': main()
