from pathlib import Path
R=Path(__file__).resolve().parent.parent;p=R/'audit_work/build_july_guard_table.py';s=p.read_text()
s=s.replace("'US','UK','CPI'", "'Fed','FOMC','rates?','policy','decision','cuts?','lowers?','holds?','keeps?','leaves?','hikes?','raises?','wins?','win','resign','majority','victory','US','UK','CPI'")
s=s.replace("'+token+r'(?![A-Za-z0-9_])'", "+re.escape(token)+r'(?![A-Za-z0-9_])'")
s=s.replace(" pattern=bound_tokens(pattern)", " pattern=bound_tokens(pattern)\n if not pattern.startswith('^'):pattern='^'+pattern")
s=s.replace("notes='July4 exit poll after21UTC is eligible as a projection for July5; settled Friday result/PM appointment is not automatically available at midnight.'", "notes='Conservative UTC-day bound only. July4 exit poll after21UTC is eligible as a projection for July5; settled Friday result/PM appointment is not automatically available at midnight.'")
s=s.replace("r'Bristol.Myers|Bristol Myers|3M|Colgate", "r'Bristol.Myers|Bristol Myers|(?<![.$0-9])3M|Colgate")
s=s.replace("('Meta Qualcomm Arm Boeing Mastercard Samsung','2024-07-31'", "('Meta Qualcomm Arm Boeing Mastercard','2024-07-31'").replace("|Albemarle|Samsung'),", "|Albemarle'),")
s=s.replace("r'(?=.*(?:Australia|Australian))(?=.*(?:jobs|employment|unemployment|labour market|labor market))'", "r'(?=.*(?:Australia|Australian))(?=.*(?:June|unemployment|jobs (?:report|data|growth|gain)|employment (?:report|data|growth|gain)|labour market|labor market))(?=.*(?:jobs|employment|unemployment|labour|labor))'")
s=s.replace("r'(?=.*(?:BOJ|Bank of Japan|Ueda))(?=.*(?:rates?|policy|decision|bond buying|bond.buying|hikes?|raises?|cuts?))'", "r'(?=.*(?:BOJ|Bank of Japan|Ueda))(?=.*(?:rates?|policy (?:decision|meeting)|decision|bond buying|bond.buying|hikes?|raises?|cuts?))'")
s=s.replace("r'(?=.*(?:Fed|FOMC|Federal Reserve|Powell))(?=.*(?:rates?|policy|decision|September cut|September easing))'", "r'(?=.*(?:Fed|FOMC|Federal Reserve|Powell))(?=.*(?:rates?|policy (?:decision|meeting)|decision|September cut|September easing))'")
start=s.index("result_pattern=r'");end=s.index('\nfor label,date,names in company_groups:',start)
s=s[:start]+"result_pattern=r'(?=.*\\b(?:earnings|results|revenue|sales|profits?|EPS|guidance|forecasts?|bookings)\\b)'"+s[end:]
needle="company_groups=[";extra="""add('SK hynix Q2 early-local earnings','2024-07-24T23:59:59Z',r'(?=.*(?:SK hynix|SK Hynix))(?=.*(?:earnings|results|revenue|sales|profits?|EPS|guidance|forecasts?))','company_result',start_days=14,notes='Conservative before-midnight UTC bound: dated company invitation says July25 press release before09:00 Seoul. Exact minute unasserted; eligible July25.')
add('Samsung Electronics Q2 full result clock uncertain','2024-07-31T23:59:59Z',r'^(?!.*Samsung Biologics)(?=.*Samsung)(?=.*(?:earnings|results|revenue|sales|profits?|EPS|guidance|forecasts?))','company_result',start_days=14,notes='Conservative omission until Aug1: full-results local date is July31 but original pre00UTC publication clock is not certified. Do not assert that every Korean morning release follows00UTC.')
""";s=s.replace(needle,extra+needle);p.write_text(s)
p=R/'tools/ready_feeds.py';s=p.read_text()
s=s.replace("|^LIVE[ :]", "|^LIVE:")
s=s.replace("SETTLED_UK=re.compile(r'", "SETTLED_UK=re.compile(r'")
s=s.replace('is named|was named|has been named|named prime minister|sworn in|has conceded|concedes defeat|conceded defeat|appointed prime minister|takes office|takes power', 'is named|was named|has been named|named prime minister|sworn in|has conceded|concedes (?:defeat|the election)|conceded (?:defeat|the election)|appointed prime minister|becomes? (?:Britain[’\\\']s |the )?prime minister|enters? Downing Street|takes office|takes power')
insert=r'''
MODAL_SUBJECT_ACTION=re.compile(r'\b(?:will|could|would|can|might|may|should)\s+(?:the\s+)?(?:Fed|FOMC|ECB|BOJ|RBA|PBOC|it|they|he|she)\s+(?:rate\s+)?(?:cuts?|hikes?|raises?|holds?|keeps?|reports?|beats?|misses?|tops?|grows?)\b',re.I)
PENDING_POLICY_ACTION=re.compile(r'\b(?:to weigh|to debate|to discuss|to consider|weighs?|considers?|debates?|discusses?|mulls?)\s+(?:(?:an?|the|another)\s+)?(?:rate\s+)?(?:hike|cut|increase|reduction)\b|\b(?:possible|potential|expected|likely|prospective|anticipated)\s+(?:(?:Fed|BOJ|ECB|PBOC)\s+)?(?:rate\s+)?(?:hike|cut|increase|reduction)\b|\b(?:opens?|opening|opened)\s+(?:the\s+)?door\s+to\s+(?:rate\s+)?cuts?\b',re.I)
FINANCIAL_COMPLETION_HINT=re.compile(r'\b(?:earnings|results|revenue|sales|profits?|EPS)\b.{0,30}\b(?:were|was|came in|surprise|surprises|surprised|beat|beats|miss|misses|rose|fell|soars?|doubles?|disappoints?)\b',re.I)
'''
s=s.replace('def guard_hit(title,published,stamp):',insert+'\ndef guard_hit(title,published,stamp):')
s=s.replace("outcome_text=FUTURE_RATE_NOUN.sub('',FORWARD_ACTION.sub('',normalised))", "outcome_text=FUTURE_RATE_NOUN.sub('',PENDING_POLICY_ACTION.sub('',MODAL_SUBJECT_ACTION.sub('',FORWARD_ACTION.sub('',normalised))))")
s=s.replace("        if kind in{'company_result','company_operation'}:", "        if kind in{'company_result','company_operation'}:")
old="""            if FINANCIAL_OUTCOME.search(MARKET_CLAUSE.sub('',outcome_text)):return label
            if clear_preview or FORWARD.search(normalised):continue
            return label"""
