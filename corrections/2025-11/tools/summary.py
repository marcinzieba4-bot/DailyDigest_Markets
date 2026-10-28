"""summary.py [dates ...] — one table over the written specs: words per section against the August 2026 medians, narration
counts, distinct cited headlines, and the retail lead / intro of every report. Reads ../specs/*.json (all dates when none
are given). Review aid only; nothing is written."""
import json, os, re, sys, glob, statistics as st

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CITE = re.compile(r'\s*\[\[(n\d{4})\]\]')
AUG = {'geo': 3063, 'sectors': 2132, 'earnings_pattern': 389, 'underowned': 500, 'crypto': 313, 'flows': 697,
       'anticipatory': 636, 'catalysts': 720, 'retail': 1146}                 # medians of the 31 August 2026 pages (blocks summed)
META = re.compile(r"\b(the writer|writer(?:'|’)s|not a reported fact|the (?:market )?card|carries no)\b", re.I)
FEED = re.compile(r"\b(the feed|feed carries|in the feed)\b", re.I)


def words(x):
    return len(CITE.sub(' ', x).split())


def section_words(spec):
    out = {}
    for k in ('geo', 'sectors', 'underowned', 'anticipatory', 'catalysts', 'retail'):
        out[k] = sum(words(t) for b in spec[k] for _, t in b['parts'])
    for k in ('earnings_pattern', 'crypto', 'flows'):
        out[k] = sum(words(t) for _, t in spec[k]['parts'])
    return out


def main():
    dates = sys.argv[1:] or [os.path.basename(f)[:-5] for f in sorted(glob.glob(os.path.join(C, 'specs', '*.json')))]
    rows = []
    for d in dates:
        s = json.load(open(os.path.join(C, 'specs', f'{d}.json')))
        sw = section_words(s); total = sum(sw.values()) + words(s['retail_intro'])
        txt = json.dumps(s, ensure_ascii=False)
        ids = set(CITE.findall(txt)); meta = len(META.findall(txt)); feed = len(FEED.findall(txt))
        geo = {g['key']: sum(words(t) for _, t in g['parts']) for g in s['geo']}
        rows.append((d, total, sw, geo, len(ids), meta, feed, s['retail'][0]['title'], s['retail_intro']))
    print('date        total  geo  sect  EP  under crypto flows antic  catal retail |  PL    CN   US   | cites meta feed')
    for d, total, sw, geo, n, meta, feed, lead, _ in rows:
        print(f"{d} {total:6d} {sw['geo']:5d} {sw['sectors']:5d} {sw['earnings_pattern']:4d} {sw['underowned']:5d} {sw['crypto']:5d} "
              f"{sw['flows']:5d} {sw['anticipatory']:5d} {sw['catalysts']:6d} {sw['retail']:6d} | {geo['PL']:4d} {geo['CN']:4d} {geo['US']:4d} | "
              f"{n:5d} {meta:4d} {feed:4d}   {lead[:60]}")
    if rows:
        med = lambda i: int(st.median(r[i] for r in rows))
        print(f"median total {med(1)} (August 10,132); retail median {int(st.median(r[2]['retail'] for r in rows))} (August 1,232 incl. intro)")
    print()
    for d, *_, lead, intro in rows:
        print(f'{d}  LEAD: {lead}\n            INTRO: {intro}')


if __name__ == '__main__':
    main()
