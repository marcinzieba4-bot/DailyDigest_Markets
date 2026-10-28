import json,re,sys,os
sys.path.insert(0,'tools')
import digest
D=sys.argv[1]
s=json.load(open('specs/'+D+'.json'))
f={i['id']:i for i in digest.load_feed(D)['items']}
print('DATE',D)
for section, label in [('sectors','Reported'),('catalysts','Catalyst & Thesis'),('retail','The Social Signal'),('flows',None)]:
 items=s[section] if isinstance(s[section],list) else [s[section]]
 for i,obj in enumerate(items):
  if section=='sectors' and i not in [2,3,12]: continue
  if section=='catalysts' and i not in [0,1]: continue
  for j,(part,t) in enumerate(obj['parts']):
   if label is not None and part!=label: continue
   if section=='flows' and part not in ['Credit Check','Equity & Fund Flows']: continue
   print(f'\n{section}[{i}].parts[{j}] {obj.get("key",obj.get("title",""))} / {part}: {t}')
   ids=list(dict.fromkeys(re.findall(r'\[\[(n\d+)\]\]',t)))
   for id in ids:
    x=f.get(id)
    print(digest.line(x) if x else id+' MISSING')
