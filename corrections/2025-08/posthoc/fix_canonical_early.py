"""Remove selected same-UTC-date publisher conflicts and their dependent claims."""
from pathlib import Path
import datetime as dt, gzip, hashlib, json
ROOT=Path(__file__).resolve().parents[1]
BACKUP=ROOT/'work/canonical_early_before'
TARGETS={'2025-08-01':['n0351','n1316'],'2025-08-04':['n1367'],'2025-08-06':['n0394','n3097'],'2025-08-07':['n4095','n6764']}
specs={d:json.loads((ROOT/'specs'/f'{d}.json').read_bytes()) for d in TARGETS}
audit={'scope':'Targeted canonical-date fixes for seven flagged source IDs in four reports; dependent claims removed or replaced using own-date eligible evidence. No claim of exhaustive original-article-vintage verification.','changed_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'reports':{}}
def sha(b):return hashlib.sha256(b).hexdigest()
for d,ids in TARGETS.items():
    path=ROOT/'specs'/f'{d}.json';raw=path.read_bytes()
    assert all(n in raw.decode() for n in ids),(d,'expected source no longer present')
    BACKUP.mkdir(parents=True,exist_ok=True);backup=BACKUP/f'{d}.json'
    if backup.exists():raise RuntimeError('Preserve original before snapshot; do not rerun')
    backup.write_bytes(raw)
    audit['reports'][d]={'before_spec_sha256':sha(raw),'removed_ids':ids,'changes':[]}
def change(d,path,new,reason,replacement_ids=None):
    node=specs[d]
    for key in path[:-1]:node=node[key]
    old=node[path[-1]];node[path[-1]]=new
    audit['reports'][d]['changes'].append({'path':'/'+('/'.join(str(x) for x in path)),'before':old,'after':new,'reason':reason,'replacement_ids':replacement_ids or []})

change('2025-08-01',['geo',2,'parts',6,1],
"The investment test for the competition campaign is whether companies change how they win and retain customers. Reuters reported leaders targeting disorderly competition. Less destructive subsidy spending could improve the value of an existing customer relationship even without a sharp rise in national consumption, but that remains an operating hypothesis rather than a completed platform agreement. Look for customer retention and margin improvement before treating policy intent as corporate execution. Technology sovereignty adds another layer. Reuters reported Chinese AI firms forming domestic alliances, while Nvidia denied security backdoors after China raised concerns over its chips. Local substitution and access to foreign technology can coexist uneasily; avoid treating either as a settled winner. [[n1238]] [[n1146]] [[n1373]]",
"Removed platform pledges whose canonical date is Aug1; retained earlier official competition-policy intent and conditional operating analysis.",['n1238'])
old=specs['2025-08-01']['geo'][2]['parts'][7][1]
change('2025-08-01',['geo',2,'parts',7,1],old.replace('or platform competition resumes before operating returns improve','or platform competition continues consuming margins before operating returns improve'),
"Removed implication that platform competition had already ceased.")
change('2025-08-01',['geo',4,'parts',0,1],
"Australia has a clearer route towards rate relief after the latest inflation evidence. The AFR reported lower inflation setting up an RBA cut. That improves the financing argument without establishing a broad recovery in household demand. Slower inflation can support purchasing power, but households still need confidence in income and enough cash after essential expenses to spend more. Mortgage-sensitive businesses should therefore be assessed on the customer's ability and willingness to buy, not simply on the market's preferred policy direction. A rate cut would improve a financing input; it would not guarantee stronger sales for every retailer or repair every household balance sheet. [[n0323]]",
"Removed ABC home-price outcome; exact pre-cutoff publisher availability was not established. Preserved eligible earlier inflation/easing evidence.")
change('2025-08-01',['underowned',1,'parts',0,1],
"Official pressure against disorderly competition creates a potential relative-margin opportunity before broad domestic reflation. Reuters reported leaders promising economic support and a crackdown on that competition. The investment question is whether businesses can earn more from existing demand by retaining customers without indefinitely subsidising each transaction. Policy intent supplies a reason to investigate, not proof that platforms have changed their behaviour. [[n1238]]",
"Replaced premature Alibaba/Meituan pledges with earlier official policy intent; no platform commitment retained.",['n1238'])
change('2025-08-01',['underowned',1,'parts',1,1],
"KWEB or selected platform shares express the opportunity, with competitive and policy risk recognised. A potential margin benefit requires less subsidy dependence while customer retention holds. If rivals continue competing aggressively, the anticipated profit improvement may fail to arrive even when the policy objective is clear.",
"Removed implication that a previously halted price war could merely reopen.")
change('2025-08-01',['underowned',1,'parts',2,1],
"Add when customer retention and operating margins improve without greater subsidy dependence. Abandon the relative-margin argument if competitive spending continues absorbing monetisation benefits. Require operating evidence before treating an official request for restraint as an investable improvement in profit.",
"Tied trigger to observable future operating evidence rather than an unverified completed pledge.")

change('2025-08-04',['geo',2,'parts',4,1],
"Policy is working through several distinct channels. Reuters reported the childcare-subsidy programme and leaders pledging support while targeting disorderly competition. The household transfer can improve spending capacity; the competition campaign attempts to change the distribution of profit within existing markets. Neither automatically resolves trade uncertainty. The US–China talks left an extension of the truce unresolved, according to CNBC's account, so exporters still face a meaningful event risk. Those differences matter for allocation: direct household support, competitive discipline and trade negotiations reach company earnings through different mechanisms. Prefer a business whose customer demand and cash generation can be assessed under imperfect trade terms rather than assuming every policy channel produces an immediate equity inflow. [[n1121]] [[n1131]] [[n1089]]",
"Removed surprise bond-interest tax and dependent asset-allocation claim; added already-eligible own-feed citation for the existing truce discussion.",['n1089'])

change('2025-08-06',['geo',1,'parts',0,1],
"Europe's investment opportunity increasingly depends on the resilience and economics of its supply chains. Reuters reported Germany aiming to reduce dependence on China for wind-power components. That identifies a procurement priority, rather than a funded order for every domestic supplier. A company's opportunity still depends on whether its product, capacity and costs match a customer's paid need. Prefer an executable project with a credible contractual return to a broad trade on the scale of a policy aspiration. Security of supply can justify additional investment, but the shareholder must still examine who funds it and how much of the value the supplier can retain. [[n3098]]",
"Removed German strategic-fund announcement and claims depending on its existence; retained earlier wind-component procurement evidence.")
change('2025-08-06',['geo',4,'parts',0,1],
"Australia's domestic-demand case must distinguish slower inflation from a full repair in household purchasing power. The Guardian described inflation falling while prices remained high. That distinction matters for retailers and housing exposure: a slower increase in expenses can improve the direction of household finances without reversing the earlier rise in their cost. Easier financing would help some borrowers, but the benefit still has to become spending at a margin the business can retain. Prefer companies delivering value and generating cash rather than assuming every consumer category rebounds as soon as the rates debate turns friendlier. The equity entry price needs its own justification alongside the customer's capacity to buy. [[n0353]]",
"Replaced unverified same-date ABC construction outcome with eligible own-date Guardian inflation-versus-price-level headline. Original Guardian publication explicitly precedes cutoff.",['n0353'])

old=specs['2025-08-07']['geo'][3]['parts'][1][1]
new=old.replace("Reuters reported a proposed 6% minimum-wage increase, while Bloomberg described the largest proposed public-worker pay rise in decades.","Reuters reported a proposed 6% minimum-wage increase.").replace('[[n4034]] [[n4095]] [[n2589]]','[[n4034]] [[n2589]]')
change('2025-08-07',['geo',3,'parts',1,1],new,
"Removed unverified same-date public-worker pay proposal; retained earlier minimum-wage proposal and June real-wage evidence.")
change('2025-08-07',['sectors',3,'parts',2,1],
"Look for producers able to protect realised cash generation through cost control, disciplined investment and a resilient operating mix. An upside surprise would require those improvements to offset weaker crude assumptions. Add only when results demonstrate that mechanism rather than assuming an announced supply change maps directly into company earnings.",
"Removed premature physical-oil tightness claim and its claimed upside implication; replaced with a conditional earnings test.")
change('2025-08-07',['sectors',3,'parts',3,1],
"OilPrice described crude falling as markets absorbed the OPEC+ supply decision. Supply expectations can move prices before the next company report establishes the effect on cash generation. Stay underweight higher-cost exposure until crude stabilises and forecasts absorb lower prices; reverse that stance if stronger realised cash flow makes distributions sustainable without additional financial strain. [[n6327]]",
"Removed uncited dependent assertion of tighter current physical conditions.")

for d,spec in specs.items():
    raw=(json.dumps(spec,indent=2,ensure_ascii=False)+'\n').encode()
    assert not any(n in raw.decode() for n in TARGETS[d]),(d,'conflicting citation survives')
    path=ROOT/'specs'/f'{d}.json';path.write_bytes(raw)
    audit['reports'][d]['after_spec_sha256']=sha(raw)
    audit['reports'][d]['feed_sha256']=sha((ROOT/'feeds'/f'{d}.json.gz').read_bytes())
audit['replacement_publication_checks']=[
 {'date':'2025-08-01','id':'n1238','canonical_url':'https://www.reuters.com/world/china/chinas-leaders-vow-support-economy-crackdown-disorderly-competition-2025-07-30/','basis':'Earlier own-feed leadership-policy report, already cited in same report; final shared canonical audit remains source of truth.'},
 {'date':'2025-08-04','id':'n1089','basis':'Own-feed CNBC July29 talks/truce headline; no post-cutoff outcome added.'},
 {'date':'2025-08-06','id':'n0353','canonical_url':'https://www.theguardian.com/news/2025/aug/05/inflation-is-down-but-prices-remain-high-when-will-the-cost-of-living-crisis-end','publisher_first_published_local':'2025-08-05 01:00AEST','publisher_first_published_utc':'2025-08-04T15:00:00Z','publisher_last_modified_local':'2025-08-05 10:43AEST','basis':'Public publisher timestamp inspected; headline-level claim only. Original complete body vintage is not established.'}
]
(ROOT/'audit/canonical_fixes_early.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n')
print('Fixed',len(specs),'reports; removed',sum(map(len,TARGETS.values())),'source IDs')
