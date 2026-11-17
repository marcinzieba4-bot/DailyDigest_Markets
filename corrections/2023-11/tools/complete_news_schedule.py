import json,datetime as dt
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;p=ROOT/'audit_work/april_release_schedule.json';s=json.loads(p.read_text())
for g in s['guards']:
 g['pattern']=g['pattern'].replace('US|U.S.|United States|American',r'\bUS\b|U\.S\.|United States|American')
 if g['label']=='US March CPI':g['pattern']=r'^(?!.*(?:China|Chinese|Japan|Japanese|Tokyo|Australia|Australian|Poland|Polish|eurozone|euro zone|Germany|German|Canada|Canadian|UK|British|Britain))(?=.*(?:\bCPI\b|consumer prices|consumer inflation|inflation report))'
 if g['label']=='US March PPI':g['pattern']=r'^(?!.*(?:China|Chinese|Japan|Japanese|Australia|Australian|Poland|Polish|eurozone|Germany|German|Canada|Canadian|UK|British|Britain))(?=.*(?:\bPPI\b|producer prices|producer inflation|wholesale prices))'
 if g['label']=='US March PCE and spending':g['pattern']=r'^(?=.*(?:\bUS\b|U\.S\.|United States|American|\bPCE\b))(?=.*(?:\bPCE\b|personal consumption|personal income|March consumer spending|March inflation))'
 if g['label']=='US first-quarter advance GDP':g['pattern']=r'^(?=.*(?:\bUS\b|U\.S\.|United States|American))(?=.*(?:GDP|gross domestic product|economic growth|economy grew))(?=.*(?:first.quarter|Q1|advance|March))'
 if g['label']in{'ECB April policy decision','BOJ April policy decision'}:g['kind']='policy'
 if g['label']=='Japan March national CPI':g['pattern']=r'^(?=.*(?:Japan|Japanese))(?=.*(?:CPI|consumer prices|consumer inflation|core inflation))(?=.*(?:March|Mar\b|national))'

def add(label,date,pattern,url,kind='company_result',time=None,notes='',lookback=14):
 d=dt.date.fromisoformat(date);eligible=d+dt.timedelta(days=1)
 while eligible.weekday()>4:eligible+=dt.timedelta(days=1)
 row=dict(label=label,release_utc=date+'T'+time+':00+00:00'if time else None,calendar_release_utc_date=date,timing_precision='verified exact historical clock'if time else'conservative UTC-day bound; exact minute unasserted',eligible_edition=eligible.isoformat(),earliest_pub_date=(d-dt.timedelta(days=lookback)).isoformat(),pattern=pattern,kind=kind,evidence=[url],notes=notes)
 if not any(g['label']==label for g in s['guards']):s['guards'].append(row)

