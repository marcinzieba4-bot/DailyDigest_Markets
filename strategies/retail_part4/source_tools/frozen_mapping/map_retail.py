"""Freeze conservative title-only instruments and crowd direction for retail topics.

No market data or future return is read. A mapped name is a candidate, not proof
of historical listing, liquidity or a tradable fill. All original items survive
with a mapping or an explicit exclusion reason.
"""
from __future__ import annotations
import csv, datetime as dt, hashlib, json, re
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parent
STOP={"AI","EV","EVS","US","USA","EU","UK","IPO","IPOS","FOMO","YOLO","WTI","ETF","ETFS",
      "GTC","CEO","WWDC","CPI","PMI","PDT","NIM","USD","IRA","IRAS","HBM","DRAM","GPU","GPUS",
      "CPU","CPUS","MLP","MLPS","GC","GC_F","CL","CL_F","XAU","XAUUSD","HG","HG_F","L1","ERC",
      "SMR","SMRS","SK","VI","GLP","GLP-1","UFO","UAP","BTD","SaaS","ATH","LNG","TSX","TSXV",
      "NASDAQ","NVIDIA","NIO?","S","P","DTE","MAG","MAG7","S1","S-1","FUD","FX","NYSE","ADR","ADRS"}
ALIASES={"TSMC":"TSM","SPX":"SPY","NDX":"QQQ","BRK.B":"BRK-B","BTC.X":"BTC","ETH.X":"ETH","EMCOR":"EME"}
TOKEN_PROXY={
    "BTC":("IBIT",1,"bitcoin_to_listed_spot_etf"),"ETH":("ETHA",1,"ether_to_listed_spot_etf"),
    "SQQQ":("QQQ",-1,"inverse_3x_to_1x_underlying"),"TQQQ":("QQQ",1,"leveraged_3x_to_1x_underlying"),
    "SOXS":("SOXX",-1,"inverse_3x_to_1x_underlying"),"SOXL":("SOXX",1,"leveraged_3x_to_1x_underlying"),
    "DUST":("GDX",-1,"inverse_2x_to_1x_underlying"),"NUGT":("GDX",1,"leveraged_2x_to_1x_underlying"),
    "AGQ":("SLV",1,"leveraged_2x_to_1x_underlying"),"SCO":("USO",-1,"inverse_2x_to_1x_oil_proxy"),
    "GUSH":("XOP",1,"leveraged_2x_to_1x_underlying"),"DFEN":("ITA",1,"leveraged_3x_to_1x_underlying"),
    "TBT":("TLT",-1,"inverse_2x_to_1x_duration_proxy"),"TMV":("TLT",-1,"inverse_3x_to_1x_duration_proxy"),
}
UNSUPPORTED_CRYPTO={"SOL","SOLANA","XRP","XLM","SEI","COCK","DOGE","SHIB","SHIBA","PEPE","FLOKI","MERY",
    "SWFTC","ZBCN","KTA","TAO","BTT","ALGO","HBAR","ATOM","AAVE","XDC","TRUMP","MELANIA","FARTCOIN",
    "TROLL","TOES","JUGS","WOJAK","RAVE","CELL","QRL","TOSHI","MAULCOIN","BUTTCOIN","WEEDCOIN","UPDOG",
    "SOLPHIN","SPERMWHALE","ORCASM","DARTH","CHIP","WIF"}
PRIVATE_TOKENS={"SPCX","SPCX.X","SPACEX","SPACEX.X","ANT"}
CRYPTO_EQUITIES={"MSTR","COIN","CRCL","RIOT","MARA","CLSK","IREN","WULF","CIFR","HUT","BITF","BTDR",
    "BTBT","GLXY","HOOD","SOFI","NBIS","APLD","CRWV","IBIT","GBTC","FBTC","BITO","ETHA","ETHE"}
