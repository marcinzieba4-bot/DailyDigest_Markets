"""showcard.py <date> [--grep REGEX] — the date's market card (../cards/<date>.json) as a compact table for the writers.

One line per instrument: ticker | name | session of the last completed close | close | 1-session / 5-session /
20-session change (%) | the close 20 sessions earlier (session). VIX also shows point changes. Order follows the
download universe (indices, commodities, crypto, FX, Poland, Europe, Asia, ETFs, single stocks). --grep filters on
ticker or name. Every number printed here is a number you may use; the Treasury block is printed first."""
import json, os, re, sys, importlib.util

T = os.path.dirname(os.path.abspath(__file__)); C = os.path.dirname(T)


def universe():
    spec = importlib.util.spec_from_file_location('fm', os.path.join(T, 'fetch_market.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m.UNIVERSE


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    d = args[0]
    rx = None
    if '--grep' in sys.argv:
        rx = re.compile(sys.argv[sys.argv.index('--grep') + 1], re.I)
        args = [a for a in args if a != sys.argv[sys.argv.index('--grep') + 1]]
    card = json.load(open(os.path.join(C, 'cards', f'{d}.json')))
    t = card['treasury']
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
    print('ticker | name | session | close | 1s % | 5s % | 20s % | close 20 sessions earlier (session)')
    mk = card['markets']
    order = [u for u in universe() if u in mk] + [u for u in mk if u not in set(universe())]
    n = 0
    for tk in order:
        m = mk[tk]
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
        cur = '' if tk.startswith('^') or tk.endswith('=X') else ' ' + m['currency']
        print(f"{tk} | {m['name']} | {m['session']} | {level}{cur} | {m['chg_1s_pct']:+.2f} | {m['chg_5s_pct']:+.2f} | "
              f"{change20} | {reference} ({m['ref_20s_session'] or 'unavailable'}){extra}")
        n += 1
    print(f'-- {n} instruments')


if __name__ == '__main__':
    main()
