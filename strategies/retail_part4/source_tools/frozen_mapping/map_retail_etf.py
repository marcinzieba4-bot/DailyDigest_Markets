"""Map retail attention to a fixed, fully observed 17-ETF research universe.

This is a NEW coarse sector-attention specification, not a repair of unavailable
stock prices. No market series or outcome enters the mapping. Individual stock,
commodity, option and crypto payoffs are never represented as their own returns.
"""
from __future__ import annotations
import csv, hashlib, json, re
from collections import Counter
from pathlib import Path
from map_retail import ROOT, map_item

UNIVERSE='SPY QQQ XLK XLC XLF XLE XLI XLY XLP XLV XLB XLRE XLU SOXX EPOL GLD IEF'.split()
GROUPS={
    'SOXX':'NVDA MU AMD INTC TSM ASML AVGO ARM MRVL AMAT LRCX KLAC QCOM SNDK ALAB CRDO COHR LITE POET AAOI INFQ',
    'XLK':'MSFT PLTR AAPL CRM NOW SNOW ORCL DELL SMCI HPE CIEN ANET FTNT PANW CRWD SOUN CRWV NBIS APLD RZLV STX WDC FSLR',
    'XLY':'TSLA NIO F LCID AMZN NKE LULU WEN CMG SBUX GME CAR HTZ EBAY ETSY HD LOW BABA JD PDD QS',
    'XLV':'CRSP BNTX SLS ADCT ADMA AVXL IBRX GUTS TERN ATAI CMPS GHRS CYBN NTLA VKTX SMMT MRNA LLY NVO JNJ ABBV AMGN BMY BSX',
    'XLF':'HOOD SOFI PYPL JPM BAC MS GS KKR APO MA SPGI BRK-B RKT',
    'XLI':'BA RTX LMT NOC KTOS AVAV RCAT ONDS RDW RKLB LUNR SPCE ESLT LHX TDY EME PWR GEV UBER BE',
    'XLC':'META GOOGL GOOG AMC RDDT DIS TTWO MGNI SKLZ ASTS',
    'XLU':'VST NRG NEE',
    'XLB':'MP UAMY USAR LAC X UUUU CCJ',
    'XLE':'XOM CVX OXY COP SLB BKR MPC VLO',
    'XLP':'WMT COST',
    'XLRE':'DLR',
}
STOCK_TO_ETF={stock:etf for etf,stocks in GROUPS.items() for stock in stocks.split()}
EXTRA_ETFS={
    'SMH':('SOXX','semiconductor_etf_to_fixed_semiconductor_etf'),
    'IGV':('XLK','software_to_broad_technology_equities'),
    'ITA':('XLI','defense_to_broad_industrial_equities'),
    'XBI':('XLV','biotech_to_broad_healthcare_equities'),
    'GDX':('XLB','gold_miners_to_broad_materials_equities'),
    'XOP':('XLE','oil_producers_to_broad_energy_equities'),
    'OIH':('XLE','oil_services_to_broad_energy_equities'),
    'ARKF':('XLF','fintech_to_broad_financial_equities'),
    'KBE':('XLF','banks_to_broad_financial_equities'),
    'XHB':('XLY','homebuilders_to_broad_discretionary_equities'),
    'SRVR':('XLRE','data_center_real_estate_to_broad_real_estate_equities'),
    'QTUM':('XLK','quantum_computing_to_broad_technology_equities'),
}
CRYPTO=re.compile(r'(?i)\bbitcoin\b|\bethereum\b|\beth\b|\bbtc\b|crypto|altcoin|meme.coin|memecoin|solana|\bxrp\b|\bxlm\b|\bdoge\b|\bdefi\b|bittensor')
FOREIGN=re.compile(r'(?i)\bchina\b|\bchinese\b|\bkorea|\bkorean\b|\bjapan|\bnikkei\b|\bgerman|\beurope|\beuropean|\bswiss\b|\bhong kong\b|\bUK\b|\bbritish\b|non[- ]us|international|rest.of.world')


