"""Resolve Google News canonical publisher URLs without fetching the publisher.

Reviewer utility: resolve_news_url.py REPORT_DATE ITEM_ID [ITEM_ID ...]
This queries only news.google.com metadata. It does not read publisher bodies or
establish an exact publication time. Canonical URL dates can nevertheless expose
one-day discrepancies hidden by nominal Google News RSS timestamps.
Protocol context follows the public googlenewsdecoder 0.2.2 implementation.
"""
from pathlib import Path
import gzip
import json
import re
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
HEADERS = {'User-Agent': 'Mozilla/5.0'}
CONTEXT = [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1,
            None, None, None, None, None, 0, 1], "X", "X", 1, [1, 1, 1],
           1, 1, None, 0, 0, None, 0]

class NewsOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        if urllib.parse.urlparse(newurl).hostname != 'news.google.com':
            raise ValueError('Refusing to fetch a publisher; metadata lookup only')
        return super().redirect_request(request, fp, code, message, headers, newurl)


def resolve(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.hostname != 'news.google.com':
        raise ValueError('Expected a Google News article URL')
    article_id = parsed.path.split('/')[-1]
    opener = urllib.request.build_opener(NewsOnly)
    page = 'https://news.google.com/rss/articles/' + article_id + '?oc=5&hl=en-US&gl=US&ceid=US:en'
    html = opener.open(urllib.request.Request(page, headers=HEADERS), timeout=25).read().decode()
    signature = re.search(r'data-n-a-sg="([^"]+)', html).group(1)
    timestamp = re.search(r'data-n-a-ts="([^"]+)', html).group(1)
    inner = ['garturlreq', CONTEXT, article_id, int(timestamp), signature]
    envelope = [[['Fbv4je', json.dumps(inner, separators=(',', ':')), None, '0']]]
    body = urllib.parse.urlencode({'f.req': json.dumps(envelope, separators=(',', ':'))}).encode()
    headers = {**HEADERS, 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'}
    request = urllib.request.Request('https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je', data=body, headers=headers)
    response = opener.open(request, timeout=25).read().decode()
    if response.startswith(")]}'"):
        response = response.split('\n\n', 1)[1]
    for row in json.loads(response):
        if isinstance(row, list) and len(row) >= 3 and row[0] == 'wrb.fr':
            result = json.loads(row[2])
            if result[0] == 'garturlres':
                return result[1]
    raise ValueError('Canonical URL missing from response')


def main():
    date, *ids = sys.argv[1:]
    feed = {x['id']: x for x in json.load(gzip.open(ROOT/'feeds'/f'{date}.json.gz', 'rt'))['items']}
    for item_id in ids:
        e = feed[item_id]
        print(json.dumps({'date': date, 'id': item_id, 'title': e['title'], 'indexed_at': e['published_at'], 'canonical_url': resolve(e['url']), 'publisher_body_fetched': False}))

if __name__ == '__main__':
    main()
