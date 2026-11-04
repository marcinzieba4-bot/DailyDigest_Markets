"""cited_titles.py <date> — list every headline that the edition's spec cites, with where it is first used.

Reads ../specs/<date>.json and the same edition's frozen feed (../feeds/<date>.json.gz or .json). Prints one line per
distinct citation: id | published (UTC) | source | headline | first use (section path). Ids missing from the feed are
flagged. Use it to check that each cited headline supports the sentence it is attached to, without reading the whole
feed. Nothing here reads other dates.
"""
import gzip, json, os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CITE = re.compile(r"\[\[(n\d{4,6})\]\]")


def load_feed(d):
    p = os.path.join(C, 'feeds', f'{d}.json')
    if os.path.exists(p):
        return json.load(open(p, encoding='utf-8'))
    return json.load(gzip.open(p + '.gz', 'rt', encoding='utf-8'))


def walk(node, path, out):
    if isinstance(node, str):
        for m in CITE.finditer(node):
            out.setdefault(m.group(1), path)
    elif isinstance(node, list):
        for i, x in enumerate(node):
            walk(x, f'{path}[{i}]', out)
    elif isinstance(node, dict):
        for k, v in node.items():
            walk(v, f'{path}.{k}' if path else k, out)


def main():
    d = sys.argv[1]
    spec = json.load(open(os.path.join(C, 'specs', f'{d}.json'), encoding='utf-8'))
    feed = {x['id']: x for x in load_feed(d)['items']}
    first = {}
    walk(spec, '', first)
    print(f'{d}: {len(first)} distinct cited headlines')
    for cid, path in sorted(first.items(), key=lambda kv: int(kv[0][1:])):
        item = feed.get(cid)
        if item is None:
            print(f'{cid} | MISSING FROM FEED | first use {path}')
            continue
        print(f"{cid} | {item['published_at'][:16].replace('T', ' ')} | {item.get('src', '')} | {item['title'][:160]} | {path}")


if __name__ == '__main__':
    main()