def clear_industry(title):
    """A title can identify an industry despite rare or unknown stock symbols."""
    patterns=[
        (r'\b(?:semiconductors?|semis|chips?|chipmakers?|memory|optics|photonics)\b','SOXX','clear_semiconductor_industry'),
        (r'\b(?:biotech|biopharma|pharma|psychedelic|glp.1|weight.loss|drugs?)\b','XLV','clear_healthcare_industry'),
        (r'\b(?:fintech|banks?|financials?|private.equity|asset.managers|mortgage)\b','XLF','clear_financial_industry'),
        (r'\b(?:defen[cs]e|aerospace|drones?|space|aviation)\b','XLI','clear_industrial_industry'),
        (r'\b(?:software|saas|cybersecurity|quantum|enterprise.ai)\b','XLK','clear_technology_industry'),
        (r'\butility|\butilities|\bpower (?:stocks|equities|companies)','XLU','clear_utility_industry'),
        (r'\bretail\b|consumer.discretionary|\bauto|\bhomebuild','XLY','clear_discretionary_industry'),
        (r'consumer.staples|recession.proof.*consumer','XLP','clear_consumer_staples_industry'),
        (r'data.center.*real.estate|\breit|\breal.estate','XLRE','clear_real_estate_industry'),
        (r'\bsteel\b|critical.mineral|rare.earth|defen[cs]e.metals|\bmining.stocks','XLB','clear_materials_industry'),
        (r'\b(?:oil|crude|petroleum|natural gas|fossil)\b','XLE','clear_fossil_energy_equity_attention'),
    ]
    for pattern,etf,rule in patterns:
        if re.search(pattern,title,re.I):return etf,rule
    return None