SPACE_PROXIES={"DXYZ","TSLA","ASTS","RKLB","LUNR","RDW","SPCE","VOYG","MNTS","WSPC","STCGF"}
# Exact company names identify named assets; they are not narrative theme proxies.
COMPANIES={r"\bnvidia\b":"NVDA",r"\bintel\b":"INTC",r"\bmicrosoft\b":"MSFT",r"\btesla\b":"TSLA",
    r"\bpalantir\b":"PLTR",r"\bmicron\b":"MU",r"\bsandisk\b":"SNDK",r"\bbroadcom\b":"AVGO",
    r"\bsuper\s*micro(?:computer)?\b":"SMCI",r"\bcoreweave\b":"CRWV",r"\bnebius\b":"NBIS",
    r"\bamazon\b":"AMZN",r"\bmeta\b":"META",r"\bapple\b":"AAPL",r"\boracle\b":"ORCL",
    r"\bblackberry\b":"BB",r"\brobinhood\b":"HOOD",r"\bsofi\b":"SOFI",r"\bgamestop\b":"GME",
    r"\bford\b":"F",r"\bnio\b":"NIO",r"\bnike\b":"NKE",r"\bwendy['’]?s\b":"WEN",
    r"\bpaypal\b":"PYPL",r"\btake[- ]two\b":"TTWO",r"\bberkshire\s+hathaway\b":"BRK-B",
    r"\breddit\b":"RDDT",r"\bcircle\s+internet\b":"CRCL",r"\btaiwan\s+semiconductor\b":"TSM",
    r"\bjpmorgan\b":"JPM",r"\bmoderna\b":"MRNA",r"\bmicrostrategy\b":"MSTR",
    r"\bemcor\b":"EME",r"\bge vernova\b":"GEV",r"\bquanta\b":"PWR",r"\bdigital realty\b":"DLR",
    r"\blumentum\b":"LITE",
}


def main_title(heading):
    value=heading.split('\xa0',1)[0].strip()
    # Quoted narrative taglines are not extra instruments or separate directions.
    # Leading quotation marks may be a descriptive title, so retain such titles.
    if value and value[0] not in ['"','“','‘']:
        value=re.split(r'["“]',value,maxsplit=1)[0].strip(' —–-/')
    return value


def direction_flags(title):
    cleaned=re.sub(r'(?i)short[- ](?:squeeze|term|interest)', '', title)
    cleaned=re.sub(r'(?i)high[- ]short[- ]interest', '', cleaned)
    negative=bool(re.search(r'(?i)\b(?:short|shorting|shorts|bearish|inverse|bear\s+bets|bear\s+bond)\b',cleaned))
    positive=bool(re.search(r'(?i)\b(?:long|longs|bullish)\b',cleaned))
    return negative,positive


def direct_tokens(title):
    output=[];excluded=[]
    crypto_context=bool(re.search(r'(?i)\b(?:crypto|bitcoin|ethereum|altcoin|memecoin|meme.coin|token|solana|defi|bittensor)\b',title))
    tokens=re.finditer(r'(?<![A-Za-z0-9])\$?([A-Z][A-Z0-9]*(?:[.\-_][A-Z0-9]+)*)\b',title)
    def non_target(start,end):
        before=title[:start];after=title[end:]
        return bool(re.search(r'(?i)(?:non[- ]|ex[- ]|beyond[- ]|anti[- ])$',before) or re.match(r'(?i)[- ]adjacent\b',after))
    for match in tokens:
        token=match.group(1)
        if non_target(match.start(1),match.end(1)):
            excluded.append({'token':token,'reason':'explicitly_excluded_or_adjacent_reference_not_target'});continue
        if ((token=='A' and re.match(r'(?i)[- ]shares',title[match.end(1):])) or
            (token=='CSI' and re.match(r'\s*300',title[match.end(1):])) or
            (token=='AST' and re.match(r'(?i)\s+SpaceMobile',title[match.end(1):])) or
            (token=='GTA' and re.match(r'\s+VI\b',title[match.end(1):]))):
            excluded.append({'token':token,'reason':'index_game_or_company_name_fragment_not_ticker'});continue
        if token in STOP:continue
        if token in PRIVATE_TOKENS or token.startswith('SPACEX'):
            excluded.append({'token':token,'reason':'private_or_unverifiable_spacex_anthropic_identifier'});continue
        if token.endswith('.X') and token not in ['BTC.X','ETH.X']:
            excluded.append({'token':token,'reason':'unsupported_crypto_token'});continue
        if token in UNSUPPORTED_CRYPTO:
            excluded.append({'token':token,'reason':'unsupported_crypto_or_ambiguous_identifier'});continue
        if token.endswith(('.TSX','.TSXV','.TO','.V','.HK')):
            excluded.append({'token':token,'reason':'foreign_listing_no_fixed_primary_mapping'});continue
        aliased='GEV' if token=='GE' and re.match(r'(?i)\s+Vernova',title[match.end(1):]) else ALIASES.get(token,token)
        if crypto_context and aliased not in CRYPTO_EQUITIES and aliased not in TOKEN_PROXY:
            excluded.append({'token':token,'reason':'crypto_context_not_an_approved_listed_crypto_equity_or_btc_eth'});continue
        if 1<=len(aliased)<=6 and re.fullmatch(r'[A-Z]+(?:-[A-Z])?',aliased):
            if not any(x[0]==aliased for x in output):output.append((aliased,token,'literal_title_ticker'))
    # Unambiguous full company names in titles may name the tradable asset even
    # when no ticker is printed. Do not use paragraph mentions for this expansion.
    for pattern,symbol in COMPANIES.items():
        match=re.search(pattern,title,re.I)
        if match and non_target(match.start(),match.end()):
            excluded.append({'token':match.group(),'reason':'explicitly_excluded_or_adjacent_reference_not_target'});continue
        if match and not any(x[0]==symbol for x in output):
            output.append((symbol,pattern,'exact_named_company'))
    return output,excluded


