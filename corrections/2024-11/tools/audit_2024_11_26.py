import sys,json,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent));from audit_late_nonretail import R,canonical,retail,finish
D='2024-11-26';p=R/'specs'/(D+'.json');s=json.loads(p.read_text());before={'retail':retail(s),'nonretail':canonical(s)}
s['catalysts'][2]['parts'][0][1]=s['catalysts'][2]['parts'][0][1].replace('Reuters reported accumulated emissions credits as other automakers lagged.','Reuters reports Tesla accumulating greenhouse-emissions credits in2023 as other automakers lagged.')
for key in ['geo','sectors','underowned','anticipatory','catalysts']:
 for x in s[key]:
  for pair in x['parts']:
   pair[1]=re.sub(r' {2,}',' ',pair[1]).replace('ispositive','is positive').replace('isbear','is bear').replace('at+','at +').replace('changed-','changed -').replace('10Y-15','10Y -15').replace('remain+','remain +').replace('and+','and +').replace('The$','The $').replace('the$','the $').replace('a$','a $').replace('potential$','potential $').replace('in2023','in 2023').replace('ModelYprice','Model Y price').replace('actual eligible company outlooks','actual company outlooks').replace('Reuters’ eligible company report','Reuters’ company report').replace('Reuters’ eligible report','Reuters’ report')
   if key=='sectors'and x['key']=='XLE':pair[1]=pair[1].replace('68.94 USD,','68.94 USD per barrel,')
   if key=='sectors'and x['key']=='XLB':pair[1]=pair[1].replace('4.09 USD,','4.09 USD per pound,')
for key in ['earnings_pattern','crypto','flows']:
 for pair in s[key]['parts']:pair[1]=re.sub(r' {2,}',' ',pair[1]).replace('toward$','toward $')
findings=[{'severity':'minor','location':'catalysts[2] Catalyst & Thesis','issue':'Tesla credit accumulation was stated without the historical year supplied by its headline.','action':'Specified2023; retained distinction from current vehicle demand and proposed policy.'},{'severity':'minor','location':'XLC/Poland/underowned prose','issue':'Eligible wording exposed input-screening status in market prose.','action':'Removed the administrative adjective without changing factual claims.'},{'severity':'minor','location':'Numerical and commodity prose','issue':'Joined signs/words, ModelY token and missing physical commodity units.','action':'Normalized spacing and added per-barrel/per-pound units to existing futures prices.'}]
finish(D,s,before,findings,'Read all eight nonretail keys against paragraph-matched own-date headlines. Reviewed Monday completed price response versus nomination, Monday China MLF and Kingfisher outcome timing, Best Buy preview, Biohaven failure versus planned pivot, Tesla historical credits and current pricing, issuer identity, source reactions, spot-FX exclusion. No fatal/major factual issue remained in settled input.')
