"""Flag paragraphs for editorial review near known release boundaries.

This is a review aid, not a semantic proof. A preview or an older release can
match; root records the disposition after reading the claim and citations.
No later event values/outcomes are supplied to writers.
"""
from pathlib import Path
import importlib.util,json,re,sys
ROOT=Path(__file__).resolve().parent.parent
RULES=[
 ('shutdown_start','2025-10-02',r'\bshutdown\b',r'\b(began|has begun|started|entered|is now|shut down|closed)\b'),
 ('october_nbp','2025-10-09',r'\b(NBP|RPP|Polish central bank)\b',r'\b(cut|lowered|reduced|decision)\b'),
 ('additional_china_tariff','2025-10-13',r'\b(Trump|tariff)\b',r'\b100\s*(?:%|percent|per cent)\b'),
 ('september_china_trade','2025-10-14',r'\b(China|Chinese)\b',r'\bSeptember\b.*\b(exports|imports|trade surplus)\b'),
 ('asml_q3','2025-10-16',r'\bASML\b',r'\b(beat|reported|orders|bookings|profit|results)\b'),
 ('september_china_cpi','2025-10-16',r'\b(China|Chinese)\b',r'\bSeptember\b.*\b(CPI|inflation|consumer prices)\b'),
 ('tsmc_q3','2025-10-17',r'\bTSMC\b',r'\b(reported|beat|record profit|results|earnings)\b'),
 ('china_q3_activity','2025-10-21',r'\b(China|Chinese)\b',r'\b(Q3|third.quarter|September)\b.*\b(GDP|industrial output|retail sales|growth)\b'),
 ('september_us_cpi','2025-10-27',r'\b(US|U\.S\.|America|CPI)\b',r'\bSeptember\b.*\b(CPI|consumer prices|inflation)\b'),
 ('australia_september_cpi','2025-10-30',r'\b(Australia|Australian|RBA)\b',r'\bSeptember\b.*\b(CPI|inflation|consumer prices)\b'),
 ('october_fomc','2025-10-30',r'\b(Fed|FOMC)\b',r'\bOctober\b.*\b(cut|decided|ended|halted|announced)\b'),
 ('trump_xi_summit','2025-10-31',r'\b(Trump|Xi)\b',r'\b(summit|meeting)\b.*\b(agreed|reached|delivered|ended|struck)\b'),
 ('tesla_ibm_q3','2025-10-23',r'\b(Tesla|IBM)\b',r'\b(Q3|third.quarter|quarterly)\b.*\b(beat|reported|fell|rose|profit|results)\b'),
 ('bigtech_oct29','2025-10-30',r'\b(Microsoft|Meta|Alphabet)\b',r'\b(Q3|third.quarter|quarterly)\b.*\b(beat|reported|profit|results)\b'),
 ('amazon_apple_oct30','2025-10-31',r'\b(Amazon|Apple)\b',r'\b(Q3|third.quarter|quarterly)\b.*\b(beat|reported|profit|results)\b'),
 ('october_ecb_boj','2025-10-31',r'\b(ECB|BOJ|Bank of Japan)\b',r'\bOctober\b.*\b(held|kept|decided|raised|cut|left)\b'),
 ('us_q3_gdp','2025-12-01',r'\b(US|U\.S\.|American)\b',r'\b(Q3|third.quarter)\b.*\b(GDP|economy grew|growth accelerated|expanded)\b'),
 ('october_china_pmi','2025-11-03',r'\b(China|Chinese)\b',r'\bOctober\b.*\b(PMI|manufacturing)\b'),
]

def main():
 spec=importlib.util.spec_from_file_location('verify',ROOT/'tools'/'verify.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
 dates=sys.argv[1:] or [p.stem for p in sorted((ROOT/'specs').glob('*.json'))]
 flags=[]
 for d in dates:
  s=json.loads((ROOT/'specs'/f'{d}.json').read_text())
  for where,label,text in v.paragraphs(s):
   for name,first,rx,actual in RULES:
    if d<first and re.search(rx,text,re.I) and re.search(actual,text,re.I):
     flags.append({'date':d,'rule':name,'first_eligible_report':first,'where':where,'label':label,'text':text})
 out={'method':'conservative keyword flags; requires contextual editorial disposition','flags':flags}
 (ROOT/'checks'/'release_guard_flags.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
 print(len(dates),'reports;',len(flags),'paragraphs require contextual review')

if __name__=='__main__':main()