def theme_targets(title):
    t=title.lower()
    # Geographic specificity precedes the sector proxy: foreign chip themes
    # should not silently become a US technology exposure.
    geographic=[(r'\bsouth korea|\bkorean|\bsk hynix|\bsamsung','EWY','korea_theme'),
        (r'\bhong kong','EWH','hong_kong_theme'),(r'\bchina|\bchinese','FXI','china_theme'),
        (r'\bjapan|\bnikkei','EWJ','japan_theme'),(r'\bgerman','EWG','germany_theme'),
        (r'\bswiss','EWL','swiss_theme'),(r'\beurope|\beuropean','IEUR','europe_theme')]
    for pattern,symbol,rule in geographic:
        if re.search(pattern,t):return [(symbol,rule)]
    metals=[]
    for pattern,symbol,rule in [(r'\bgold\b','GLD','gold_theme'),(r'\bsilver\b','SLV','silver_theme'),(r'\bcopper\b','CPER','copper_theme')]:
        if re.search(pattern,t):metals.append((symbol,rule))
    if metals:return metals
    if re.search(r'\bbitcoin\b',t):return [('IBIT','bitcoin_to_listed_spot_etf')]
    if re.search(r'\bethereum\b|\bether\b',t):return [('ETHA','ether_to_listed_spot_etf')]
    if re.search(r'\bbond|\btreasur',t):
        return [('TLT' if re.search(r'long[- ]duration|long[- ]term|20.year|30.year',t) else 'IEF','duration_theme')]
    if re.search(r'\boil\b|\bwti\b|\bcrude\b|\benergy\b',t):
        if re.search(r'\bnuclear|\buranium|\bsmr\b',t):return [('URA','nuclear_uranium_theme')]
        return [('XLE','energy_equity_theme')] if re.search(r'\bstocks|\bequit|\bmajors|\bproducers|\brefiners|\binfrastructure',t) else [('USO','oil_wti_theme')]
    themes=[(r'\bsemiconductor|\bsemis\b|\bchip|\bmemory\b|\btsmc\b','SOXX','semiconductor_theme'),
        (r'\bsoftware|\bsaas\b|\benterprise ai','IGV','software_theme'),
        (r'\brussell|\bsmall[- ]caps?\b|\bsmall caps?\b|\bsmall-cap value','IWM','russell_small_caps_theme'),
        (r'\b(?:s&p|sp500|s & p)|\bbroad (?:u\.s\.|market|index)|\bvti\b','SPY','broad_us_equity_theme'),
        (r'\bdata ?center|\bphysical buildout','SRVR','data_centers_theme'),
        (r'\bdefen[cs]e|\baerospace','ITA','defense_theme'),
        (r'\bbiotech|\bbiopharma|\bpharma|\bglp-1|weight.loss','XBI','biotech_theme'),
        (r'\bnuclear|\buranium|\bsmr\b','URA','nuclear_uranium_theme'),
        (r'\bquantum\b','QTUM','quantum_theme'),(r'\brobotic|\brobotaxi|\bautonomous|\blidar','BOTZ','robotics_theme'),
        (r'\butilit','XLU','utilities_theme'),(r'\bcannabis','MSOS','cannabis_theme'),
        (r'\bfintech','ARKF','fintech_theme'),(r'\bhomebuild|\bhousing','XHB','homebuilders_theme'),
        (r'\bbank|\bfinancials','KBE','bank_theme'),
        (r'\bquality|\bdefensive|\bdefensives|recession.proof','USMV','quality_defensive_equity_theme'),
        (r'\bnasdaq|\bmega.cap|\bmag ?7|\bbig.tech|\bai\b','QQQ','broad_ai_nasdaq_theme')]
    for pattern,symbol,rule in themes:
        if re.search(pattern,t):return [(symbol,rule)]
    return []


