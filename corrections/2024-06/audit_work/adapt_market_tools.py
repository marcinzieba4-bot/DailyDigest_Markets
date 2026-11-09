from pathlib import Path
R=Path('/workspace/work/june2024/tools')
p=R/'fetch_market.py';s=p.read_text().replace('July 2024 set','June 2024 set').replace('2024-07-31','2024-06-28').replace("LAST = '2024-07-30'","FIRST, LAST = '2024-04-01', '2024-06-27'").replace('dt.datetime(2024, 5, 1','dt.datetime(2024, 4, 1').replace('dt.datetime(2024, 7, 31','dt.datetime(2024, 6, 28').replace('No eligible July trading','No eligible June trading').replace("'IBIT', 'ETHA', 'COIN'","'IBIT', 'COIN'").replace("r[0] < '2024-07-01'","r[0] < '2024-06-03'")
p.write_text(s)
p=R/'build_cards.py';s=p.read_text().replace("'ETHA': 'ETHA (iShares Ethereum Trust)',",'').replace('(2024, 7)','(2024, 6)').replace('Only July 2024 weekdays','Only June 2024 weekdays').replace('dt.date(2024,7,n)','dt.date(2024,6,n)').replace('range(1,32)','range(3,29)')
s=s.replace("'prior_5obs_date': days[-6],", "'prior_1obs_date': days[-2], 'chg_1obs_bps': {'2y': bp(pc['2 Yr'], tr[days[-2]]['2 Yr']), '10y': bp(pc['10 Yr'], tr[days[-2]]['10 Yr'])},\n        'prior_5obs_date': days[-6],")
p.write_text(s)
p=R/'validate_market.py';s=p.read_text().replace('July2024','June2024').replace('dt.date(2024,7,n)','dt.date(2024,6,n)').replace('range(1,32)','range(3,29)').replace("'2024-05-01','2024-07-30'","'2024-04-01','2024-06-27'").replace('len(raw)==289 and len(cards)==23','len(raw)==288 and len(cards)==20').replace('Expected289raw/23cards','Expected288raw/20cards').replace("{'NBIS','CRWV','SNDK'}","{'NBIS','CRWV','SNDK','ETHA'}").replace("{'NBIS','CRWV','SNDK','^IRX','^TNX'}","{'NBIS','CRWV','SNDK','ETHA','^IRX','^TNX'}")
a=s.index("for d in ('2024-07-04'");b=s.index('result={',a)
s=s[:a]+'''for d in ('2024-06-19','2024-06-20'):
 ck(cards[d]['markets']['^GSPC']['session']=='2024-06-18' and cards[d]['treasury']['prior_close_date']=='2024-06-18',d+' Juneteenthpriorclose')
ck(all('ETHA' not in c['markets'] for c in cards.values()) and 'ETHA' not in raw,'ETHAabsentallJune')
ck(cards['2024-06-10']['markets']['NVDA']['reference_share_units_differ'] is False and cards['2024-06-11']['markets']['NVDA']['reference_share_units_differ'] is True,'NVDAsplitboundary')
ck(cards['2024-06-26']['markets']['CMG']['reference_share_units_differ'] is False and cards['2024-06-27']['markets']['CMG']['reference_share_units_differ'] is True,'CMGsplitboundary')
ck(float(cards['2024-06-03']['markets']['MSTR']['close'].replace(',',''))>1000,'MSTRas-tradedrestoration')
''' + s[b:]
s=s.replace("'XCBF package July3 timing is a conservative before-cutoff eligibility check, not certification of the exact VIX print time; independent review records the primary Cboe early-close notice.',",'')
s=s.replace("for key,col in {'2y':'2 Yr','10y':'10 Yr'}.items():ck(x['chg_5obs_bps'][key]==bp(last[col],five[col]),d+' fivebps'+key)","for key,col in {'2y':'2 Yr','10y':'10 Yr'}.items():\n  ck(x['chg_5obs_bps'][key]==bp(last[col],five[col]),d+' fivebps'+key)\n  ck(x['prior_1obs_date']==days[-2] and x['chg_1obs_bps'][key]==bp(last[col],tr[days[-2]][col]),d+' onebps'+key)")
p.write_text(s)
