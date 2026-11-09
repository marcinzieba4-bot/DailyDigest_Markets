"""cited_titles.py <date> — list every headline that the edition's spec cites, with where it is first used.

Reads ../specs/<date>.json and the same edition's frozen feed (../feeds/<date>.json.gz or .json). Prints one line per
distinct citation: id | published (UTC) | source | headline | first use (section path). Ids missing from the feed are
flagged. Use it to check that each cited headline supports the sentence it is attached to, without reading the whole
feed. Nothing here reads other dates.
"""
import argparse, json, os, re
from verify import validate_date, load_feed, load_exclusions

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CITE = re.compile(r"\[\[(n\d{4,6})\]\]")


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
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('date');mode=parser.add_mutually_exclusive_group();mode.add_argument('--nonretail',action='store_true');mode.add_argument('--retail',action='store_true')
    args=parser.parse_args();d=args.date;validate_date(d)
    folder='nonretail_drafts' if args.nonretail else 'retail_drafts' if args.retail else 'specs'
    spec=json.load(open(os.path.join(C,folder,f'{d}.json'),encoding='utf-8'))
    own_feed=load_feed(d);excluded=load_exclusions(d,own_feed)
    feed = {x['id']: x for x in own_feed['items']}
    first = {}
    walk(spec, '', first)
    print(f'{d}: {len(first)} distinct cited headlines')
    failed=False
    for cid, path in sorted(first.items(), key=lambda kv: int(kv[0][1:])):
        item = feed.get(cid)
        if item is None:
            print(f'{cid} | MISSING FROM FEED | first use {path}')
            failed=True; continue
        if cid in excluded: print(cid+' | EXCLUDED OWN-DATE SOURCE');failed=True
        print(f"{cid} | {item['published_at'][:16].replace('T', ' ')} | {item.get('src', '')} | {item['title']} | {path}")

    if failed: raise SystemExit(1)


if __name__ == '__main__':
    main()
