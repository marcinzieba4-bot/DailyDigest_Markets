import sys,json,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent));from audit_late_nonretail import R,canonical,retail,finish
D='2024-11-25';p=R/'specs'/(D+'.json');s=json.loads(p.read_text());before={'retail':retail(s),'nonretail':canonical(s)}
s['geo'][0]['parts'][0][1]=s['geo'][0]['parts'][0][1].replace('Its subsequent account','Its separate account')
s['geo'][1]['parts'][1][1]=s['geo'][1]['parts'][1][1].replace('The latest available euro-zone manufacturing baseline','The October euro-zone manufacturing baseline')
s['sectors'][1]['parts'][1][1]=s['sectors'][1]['parts'][1][1].replace('remain eligible examples','remain examples')
s['sectors'][3]['parts'][3][1]='A possible ceasefire can alter the supply-risk premium before its implementation is secure. Treat de-escalation as a conditional scenario and keep commodity funds, producers and service companies separate. Reduce a position whose expected premium is no longer supported by the actual commercial risk.'
for key in ['geo','sectors','underowned','anticipatory','catalysts']:
 for x in s[key]:
  for pair in x['parts']:
   pair[1]=re.sub(r' {2,}',' ',pair[1]).replace('ispositive','is positive').replace('isbear','is bear').replace('at+','at +').replace('rose+','rose +').replace('the$','the $').replace('above$','above $').replace('than$','than $')
   if key=='sectors'and x['key']=='XLE':pair[1]=pair[1].replace('71.24 USD,','71.24 USD per barrel,')
   if key=='sectors'and x['key']=='XLB':pair[1]=pair[1].replace('4.07 USD,','4.07 USD per pound,')
for key in ['earnings_pattern','crypto','flows']:
 for pair in s[key]['parts']:pair[1]=re.sub(r' {2,}',' ',pair[1]).replace('above$','above $').replace('than$','than $')
findings=[{'severity':'minor','location':'EU Activity & Inflation','issue':'October PMI baseline was called the latest available baseline, an unnecessary freshness implication.','action':'Identified the month directly without a latest claim.'},{'severity':'minor','location':'XLC and XLE prose','issue':'Eligible and uncompleted-next-session phrasing exposed authoring discipline rather than ordinary market analysis.','action':'Removed eligible wording and expressed ceasefire risk as a market scenario.'},{'severity':'minor','location':'Numerical prose','issue':'Joined tokens, repeated spaces and missing physical commodity units.','action':'Normalized spacing and specified per-barrel/per-pound units.'}]
finish(D,s,before,findings,'All eight nonretail keys read with own-date cited headline ledger. Checked nomination versus enacted policy/next-session outcome; prospective IPOs; approved Japan fiscal package scopes; company identities; source-supported reactions; weekend crypto versus Friday exchange sessions; spot-FX exclusion. No fatal/major factual issue remained in the settled input.')
