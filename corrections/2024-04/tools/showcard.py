"""showcard.py <date> [--grep REGEX] — the date's market card (../cards/<date>.json) as a compact table for the writers.

One line per instrument: ticker | name | session of the last completed close | close | 1-session / 5-session /
20-session change (%) | the close 20 sessions earlier (session). VIX also shows point changes. Order follows the
download universe (indices, commodities, crypto, Poland, Europe, Asia, ETFs, single stocks). --grep filters on
ticker or name. Every number printed here still needs the correct instrument, session, horizon and unit; the Treasury block is printed first."""
import argparse, json, os, re
from verify import validate_date

T = os.path.dirname(os.path.abspath(__file__)); C = os.path.dirname(T)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('date');parser.add_argument('--grep')
    args=parser.parse_args();d=args.date;validate_date(d)
    rx=re.compile(args.grep,re.I) if args.grep else None
    card = json.load(open(os.path.join(C, 'cards', f'{d}.json')))
    if card.get('report_date')!=d or card.get('cutoff_utc')!=d+'T00:00:00Z': raise ValueError('Own-card identity/cutoff mismatch')
    t = card['treasury']
    if t['prior_close_date']>=d or any(m['session']>=d for m in card['markets'].values()): raise ValueError('Card contains a session on/after cutoff')
    print(f"MARKET CARD {card['report_date']} ({card['label']}) — every value is a completed observation before the cutoff")
    print(f"US Treasury par curve, prior close {t['prior_close_date']}: " +
          ', '.join(f'{k.upper()} {v}' for k, v in t['prior_close_pct'].items()))
    print(f"  10Y-2Y {t['spread_10y_2y_bps']:+d} bps | 10Y-3M {t['spread_10y_3m_bps']:+d} bps | 30Y-10Y {t['spread_30y_10y_bps']:+d} bps")
    print(f"  20 observations (from {t['obs20_earlier_date']}): 2Y {t['chg_20obs_bps']['2y']:+d} bps (was {t['obs20_earlier_pct']['2y']}), "
          f"10Y {t['chg_20obs_bps']['10y']:+d} bps (was {t['obs20_earlier_pct']['10y']}), spread {t['chg_20obs_bps']['spread']:+d} bps, "
          f"3M {t['chg_20obs_bps']['3m']:+d} bps, 30Y {t['chg_20obs_bps']['30y']:+d} bps")
    print(f"  5 observations (from {t['prior_5obs_date']}): 2Y {t['chg_5obs_bps']['2y']:+d} bps, 10Y {t['chg_5obs_bps']['10y']:+d} bps")
    print(f"  curve shape: {t['curve_shape']} | 20-observation move: {t['curve_move_20obs']}")
    print()
    print('ticker | name | completed session | close | 1s % (from session) | 5s % (from session) | 20s % | close 20 sessions earlier (session)')
    mk = card['markets']
    order = list(mk)
    n = 0
    for tk in order:
        m = mk[tk]
        if tk.endswith('=X'): continue
        if rx and not (rx.search(tk) or rx.search(m['name'])):
            continue
        extra = f" | VIX pts: 1s {m['chg_1s_pts']:+.2f}, 20s {m['chg_20s_pts']:+.2f}" if 'chg_1s_pts' in m else ''
        if m.get('level_restriction'):
            extra += ' | Level withheld: ' + m['level_restriction']
        if m.get('reference_share_units_differ'):
            extra += ' | Reference warning: ' + m['reference_level_note']
        if m.get('history_limitation'):
            extra += ' | ' + m['history_limitation']
        level = m['close'] if m['close'] is not None else 'withheld'
        reference = m['ref_20s_close'] if m['ref_20s_close'] is not None else ('unavailable' if m.get('history_limitation') else 'withheld')
        change20 = f"{m['chg_20s_pct']:+.2f}" if m['chg_20s_pct'] is not None else 'unavailable'
        change1 = f"{m['chg_1s_pct']:+.2f}" if m['chg_1s_pct'] is not None else 'unavailable'
        change5 = f"{m['chg_5s_pct']:+.2f}" if m['chg_5s_pct'] is not None else 'unavailable'
        fallback_unit = 'index points' if tk.startswith('^') or tk in {'DX-Y.NYB', '000001.SS'} else m['currency']
        cur = ' ' + (m.get('level_unit') or fallback_unit)
        reference_units = cur if m['ref_20s_close'] is not None else ''
        from1 = m.get('ref_1s_session') or 'unavailable'
        from5 = m.get('ref_5s_session') or 'unavailable'
        print(f"{tk} | {m['name']} | {m['session']} | {level}{cur} | {change1} ({from1}) | {change5} ({from5}) | "
              f"{change20} | {reference}{reference_units} ({m['ref_20s_session'] or 'unavailable'}){extra}")
        n += 1
    print(f'-- {n} instruments')


if __name__ == '__main__':
    main()