new="""            # Preserve observed separate disclosures/issuer roles, not a future
            # parent-company result: Westlife franchisee, industry EV sales and
            # litigation about streaming-revenue taxation are different events.
            if re.search(r'McDonald',label,re.I)and re.search(r'Westlife|franchisee|India (?:operator|franchise)',title,re.I):continue
            if re.search(r'Tesla Alphabet',label)and re.search(r'EV Sales|electric.vehicle sales',title,re.I)and not re.search(r'earnings|profits?|EPS|guidance|revenue',title,re.I):continue
            if FINANCIAL_COMPLETION_HINT.search(MARKET_CLAUSE.sub('',outcome_text))or FINANCIAL_OUTCOME.search(MARKET_CLAUSE.sub('',outcome_text)):return label
            if re.search(r'court|lawsuit|appeal|tax',title,re.I)and not re.search(r'earnings|results|profits?|EPS|quarter',title,re.I):continue
            if clear_preview:continue
            return label"""
assert old in s;s=s.replace(old,new)
s=s.replace("calendar_notice=bool(re.search(r'announc", "calendar_notice=bool(re.search(r'announc")
s=s.replace("or re.search(r'Outlook for|optimism about',normalised,re.I))", "or re.search(r'Outlook for|optimism about|before (?:Q[1-4] |quarterly )?(?:earnings|results)|nears? (?:the )?earnings|earnings to (?:reflect|show|test|reveal|shed)|here.s what you need to know|meeting started',normalised,re.I))")
s=s.replace("        if label.startswith('US June retail sales')", "        if label.startswith('China Q2 GDP')and re.search(r'Penfolds|\\bMay\\b',title,re.I):continue\n        if label.startswith('US Q2 GDP')and re.search(r'largest economies|GDP \\(PPP\\)',title,re.I):continue\n        if label.startswith('US June retail sales')")
s=s.replace('cuts?|hikes?|raises?|holds?|held', 'cuts?|hikes?|lifts?|lifted|raises?|holds?|held')
p.write_text(s)
print('Observed safety, preview, issuer-role and performance fixes applied')
