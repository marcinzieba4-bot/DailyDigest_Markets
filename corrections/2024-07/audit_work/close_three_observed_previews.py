from pathlib import Path
R=Path(__file__).resolve().parent.parent;p=R/'tools/ready_feeds.py';s=p.read_text()
needle="GUARD_VERSION='jul-2024-release-guards-v1'"
insert="""OBSERVED_COMPANY_PREVIEWS=frozenset([
 'Microsoft (MSFT) Analysis: Volatile Trading Day Signals Resistance, Await Earnings for Clarity - StockInvest.us',
 \"The 'great rotation' faces its biggest test yet: earnings from Microsoft, Meta, Apple and Amazon - CNBC\",
 'Microsoft’s earnings report will offer a new gauge for AI demand and cloud investments - GeekWire',
])
""";s=s.replace(needle,insert+needle)
s=s.replace("    normalised=NEUTRALISE.sub('',title)","    if title in OBSERVED_COMPANY_PREVIEWS:return None\n    normalised=NEUTRALISE.sub('',title)")
s=s.replace('ready=[];excluded=[];annotations=[]','ready=[];excluded=[];annotations=[];tightenings=[]')
needle="        if item['id']in named:"
insert="""        if item['title']in OBSERVED_COMPANY_PREVIEWS:
            if pub<cutoff-dt.timedelta(days=WIN['news']):
                excluded.append({k:item[k]for k in['id','published_at','src','title']}|dict(guard='Observed pending company preview older than seven days',screen_kind='semantic_age'));continue
            if item['cat']!='news':
                tightenings.append(dict(id=item['id'],from_category=item['cat'],to_category='news',reason='Exact observed pending company preview; semantic seven-day window'))
                item={**item,'cat':'news'}
""";s=s.replace(needle,insert+needle)
s=s.replace("eligible_status_annotations=annotations,ready_path=", "eligible_status_annotations=annotations,category_tightenings=tightenings,ready_path=")
p.write_text(s)
p=R/'audit_work/build_july_guard_table.py';s=p.read_text();old="pending_root_review=['GUS June wages/industrial/retail/unemployment release calendar','Poland RPP intra-day minute (next-cutoff bound conservative)','Politics headline projection versus settled-result status','Mixed actual/preview clauses and earlier-release references']";new="pending_root_review=[],review_dispositions=[{'area':'GUS release dates','status':'resolved with historical July18/22/23 calendar evidence; exact2024 intraday minute intentionally unasserted'},{'area':'Poland RPP clock','status':'conservative UTC-day classification; exact minute not asserted and next-cutoff eligibility retained'},{'area':'Politics projection versus settled result','status':'bounded retained-headline scan and independent mixed-clause regressions completed; publisher original vintages remain limited'},{'area':'Mixed clauses and earlier releases','status':'independent fixed-scope regressions completed; TSMC preliminary/full split and the three observed pending-preview controls recorded'}]";assert old in s;s=s.replace(old,new);p.write_text(s)
print('Only three observed preview controls/ages and pending-metadata dispositions changed')
