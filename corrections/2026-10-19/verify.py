#!/usr/bin/env python3
"""verify.py <date>  — checks edited/<date>.html against the original and the truth card."""
import sys,re,json,html,collections
W='/tmp/claude-0/-home-user/01233cf7-f758-5bad-b280-d38226412ca9/scratchpad/work'
A='/tmp/claude-0/-home-user/01233cf7-f758-5bad-b280-d38226412ca9/scratchpad/archive'
sys.path.insert(0,W)
from totext import totext
d=sys.argv[1]
orig=open(f'{A}/reports__archive__{d}.html',encoding='utf-8').read()
new=open(f'{W}/edited/{d}.html',encoding='utf-8').read()
card=json.load(open(f'{W}/cards/{d}.json'))
to=totext(orig); tn=totext(new)
fails=[]; warns=[]
# 1. HTML structure unchanged (tag multiset)
tags=lambda s: collections.Counter(re.findall(r'<(/?\w+)',s))
if tags(orig)!=tags(new): fails.append(f"tag multiset differs: {tags(orig)-tags(new)} / {tags(new)-tags(orig)}")
if '&mdash;' in orig and '&mdash;' not in new: warns.append("&mdash; entity disappeared")
# 2. wrong 2Y values no longer attached to 2Y
for v in card['wrong_2y_values_in_report_actually_13w_tbill']:
    for m in re.finditer(r'(\b2Y|two-year|2-year|front[- ]end|short[- ]end)[^.]{0,60}?'+re.escape(v)+r'\s*%',tn,re.I):
        fails.append("wrong 2Y value still present: "+m.group(0))
    for m in re.finditer(re.escape(v)+r'\s*%[^.]{0,40}?(\b2Y|two-year|2-year)',tn,re.I):
        fails.append("wrong 2Y value still present: "+m.group(0))
# 3. percent-change on yields
OTHER=r'(oil|WTI|crude|VIX|S&P|SPX|gold|copper|BTC|bitcoin|Nasdaq|Russell|DXY|dollar|euro|yen|EUR|JPY|Dow|equit|stock|index|ratio|CPI|inflation|GDP|earnings|revenue|dividend|share|price|APY|rate hike|hike|cut|probability|odds|chance)'
def clean(ctx): return not re.search(OTHER,ctx,re.I)
for m in re.finditer(r'(10Y|2Y|30Y|[Yy]ields?|Treasur\w*)([^.]{0,45}?)[↑↓]\s?\d+(\.\d+)?\s?%',tn):
    if clean(m.group(2)): fails.append("percent arrow on a yield: "+m.group(0))
for m in re.finditer(r'(10Y|2Y|[Yy]ields?)([^.]{0,40}?)\b(up|down|rose|fell|surg\w+|climb\w+|jump\w+|dropp?\w*|slid\w*)\s+(by\s+)?\d+(\.\d+)?\s?%',tn):
    if clean(m.group(2)): fails.append("percent move on a yield: "+m.group(0))
for m in re.finditer(r'\(\s?[↑↓]\d+(\.\d+)?%\s?(vs 4W)?\)',tn):
    ctx=tn[max(0,m.start()-50):m.start()]
    mm=re.search(r'(10Y|2Y|[Yy]ield|Treasur)(?!.*(10Y|2Y|[Yy]ield|Treasur))(.*)$',ctx)
    if mm and clean(mm.group(3)): fails.append("percent arrow near yield: "+ctx[-40:]+m.group(0))
# 4. old wrong spreads next to curve words
old_spreads=set(re.findall(r'(?:spread|10Y-2Y|2s10s|10s-2s|curve)[^.]{0,40}?\+?(\d{2,3})\s?bps',to))|set(re.findall(r'\+?(\d{2,3})\s?bps[^.]{0,30}?(?:spread|10Y-2Y|2s10s|10s-2s|curve)',to))
ok_sp={str(card['prior_close']['spread_10y_2y_bps']+k) for k in (-1,0,1)}|{str(card['four_weeks_before_prior_close']['spread_10y_2y_bps']+k) for k in (-1,0,1)}|{str(card['prior_close']['spread_10y_3m_bps']+k) for k in (-1,0,1)}|{str(card['prior_close']['spread_30y_10y_bps']+k) for k in (-1,0,1)}
for v in old_spreads-ok_sp:
    for m in re.finditer(r'(?:spread|10Y-2Y|2s10s|10s-2s|curve|steep\w*)[^.]{0,40}?\+?'+v+r'\s?bps',tn,re.I): fails.append("old spread value still present: "+m.group(0))
    for m in re.finditer(r'\+?'+v+r'\s?bps[^.]{0,30}?(?:spread|10Y-2Y|2s10s|10s-2s|curve)',tn,re.I): fails.append("old spread value still present: "+m.group(0))
# 5. numbers introduced by the edit must come from the card (or exist in the original)
nums=lambda s:set(re.findall(r'\d+(?:[.,]\d+)?',s))
allowed=set()
def walk(o):
    if isinstance(o,dict): [walk(v) for v in o.values()]
    elif isinstance(o,list): [walk(v) for v in o]
    elif isinstance(o,(int,float)):
        allowed.add(str(o)); allowed.add(str(abs(o)))
        if isinstance(o,int): [allowed.add(str(abs(o)+k)) for k in (-1,1)]
        if isinstance(o,float): allowed.add(f"{o:.2f}"); allowed.add(f"{o:.1f}")
    elif isinstance(o,str): allowed.update(nums(o))
c2=dict(card); c2.pop('flagged_sentences',None); c2.pop('wrong_2y_values_in_report_actually_13w_tbill',None); c2.pop('tbill_13w_live',None); walk(c2)
allowed|={'1','2','4','5','10','20','90','100','2s','10s','2026'}
newnums=nums(tn)-nums(to)-allowed
if newnums: warns.append("numbers not in original or card (review): "+', '.join(sorted(newnums)))
# 6. no meta commentary
for w in ['corrected','originally','retroactiv','T-bill mix','mislabel','erratum','revised']:
    if w.lower() in tn.lower() and w.lower() not in to.lower(): fails.append("meta commentary word added: "+w)
# 7. unchanged?
if orig==new: fails.append("file unchanged")
print(f"== {d}: {'PASS' if not fails else 'FAIL'}")
for f in fails: print("  FAIL:",f)
for w in warns: print("  WARN:",w)
sys.exit(1 if fails else 0)
