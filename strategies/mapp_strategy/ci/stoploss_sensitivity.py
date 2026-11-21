"""Stop-loss sensitivity for the fixed 25% unhedged mapp_strategy (separate diagnostic).

Reads a completed `extended-history` run directory and re-simulates the `unhedged25` book with a
per-ETF stop-loss overlay at -5%, -8% and -10%, under two daily-bar execution conventions:

  intraday  a resting stop order. On a held day, if the adjusted open already gaps through the
            stop the leg is sold at that open; otherwise, if the adjusted low touches the stop, it
            is sold at the stop price. The entry day counts (entry is at the open, so that day's
            low occurs after the fill).
  close     if a completed adjusted close is at or through the stop, the leg is sold at the next
            session's adjusted open.

Everything else is the frozen strategy: same 55 baskets and entry dates, 25% of opening equity,
fixed units, 10 bp per order, ten-session/21-day time exit, no hedge, zero cash yield. A stopped
basket keeps its reserved window: no new basket starts before the original scheduled exit plus
the two-session cooldown, so every variant trades the same signal schedule.

Prices come from the frozen `engine/data.py` helper (read-only); the economic simulator
`engine/run_nohedge.py` is neither imported nor modified. With stops disabled, this simulator must reproduce
the engine's unhedged25 daily NAV exactly, and its risk statistics must match the published
fixed-25% report; both checks are asserted before any stop result is written.

Usage (from strategies/mapp_strategy, after `python mapp_strategy.py extended-history ...`):
    python ci/stoploss_sensitivity.py --root <completed run dir> --out backtests/2022_2026_stoploss_sensitivity
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

STRATEGY_ID = "mapp_strategy"
FEE = 0.001
ALLOCATION = 0.25
CAPITAL = 100_000.0
STOPS = [0.05, 0.08, 0.10]
MODES = ["intraday", "close"]
REFERENCE_METRICS = "backtests/2022_2026_no_gaps_fixed25/risk_metrics.json"


# ----------------------------------------------------------------------------------------------
# Inputs
# ----------------------------------------------------------------------------------------------
def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_inputs(root: Path):
    sys.path.insert(0, str(root / "engine"))
    import data as helper  # frozen completed-bar helper; read-only use

    prices = helper.Data(root)
    prepared = json.loads((root / "inputs/main_archive_replay_prepared.json").read_text())
    cohorts = prepared["cohorts"]["etf_own"]
    days = [d for d in prices.days if prepared["start"] <= d <= prepared["end"]]

    # Adjusted lows/highs from the same raw Yahoo campaign, scaled exactly like the adjusted open.
    low, high = {}, {}
    for path in sorted((root / "market/raw").glob("*.json")):
        result = json.loads(path.read_text())["chart"]["result"][0]
        symbol = result["meta"]["symbol"].upper()
        quote = result["indicators"]["quote"][0]
        adjclose = result["indicators"]["adjclose"][0]["adjclose"]
        for i, stamp in enumerate(result["timestamp"]):
            day = dt.datetime.fromtimestamp(stamp, dt.timezone.utc).astimezone(helper.NY).date().isoformat()
            row = prices.rows.get(symbol, {}).get(day)
            if row is None or quote["low"][i] is None:
                continue
            factor = adjclose[i] / quote["close"][i]
            low[symbol, day] = quote["low"][i] * factor
            high[symbol, day] = quote["high"][i] * factor
            assert low[symbol, day] <= min(row["adjusted_open"], row["adjclose"]) * (1 + 1e-9), (symbol, day)
            assert high[symbol, day] >= max(row["adjusted_open"], row["adjclose"]) * (1 - 1e-9), (symbol, day)
    return prices, cohorts, days, low, high


# ----------------------------------------------------------------------------------------------
# Simulation
# ----------------------------------------------------------------------------------------------
def simulate(prices, cohorts, days, low, high, stop=None, mode="intraday"):
    entries = {c["entry_date"]: c for c in cohorts}
    cash = 1.0
    legs: list[dict] = []
    basket = None
    daily, baskets = [], []
    previous_nav = 1.0

    def nav(day, kind):
        return cash + sum(l["qty"] * prices.p(l["symbol"], day, kind) for l in legs if l["open"])

    def sell(leg, day, price, reason):
        nonlocal cash
        fee = abs(leg["qty"] * price) * FEE
        cash += leg["qty"] * price - fee
        leg.update(open=False, exit_date=day, exit_price=price, exit_fee=fee, exit_reason=reason)

    for day in days:
        # 1) Opening: pending close-triggered stops, gap-through stops, then the scheduled time exit.
        if basket:
            for leg in legs:
                if not leg["open"]:
                    continue
                opening = prices.p(leg["symbol"], day, "open")
                if leg.get("pending"):
                    sell(leg, day, opening, "stop_close_next_open")
                elif day == basket["exit_date"]:
                    sell(leg, day, opening, "time_limit")
                elif (mode == "intraday" and stop and day != basket["entry_date"]
                      and (opening - leg["stop"]) * leg["direction"] <= 0):
                    sell(leg, day, opening, "stop_gap_open")
            if day == basket["exit_date"]:
                baskets.append(close_basket(basket, legs))
                basket, legs = None, []
        if day in entries:
            assert basket is None
            cohort = entries[day]
            opening_nav = nav(day, "open")
            for ref in cohort["legs"]:
                price = prices.p(ref["symbol"], day)
                direction = int(ref["direction"])
                notional = opening_nav * ALLOCATION * float(ref["weight"]) / (1 + FEE)
                qty = direction * notional / price
                fee = notional * FEE
                cash -= qty * price + fee
                legs.append(dict(symbol=ref["symbol"], direction=direction, qty=qty, entry_price=price,
                                 entry_notional=notional, entry_fee=fee, open=True,
                                 stop=price * (1 - stop * direction) if stop else None))
            basket = dict(cohort, entry_nav=opening_nav)
        # 2) Intraday: a resting stop touched by the session low (high for a short).
        if basket and stop and mode == "intraday" and day != basket["exit_date"]:
            for leg in legs:
                if leg["open"]:
                    extreme = low[leg["symbol"], day] if leg["direction"] > 0 else high[leg["symbol"], day]
                    if (extreme - leg["stop"]) * leg["direction"] <= 0:
                        sell(leg, day, leg["stop"], "stop_intraday")
        # 3) Close-based trigger, executed at the next opening.
        if basket and stop and mode == "close":
            for leg in legs:
                if (leg["open"] and not leg.get("pending")
                        and (prices.p(leg["symbol"], day, "close") - leg["stop"]) * leg["direction"] <= 0):
                    leg["pending"] = True
        close_nav = nav(day, "close")
        daily.append(dict(date=day, nav=close_nav, daily_return=close_nav / previous_nav - 1))
        previous_nav = close_nav
    assert basket is None, "A basket remained open at the endpoint"
    return daily, baskets


def close_basket(basket, legs):
    gross = sum(l["qty"] * (l["exit_price"] - l["entry_price"]) for l in legs)
    fees = sum(l["entry_fee"] + l["exit_fee"] for l in legs)
    stopped = [l for l in legs if l["exit_reason"].startswith("stop")]
    return dict(
        basket_id=basket["basket_id"], report_date=basket["report_date"], entry_date=basket["entry_date"],
        scheduled_exit_date=basket["exit_date"],
        actual_exit_date=max(l["exit_date"] for l in legs),
        stop_exit_date=min((l["exit_date"] for l in stopped), default=""),
        exit_reasons="|".join(sorted({l["exit_reason"] for l in legs})),
        positions="|".join(("Long " if l["direction"] > 0 else "Short ") + l["symbol"] for l in legs),
        entry_prices="|".join(f"{l['symbol']}={l['entry_price']:.6f}" for l in legs),
        exit_prices="|".join(f"{l['symbol']}={l['exit_price']:.6f}" for l in legs),
        stop_prices="|".join(f"{l['symbol']}={l['stop']:.6f}" for l in legs if l["stop"]),
        entry_nav=basket["entry_nav"], entry_notional=sum(l["entry_notional"] for l in legs),
        gross=gross, fees=fees, net=gross - fees, stopped=bool(stopped),
        basket_return=sum(l["direction"] * (l["exit_price"] / l["entry_price"] - 1) for l in legs) / len(legs),
    )


# ----------------------------------------------------------------------------------------------
# Risk statistics (definitions identical to the published fixed-25% report)
# ----------------------------------------------------------------------------------------------
def recovery_episodes(daily):
    peak, peak_index, episodes, current = 1.0, None, [], None
    for i, row in enumerate(daily):
        value = row["nav"]
        if current is None:
            if value >= peak:
                peak, peak_index = value, i
            else:
                current = dict(peak_index=peak_index if peak_index is not None else i, first_under=i,
                               trough_index=i, trough=value, peak=peak)
        else:
            if value < current["trough"]:
                current.update(trough=value, trough_index=i)
            if value > peak:
                current["recovery_index"] = i
                episodes.append(current)
                current = None
                peak, peak_index = value, i
    if current is not None:
        episodes.append(current)
    dates = [r["date"] for r in daily]
    out = []
    for e in episodes:
        start = dt.date.fromisoformat(dates[e["peak_index"]])
        end_index = e.get("recovery_index")
        stop_index = end_index if end_index is not None else len(daily) - 1
        out.append(dict(
            peak_date=dates[e["peak_index"]], trough_date=dates[e["trough_index"]],
            recovery_date=dates[end_index] if end_index is not None else None, recovered=end_index is not None,
            calendar_days=(dt.date.fromisoformat(dates[stop_index]) - start).days,
            sessions=stop_index - e["peak_index"], drawdown_pct=(1 - e["trough"] / e["peak"]) * 100))
    return out


def tail(returns, level):
    """Empirical (linearly interpolated) loss quantile; shortfall averages losses at or beyond it."""
    losses = -np.asarray(returns)
    var = float(np.quantile(losses, level))
    beyond = losses[losses >= var]
    return dict(loss_var_pct=var * 100, mean_tail_loss_pct=float(beyond.mean() * 100), tail_sessions=int(beyond.size))


def risk_metrics(daily, baskets):
    values = np.array([1.0] + [r["nav"] for r in daily])
    returns = np.array([r["daily_return"] for r in daily])
    first, last = dt.date.fromisoformat(daily[0]["date"]), dt.date.fromisoformat(daily[-1]["date"])
    years = (last - first).days / 365.25
    cagr = values[-1] ** (1 / years) - 1
    drawdown = values / np.maximum.accumulate(values) - 1
    vol = returns.std(ddof=1) * math.sqrt(252)
    downside = math.sqrt(float(np.mean(np.minimum(returns, 0) ** 2))) * math.sqrt(252)
    nets = [b["net"] * CAPITAL for b in baskets]
    winners, losers = [x for x in nets if x > 0], [x for x in nets if x < 0]
    streak = best_streak = 0
    for x in nets:
        streak = streak + 1 if x < 0 else 0
        best_streak = max(best_streak, streak)
    episodes = recovery_episodes(daily)
    done = [e for e in episodes if e["recovered"]]
    worst = min(baskets, key=lambda b: b["net"])
    best = max(baskets, key=lambda b: b["net"])
    worst_day = int(np.argmin(returns))
    trough = int(np.argmin(drawdown))
    return dict(
        ending_nav_usd=values[-1] * CAPITAL, net_pnl_usd=(values[-1] - 1) * CAPITAL,
        total_net_return_pct=(values[-1] - 1) * 100, cagr_pct=cagr * 100,
        annualized_daily_volatility_pct=vol * 100, annualized_downside_deviation_pct=downside * 100,
        sharpe_zero_rate=returns.mean() / returns.std(ddof=1) * math.sqrt(252),
        sortino_zero_target=returns.mean() * 252 / downside,
        calmar=cagr / abs(drawdown.min()),
        max_drawdown_pct=float(drawdown.min() * 100), max_drawdown_trough_date=daily[trough - 1]["date"] if trough else None,
        worst_session=dict(date=daily[worst_day]["date"], return_pct=float(returns[worst_day] * 100)),
        empirical_daily_95=tail(returns, 0.95), empirical_daily_99=tail(returns, 0.99),
        basket_count=len(baskets), stopped_baskets=sum(b["stopped"] for b in baskets),
        winners=len(winners), losers=len(losers), win_rate_pct=len(winners) / len(nets) * 100,
        profit_factor=sum(winners) / -sum(losers),
        average_winner_net_usd=float(np.mean(winners)), average_loser_net_usd=float(np.mean(losers)),
        worst_basket=dict(entry_date=worst["entry_date"], positions=worst["positions"], net_pnl_usd=worst["net"] * CAPITAL,
                          basket_return_pct=worst["basket_return"] * 100),
        best_basket=dict(entry_date=best["entry_date"], positions=best["positions"], net_pnl_usd=best["net"] * CAPITAL,
                         basket_return_pct=best["basket_return"] * 100),
        worst_basket_return_pct=min(b["basket_return"] for b in baskets) * 100,
        longest_losing_streak_baskets=best_streak,
        transaction_cost_usd=sum(b["fees"] for b in baskets) * CAPITAL,
        recovery=dict(completed_episodes=len(done), median_calendar_days=float(np.median([e["calendar_days"] for e in done])),
                      p90_calendar_days=float(np.percentile([e["calendar_days"] for e in done], 90)),
                      max_calendar_days=max(e["calendar_days"] for e in done),
                      sessions_below_high=int(sum(r["nav"] < m for r, m in zip(daily, np.maximum.accumulate(values)[1:])))),
    )


def year_windows(daily):
    rows, anchor, by_year = [], 1.0, {}
    for r in daily:
        by_year.setdefault(r["date"][:4], []).append(r["nav"])
    for year, navs in by_year.items():
        path = np.array([anchor] + navs)
        rows.append(dict(year=year, return_pct=(navs[-1] / anchor - 1) * 100,
                         within_year_max_drawdown_pct=float((path / np.maximum.accumulate(path) - 1).min() * 100)))
        anchor = navs[-1]
    return rows


def check_reference(metrics, root_reference: Path):
    """The no-stop book must reproduce the published fixed-25% risk statistics."""
    if not root_reference.exists():
        print("reference risk metrics not found; skipping published-statistics identity check")
        return "skipped"
    ref = json.loads(root_reference.read_text())
    pairs = [
        ("total_net_return_pct", ref["total_net_return_pct"]), ("cagr_pct", ref["cagr_pct"]),
        ("annualized_daily_volatility_pct", ref["annualized_daily_volatility_pct"]),
        ("annualized_downside_deviation_pct", ref["annualized_downside_deviation_pct"]),
        ("sharpe_zero_rate", ref["sharpe_zero_rate"]), ("sortino_zero_target", ref["sortino_zero_target"]),
        ("calmar", ref["calmar"]), ("max_drawdown_pct", ref["max_drawdown_pct"]),
        ("win_rate_pct", ref["win_rate_pct"]), ("profit_factor", ref["profit_factor"]),
        ("transaction_cost_usd", ref["transaction_cost_usd"]),
    ]
    for key, wanted in pairs:
        assert math.isclose(metrics[key], wanted, rel_tol=2e-4, abs_tol=2e-4), (key, metrics[key], wanted)
    for level in ["empirical_daily_95", "empirical_daily_99"]:
        for key in ["loss_var_pct", "mean_tail_loss_pct", "tail_sessions"]:
            assert math.isclose(metrics[level][key], ref[level][key], rel_tol=2e-4, abs_tol=2e-4), (level, key)
    rec, wanted = metrics["recovery"], ref["above_prior_high_recovery"]
    for key in ["completed_episodes", "median_calendar_days", "p90_calendar_days", "max_calendar_days", "sessions_below_high"]:
        assert rec[key] == wanted[key], (key, rec[key], wanted[key])
    return "passed"


# ----------------------------------------------------------------------------------------------
# Charts
# ----------------------------------------------------------------------------------------------
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
SERIES = {None: INK, 0.05: "#2a78d6", 0.08: "#eb6834", 0.10: "#1baf7a"}


def label_of(stop):
    return "No stop" if stop is None else f"−{int(round(stop * 100))}% stop"


def spread_labels(values, gap):
    order = sorted(range(len(values)), key=lambda i: values[i])
    placed = list(values)
    for a, b in zip(order, order[1:]):
        if placed[b] - placed[a] < gap:
            placed[b] = placed[a] + gap
    return placed


def plot_pnl(books, path: Path, start_label: str, end_label: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.edgecolor": AXIS, "axes.labelcolor": INK2,
                         "xtick.color": INK2, "ytick.color": INK2})
    fig, axes = plt.subplots(2, 2, figsize=(15.5, 8.8), dpi=150, sharex=True,
                             gridspec_kw=dict(height_ratios=[2.1, 1], hspace=0.16, wspace=0.52))
    fig.patch.set_facecolor(SURFACE)
    fig.text(0.055, 0.955, "Stop-loss test: no stop vs −5%, −8%, −10%", fontsize=19, fontweight="bold", color=INK)
    fig.text(0.055, 0.918, f"Fixed 25% unhedged mapp_strategy  ·  same 55 baskets  ·  {start_label} to {end_label}  ·  $100,000 start",
             fontsize=11, color=INK2)
    titles = {"intraday": "Resting stop order (fills at stop, or at the open on a gap)",
              "close": "Stop on daily close (sells at the next open)"}
    for col, mode in enumerate(MODES):
        top, bottom = axes[0][col], axes[1][col]
        variants = [(None, books[(None, "none")])] + [(s, books[(s, mode)]) for s in STOPS]
        finals = []
        for stop, (daily, _) in reversed(variants):
            dates = [dt.date.fromisoformat(r["date"]) for r in daily]
            pnl = np.array([r["nav"] - 1 for r in daily]) * CAPITAL
            values = np.array([1.0] + [r["nav"] for r in daily])
            dd = (values / np.maximum.accumulate(values) - 1)[1:] * 100
            width = 1.5 if stop is None else 1.8
            top.plot(dates, pnl, color=SERIES[stop], lw=width, solid_joinstyle="round", zorder=4 if stop is None else 3)
            bottom.plot(dates, dd, color=SERIES[stop], lw=width * 0.85, zorder=4 if stop is None else 3)
            finals.append((stop, dates[-1], pnl[-1], (values[-1] - 1) * 100))
        positions = spread_labels([f[2] for f in finals], 2300)
        label_x = dt.date.fromisoformat(days_end(books)) + dt.timedelta(days=40)
        for (stop, day, value, pct), y in zip(finals, positions):
            top.scatter([day], [value], s=28, color=SERIES[stop], zorder=5, edgecolor=SURFACE, linewidth=1.2)
            top.scatter([label_x], [y], s=34, marker="s", color=SERIES[stop], clip_on=False, zorder=5)
            sign = "+" if pct >= 0 else "−"
            top.text(label_x + dt.timedelta(days=30), y, f"{label_of(stop)}  {sign}{abs(pct):.2f}%",
                     fontsize=9.8, color=INK, va="center", clip_on=False)
        top.set_title(titles[mode], loc="left", fontsize=12.5, color=INK, fontweight="bold", pad=10)
        if mode == "close":
            top.text(dt.date(2022, 2, 1), 27500, "−8% and −10% lines coincide: both cut only\nSOXX Aug 2024 before its scheduled exit",
                     fontsize=9.2, color=INK2, va="top")
        top.set_ylim(-6000, 30000)
        top.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
            lambda v, _: "$0" if v == 0 else ("−" if v < 0 else "") + f"${abs(v) / 1000:.0f}k"))
        bottom.set_ylim(-6.6, 0.4)
        bottom.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: ("−" if v < 0 else "") + f"{abs(v):.0f}%"))
        top.set_ylabel("Net P&L (USD)", fontsize=10.5)
        bottom.set_ylabel("Drawdown from high", fontsize=10.5)
        for ax in (top, bottom):
            ax.set_facecolor(SURFACE)
            ax.grid(axis="y", color=GRID, lw=0.8)
            ax.axhline(0, color=AXIS, lw=0.9, zorder=1)
            for side in ["top", "right", "left"]:
                ax.spines[side].set_visible(False)
            ax.tick_params(axis="both", length=0, labelsize=9.5)
            ax.set_xlim(dt.date(2021, 12, 15), dt.date(2026, 12, 20))
        bottom.xaxis.set_major_locator(mdates.YearLocator())
        bottom.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    handles = [plt.Line2D([], [], color=SERIES[s], lw=2.2) for s in [None] + STOPS]
    fig.legend(handles, [label_of(s) for s in [None] + STOPS], loc="upper right", bbox_to_anchor=(0.985, 0.975),
               ncol=4, frameon=False, fontsize=10.5, handlelength=1.8, labelcolor=INK)
    fig.text(0.055, 0.025, "Daily closing marks, net of 10 bp per order. Each stop sits a fixed percentage below the ETF's entry price. "
             "A stopped basket keeps its reserved window, so all variants trade the same signals.", fontsize=9.2, color=MUTED)
    fig.subplots_adjust(left=0.06, right=0.845, top=0.85, bottom=0.085)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def days_end(books):
    return books[(None, "none")][0][-1]["date"]


def plot_excursions(rows, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11.5, 7.4), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    fig.text(0.075, 0.94, "Most deep dips recovered before the time exit", fontsize=18, fontweight="bold", color=INK)
    fig.text(0.075, 0.903, "Each dot is one ETF position (56 across 55 baskets): its lowest intraday price while held vs. its "
             "return at the normal ten-session exit", fontsize=10.8, color=INK2)
    x = np.array([r["worst_intraday_vs_entry_pct"] for r in rows])
    y = np.array([r["return_at_time_exit_pct"] for r in rows])
    deep = x <= -5
    for level, name in [(-5, "−5% stop"), (-8, "−8% stop"), (-10, "−10% stop")]:
        ax.axvline(level, color=AXIS, lw=1.0, zorder=1)
        ax.text(level + 0.08, 9.3, name, fontsize=9.5, color=INK2, va="top")
    ax.axhline(0, color=AXIS, lw=0.9, zorder=1)
    ax.scatter(x[~deep], y[~deep], s=46, color="#c3c2b7", edgecolor=SURFACE, linewidth=1.5, zorder=3,
               label="Never fell 5% below entry (49 positions)")
    ax.scatter(x[deep], y[deep], s=64, color="#2a78d6", edgecolor=SURFACE, linewidth=1.5, zorder=4,
               label="Fell 5% or more below entry (7 positions)")
    offsets = {"SOXX 2024-08": (8, 9), "XLY 2022-01": (-10, 10), "GLD 2026-11": (10, -4), "XLY 2025-04": (10, 5),
               "XLK 2023-09": (-12, -16), "SOXX 2024-01": (8, -24), "XLK 2023-10": (-10, 8)}
    for r, xi, yi in zip(rows, x, y):
        if xi <= -5:
            key = f"{r['symbol']} {r['entry_date'][:7]}"
            dx, dy = offsets.get(key, (8, 6))
            sign = "+" if yi >= 0 else "−"
            ax.annotate(f"{r['symbol']} {dt.date.fromisoformat(r['entry_date']).strftime('%b %Y')}: {sign}{abs(yi):.1f}% at exit",
                        xy=(xi, yi), xytext=(dx, dy), textcoords="offset points", fontsize=9.2, color=INK,
                        ha="right" if dx < 0 else "left", va="center")
    ax.set_xlim(-12, 3)
    ax.set_ylim(-13, 10)
    ax.set_xlabel("Lowest intraday price while held, vs. entry", fontsize=10.5, color=INK2)
    ax.set_ylabel("Return at the normal time exit", fontsize=10.5, color=INK2)
    pct = matplotlib.ticker.FuncFormatter(lambda v, _: ("−" if v < 0 else "+" if v > 0 else "") + f"{abs(v):.0f}%")
    ax.xaxis.set_major_formatter(pct)
    ax.yaxis.set_major_formatter(pct)
    ax.grid(color=GRID, lw=0.7)
    for side in ["top", "right", "left", "bottom"]:
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0, labelsize=9.5, colors=INK2)
    ax.legend(loc="lower right", frameon=False, fontsize=10, labelcolor=INK)
    fig.text(0.075, 0.03, "A stop only helps a position that keeps falling after crossing the line. Five of the seven deep dips "
             "ended above −5%; two (XLY Jan 2022, GLD Nov 2026) kept falling.", fontsize=9.2, color=MUTED)
    fig.subplots_adjust(left=0.09, right=0.97, top=0.86, bottom=0.12)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


# ----------------------------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------------------------
def write_csv(path: Path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, required=True, help="Completed extended-history run directory")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "backtests/2022_2026_stoploss_sensitivity")
    args = parser.parse_args()
    root, out = args.root.resolve(), args.out.resolve()
    (out / "figures").mkdir(parents=True, exist_ok=True)
    prices, cohorts, days, low, high = load_inputs(root)

    books = {(None, "none"): simulate(prices, cohorts, days, low, high)}
    engine = list(csv.DictReader((root / "results/archive_replay_unhedged25_daily.csv").open()))
    base_daily = books[(None, "none")][0]
    assert [r["date"] for r in engine] == [r["date"] for r in base_daily]
    nav_error = max(abs(float(a["nav"]) - b["nav"]) for a, b in zip(engine, base_daily))
    assert nav_error < 1e-10, nav_error
    for mode in MODES:
        for stop in STOPS:
            books[(stop, mode)] = simulate(prices, cohorts, days, low, high, stop, mode)

    metrics, years, trades, stopped, nav_rows = {}, [], [], [], {}
    base_by_entry = {b["entry_date"]: b for b in books[(None, "none")][1]}
    for (stop, mode), (daily, baskets) in books.items():
        key = "none" if stop is None else f"{mode}_{int(round(stop * 100))}"
        metrics[key] = dict(stop_pct=None if stop is None else -stop * 100, execution=mode, **risk_metrics(daily, baskets))
        metrics[key]["stopped_baskets_net_change_vs_holding_usd"] = sum(
            (b["net"] - base_by_entry[b["entry_date"]]["net"]) * CAPITAL for b in baskets if b["stopped"])
        for y in year_windows(daily):
            years.append(dict(variant=key, **y))
        for b in baskets:
            trades.append(dict(strategy_id=STRATEGY_ID, variant=key, stop_pct=metrics[key]["stop_pct"], execution=mode,
                               **{k: v for k, v in b.items() if k not in ["entry_nav", "entry_notional", "gross", "fees", "net"]},
                               equity_before_entry_usd=b["entry_nav"] * CAPITAL, entry_notional_usd=b["entry_notional"] * CAPITAL,
                               gross_pnl_usd=b["gross"] * CAPITAL, transaction_cost_usd=b["fees"] * CAPITAL,
                               net_pnl_usd=b["net"] * CAPITAL, net_account_return_pct=b["net"] / b["entry_nav"] * 100))
            if b["stopped"]:
                held = base_by_entry[b["entry_date"]]
                stopped.append(dict(variant=key, stop_pct=-stop * 100, execution=mode, positions=b["positions"],
                                    entry_date=b["entry_date"], stop_exit_date=b["stop_exit_date"],
                                    scheduled_exit_date=b["scheduled_exit_date"], exit_reasons=b["exit_reasons"],
                                    basket_return_with_stop_pct=b["basket_return"] * 100,
                                    basket_return_if_held_pct=held["basket_return"] * 100,
                                    net_pnl_with_stop_usd=b["net"] * CAPITAL, net_pnl_if_held_usd=held["net"] * CAPITAL,
                                    stop_effect_usd=(b["net"] - held["net"]) * CAPITAL))
        for r in daily:
            nav_rows.setdefault(r["date"], {"date": r["date"]})[f"{key}_nav_usd"] = r["nav"] * CAPITAL

    identity = check_reference(metrics["none"], Path(__file__).resolve().parents[1] / REFERENCE_METRICS)

    excursions = []
    for c in cohorts:
        start, end = prices.index[c["entry_date"]], prices.index[c["exit_date"]]
        for leg in c["legs"]:
            entry = prices.p(leg["symbol"], c["entry_date"])
            lows = [low[leg["symbol"], d] for d in prices.days[start:end]]
            excursions.append(dict(entry_date=c["entry_date"], exit_date=c["exit_date"], symbol=leg["symbol"],
                                   direction=int(leg["direction"]),
                                   worst_intraday_vs_entry_pct=(min(lows) / entry - 1) * 100,
                                   worst_close_vs_entry_pct=(min(prices.p(leg["symbol"], d, "close") for d in prices.days[start:end]) / entry - 1) * 100,
                                   return_at_time_exit_pct=(prices.p(leg["symbol"], c["exit_date"]) / entry - 1) * 100))
    assert all(e["direction"] == 1 for e in excursions), "Excursion chart assumes long legs"

    write_csv(out / "metrics.csv", [dict(variant=k, **{m: v for m, v in row.items() if not isinstance(v, dict)}) for k, row in metrics.items()])
    write_csv(out / "calendar_year_returns.csv", years)
    write_csv(out / "trades.csv", trades)
    write_csv(out / "stopped_trades.csv", stopped)
    write_csv(out / "daily_nav.csv", list(nav_rows.values()))
    write_csv(out / "position_excursions.csv", excursions)
    (out / "risk_metrics.json").write_text(json.dumps(dict(
        strategy_id=STRATEGY_ID, schedule="absolute_reserved", policy="unhedged25", constant_basket_budget_fraction=ALLOCATION,
        first_session=days[0], last_session=days[-1], market_sessions=len(days), baskets=len(cohorts),
        stop_levels_pct=[-s * 100 for s in STOPS], executions=MODES,
        checks=dict(no_stop_daily_nav_max_abs_error=nav_error, published_fixed25_statistics_identity=identity),
        variants=metrics,
        input_sha256={p: sha(root / p) for p in ["prices.csv", "inputs/main_archive_replay_prepared.json",
                                                 "results/archive_replay_unhedged25_daily.csv"]},
    ), indent=2, allow_nan=False) + "\n")
    plot_pnl(books, out / "figures/stoploss_pnl_drawdown.png",
             dt.date.fromisoformat(days[0]).strftime("%-d %b %Y"), dt.date.fromisoformat(days[-1]).strftime("%-d %b %Y"))
    plot_excursions(excursions, out / "figures/position_excursions.png")

    print(f"no-stop reproduction: max NAV error {nav_error:.1e}; published statistics identity: {identity}")
    print(f"{'variant':12} {'return':>8} {'maxDD':>7} {'Sharpe':>6} {'stops':>5} {'effect':>9}")
    for key, m in metrics.items():
        print(f"{key:12} {m['total_net_return_pct']:+7.2f}% {m['max_drawdown_pct']:6.2f}% {m['sharpe_zero_rate']:6.2f} "
              f"{m['stopped_baskets']:5d} {m['stopped_baskets_net_change_vs_holding_usd']:+9.0f}")


if __name__ == "__main__":
    main()