def map_item(item):
    title=main_title(item['heading']);negative,positive=direction_flags(title)
    candidates,unsupported=direct_tokens(title)
    mapped=[]
    result={'main_title':title,'mapping_status':'unmapped','mapping_rule':'','mapping_reason':'',
        'crowd_direction':'','mapped_symbols':'','mapped_directions':'{}','targets':'[]',
        'unsupported_tokens':json.dumps(unsupported,ensure_ascii=False)}
    def reject(reason,rule='conservative_exclusion'):
        result.update(mapping_rule=rule,mapping_reason=reason);return result
    if re.search(r'(?i)\b(?:options?|calls?|puts?|0dte|zero.days.to.expiration|theta)\b',title):
        return reject('Options or option-linked heading; no historical option payoffs or underlying-direction substitute fabricated.','options_exclusion')
    if re.search(r'(?i)\b(?:oil|wti|crude)\b',title) and {x[0] for x in candidates}&{'UAL','DAL','AAL','JETS'}:
        return reject('Oil heading lists airline fuel-cost references; crowd instrument/direction cannot be identified safely.','conflicting_instrument_context')
    inverse=[x for x in candidates if x[0] in TOKEN_PROXY and TOKEN_PROXY[x[0]][1]<0]
    if negative and positive and not inverse:
        return reject('Heading combines long and short legs without a single unambiguous underlying exposure.','mixed_direction_exclusion')
    if re.search(r'(?i)\bvs\.?\b|\bversus\b|\bdivergence\b|pick.winner|dump.loser',title) and not inverse:
        return reject('Relative or divergent legs cannot safely be represented as a same-direction basket.','relative_leg_exclusion')
    if re.search(r'(?i)spacex|starlink|anthropic|pre[- ]ipo|private (?:market|secondary)',title):
        if re.search(r'(?i)rotation|\bsell\b|\bdump\b',title):
            return reject('Rotation between a private IPO and listed names has ambiguous target roles.','private_ipo_rotation_exclusion')
        proxies=[x for x in candidates if x[0] in SPACE_PROXIES]
        if not proxies:
            return reject('Private/pre-IPO narrative without an explicitly named supported listed proxy.','private_ipo_exclusion')
        candidates=proxies
    if re.search(r'(?i)\bIPOs?\b',title) and not candidates:
        return reject('IPO wave without an explicitly named historically listed instrument.','private_ipo_exclusion')
    if re.search(r'(?i)skepticism|bubble.pop|reappraisal|anxiety|awareness|\bwatch\b|stalled.but.stalked|crash.preparation|stock.market.crash.preparation|bond.vigilante|fiscal.doom',title) and not negative and not re.search(r'(?i)buy|dip|long|bullish|rotation',title):
        return reject('Narrative concern or watch posture lacks an explicit actionable crowd direction.','direction_ambiguity_exclusion')
    if re.search(r'(?i)\bcash\b|cash.is.king|volatility|\bvol\b|prediction.market|kalshi|rate.hike.speculation|election.trades|election.positioning',title) and not candidates:
        return reject('Cash, volatility, event positioning or private prediction market without a specified tradable directional asset.','nondirectional_exclusion')
    if not candidates and any(x['reason']=='explicitly_excluded_or_adjacent_reference_not_target' for x in unsupported):
        return reject('Only an excluded or adjacent company is named; a broad proxy would reintroduce that name.','non_target_reference_exclusion')
    if not candidates and re.search(r'(?i)geopolitical event|summit|ceasefire|peace deal|election trades|election positioning',title) and not re.search(r'(?i)stocks|equities|bonds|treasur|gold|silver|oil|crude|bitcoin|ether|nasdaq|russell|semiconductor',title):
        return reject('Event or summit reference does not identify the asset being traded.','nondirectional_event_exclusion')
    direction=-1 if negative else 1
    if candidates:
        for symbol,token,rule in candidates:
            if symbol in TOKEN_PROXY:
                underlying,proxy_direction,proxy_rule=TOKEN_PROXY[symbol]
                crowd=proxy_direction if symbol not in ['BTC','ETH'] else direction
                mapped.append({'symbol':underlying,'direction':crowd,'proxy':True,'original_token':token,'rule':proxy_rule})
            else:mapped.append({'symbol':symbol,'direction':direction,'proxy':False,'original_token':token,'rule':rule})
        rule='explicit_title_instruments'
    else:
        # Unsupported crypto is not silently transformed into an equity sector.
        if re.search(r'(?i)crypto|altcoin|meme.coin|solana|bittensor|defi|\bxrp\b|\bxlm\b|\bdoge\b',title) and not re.search(r'(?i)bitcoin|ethereum|\bbtc\b|\beth\b',title):
            return reject('No supported Bitcoin/Ether or explicitly named listed crypto-equity instrument.','unsupported_crypto_exclusion')
        for symbol,theme_rule in theme_targets(title):
            mapped.append({'symbol':symbol,'direction':direction,'proxy':True,'original_token':title,'rule':theme_rule})
        rule='fixed_heading_theme_proxy'
    dedup={}
    for target in mapped:
        if target['symbol'] in dedup and dedup[target['symbol']]['direction']!=target['direction']:
            return reject('Opposite directions resolve to the same underlying; no net position inferred.','conflicting_resolved_directions')
        dedup.setdefault(target['symbol'],target)
    mapped=list(dedup.values())
    if not mapped:return reject('No unambiguous named instrument or approved fixed heading-theme proxy.','no_mapping')
    if len({x['direction'] for x in mapped})>1:
        return reject('Mixed long/short basket is not reduced to a single crowd direction.','mixed_resolved_basket_exclusion')
    for target in mapped:target['weight']=1/len(mapped)
    result.update(mapping_status='mapped',mapping_rule=rule,
        mapping_reason='Only main heading instruments; equal weights across distinct resolved targets. Candidate listing/liquidity eligibility is checked separately using lagged information.',
        crowd_direction=str(mapped[0]['direction']),mapped_symbols='|'.join(x['symbol'] for x in mapped),
        mapped_directions=json.dumps({x['symbol']:x['direction'] for x in mapped},sort_keys=True),
        targets=json.dumps(mapped,ensure_ascii=False))
    return result


