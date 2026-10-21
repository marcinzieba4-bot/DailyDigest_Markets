"""card_yield.py <date> <report.html> — the US-Treasury ground-truth card, same logic as corrections/2026-10-19/cards.py:
official Treasury par closes up to the last business day BEFORE the date, the live 10Y the report quotes, 4-week bps moves."""
import sys, re, csv, json, datetime as dt
sys.path.insert(0, '/home/user/DailyDigest_Markets/corrections/2026-10-19')
from totext import totext
W = '/tmp/claude-0/-home-user-DailyDigest-Markets/350e9aa9-be2b-5699-b30e-16c2be0713f3/scratchpad/d0624/work/data'
T = {}
for r in csv.DictReader(open(f'{W}/treasury_2026.csv')):
    m, d_, y = r['Date'].split('/'); T[f'{y}-{m}-{d_}'] = {'3m': float(r['3 Mo']), '2y': float(r['2 Yr']), '5y': float(r['5 Yr']), '10y': float(r['10 Yr']), '30y': float(r['30 Yr'])}
TK = sorted(T)
def yf(sym): return {r['Date']: float(r['Close']) for r in csv.DictReader(open(f'{W}/yf_{sym}.csv'))}
Y = {'TNX': yf('TNX'), 'IRX': yf('IRX')}
def asof(series, date):
    best = None
    for k in sorted(series):
        if k <= date: best = k
        else: break
    return best, series[best]
KW = re.compile(r'(yield|10Y|2Y|two-year|ten-year|bps|basis point|curve|steepen|flatten|invert|front[- ]end|short[- ]end|long[- ]end|Treasur|NIM|term premium|duration)', re.I)
def label_move(c2, c10):
    if abs(c2) < 4 and abs(c10) < 4: return 'little changed'
    if c10 >= c2 and c10 > 0: return 'bear steepening (both up, 10Y up more)' if c2 > 0 else 'steepening (10Y up, 2Y down/flat)'
    if c10 < c2 and c2 > 0: return 'bear flattening (both up, 2Y up more)' if c10 > 0 else 'flattening (2Y up, 10Y down/flat)'
    if c10 <= c2 and c10 < 0: return 'bull flattening (both down, 10Y down more)' if c2 < 0 else 'flattening (10Y down, 2Y up/flat)'
    if c2 < c10 and c2 < 0: return 'bull steepening (both down, 2Y down more)' if c10 < 0 else 'steepening (2Y down, 10Y up/flat)'
    return 'mixed'
def steep_label(sp):
    if sp < 0: return 'INVERTED'
    if sp < 25: return 'positive but very flat'
    if sp < 60: return 'positively sloped but still flat by historical standards (long-run average roughly +90 to +100 bps)'
    if sp < 100: return 'moderately steep, approaching the long-run average'
    return 'steep'
d, f = sys.argv[1], sys.argv[2]
t = totext(open(f, encoding='utf-8').read())
m = re.search(r'10Y(?: yield| Yield| Treasury)?[^.\d]{0,25}?(\d\.\d\d)\s*%', t)
rep10 = float(m.group(1)) if m else None
kT, _ = asof(Y['TNX'], d); keysT = sorted(Y['TNX']); refT = keysT[max(0, keysT.index(kT) - 20)]; ref10 = Y['TNX'][refT]
live10 = rep10 if rep10 else round(Y['TNX'][kT], 2)
P = max(k for k in TK if k < d); P4 = TK[max(0, TK.index(P) - 20)]; c = T[P]; c4 = T[P4]
sp = round((c['10y'] - c['2y']) * 100); sp4 = round((c4['10y'] - c4['2y']) * 100)
chg2 = round((c['2y'] - c4['2y']) * 100); chg10o = round((c['10y'] - c4['10y']) * 100)
m2 = sorted(set(re.findall(r'\b2Y[^.\d]{0,40}?(\d\.\d\d)\s*%', t)))
kI, irx = asof(Y['IRX'], d)
sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', t) if KW.search(s)]
print(json.dumps(dict(
    report_date=d, weekday=dt.date.fromisoformat(d).strftime('%A'),
    live_10y_reading_in_report=live10, live_10y_session=kT,
    live_10y_change_vs_4w_bps=round((live10 - ref10) * 100), live_10y_4w_ago_value=round(ref10, 2), live_10y_4w_ago_date=refT,
    prior_official_close_date=P,
    prior_close={'3m_bill': c['3m'], '2y': c['2y'], '5y': c['5y'], '10y': c['10y'], '30y': c['30y'], 'spread_10y_2y_bps': sp, 'spread_10y_3m_bps': round((c['10y'] - c['3m']) * 100), 'spread_30y_10y_bps': round((c['30y'] - c['10y']) * 100)},
    four_weeks_before_prior_close={'date': P4, '2y': c4['2y'], '10y': c4['10y'], 'spread_10y_2y_bps': sp4},
    change_vs_4w_at_prior_close={'2y_bps': chg2, '10y_bps': chg10o, 'spread_10y_2y_bps': sp - sp4, 'curve_move': label_move(chg2, chg10o)},
    curve_shape_label=steep_label(sp),
    wrong_2y_values_in_report_actually_13w_tbill=m2, tbill_13w_live=round(irx, 2),
    flagged_sentences=sents), indent=1, ensure_ascii=False))