def map_etf_item(item):
    direct=map_item(item);title=direct['main_title'];lower=title.lower()
    result={k:direct[k] for k in ['main_title','mapping_status','mapping_rule','mapping_reason','crowd_direction','mapped_symbols','mapped_directions','targets','unsupported_tokens']}
    result.update(original_direct_targets=direct['targets'],basis_risk_flags='[]',unrepresented_targets='[]',
        mapping_specification='fixed_17_etf_sector_attention_v1')
    def reject(reason,rule):
        result.update(mapping_status='unmapped',mapping_rule=rule,mapping_reason=reason,crowd_direction='',mapped_symbols='',mapped_directions='{}',targets='[]')
        return result
    if direct['mapping_status']!='mapped':return result
    if CRYPTO.search(title):return reject('Crypto-related topic has no approved instrument in the fixed ETF universe.','etf_crypto_exclusion')
    if re.search(r'(?i)spacex|starlink|anthropic|pre[- ]ipo|\bipo\b|\bIPOs\b|private.market',title):
        return reject('Private or IPO narrative is not replaced with a sector ETF.','etf_private_ipo_exclusion')
    if FOREIGN.search(title):return reject('Regional or foreign-market thesis lacks an appropriate available ETF in the fixed universe.','etf_foreign_region_exclusion')
    direct_targets=json.loads(direct['targets'])
    if any(t['symbol'] in ['IWM','RSP'] for t in direct_targets) and not re.search(r'(?i)\b(?:technology|semiconductor|chip|biotech|bank|energy|defen[cs]e|healthcare|utility|financial|industry|industrial)\b',title):
        return reject('Small-cap or breadth rotation is not represented by a large-cap sector ETF.','etf_small_cap_breadth_exclusion')
    if re.search(r'\bsilver\b',lower) and not re.search(r'\bgold\b',lower):
        return reject('Silver-only attention has no SLV or equivalent instrument in the fixed universe.','etf_silver_exclusion')
    copper=bool(re.search(r'\bcopper\b',lower))
    copper_equity=bool(re.search(r'(?i)stocks|equities|\bminers|\bmining',title))
    if copper and not copper_equity and not re.search(r'\bgold\b',lower):
        return reject('Pure copper commodity attention lacks an approved commodity instrument; XLB is not fabricated copper performance.','etf_pure_copper_exclusion')
    oil=bool(re.search(r'(?i)\boil\b|\bwti\b|\bcrude\b',title))
    energy_context=bool(re.search(r'(?i)\benergy\b|stocks|equities|majors|producers|refiners|\boil services\b',title))
    if oil and not energy_context:
        return reject('Pure crude or oil fund attention is not replaced with energy equity performance.','etf_pure_oil_exclusion')
    targets=[];unrepresented=[];flags=[]
    for target in direct_targets:
        symbol=target['symbol'];direction=target['direction'];mapped=None;rule=None;coarse=True
        if symbol=='GLD' and re.search(r'(?i)gold.miners|gold.mining',title) and target.get('rule')=='gold_theme':
            mapped='XLB';rule='gold_miner_equity_attention_to_broad_materials_proxy';flags.append('gold_miner_to_broad_materials_basis_risk')
        elif symbol in UNIVERSE:
            mapped=symbol;rule='supported_fixed_universe_etf';coarse=bool(target.get('proxy'))
        elif symbol in STOCK_TO_ETF:
            mapped=STOCK_TO_ETF[symbol];rule='fixed_named_stock_sector_crosswalk'
        elif symbol in EXTRA_ETFS:
            mapped,rule=EXTRA_ETFS[symbol]
        elif symbol=='TLT':
            mapped='IEF';rule='long_duration_attention_to_intermediate_treasury_proxy';flags.append('duration_mismatch_TLT_to_IEF')
        elif symbol in ['USO','UGA','OIL'] and energy_context:
            mapped='XLE';rule='oil_energy_attention_to_energy_equity_proxy';flags.append('oil_fund_to_energy_equity_basis_risk')
        elif symbol=='CPER' and copper_equity:
            mapped='XLB';rule='copper_mining_equity_attention_to_materials_proxy';flags.append('copper_mining_to_broad_materials_basis_risk')
        elif symbol=='SLV' and re.search(r'\bgold\b',lower):
            unrepresented.append({'symbol':symbol,'reason':'silver_component_unrepresented_no_SLV'});continue
        elif symbol in ['TAN','URA'] or re.search(r'(?i)\b(?:solar|photovoltaic|nuclear|uranium|SMR)\b',title):
            # Confident named-company mappings above take precedence. A broad
            # nuclear/solar ETF or unknown specialist is not oil/gas equity.
            unrepresented.append({'symbol':symbol,'reason':'specialist_solar_or_nuclear_exposure_has_no_faithful_fixed_universe_proxy'});continue
        elif symbol in ['IBIT','ETHA','GBTC','BTC','ETH','FXI','EWY','EWH','EWG','EWJ','EWL','IEUR','IWM','RSP']:
            unrepresented.append({'symbol':symbol,'reason':'no_appropriate_fixed_universe_proxy'});continue
        else:
            industry=clear_industry(title)
            if industry:mapped,rule=industry;rule='title_industry_for_unclassified_named_target:'+rule
        if mapped is None:
            unrepresented.append({'symbol':symbol,'reason':'not_in_confident_static_sector_dictionary_or_clear_title_industry'});continue
        if mapped=='XLB' and (symbol=='GDX' or re.search(r'(?i)gold.miners',title)):
            flags.append('gold_miner_to_broad_materials_basis_risk')
        if symbol=='ASTS':flags.append('ASTS_telecom_to_broad_communications_basis_risk')
        if symbol in ['CCJ','UUUU']:flags.append('uranium_miner_equity_to_broad_materials_basis_risk')
        if symbol in ['FSLR','BE','QS']:flags.append('specialist_named_equity_to_broad_business_sector_basis_risk')
        if coarse and mapped not in ['SPY','QQQ','GLD','IEF']:
            flags.append('broad_sector_proxy_not_named_stock_or_specialist_fund_returns')
        if target.get('proxy') and ('inverse_' in target.get('rule','') or 'leveraged_' in target.get('rule','')):
            flags.append('leveraged_or_inverse_product_normalized_to_1x_direction_once')
        targets.append({'symbol':mapped,'direction':direction,'proxy':coarse,
            'source_target':symbol,'original_token':target.get('original_token',''),'rule':rule})
    collapsed={}
    for target in targets:
        if target['symbol'] in collapsed and collapsed[target['symbol']]['direction']!=target['direction']:
            return reject('Opposite source directions collapse onto the same ETF; no cancellation is guessed.','etf_conflicting_directions_exclusion')
        if target['symbol'] not in collapsed:collapsed[target['symbol']]=target
        else:
            collapsed[target['symbol']].setdefault('additional_source_targets',[]).append(target['source_target'])
    targets=list(collapsed.values())
    if not targets:
        result['unrepresented_targets']=json.dumps(unrepresented)
        return reject('No supported ETF exposure can be identified confidently; attention remains in cash.','etf_no_confident_proxy')
    for target in targets:target['weight']=1/len(targets)
    if re.search(r'\bsilver\b',lower) and re.search(r'\bgold\b',lower):flags.append('gold_component_only_silver_unrepresented')
    if unrepresented:flags.append('partial_topic_representation_unmapped_components_excluded')
    result.update(mapping_status='mapped',mapping_rule='fixed_17_etf_attention_crosswalk',
        mapping_reason='Equal-weight distinct ETF attention targets; this does not claim named stock, commodity, inverse-fund or option returns.',
        crowd_direction=direct['crowd_direction'],mapped_symbols='|'.join(t['symbol'] for t in targets),
        mapped_directions=json.dumps({t['symbol']:t['direction'] for t in targets},sort_keys=True),
        targets=json.dumps(targets,ensure_ascii=False),basis_risk_flags=json.dumps(sorted(set(flags))),
        unrepresented_targets=json.dumps(unrepresented,ensure_ascii=False))
    return result