def main():
    rows=list(csv.DictReader((ROOT/'retail_items.csv').open()))
    mapped=[{**row,**map_item(row)} for row in rows]
    with (ROOT/'mapped_items.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(mapped[0]));writer.writeheader();writer.writerows(mapped)
    symbols=sorted({target['symbol'] for row in mapped for target in json.loads(row['targets'])})
    audit={'mapping_version':'1.0-title-only-fixed-proxies','mapping_frozen_before_price_outcome_reads':True,
        'input_sha256':hashlib.sha256((ROOT/'retail_items.csv').read_bytes()).hexdigest(),
        'items':len(mapped),'mapping_status_counts':dict(Counter(row['mapping_status'] for row in mapped)),
        'rule_counts':dict(Counter(row['mapping_rule'] for row in mapped)),
        'by_slot':{str(slot):dict(Counter(row['mapping_status'] for row in mapped if row['slot']==str(slot))) for slot in range(1,5)},
        'candidate_symbols':symbols,'candidate_symbol_count':len(symbols),
        'mapped_is_not_market_eligibility':True,
        'unsupported_tokens':dict(Counter(x['token'] for row in mapped for x in json.loads(row['unsupported_tokens']))),
        'fixed_token_proxies':TOKEN_PROXY,'exact_company_aliases':COMPANIES,
        'stopwords':sorted(STOP),'unsupported_crypto':sorted(UNSUPPORTED_CRYPTO),
        'title_only_rule':'Main heading before NBSP; quoted trailing narrative is removed. Body, smart-money fields and invalidation paragraphs do not influence mapping.',
        'exclusions':[{'report_date':row['report_date'],'slot':row['slot'],'heading':row['heading'],'reason':row['mapping_reason']} for row in mapped if row['mapping_status']!='mapped']}
    (ROOT/'mapping_audit.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False))
    (ROOT/'universe.json').write_text(json.dumps({'symbols':symbols,'mapping_version':audit['mapping_version'],
        'candidate_only':True,'no_price_or_return_reads':True},indent=2))
    print(json.dumps({k:audit[k] for k in ['items','mapping_status_counts','rule_counts','by_slot','candidate_symbol_count']},indent=2))


if __name__=='__main__':main()
