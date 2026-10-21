"""Shared paths and helpers for the China / growth-pulse retrospective (corrections/china)."""
import os, re, json, html, datetime as dt
C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # corrections/china
REPORTS = os.path.join(os.path.dirname(C), '2026-10-19', 'html')          # canonical corrected archive
BLOCK_RE = re.compile(r'<div style="margin-bottom:24px;[^"]*">\s*<h3[^>]*>🇨🇳[^\n]*\n(?:.*?\n)*?</div>')
WIN = {'china_pmi': 35, 'china_credit': 35, 'china_activity': 35, 'growth_pmi': 35, 'growth_credit': 35,
       'growth_housing': 35, 'china_trade': 35, 'china_property': 35}                     # buckets mixing monthly topics

def report(d):
    return open(os.path.join(REPORTS, f'{d}.html'), encoding='utf-8').read()

def china_block(s):
    m = BLOCK_RE.search(s)
    return m

def totext(s):
    t = html.unescape(re.sub(r'<[^>]+>', ' ', s))
    return re.sub(r'\s+', ' ', t)

def nums(t):
    t = re.sub(r'\d{1,3}(?:,\d{3})+', lambda m: m.group(0).replace(',', ''), t)
    return set(re.findall(r'\d+(?:\.\d+)?', t))

def feed_items(d):
    """Headlines eligible for report date d: dated strictly before d, within 35 days (monthly) / the harvest window."""
    f = json.load(open(os.path.join(C, 'feeds', f'{d}.json')))
    out = [x for items in f['feeds'].values() for x in items]
    e = os.path.join(C, 'feeds_earn', f'{d}.json')               # earnings headlines for the Sector Deep Dive
    if os.path.exists(e):
        out += [x for items in json.load(open(e))['feeds'].values() for x in items]
    return out

SECTOR_RE = re.compile(r'(<h2[^>]*>📊 Sector Deep Dive</h2>)(.*?)(?=<hr style="border:none;border-top:2px solid #eee;margin:28px 0">\s*<h2[^>]*>🔍 Underowned)', re.S)