def main():
    rows=list(csv.DictReader((ROOT/'retail_items.csv').open()))
    mapped=[{**row,**map_etf_item(row)} for row in rows]
    with (ROOT/'etf_items.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(mapped[0]));writer.writeheader();writer.writerows(mapped)
    assert len(STOCK_TO_ETF)==153,len(STOCK_TO_ETF)
    assert set(STOCK_TO_ETF.values())<=set(UNIVERSE)
    assert all(t['symbol'] in UNIVERSE for row in mapped for t in json.loads(row['targets']))
    audit={'mapping_version':'fixed_17_etf_sector_attention_v1','new_specification_frozen_before_price_outcome_reads':True,
        'items':len(mapped),'fixed_universe':UNIVERSE,'static_stock_dictionary_count':len(STOCK_TO_ETF),
        'static_stock_dictionary':STOCK_TO_ETF,'specialist_etf_crosswalk':EXTRA_ETFS,
        'counts':dict(Counter(row['mapping_status'] for row in mapped)),
        'by_slot':{str(slot):dict(Counter(row['mapping_status'] for row in mapped if row['slot']==str(slot))) for slot in range(1,5)},
        'rules':dict(Counter(row['mapping_rule'] for row in mapped)),
        'basis_risk_flags':dict(Counter(flag for row in mapped for flag in json.loads(row['basis_risk_flags']))),
        'target_counts':dict(Counter(t['symbol'] for row in mapped for t in json.loads(row['targets']))),
        'source_hashes':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['retail_items.csv','map_retail.py','map_retail_etf.py']},
        'excluded':[{'report_date':row['report_date'],'slot':row['slot'],'heading':row['heading'],'reason':row['mapping_reason']} for row in mapped if row['mapping_status']!='mapped']}
    (ROOT/'etf_mapping_audit.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False))
    (ROOT/'etf_item_schema.json').write_text(json.dumps({
        'primary_key':['report_date','slot'],'source_only':'Only the item main heading and frozen title mapping; all bodies, other sections and price data excluded.',
        'claim_scope':'Returns on the fixed ETF sector-attention implementation; not returns on original stock/commodity/options/crypto trades.',
        'universe':UNIVERSE,'targets':'JSON list with symbol,direction (+1/-1),weight (equal across DISTINCT ETFs),proxy,source_target,rule.',
        'deduplication':'Multiple semiconductor names become one SOXX target; ticker count never increases conviction.',
        'basis_risk_flags':'Explicit source instrument to coarse sector/duration/energy-equity mismatch flags.',
        'unrepresented_targets':'Unmapped components remain unrepresented; no invented prices or unavailable ETF substitutions.',
        'mapping_status':'All original 892 rows retained, mapped or explicitly excluded.'},indent=2))
    print(json.dumps({k:audit[k] for k in ['items','static_stock_dictionary_count','counts','by_slot','target_counts']},indent=2))


if __name__=='__main__':main()
