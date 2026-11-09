"""Independent historical release-calendar retrieval; no report drafting."""
from pathlib import Path
import concurrent.futures,hashlib,json,re,datetime as dt
import urllib.request
from types import SimpleNamespace
from html.parser import HTMLParser
class Parser(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.stack=[];self.nodes=[];self.metadata={};self.links=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='meta' and a.get('content'):self.metadata[a.get('property')or a.get('name')]=a['content']
  if tag=='a' and a.get('href'):self.links.append(a['href'])
  if tag not in {'meta','link','img','br','hr','input','source','wbr'}:self.stack.append({'tag':tag,'text':[]})
 def handle_data(self,data):
  for x in self.stack:x['text'].append(data)
 def handle_endtag(self,tag):
  for i in range(len(self.stack)-1,-1,-1):
   if self.stack[i]['tag']==tag:
    for x in self.stack[i:]:self.nodes.append((x['tag'],' '.join(' '.join(x['text']).split())))
    del self.stack[i:];break
R=Path(__file__).resolve().parent
URLS={
'gus_2024_07_18':'https://stat.gov.pl/kalendarium/18-07-2024.html',
'gus_2024_07_22':'https://stat.gov.pl/kalendarium/22-07-2024.html',
'gus_2024_07_23':'https://stat.gov.pl/kalendarium/23-07-2024.html',
'gus_2024_07_24':'https://stat.gov.pl/kalendarium/24-07-2024.html',
'gus_2024_07_31':'https://stat.gov.pl/kalendarium/31-07-2024.html',
'skhynix_2024q2_invitation':'https://news.skhynix.com/en/q2-2024-earnings-conference-call-invitation/',
'samsung_2024q2_results':'https://news.samsung.com/global/samsung-electronics-announces-results-for-second-quarter-of-2024',
'skhynix_2024q2_results':'https://news.skhynix.com/en/sk-hynix-announces-2q24-financial-results/'
}
def fetch(pair):
 name,url=pair
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=40) as response:r=SimpleNamespace(content=response.read(),url=response.url,status_code=response.status)
 except Exception as exc:
  return {'name':name,'url':url,'error':str(exc)}
 p=R/(name+'.html');p.write_bytes(r.content);s=Parser();s.feed(r.content.decode('utf-8',errors='replace'))
 metas=s.metadata
 headers=[text for tag,text in s.nodes if tag in {'h1','h2','h3','time'}]
 matching=[text for tag,text in s.nodes if tag in {'p','div','span','li','td'} and text and re.search(r'before 9:00|9:00 a.m|08:30|8:30|2024/07|2024-07|godz|Wynagrodzen|zatrudnienie|Dynamika produkcji|sprzedaży detalicznej|bezroboc|Bezroboc|earnings on|conference call will',text,re.I) and len(text)<1000]
 row={'name':name,'url':url,'final_url':r.url,'status':r.status_code,'retrieved_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'sha256':hashlib.sha256(r.content).hexdigest(),'bytes':len(r.content),'headers':headers,'metadata':metas,'timing_candidate_excerpts':list(dict.fromkeys(matching)),'pdf_links':[x for x in s.links if '.pdf' in x]}
 (R/(name+'.json')).write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n')
 return {k:row[k] for k in ['name','status','headers','metadata','timing_candidate_excerpts']}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as e:
 for r in e.map(fetch,URLS.items()):print(json.dumps(r,ensure_ascii=False))
