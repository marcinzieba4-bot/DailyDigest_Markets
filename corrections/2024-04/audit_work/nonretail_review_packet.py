"""Display only one date's exact current nonretail prose and cited evidence.

This is a reviewer read helper. It changes no draft, source or acceptance.
"""
from pathlib import Path
import gzip,json,sys,hashlib,re
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
import verify

def main():
 d=sys.argv[1];verify.validate_date(d);group=sys.argv[2]if len(sys.argv)>2 else'all'
 spec=json.loads((ROOT/'nonretail_drafts'/f'{d}.json').read_bytes());feed=verify.load_feed(d);e={r['id']:r for r in feed['items']}
 card=json.loads((ROOT/'cards'/f'{d}.json').read_bytes());ex=json.loads((ROOT/'exclusions'/f'{d}.json').read_bytes())
 print('DATE',d,'GROUP',group)
 print('DRAFT_SHA256',hashlib.sha256((ROOT/'nonretail_drafts'/f'{d}.json').read_bytes()).hexdigest())
 print('VERIFIER',verify.verify(d,nonretail=True))
 print('EXCLUSIONS',json.dumps(ex,ensure_ascii=False))
 blocks=[]
 for key in ['geo','sectors','earnings_pattern','underowned','crypto','flows','anticipatory','catalysts']:
  if group!='all'and(group=='geo'and key!='geo'or group=='sectors'and key!='sectors'or group=='other'and key in {'geo','sectors'}):continue
  arr=spec[key]if isinstance(spec[key],list)else[spec[key]]
  for i,b in enumerate(arr):blocks.append((key+':'+str(b.get('key',i)),b))
 cited=[]
 for where,b in blocks:
  print('\nBLOCK',where,b.get('title',''),b.get('stance',''),b.get('label',''))
  for label,text in b['parts']:
   print(label+': '+text)
   for n in re.findall(r'\[\[(n\d{4,6})\]\]',text):
    if n not in cited:cited.append(n)
 print('\nEXACT CITED HEADLINES')
 for n in cited:
  row=e[n];print(n,row['src'],row['published_at'],row['cat'],row['title'])
 if group in {'all','geo'}:
  print('TREASURY',json.dumps(card['treasury'],ensure_ascii=False))
  for ticker in ['^GSPC','^VIX','DX-Y.NYB','EPOL','^WIG20','^N225','^AXJO','^HSI','000300.SS']:
   if ticker in card['markets']:print('MARKET',ticker,json.dumps(card['markets'][ticker],ensure_ascii=False))
 if group in {'all','sectors','other'}:
  print('MARKET TABLE: ticker | session | close | 1s% | 5s% | 20s% | ref1 | ref5 | ref20')
  body=' '.join(t for _,b in blocks for _,t in b['parts'])
  for ticker,m in card['markets'].items():
   if not re.search(r'(?<![A-Za-z0-9])'+re.escape(ticker)+r'(?![A-Za-z0-9])',body) and not any(word.lower()in body.lower()and ticker==code for word,code in [('Bitcoin','BTC-USD'),('Ether','ETH-USD'),('copper','HG=F'),('gold','GC=F'),('WTI','CL=F')]):continue
   print(ticker, '|', m['session'], '|',m['close'],'|',m.get('chg_1s_pct'),'|',m.get('chg_5s_pct'),'|',m.get('chg_20s_pct'),'|',m.get('ref_1s_session'),'|',m.get('ref_5s_session'),'|',m.get('ref_20s_session'))

if __name__=='__main__':main()
