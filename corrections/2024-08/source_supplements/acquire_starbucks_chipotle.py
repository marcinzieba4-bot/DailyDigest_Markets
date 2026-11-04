"""Separate own-cutoff retail research; never mutate frozen author inputs."""
from pathlib import Path
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import fetch_news as news

news.ROOT = ROOT / 'source_supplements'
news.CACHE = news.ROOT / 'cache'
news.RAW = news.ROOT / 'rss_raw'
news.VERSION = 'aug-2024-own-cutoff-retail-supplement-v1'
DATES = ['2024-08-14', '2024-08-15', '2024-08-16', '2024-08-19', '2024-08-20']
QUERIES = ['Starbucks', 'Chipotle', 'Starbucks shares', 'Chipotle shares',
           'Starbucks retail investors', 'Chipotle retail investors']

def main():
    jobs = [('retail_attention', query, 'news', ('en-US', 'US', 'US:en'),
             dt.date.fromisoformat(date) - dt.timedelta(days=7),
             dt.date.fromisoformat(date)) for date in DATES for query in QUERIES]
    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        batches = list(pool.map(news.fetch, jobs))
    for date in DATES:
        own = [batch for batch in batches if batch['upper_date_exclusive'] == date]
        assert all(batch['status'] == 'fetched' for batch in own)
        assert not any(batch.get('possibly_capped') for batch in own), 'Refine capped requests before use'
        merged = {}
        for batch in own:
            for item in batch['items']:
                key = (item['title'], item['src'], item['published_at'])
                if key not in merged:
                    merged[key] = {**item, 'query_signatures': [], 'queries': []}
                merged[key]['query_signatures'].append(batch['signature'])
                merged[key]['queries'].append(batch['query'])
        payload = {
            'report_date': date, 'cutoff_utc': date + 'T00:00:00Z',
            'category': 'news', 'window_days': 7,
            'status': 'research_only_not_admitted',
            'rule': 'Every request ends at this own report cutoff; no later query window supports an earlier date. Original frozen base feeds, IDs and acceptance receipts are untouched. RSS headlines still require editorial/release review.',
            'batches': own, 'items': list(merged.values()),
        }
        target = news.ROOT / (date + '_starbucks_chipotle.json')
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        print(date, len(own), sum(len(batch['items']) for batch in own))
    return batches

if __name__ == '__main__':
    main()