company=[
('JPMorgan','2024-04-12',r'JPMorgan|JP Morgan|JPM\b','https://www.jpmorganchase.com/ir/news/2024/jpmc-to-host-first-quarter-2024-earnings-call'),
('Citigroup','2024-04-12',r'Citigroup|\bCiti\b','https://www.citigroup.com/global/news/press-release/2024/first-quarter-2024-results-and-key-metrics'),
('Wells Fargo','2024-04-12',r'Wells Fargo','https://www.sec.gov/Archives/edgar/data/72971/000007297124000115/wfc1qer04-12x24ex991xrelea.htm'),
('BlackRock','2024-04-12',r'BlackRock','https://www.sec.gov/Archives/edgar/data/1364742/000095017024043859/blk-20240412.htm'),
('Goldman Sachs','2024-04-15',r'Goldman Sachs|Goldman','https://www.goldmansachs.com/pressroom/press-releases/2024/announcement-02-16-2024'),
('Bank of America','2024-04-16',r'Bank of America|BofA','https://newsroom.bankofamerica.com/content/newsroom/press-releases/2024/04/bank-of-america-reports-first-quarter-2024-financial-results.html'),
('Morgan Stanley','2024-04-16',r'Morgan Stanley','https://www.morganstanley.com/press-releases/morgan-stanley-reports-first-quarter-2024'),
('UnitedHealth','2024-04-16',r'UnitedHealth|UNH\b','https://www.unitedhealthgroup.com/newsroom/2024/2024-04-16-uhg-reports-first-quarter-results.html'),
('Johnson and Johnson','2024-04-16',r'Johnson.{0,5}Johnson|J&J|JNJ\b','https://www.jnj.com/media-center/press-releases/johnson-johnson-reports-q1-2024-results'),
('ASML','2024-04-17',r'ASML','https://www.asml.com/news/press-releases/2024/q1-2024-financial-results'),
('TSMC','2024-04-18',r'TSMC|Taiwan Semiconductor','https://investor.tsmc.com/english/quarterly-results/2024/q1'),
('Netflix','2024-04-18',r'Netflix','https://ir.netflix.net/investor-news-and-events/financial-releases/press-release-details/2024/Netflix-to-Announce-First-Quarter-2024-Financial-Results/default.aspx'),
('Tesla','2024-04-23',r'Tesla|TSLA\b','https://ir.tesla.com/press-release/tesla-releases-first-quarter-2024-financial-results'),
('PepsiCo','2024-04-23',r'PepsiCo|Pepsi','https://www.pepsico.com/en/newsroom/press-releases/2024/pepsico-announces-timing-and-availability-of-first-quarter-2024-financial-results'),
('Meta','2024-04-24',r'\bMeta\b|Facebook','https://investor.atmeta.com/investor-news/press-release-details/2024/Meta-Reports-First-Quarter-2024-Results/default.aspx'),
('Microsoft','2024-04-25',r'Microsoft|MSFT\b','https://www.microsoft.com/en-us/investor/earnings/fy-2024-q3/press-release-webcast'),
('Alphabet','2024-04-25',r'Alphabet|Google','https://abc.xyz/investor/events/event-details/2024/2024-q1-earnings-call/'),
('Exxon','2024-04-26',r'Exxon','https://corporate.exxonmobil.com/news/news-releases/2024/0426_exxonmobil-announces-first-quarter-2024-results'),
('Chevron','2024-04-26',r'Chevron','https://chevroncorp.gcs-web.com/news-releases/news-release-details/chevron-reports-first-quarter-2024-results'),
('Coca Cola','2024-04-30',r'Coca.Cola','https://www.coca-colacompany.com/media-center/coca-cola-reports-first-quarter-2024-results'),
('Amazon','2024-04-30',r'Amazon','https://ir.aboutamazon.com/news-release/news-release-details/2024/Amazon-com-Announces-First-Quarter-Results-68b9258cd/'),
]
for label,date,name,url in company:
 add(label+' April quarterly result',date,r'^(?=.*(?:'+name+r'))(?=.*(?:earnings|results|quarter|profit|EPS|guidance|outlook))',url)
add('Tesla Q1 vehicle production and deliveries','2024-04-02',r'^(?=.*(?:Tesla|TSLA))(?=.*(?:deliveries|delivered|delivery|production))(?=.*(?:quarter|Q1|first.quarter|March))','https://ir.tesla.com/press-release/tesla-vehicle-production-deliveries-and-date-financial-results-webcast-first-quarter-2024',kind='company_operation')
add('Trump Media annual loss disclosure','2024-04-01',r'^(?=.*(?:Trump Media|Truth Social|\bDJT\b))(?=.*(?:2023|annual|\$58|58 million|58.2|loss|revenue))','https://apnews.com/article/6a6504f244c3130e102d11c40ad0d7ff',kind='company_result',lookback=7)
add('Bitcoin fourth halving completed','2024-04-20',r'^(?=.*(?:Bitcoin|\bBTC\b))(?=.*halving)','https://www.blockchain.com/explorer/blocks/btc/840000',kind='staged_event',time='00:09',notes='Block header clock00:09:27UTC; minute shown conservatively. Pending countdown is not completed halving.',lookback=7)
add('Israeli retaliation inside Iran','2024-04-19',r'^(?=.*(?:Israel|Israeli))(?=.*(?:strik|attack|retaliat|explosion|drone))(?=.*(?:Iran|Isfahan))','https://www.reuters.com/fact-check/video-explosion-predates-april-19-attack-iran-2024-04-19/',kind='staged_event',notes='Exact minute unasserted; UTC-day conservative screen. Earlier consular strike in Syria and Iranian attack on Israel are distinct events.',lookback=7)
p.write_text(json.dumps(s,ensure_ascii=False,indent=2))
dp=ROOT/'audit_work/april_observed_semantic_dispositions.json';d=json.loads(dp.read_text());accepted=[
{'title':'Illinois payroll jobs increase, unemployment rate up slightly in February - The Chicago Crusader','guard':'US March payrolls','disposition':'not_this_event','reason':'February Illinois state employment release is a different reference period and geography from March United States national payrolls; root independently confirmed title in raw feed.','reviewer':'root'},
{'title':'Thune pushes for free trade agreements as ag trade deficit rises - South Dakota Searchlight','guard':'US February trade balance','disposition':'not_this_event','reason':'Political agricultural-trade advocacy is distinct from completed February United States national trade-balance statistical release; root independently confirmed title in raw feed.','reviewer':'root'}]
for x in accepted:
 if not any(z['title']==x['title']and z['guard']==x['guard']for z in d['dispositions']):d['dispositions'].append(x)
dp.write_text(json.dumps(d,ensure_ascii=False,indent=2));print('guards',len(s['guards']),'dispositions',len(d['dispositions']))
