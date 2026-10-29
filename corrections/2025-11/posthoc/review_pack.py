"""Print selected own-date critical claims with their cited headline evidence.
Independent reviewer aid only; this samples, rather than verifies, a complete report.
"""
from pathlib import Path
import gzip, json, re, sys
ROOT=Path(__file__).resolve().parent.parent
CITE=re.compile(r'\[\[(n\d{4,6})\]\]')
def main():
 date=sys.argv[1]; spec=json.loads((ROOT/'specs'/f'{date}.json').read_text())
 feed={x['id']:x for x in json.load(gzip.open(ROOT/'feeds'/f'{date}.json.gz','rt'))['items']}
 select={'EU':{'New / Most Important'},'US':{'Macro Stance','Rates & Curve','New / Most Important'},'CN':{'PMIs & Activity','Credit Impulse','New / Most Important'},'PL':{'Macro Stance','New / Most Important'},'JP':{'Activity & Currency'},'AU':{'Macro Stance'}}
 rows=[]
 for block in spec['geo']:
  for label,text in block['parts']:
   if label in select.get(block['key'],set()):rows.append((f"geo:{block['key']} / {label}",text))
 for block in spec['sectors']:
  if block['key'] in ('XLF','XLV','SXAP'):
   rows.append(('sector:'+block['key']+' / Reported',next(t for label,t in block['parts'] if label=='Reported')))
 for label,text in spec['earnings_pattern']['parts']:
  if label in ('Rewarded','Punished'):rows.append(('earnings / '+label,text))
 for label,text in spec['retail'][0]['parts']:
  if label in ('What Is Driving It','The Social Signal'):rows.append(('retail lead / '+label,text))
 for label,text in spec['flows']['parts']:
  if label=='Equity & Fund Flows':rows.append(('flows / '+label,text))
 for b in spec['catalysts'][:2]:rows.append(('catalyst / '+b['title'],b['parts'][0][1]))
 print('REPORT',date,'RETAIL',spec['retail'][0]['title'])
 for label,text in rows:
  print('\n'+label+'\n'+text)
  for key in dict.fromkeys(CITE.findall(text)):
   e=feed[key];print(' EVIDENCE',key,e['published_at'],e['title'])
if __name__=='__main__':main()
