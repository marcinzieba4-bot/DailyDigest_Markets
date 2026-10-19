import csv, json, glob, os, re, datetime as dt
W='/tmp/claude-0/-home-user/01233cf7-f758-5bad-b280-d38226412ca9/scratchpad/work'
def load(sym):
    return {r['Date']:float(r['Close']) for r in csv.DictReader(open(f'{W}/data/yf_{sym}.csv'))}
S={'usdpln':load('PLN_X'),'eurpln':load('EURPLN_X'),'epol_usd':load('EPOL'),'pko':load('PKO_WA'),'pekao':load('PEO_WA'),'orlen':load('PKN_WA'),
   'kghm':load('KGH_WA'),'pge':load('PGE_WA'),'allegro':load('ALE_WA'),'dino':load('DNP_WA'),'cdprojekt':load('CDR_WA'),'lpp':load('LPP_WA')}
def asof(series,d):
    ks=[k for k in sorted(series) if k<d]; return ks[-1], ks
def card(d):
    out={'report_date':d,'note':'All values are closes strictly before the report date (prior session). Percent changes are vs ~1 week (5 sessions) and ~4 weeks (20 sessions) earlier.'}
    for name,ser in S.items():
        k,ks=asof(ser,d); i=ks.index(k); v=ser[k]
        w1=ser[ks[max(0,i-5)]]; w4=ser[ks[max(0,i-20)]]
        dec=4 if 'pln' in name else 2
        out[name]={'date':k,'close':round(v,dec),'chg_1w_pct':round((v-w1)/w1*100,1),'chg_4w_pct':round((v-w4)/w4*100,1)}
    return out
for f in sorted(glob.glob(f'{W}/edited/*.html')):
    d=os.path.basename(f)[:-5]
    json.dump(card(d),open(f'{W}/pl/cards/{d}.json','w'),indent=1)
    s=open(f,encoding='utf-8').read()
    m=re.search(r'<div style="margin-bottom:24px;[^"]*">\s*<h3[^>]*>🇵🇱[^\n]*\n(?:.*?\n)*?</div>',s)
    open(f'{W}/pl/old/{d}.html','w',encoding='utf-8').write(m.group(0))
print(json.dumps(card('2026-08-01'),indent=1))
