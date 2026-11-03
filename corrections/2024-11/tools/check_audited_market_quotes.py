"""Independent quote binding for the reviewed late-month nonretail prose.
Checks each recognised close/return/session sentence against one actual instrument,
not a bag of all numbers in the card. It does not substitute for prose review.
"""
import json,re,hashlib
from pathlib import Path
R=Path(__file__).resolve().parent.parent
Q=re.compile(r'(?P<label>[^.!?\n]{1,120}?)\s+(?:closed|ended|finished)\s+at\s+(?P<close>[\d,]+(?:\.\d+)?)\s+(?P<currency>USD|PLN|JPY|AUD|EUR|index points)(?: per (?:barrel|pound))?,\s*(?:a\s*)?(?P<ret>[+\-]?\d+(?:\.\d+)?)%\s*(?:change\s*)?(?P<horizon>over\s+(?:20|five)\s+sessions|in\s+the\s+prior\s+session)\s*\(Yahoo Finance, prior (?:completed daily close|close) (?P<session>\d{4}-\d{2}-\d{2})\)')
def num(s):return float(str(s).replace(',',''))
def parts(s):
 for key in ['geo','sectors','underowned','anticipatory','catalysts']:
  for i,x in enumerate(s[key]):
   for label,t in x['parts']:yield f'{key}[{i}] {label}',t
 for key in ['earnings_pattern','crypto','flows']:
  for label,t in s[key]['parts']:yield f'{key} {label}',t
for d in ['2024-11-21','2024-11-22','2024-11-25','2024-11-26']:
 p=R/'specs'/(d+'.json');s=json.loads(p.read_text());c=json.loads((R/'cards'/(d+'.json')).read_text());rows=[];errors=[]
 for where,t in parts(s):
  for m in Q.finditer(t):
   v=m.groupdict();field='chg_20s_pct'if'20'in v['horizon']else'chg_5s_pct'if'five'in v['horizon']else'chg_1s_pct'
   candidates=[]
   for ticker,a in c['markets'].items():
    if ticker.endswith('=X')or a.get('close')is None or a.get(field)is None:continue
    if abs(num(a['close'])-num(v['close']))>0.005 or abs(float(a[field])-float(v['ret']))>0.005 or a['session']!=v['session']:continue
    if v['currency']!='index points'and a['currency']!=v['currency']:continue
    candidates.append((ticker,a))
   if not candidates:errors.append({'where':where,'quote':m.group(0),'error':'No same instrument close/return-horizon/session/currency match'});continue
   if len(candidates)>1:
    label=v['label'].casefold();selected=[x for x in candidates if x[0].casefold()in label or x[1]['name'].split('(')[0].strip().casefold()in label]
    if len(selected)==1:candidates=selected
   if len(candidates)!=1:errors.append({'where':where,'quote':m.group(0),'error':'Ambiguous instrument binding','candidates':[x[0]for x in candidates]});continue
   ticker,a=candidates[0];label=v['label'].strip()
   words=lambda x:set(re.findall(r'[a-z0-9]+',x.casefold()))
   overlap=words(label)&(words(a['name'])|words(ticker))
   if not overlap:errors.append({'where':where,'quote':m.group(0),'error':'Instrument name did not overlap unique value match','matched':ticker});continue
   rows.append({'where':where,'label':label,'ticker':ticker,'close':v['close'],'return_pct':v['ret'],'return_field':field,'session':v['session']})
 out={'date':d,'scope':'Recognised explicit nonretail close+return+horizon+session sentences; spot-FX excluded; Treasury separately reviewed against card','quotes_checked':len(rows),'errors':errors,'records':rows,'full_spec_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
 (R/'audit'/('numeric_quote_binding_'+d+'.json')).write_text(json.dumps(out,indent=2));print(d,'bound',len(rows),'errors',len(errors))
 for e in errors:print(e)
 if errors:raise SystemExit(1)
