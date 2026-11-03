import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent));from audit_late_nonretail import R,canonical,retail,finish
D='2024-11-22';p=R/'specs'/(D+'.json');s=json.loads(p.read_text());before={'retail':retail(s),'nonretail':canonical(s)}
s['catalysts'][5]['parts'][0][1]='Reuters reports protesters holding out at Tesla’s German plant as police clear a camp. [[n4345]] A separate Reuters report describes Tesla gaining on prospective federal self-driving rules. [[n4198]] The operating protest and the policy possibility are distinct risks and opportunities; neither establishes a completed rule change or a delivered commercial gain.'
s['geo'][0]['parts'][0][1]=s['geo'][0]['parts'][0][1].replace('Capital is available; the valuation hurdle differs sharply between companies.','Banking-system reserves look ample; the valuation hurdle still differs sharply between companies.')
for key in ['geo','sectors','underowned','anticipatory','catalysts']:
 for x in s[key]:
  for pair in x['parts']:
   pair[1]=pair[1].replace('ispositive','is positive').replace('withbear','with bear').replace('are+','are +').replace('and+','and +').replace('−2Y+','−2Y +').replace('a$','a $').replace('at the$','at the $').replace('potential$','potential $')
   if key=='sectors'and x['key']=='XLE':pair[1]=pair[1].replace('70.10 USD,','70.10 USD per barrel,')
   if key=='sectors'and x['key']=='XLB':pair[1]=pair[1].replace('4.11 USD,','4.11 USD per pound,')
findings=[{'severity':'major','location':'catalysts[5] Catalyst & Thesis','issue':'German plant protest headline alone did not support the separate self-driving policy factual context.','action':'Added exact own-date Reuters self-driving-rule source n4198 and separated the two events.'},{'severity':'minor','location':'US macro and commodity/curve prose','issue':'Abundant banking reserves were phrased as general availability of capital; minor joined tokens and commodity physical units needed precision.','action':'Narrowed reserve inference, separated tokens and added per-barrel/per-pound units.'}]
finish(D,s,before,findings,'Read all eight nonretail keys and their paragraph-matched headline ledger. Reviewed own-card numbers and sessions, Japan CPI at pre-midnight UTC timing, known versus prospective company events, issuer identity and spot-FX exclusion. Retail excluded and preserved.')
