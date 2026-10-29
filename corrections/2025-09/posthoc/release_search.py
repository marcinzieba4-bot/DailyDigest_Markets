"""Reviewer-only official-index and historical release search; never feeds writer evidence."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json,urllib.request,urllib.parse,xml.etree.ElementTree as ET,datetime
ROOT=Path(__file__).resolve().parent
queries=[
 ('us_bls','site:bls.gov ("September" "2025") ("Employment Situation" OR "Consumer Price Index" OR "Producer Price Index" OR "benchmark")'),
 ('us_benchmark','"September 9, 2025" "benchmark" "911,000"'),
 ('us_bea','site:bea.gov "September" "2025" ("Personal Income" OR "Gross Domestic Product")'),
 ('fed','site:federalreserve.gov "September 17, 2025" ("statement" OR "projections")'),
 ('ecb','site:ecb.europa.eu "11 September 2025" "Monetary policy"'),
 ('boj','site:boj.or.jp "September 19, 2025"'),
 ('rba','site:rba.gov.au "30 September 2025"'),
 ('nbp','"Poland" "September 3, 2025" "rates"'),
 ('plstats','site:stat.gov.pl "2025" "August" ("September" OR "09.2025")'),
 ('pldata','Poland August 2025 ("industrial output" OR "retail sales" OR "wages" OR "unemployment")'),
 ('chtrade','China August trade exports September 8 2025'),
 ('chprices','China August 2025 CPI PPI September 10'),
 ('chactivity','China August 2025 industrial output retail sales September 15'),
 ('chpmi','China September 2025 PMI September 30'),
 ('jpdata','Japan September 2025 ("GDP" OR "inflation" OR "industrial output" OR "unemployment")'),
 ('jpofficial','site:stat.go.jp "2025" "September" ("August" OR "July")'),
 ('abs','site:abs.gov.au "September" "2025" ("GDP" OR "Labour Force" OR "Monthly Consumer Price")'),
 ('austdata','Australia September 2025 ("GDP" OR "employment" OR "inflation")'),
 ('oracle','Oracle September 2025 first quarter results'),
 ('broadcom','Broadcom September 2025 third quarter results'),
 ('adobe','Adobe September 2025 third quarter results'),
 ('micron','Micron September 2025 fourth quarter results'),
 ('ai_deals','September 2025 OpenAI Nvidia Oracle investment agreement'),
 ('asx_premarket','September 2025 Australian stocks BHP Rio earnings announcement'),
 ('labor_day','September 1 2025 Labor Day US stock market closed'),
]
def fetch(t):
 key,q=t;q+=' after:2025-08-27 before:2025-10-02'
 url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':q,'hl':'en-US','gl':'US','ceid':'US:en'})
 out={'key':key,'query':q,'request_url':url,'items':[],'verification':'Google News RSS/index metadata only; original source body not fetched'}
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=35) as r:raw=r.read()
  root=ET.fromstring(raw)
  for x in root.findall('.//item'):
   s=x.find('source');out['items'].append({'title':x.findtext('title'),'indexed_timestamp':x.findtext('pubDate'),'indexed_url':x.findtext('link'),'source':s.text if s is not None else None,'source_home':s.get('url') if s is not None else None})
 except Exception as e:out['error']=str(e)[:160]
 return out
if __name__=='__main__':
 with ThreadPoolExecutor(max_workers=8) as p:rows=list(p.map(fetch,queries))
 (ROOT/'release_search_evidence.json').write_text(json.dumps({'purpose':'Reviewer only; may include post-cutoff facts. Do not feed to writers.','fetched_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'queries':rows},indent=2,ensure_ascii=False))
 for r in rows:
  print(r['key'],len(r['items']),r.get('error',''))
  for x in r['items'][:4]:print(' ',x['indexed_timestamp'],x['title'])
