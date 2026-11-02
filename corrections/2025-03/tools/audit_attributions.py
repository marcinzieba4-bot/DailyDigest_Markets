"""Flag named-outlet attributions absent from that paragraph's cited metadata.

This is a reviewer diagnostic, not semantic verification of every factual claim.
Syndication can create false positives; no report is changed automatically.
"""
from pathlib import Path
import datetime as dt
import gzip
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
CITE = re.compile(r'\[\[(n\d{4,6})\]\]')
PROVIDERS = {
    'Reuters': (r'\bReuters\b', ['reuters']),
    'Bloomberg': (r'\bBloomberg\b', ['bloomberg']),
    'CNBC': (r'\bCNBC\b', ['cnbc']),
    'CNN': (r'\bCNN\b', ['cnn']),
    'Guardian': (r'\bGuardian\b', ['guardian']),
    'ABC': (r'\bABC\b', ['abcnews', 'australianbroadcasting', 'abcnetau']),
    'Stocktwits': (r'\bStocktwits\b', ['stocktwits']),
    'Financial Times': (r'\b(?:Financial Times|FT)\b', ['financialtimes', 'ft']),
    'Wall Street Journal': (r'\b(?:Wall Street Journal|WSJ)\b', ['wallstreetjournal', 'wsj']),
    'AFR': (r'\b(?:AFR|Australian Financial Review)\b', ['afr', 'australianfinancialreview']),
    'SCMP': (r'\b(?:SCMP|South China Morning Post)\b', ['scmp', 'southchinamorningpost']),
    'CoinDesk': (r'\bCoinDesk\b', ['coindesk']),
    'The Block': (r'\bThe Block\b', ['theblock']),
    'Business Insider': (r'\bBusiness Insider\b', ['businessinsider']),
}


def strings(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from strings(child, path+(key,))
    elif isinstance(value, list):
        for key, child in enumerate(value):
            yield from strings(child, path+(key,))
    elif isinstance(value, str):
        yield path, value


def norm(value):
    return re.sub(r'[^a-z0-9]', '', value.lower())


def main():
    dates = sys.argv[1:] or sorted(p.stem for p in (ROOT/'specs').glob('*.json'))
    flags = []
    hashes = {}
    feed_hashes = {}
    paragraphs = 0
    for date in dates:
        sp = ROOT/'specs'/f'{date}.json'
        raw = sp.read_bytes()
        hashes[date] = hashlib.sha256(raw).hexdigest()
        feed_raw = (ROOT/'feeds'/f'{date}.json.gz').read_bytes()
        feed_hashes[date] = hashlib.sha256(feed_raw).hexdigest()
        feed = {r['id']: r for r in json.loads(gzip.decompress(feed_raw))['items']}
        for path, prose in strings(json.loads(raw)):
            ids = sorted(set(CITE.findall(prose)))
            if not ids:
                continue
            paragraphs += 1
            metadata = {key: feed[key] for key in ids}
            labels = [norm(r['src']) for r in metadata.values()]
            hay = ' '.join(norm(r['src']+' '+r['title']) for r in metadata.values())
            raw_metadata = ' '.join(r['src']+' '+r['title'] for r in metadata.values())
            for provider, (pattern, aliases) in PROVIDERS.items():
                matched = any((alias in labels or alias+'com' in labels
                               or re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)', raw_metadata, re.I)) if len(alias) <= 3
                              else alias in hay for alias in aliases)
                if re.search(pattern, prose, re.I) and not matched:
                    flags.append({'date': date, 'path': list(path), 'provider': provider,
                                  'prose': prose, 'cited': [{k: r[k] for k in ['id', 'src', 'title']} for r in metadata.values()]})
    result = {'scope': 'Named-outlet consistency against cited headline metadata only; not a complete semantic or body-vintage audit.',
              'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'reports': len(dates), 'cited_paragraphs': paragraphs, 'flags': flags,
              'spec_sha256': hashes, 'automatic_report_changes': False,
              'feed_sha256': feed_hashes,
              'auditor_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    path = ROOT/'checks/source_attribution_diagnostic.json'
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'reports': len(dates), 'cited_paragraphs': paragraphs, 'flags': len(flags)}))
    for row in flags:
        print(row['date'], row['path'], row['provider'], [r['id'] for r in row['cited']])


if __name__ == '__main__':
    main()
