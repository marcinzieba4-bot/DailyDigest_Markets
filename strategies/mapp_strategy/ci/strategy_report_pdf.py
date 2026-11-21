"""Build the mapp_strategy PDF report: strategy logic, risk statistics and charts.

Reads only the published fixed-25% ledgers in backtests/2022_2026_no_gaps_fixed25 (daily equity, trades,
risk metrics) and writes four charts plus mapp_strategy_report.pdf into that folder. No simulation is run.

Needs matplotlib, the Inter font, Node.js and the Playwright package with its Chromium browser:
    python ci/strategy_report_pdf.py
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "backtests/2022_2026_no_gaps_fixed25"
FIG = DATA / "figures"
PDF = DATA / "mapp_strategy_report.pdf"

INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#ffffff"
POS, NEG, MID = "#2a78d6", "#e34948", "#f0efec"   # diverging pair: gains blue, losses red, neutral gray


# ----------------------------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------------------------
def load():
    metrics = json.loads((DATA / "risk_metrics.json").read_text())
    daily = list(csv.DictReader((DATA / "daily_nav.csv").open()))
    trades = list(csv.DictReader((DATA / "trades.csv").open()))
    for r in daily:
        for k in ["nav_usd", "daily_return", "drawdown", "gross_exposure_close", "spy_daily_total_return"]:
            r[k] = float(r[k])
    for t in trades:
        for k in ["net_pnl_usd", "net_account_return_pct", "net_basket_return_pct", "gross_pnl_usd", "transaction_cost_usd"]:
            t[k] = float(t[k])
    return metrics, daily, trades


def spy_benchmark(daily):
    """SPY total return from the first session's close to the last close (same window as the account)."""
    r = np.array([row["spy_daily_total_return"] for row in daily[1:]])
    eq = np.cumprod(1 + r)
    years = (dt.date.fromisoformat(daily[-1]["date"]) - dt.date.fromisoformat(daily[0]["date"])).days / 365.25
    dd = eq / np.maximum.accumulate(np.r_[1.0, eq])[1:] - 1
    return dict(total=(eq[-1] - 1) * 100, cagr=(eq[-1] ** (1 / years) - 1) * 100, vol=r.std(ddof=1) * 252 ** 0.5 * 100,
                maxdd=dd.min() * 100, sharpe=r.mean() / r.std(ddof=1) * 252 ** 0.5)


def monthly_returns(daily):
    month_end = {}
    for row in daily:
        month_end[row["date"][:7]] = row["nav_usd"]
    out, prev = {}, 100_000.0
    for m in sorted(month_end):
        out[m] = (month_end[m] / prev - 1) * 100
        prev = month_end[m]
    return out


# ----------------------------------------------------------------------------------------------
# Charts
# ----------------------------------------------------------------------------------------------
def style():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "Inter", "font.size": 9, "axes.edgecolor": AXIS, "axes.labelcolor": INK2,
                         "xtick.color": INK2, "ytick.color": INK2, "axes.unicode_minus": True})
    return plt


def money(v, _=None):
    if v == 0:
        return "$0"
    return ("−" if v < 0 else "") + (f"${abs(v) / 1000:.0f}k" if abs(v) >= 1000 else f"${abs(v):.0f}")


def pct(v, _=None, digits=0):
    if round(abs(v), digits) == 0:
        return f"{0:.{digits}f}%"
    return ("−" if v < 0 else "+" if v > 0 else "") + f"{abs(v):.{digits}f}%"


def clean(ax, grid_axis="y"):
    ax.set_facecolor(SURFACE)
    ax.grid(axis=grid_axis, color=GRID, lw=0.7)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0, labelsize=8.5)


def chart_equity(daily, metrics, path):
    plt = style()
    import matplotlib.dates as mdates
    import matplotlib.ticker as mt
    dates = [dt.date.fromisoformat(r["date"]) for r in daily]
    pnl = np.array([r["nav_usd"] for r in daily]) - 100_000
    dd = np.array([r["drawdown"] for r in daily]) * 100
    fig, (top, bot) = plt.subplots(2, 1, figsize=(8, 6.3), dpi=220, sharex=True, gridspec_kw=dict(height_ratios=[2.2, 1], hspace=0.12))
    fig.patch.set_facecolor(SURFACE)
    top.plot(dates, pnl, color=POS, lw=1.6, solid_joinstyle="round")
    top.scatter([dates[-1]], [pnl[-1]], s=22, color=POS, zorder=5, edgecolor=SURFACE, linewidth=1.1)
    top.annotate(f"${pnl[-1]:,.0f}", (dates[-1], pnl[-1]), xytext=(7, 0), textcoords="offset points", va="center", fontsize=9, color=INK, fontweight="semibold")
    peak = int(np.argmax(pnl))
    top.annotate(f"High ${pnl[peak]:,.0f}\n{dates[peak]:%d %b %Y}", (dates[peak], pnl[peak]), xytext=(-8, 6), textcoords="offset points",
                 ha="right", va="bottom", fontsize=7.8, color=INK2)
    top.axhline(0, color=AXIS, lw=0.8)
    top.yaxis.set_major_formatter(mt.FuncFormatter(money))
    top.set_title("Net P&L (USD), $100,000 start", loc="left", fontsize=9.5, color=INK, fontweight="semibold", pad=6)
    bot.fill_between(dates, dd, 0, color=NEG, alpha=0.14, lw=0)
    bot.plot(dates, dd, color=NEG, lw=1.0)
    worst = int(np.argmin(dd))
    bot.annotate(f"{pct(dd[worst], digits=2)}\nmax", (dates[worst], dd[worst]), xytext=(7, 0), textcoords="offset points",
                 ha="left", va="center", fontsize=7.8, color=INK)
    rec = metrics["above_prior_high_recovery"]["five_longest_completed"][0]
    a, b = dt.date.fromisoformat(rec["peak_date"]), dt.date.fromisoformat(rec["recovery_date"])
    bot.annotate("", xy=(a, -3.15), xytext=(b, -3.15), arrowprops=dict(arrowstyle="|-|", color=INK2, lw=0.8, mutation_scale=2.5))
    bot.text(a + (b - a) / 2, -3.35, f"longest recovery: {rec['calendar_days']} days", ha="center", va="top", fontsize=7.5, color=INK2)
    bot.set_ylim(-4.3, 0.3)
    bot.yaxis.set_major_formatter(mt.FuncFormatter(lambda v, _: pct(v)))
    bot.set_title("Drawdown from the running equity high", loc="left", fontsize=9.5, color=INK, fontweight="semibold", pad=6)
    for ax in (top, bot):
        clean(ax)
        ax.set_xlim(dates[0] - dt.timedelta(days=10), dates[-1] + dt.timedelta(days=12))
    bot.set_xticks([dt.date(y, 1, 1) for y in range(dates[0].year, dates[-1].year + 1)])
    bot.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.subplots_adjust(left=0.085, right=0.89, top=0.94, bottom=0.06)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def chart_monthly(monthly, path):
    plt = style()
    from matplotlib.colors import LinearSegmentedColormap, to_rgb
    years = sorted({m[:4] for m in monthly})
    grid = np.full((len(years), 12), np.nan)
    for m, v in monthly.items():
        grid[years.index(m[:4]), int(m[5:]) - 1] = v
    yearly = []
    for y in years:
        vals = [v for m, v in monthly.items() if m.startswith(y)]
        yearly.append((np.prod([1 + v / 100 for v in vals]) - 1) * 100)
    cmap = LinearSegmentedColormap.from_list("div", [NEG, MID, POS])
    lim = 3.0
    fig, ax = plt.subplots(figsize=(8, 2.75), dpi=220)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for i in range(len(years)):
        for j in range(13):
            v = grid[i, j] if j < 12 else yearly[i]
            if np.isnan(v):
                continue
            x = j if j < 12 else 12.35
            color = cmap((np.clip(v, -lim, lim) + lim) / (2 * lim)) if j < 12 else MID
            ax.add_patch(plt.Rectangle((x + 0.04, i + 0.06), 0.92, 0.88, color=color, lw=0))
            lum = np.dot(to_rgb(color), [0.2126, 0.7152, 0.0722])
            ax.text(x + 0.5, i + 0.5, pct(v, digits=1), ha="center", va="center", fontsize=7.4,
                    color="#ffffff" if lum < 0.45 else INK, fontweight="semibold" if j == 12 else "normal")
    ax.set_xlim(0, 13.35)
    ax.set_ylim(len(years), 0)
    ax.set_xticks([j + 0.5 for j in range(12)] + [12.85])
    ax.set_xticklabels([dt.date(2000, j + 1, 1).strftime("%b") for j in range(12)] + ["Year"], fontsize=8.2)
    ax.set_yticks([i + 0.5 for i in range(len(years))])
    ax.set_yticklabels(years, fontsize=8.2)
    ax.xaxis.tick_top()
    ax.tick_params(length=0, colors=INK2)
    for side in ax.spines.values():
        side.set_visible(False)
    fig.subplots_adjust(left=0.065, right=0.995, top=0.88, bottom=0.02)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def chart_trades(trades, path):
    plt = style()
    import matplotlib.ticker as mt
    pnl = np.array([t["net_pnl_usd"] for t in trades])
    x = np.arange(1, len(trades) + 1)
    fig, ax = plt.subplots(figsize=(8, 3.0), dpi=220)
    fig.patch.set_facecolor(SURFACE)
    ax.bar(x, pnl, width=0.72, color=[POS if v > 0 else NEG for v in pnl], lw=0)
    ax.axhline(0, color=AXIS, lw=0.8)
    for idx, side in [(int(np.argmax(pnl)), 1), (int(np.argmin(pnl)), -1)]:
        t = trades[idx]
        sign = "+" if pnl[idx] > 0 else "−"
        label = f"{t['funded_positions'].replace('Long ', '')} {dt.date.fromisoformat(t['entry_date']):%b %Y}\n{sign}${abs(pnl[idx]):,.0f}"
        ax.annotate(label, (x[idx], pnl[idx]), xytext=(-8, 0), textcoords="offset points", ha="right", va="center", fontsize=7.6, color=INK)
    starts = {}
    for i, t in enumerate(trades, 1):
        starts.setdefault(t["entry_date"][:4], i)
    for y, i in starts.items():
        ax.axvline(i - 0.5, color=GRID, lw=0.8, zorder=0)
    ax.set_xticks([i - 0.5 for i in starts.values()])
    ax.set_xticklabels(list(starts), ha="left", fontsize=8.2)
    ax.set_ylim(-4300, 5200)
    ax.set_xlim(0.2, len(trades) + 0.8)
    ax.yaxis.set_major_formatter(mt.FuncFormatter(money))
    ax.set_xlabel("Trades in entry order, grouped by entry year", fontsize=8.2)
    clean(ax)
    ax.grid(axis="x", visible=False)
    fig.subplots_adjust(left=0.085, right=0.99, top=0.97, bottom=0.15)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def chart_etfs(trades, path):
    plt = style()
    import matplotlib.ticker as mt
    pnl, count, wins = defaultdict(float), defaultdict(int), defaultdict(int)
    for t in trades:
        key = t["funded_positions"].replace("Long ", "").replace(", ", " + ").replace("|", " + ")
        pnl[key] += t["net_pnl_usd"]; count[key] += 1; wins[key] += t["net_pnl_usd"] > 0
    keys = sorted(pnl, key=lambda k: pnl[k])
    fig, ax = plt.subplots(figsize=(8, 3.3), dpi=220)
    fig.patch.set_facecolor(SURFACE)
    y = np.arange(len(keys))
    vals = [pnl[k] for k in keys]
    ax.barh(y, vals, height=0.66, color=[POS if v > 0 else NEG for v in vals], lw=0)
    for yi, k, v in zip(y, keys, vals):
        sign = "+" if v > 0 else "−"
        ax.text(v + (180 if v >= 0 else -180), yi, f"{sign}${abs(v):,.0f}", va="center", ha="left" if v >= 0 else "right", fontsize=7.8, color=INK)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{k}  ({count[k]} trade{'s' if count[k] > 1 else ''}, {wins[k]} won)" for k in keys], fontsize=8)
    ax.axvline(0, color=AXIS, lw=0.8)
    ax.set_xlim(min(vals) - 1500, max(vals) + 1800)
    ax.xaxis.set_major_formatter(mt.FuncFormatter(money))
    clean(ax, grid_axis="x")
    fig.subplots_adjust(left=0.27, right=0.99, top=0.98, bottom=0.08)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return pnl, count


# ----------------------------------------------------------------------------------------------
# HTML and PDF
# ----------------------------------------------------------------------------------------------
def fmt_money(v, sign=False):
    s = f"${abs(v):,.0f}"
    if v < 0:
        return "−" + s
    return ("+" if sign else "") + s


def fmt_pct(v, digits=2, sign=True):
    if v < 0:
        return f"−{abs(v):.{digits}f}%"
    return ("+" if sign and v > 0 else "") + f"{v:.{digits}f}%"


def row(label, value, note=""):
    return f"<tr><td>{label}</td><td class=num>{value}</td>{f'<td class=note>{note}</td>' if note is not None else ''}</tr>"


def build_html(metrics, daily, trades, spy, etf_pnl, etf_count, figs):
    m = metrics
    rec = m["above_prior_high_recovery"]
    first, last = dt.date.fromisoformat(m["first_session"]), dt.date.fromisoformat(m["last_session"])
    yr_2026 = next(y for y in m["year_windows"] if y["year"] == 2026)
    top3 = sorted(etf_pnl, key=lambda k: -etf_pnl[k])[:3]
    top3_share = sum(etf_pnl[k] for k in top3) / m["net_pnl_usd"] * 100
    hold_days = [int(t["holding_calendar_days"]) for t in trades]
    tiles = [("Net return", fmt_pct(m["total_net_return_pct"]), f"$100,000 → {fmt_money(m['ending_nav_usd'])}"),
             ("Annual growth (CAGR)", fmt_pct(m["cagr_pct"]), f"over {(last - first).days / 365.25:.1f} years"),
             ("Max drawdown", fmt_pct(m["max_drawdown_pct"]), "closing equity"),
             ("Sharpe ratio", f"{m['sharpe_zero_rate']:.2f}", f"Sortino {m['sortino_zero_target']:.2f}"),
             ("Win rate", f"{m['win_rate_pct']:.0f}%", f"{m['winners']} of {m['basket_count']} trades"),
             ("Avg. invested", f"{m['average_close_gross_exposure_pct']:.0f}%", "of equity, daily close")]
    tile_html = "".join(f'<div class=tile><div class=k>{k}</div><div class=v>{v}</div><div class=s>{s}</div></div>' for k, v, s in tiles)

    flow = [("1", "Daily report", "Part 4 theme of <i>What Retail Is Playing</i>"),
            ("2", "Map to ETF", "Fixed 17-ETF universe"),
            ("3", "Checks", "Liquidity, then 20-day trend"),
            ("4", "Buy at open", "25% of equity"),
            ("5", "Hold", "10 trading sessions"),
            ("6", "Sell at open", "then wait 1 session")]
    flow_html = '<div class=flow>' + '<div class=arrow>→</div>'.join(
        f'<div class=step><div class=n>{n}</div><div class=t>{t}</div><div class=d>{d}</div></div>' for n, t, d in flow) + '</div>'

    years_rows = "".join(
        f"<tr><td>{y['year'] if y['year'] != 2026 else '2026 (to 20 Nov)'}</td><td class=num>{fmt_pct(y['net_return_pct'])}</td>"
        f"<td class=num>{fmt_money(y['net_pnl_usd'], True)}</td><td class=num>{y['annualized_volatility_pct']:.2f}%</td>"
        f"<td class=num>{fmt_pct(y['within_year_max_drawdown_pct'])}</td><td class=num>{y['funded_baskets_by_entry']}</td></tr>"
        for y in m["year_windows"])

    longest = rec["five_longest_completed"]
    rec_rows = "".join(f"<tr><td>{e['peak_date']}</td><td>{e['trough_date']}</td><td>{e['recovery_date']}</td>"
                       f"<td class=num>{e['calendar_days']} days</td><td class=num>{fmt_pct(-e['drawdown_pct'])}</td></tr>" for e in longest[:3])
    open_dd = rec["unfinished"]

    css = """
@page { size: A4; margin: 15mm 15mm 16mm 15mm; }
:root { --ink:#0b0b0b; --ink2:#52514e; --muted:#898781; --rule:#e1e0d9; --wash:#f4f3ef; --link:#1c5cab; --accent:#2a78d6; }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { margin:0; color:var(--ink); font-family:Inter, system-ui, sans-serif; font-size:9.2pt; line-height:1.47;
       font-variant-ligatures:no-contextual; font-feature-settings:"calt" 0; }
li::marker { font-variant-numeric:normal; }
.kicker { font-size:7.8pt; letter-spacing:.07em; text-transform:uppercase; color:var(--accent); font-weight:600; margin-bottom:3pt; }
h1 { font-size:22pt; line-height:1.12; margin:0 0 4pt; font-weight:700; letter-spacing:-.015em; }
.meta { color:var(--ink2); font-size:8.8pt; }
.tiles { display:grid; grid-template-columns:repeat(6,1fr); gap:6pt; margin:11pt 0 10pt; }
.tile { background:var(--wash); border-radius:6pt; padding:7pt 8pt; }
.tile .k { font-size:7pt; color:var(--ink2); }
.tile .v { font-size:14.5pt; font-weight:600; margin:1pt 0; letter-spacing:-.01em; }
.tile .s { font-size:6.9pt; color:var(--muted); }
h2 { font-size:13pt; margin:14pt 0 6pt; padding-top:8pt; border-top:1px solid var(--rule); break-after:avoid; }
h2.first { border-top:none; padding-top:0; margin-top:6pt; }
h3 { font-size:10pt; margin:10pt 0 4pt; break-after:avoid; }
p { margin:0 0 6.5pt; }
ol { margin:0 0 8pt; padding-left:15pt; }
li { margin:0 0 4pt; }
strong { font-weight:600; }
figure { margin:4pt 0 8pt; break-inside:avoid; }
figure img { width:100%; display:block; }
figcaption { font-size:7.8pt; color:var(--muted); margin-top:3pt; }
.flow { display:flex; align-items:stretch; gap:3pt; margin:6pt 0 10pt; }
.step { flex:1; background:var(--wash); border-radius:6pt; padding:6pt 7pt; }
.step .n { font-size:7pt; color:var(--accent); font-weight:700; }
.step .t { font-size:8.6pt; font-weight:600; margin:1pt 0; }
.step .d { font-size:7.2pt; color:var(--ink2); line-height:1.3; }
.arrow { align-self:center; color:var(--muted); font-size:10pt; }
.grid2 { display:grid; grid-template-columns:1fr 1fr; gap:4pt 16pt; }
table { border-collapse:collapse; width:100%; margin:2pt 0 8pt; font-size:8.2pt; }
th { font-weight:600; color:var(--ink2); text-align:left; border-bottom:1px solid #c3c2b7; padding:3pt 5pt; }
td { border-bottom:1px solid var(--rule); padding:2.6pt 5pt; vertical-align:top; }
td.num, th.num { text-align:right; white-space:nowrap; }
td.note { color:var(--muted); font-size:7.4pt; }
table.kv td:first-child { color:var(--ink2); }
.box { background:var(--wash); border-radius:6pt; padding:8pt 11pt; margin:6pt 0 8pt; break-inside:avoid; }
.box p:last-child, .box ul:last-child { margin-bottom:0; }
ul { margin:0 0 6pt; padding-left:14pt; }
.small { font-size:7.8pt; color:var(--ink2); }
.pb { break-before:page; }
.avoid { break-inside:avoid; }
"""

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>mapp_strategy report</title><style>{css}</style></head><body>
<div class=kicker>mapp_strategy · Strategy report</div>
<h1>Mapped-sector retail themes</h1>
<div class=meta>Fixed 25% baskets, no hedge · backtest {first:%-d %b %Y} – {last:%-d %b %Y} · {m['market_sessions']:,} U.S. sessions · {m['provenance']['archived_reports']:,} daily reports · {m['basket_count']} trades</div>
<div class=tiles>{tile_html}</div>
<p><strong>The strategy turned $100,000 into {fmt_money(m['ending_nav_usd'])} ({fmt_pct(m['total_net_return_pct'])} after costs) with a maximum drawdown of only {fmt_pct(m['max_drawdown_pct'])}.</strong>
It buys a sector ETF linked to the retail theme of the day, holds it for ten trading sessions and otherwise sits in cash. It was invested on {m['active_session_pct']:.0f}% of sessions and averaged {m['average_close_gross_exposure_pct']:.0f}% of equity in the market. That is why both its returns and its losses are small next to holding the S&amp;P 500.</p>
<figure><img src="{figs['equity']}"><figcaption>Daily closing equity, net of all trading costs. The account is flat after the last trade closed on {last:%-d %B %Y}; it ended {fmt_money(open_dd['peak_nav_usd'] - open_dd['end_nav_usd'])} below its {dt.date.fromisoformat(open_dd['peak_date']):%-d %B} high.</figcaption></figure>

<h2 class=pb>How the strategy works</h2>
{flow_html}
<ol>
<li><strong>Signal.</strong> Each daily <i>What Retail Is Playing</i> report lists four themes retail investors are trading. The strategy uses only the fourth. A report counts as available at 23:59:59 New York time on its printed date, and the strategy acts at the next market opening.</li>
<li><strong>Mapping.</strong> The theme heading is mapped to one ETF in a fixed universe of 17: SPY, QQQ, XLK, XLC, XLF, XLE, XLI, XLY, XLP, XLV, XLB, XLRE, XLU, SOXX, EPOL, GLD and IEF. Individual stocks go through a fixed 153-stock list, for example NVDA → SOXX, TSLA → XLY, XOM → XLE and JPM → XLF. Several stocks in one sector count as one ETF. The trade is long unless the heading explicitly says short, bearish or inverse. Themes that cannot be mapped safely (options, crypto, private companies, mixed long/short ideas) are skipped.</li>
<li><strong>Liquidity check.</strong> The ETF must be a U.S.-listed dollar instrument with an opening price, and its median daily dollar volume over the previous 20 sessions must be at least $10 million.</li>
<li><strong>Waiting period.</strong> At each opening, the strategy takes the newest ready report, if it is at most four calendar days old and has not been used. That report reserves the next trading window <i>before</i> the trend check. If the trend check then fails, the window stays reserved and the money stays in cash. Only one trade is open at a time. Over the backtest, {93} windows were reserved and {m['basket_count']} were funded.</li>
<li><strong>Trend check.</strong> For a long trade, the ETF's last completed close must be above the average of its last 20 closes (below it for a short). All {m['basket_count']} trades in the backtest were long.</li>
<li><strong>Size.</strong> Each trade gets 25% of current equity, including the entry fee, split equally across its ETFs. The share count stays fixed while the trade is open. The size never increases after losses.</li>
<li><strong>Exit.</strong> The trade is sold at the opening of the tenth trading session after entry, and never later than 21 calendar days after entry. Every trade in the backtest held exactly ten sessions ({min(hold_days)}–{max(hold_days)} calendar days). There is no stop-loss and no profit target.</li>
<li><strong>Cooldown.</strong> After the exit session, the strategy skips one more session before a new window can start.</li>
<li><strong>Costs.</strong> Each order pays 10 basis points of its value. Cash earns no interest. There is no hedge.</li>
</ol>
<div class=box><p><strong>Status at {last:%-d %B %Y}:</strong> flat. The final trade, a GLD basket, closed at the opening on 20 November. Under the cooldown rule, the earliest next entry is the opening of Tuesday, 24 November 2026, from the newest report available by then, provided its ETF passes the trend check.</p></div>

<h2>Risk and return</h2>
<div class=grid2>
<div class=avoid><h3>Return</h3><table class=kv>
{row('Starting equity', '$100,000', None)}
{row('Ending equity', fmt_money(m['ending_nav_usd']), None)}
{row('Net P&amp;L', fmt_money(m['net_pnl_usd'], True), None)}
{row('Gross trade P&amp;L', fmt_money(m['gross_trade_pnl_usd'], True), None)}
{row('Trading costs', fmt_money(-m['transaction_cost_usd']), None)}
{row('Net return', fmt_pct(m['total_net_return_pct']), None)}
{row('Annual growth (CAGR)', fmt_pct(m['cagr_pct']), None)}
</table></div>
<div class=avoid><h3>Risk</h3><table class=kv>
{row('Annualized volatility', f"{m['annualized_daily_volatility_pct']:.2f}%", None)}
{row('Downside deviation', f"{m['annualized_downside_deviation_pct']:.2f}%", None)}
{row('Maximum drawdown', fmt_pct(m['max_drawdown_pct']), None)}
{row('Worst day', f"{fmt_pct(m['worst_session']['return_pct'])} ({dt.date.fromisoformat(m['worst_session']['date']):%-d %b %Y})", None)}
{row('Best day', f"{fmt_pct(m['best_session']['return_pct'])} ({dt.date.fromisoformat(m['best_session']['date']):%-d %b %Y})", None)}
{row('Daily VaR / expected shortfall, 95%', f"{m['empirical_daily_95']['loss_var_pct']:.2f}% / {m['empirical_daily_95']['mean_tail_loss_pct']:.2f}%", None)}
{row('Daily VaR / expected shortfall, 99%', f"{m['empirical_daily_99']['loss_var_pct']:.2f}% / {m['empirical_daily_99']['mean_tail_loss_pct']:.2f}%", None)}
</table></div>
<div class=avoid><h3>Risk-adjusted</h3><table class=kv>
{row('Sharpe ratio (0% risk-free)', f"{m['sharpe_zero_rate']:.2f}", None)}
{row('Sortino ratio', f"{m['sortino_zero_target']:.2f}", None)}
{row('Calmar ratio', f"{m['calmar']:.2f}", None)}
{row('Beta to SPY, all / invested days', f"{m['all_session_spy_beta']:.2f} / {m['active_session_spy_beta']:.2f}", None)}
{row('Correlation with SPY', f"{m['all_session_spy_correlation']:.2f}", None)}
</table></div>
<div class=avoid><h3>Exposure</h3><table class=kv>
{row('Sessions with a position', f"{m['active_sessions']} of {m['market_sessions']} ({m['active_session_pct']:.0f}%)", None)}
{row('Average invested, daily close', f"{m['average_close_gross_exposure_pct']:.1f}%", None)}
{row('Highest invested', f"{m['max_sampled_gross_exposure_pct']:.1f}%", None)}
{row('Lowest cash share', f"{m['min_close_cash_pct']:.1f}%", None)}
{row('Leverage or short borrowing', 'none', None)}
</table></div>
<div class=avoid><h3>Trades</h3><table class=kv>
{row('Trades / winners / losers', f"{m['basket_count']} / {m['winners']} / {m['losers']}", None)}
{row('Win rate', f"{m['win_rate_pct']:.1f}%", None)}
{row('Profit factor', f"{m['profit_factor']:.2f}", None)}
{row('Average winner / loser', f"{fmt_money(m['average_winner_net_usd'], True)} / {fmt_money(m['average_loser_net_usd'])}", None)}
{row('Best trade', f"{m['best_basket']['symbols']} {fmt_money(m['best_basket']['net_pnl_usd'], True)} ({fmt_pct(m['best_basket']['account_return_pct'])} of equity)", None)}
{row('Worst trade', f"{m['worst_basket']['symbols']} {fmt_money(m['worst_basket']['net_pnl_usd'])} ({fmt_pct(m['worst_basket']['account_return_pct'])} of equity)", None)}
{row('Longest losing streak', f"{m['longest_losing_streak']['baskets']} trades, {fmt_money(m['longest_losing_streak']['net_pnl_usd'])}", None)}
</table></div>
<div class=avoid><h3>Recovery to a new high</h3><table class=kv>
{row('Drawdown periods (completed)', f"{rec['completed_episodes'] + 1} ({rec['completed_episodes']})", None)}
{row('Median time to recover', f"{rec['median_calendar_days']:.1f} days", None)}
{row('90th percentile', f"{rec['p90_calendar_days']:.0f} days", None)}
{row('Longest recovery', f"{rec['max_calendar_days']} days", None)}
{row('Sessions below the running high', f"{rec['pct_sessions_below_high']:.0f}%", None)}
{row('Current drawdown (open)', f"{fmt_pct(-open_dd['drawdown_pct'])} since {dt.date.fromisoformat(open_dd['peak_date']):%-d %b %Y}", None)}
</table></div>
</div>

<div class=avoid><h3>Compared with holding SPY over the same period</h3>
<table>
<tr><th></th><th class=num>Net return</th><th class=num>CAGR</th><th class=num>Volatility</th><th class=num>Max drawdown</th><th class=num>Sharpe</th></tr>
<tr><td>mapp_strategy</td><td class=num>{fmt_pct(m['total_net_return_pct'])}</td><td class=num>{fmt_pct(m['cagr_pct'])}</td><td class=num>{m['annualized_daily_volatility_pct']:.2f}%</td><td class=num>{fmt_pct(m['max_drawdown_pct'])}</td><td class=num>{m['sharpe_zero_rate']:.2f}</td></tr>
<tr><td>SPY buy and hold (dividends reinvested)</td><td class=num>{fmt_pct(spy['total'])}</td><td class=num>{fmt_pct(spy['cagr'])}</td><td class=num>{spy['vol']:.2f}%</td><td class=num>{fmt_pct(spy['maxdd'])}</td><td class=num>{spy['sharpe']:.2f}</td></tr>
</table>
<p class=small>SPY was fully invested throughout; the strategy averaged {m['average_close_gross_exposure_pct']:.0f}% invested. The strategy earned less in total but took far less risk, with a higher return per unit of volatility.</p></div>

<p class=small>Daily returns use the previous closing equity. Volatility is the sample standard deviation of daily returns × √252. Sharpe uses a zero risk-free rate; Sortino uses the root mean square of negative daily returns; Calmar divides CAGR by the maximum drawdown. VaR is the empirical daily loss quantile and expected shortfall the average loss at or beyond it. A recovery runs from the last close at a high to the first close above it.</p>

<h2 class=pb>Returns over time</h2>
<h3>Monthly returns</h3>
<figure><img src="{figs['monthly']}"><figcaption>Month-end equity change. Blue months gained and red months lost; most months without a trade show 0.0%. The last column compounds each year.</figcaption></figure>
<h3>Calendar years</h3>
<table>
<tr><th>Year</th><th class=num>Net return</th><th class=num>Net P&amp;L</th><th class=num>Volatility</th><th class=num>Max drawdown in year</th><th class=num>Trades entered</th></tr>
{years_rows}
</table>
<h3>Longest recoveries</h3>
<table>
<tr><th>Previous high</th><th>Low point</th><th>New high</th><th class=num>Duration</th><th class=num>Depth</th></tr>
{rec_rows}
</table>

<h2>Trades</h2>
<h3>Net P&amp;L of every trade</h3>
<figure><img src="{figs['trades']}"><figcaption>All {m['basket_count']} trades in entry order, after costs. Every trade used 25% of equity at entry and held ten sessions.</figcaption></figure>
<h3>Net P&amp;L by ETF</h3>
<figure><img src="{figs['etfs']}"><figcaption>Total net P&amp;L per ETF across all trades, with the number of trades and winners.</figcaption></figure>

<h2 class=pb>Limitations</h2>
<ul>
<li><strong>Concentrated results.</strong> {', '.join(top3)} produced {top3_share:.0f}% of net P&amp;L, and 2026 alone produced {yr_2026['net_pnl_usd'] / m['net_pnl_usd'] * 100:.0f}% ({fmt_money(yr_2026['net_pnl_usd'], True)}). The other years each returned about 3%.</li>
<li><strong>Selection, not timing.</strong> An earlier analysis of this strategy found no evidence that its entry timing beats random timing. Its returns come mainly from which sector each theme points to.</li>
<li><strong>Small sample.</strong> {m['basket_count']} trades over almost five years. A few trades move the totals noticeably.</li>
<li><strong>Retrospective reports.</strong> The reports are current reconstructions. Treating each as available at the end of its printed date is a simulation assumption; this is not a record of live trading.</li>
<li><strong>Costs and fills.</strong> Orders fill at the adjusted opening price with a 10 bp cost. Real fills, taxes and spreads can differ.</li>
<li><strong>Single path.</strong> No parameter was optimized, and the rules were fixed before this run, but no part of the history was held back for out-of-sample testing.</li>
</ul>
<h3>Data and reproduction</h3>
<p class=small>Reports: {m['provenance']['archived_reports']:,} public <i>What Retail Is Playing</i> reports, every weekday from January 2022 to 20 November 2026 present; {m['provenance']['reports_without_part4']} had fewer than four topics and gave no signal. Prices: one Yahoo daily download for the 17 ETFs ({m['provenance']['price_rows']:,} rows), with opening prices adjusted for dividends and splits in the same way as closing prices. The results come from the repository's <span style="font-family:'JetBrains Mono',monospace">mapp_strategy.py extended-history</span> command, and an independent price-and-position replay matched every daily equity value and trade. A fresh rerun on 21 November 2026 reproduced all {m['basket_count']} trades, with daily equity within $0.03. Full ledgers: strategies/mapp_strategy/backtests/2022_2026_no_gaps_fixed25 (daily_nav.csv, trades.csv, risk_metrics.json).</p>
</body></html>"""
    return html


RENDER_JS = r"""
const { chromium } = require('playwright');
(async () => {
  const [htmlPath, pdfPath] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + htmlPath, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.pdf({ path: pdfPath, preferCSSPageSize: true, printBackground: true, displayHeaderFooter: true,
    headerTemplate: '<span></span>',
    footerTemplate: `<div style="width:100%;font-family:Inter,sans-serif;font-size:7.3pt;color:#898781;font-variant-ligatures:no-contextual;font-feature-settings:'calt' 0;padding:0 15mm;display:flex;justify-content:space-between;">
      <span>mapp_strategy · Strategy report · backtest to 20 Nov 2026</span>
      <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>` });
  await browser.close();
})();
"""


def main():
    metrics, daily, trades = load()
    assert len(trades) == metrics["basket_count"] and len(daily) == metrics["market_sessions"]
    FIG.mkdir(exist_ok=True)
    figs = {k: FIG / f"report_{k}.png" for k in ["equity", "monthly", "trades", "etfs"]}
    chart_equity(daily, metrics, figs["equity"])
    chart_monthly(monthly_returns(daily), figs["monthly"])
    chart_trades(trades, figs["trades"])
    etf_pnl, etf_count = chart_etfs(trades, figs["etfs"])
    assert abs(sum(etf_pnl.values()) - metrics["net_pnl_usd"]) < 0.01
    html = build_html(metrics, daily, trades, spy_benchmark(daily), etf_pnl, etf_count, {k: v.as_uri() for k, v in figs.items()})
    with tempfile.TemporaryDirectory() as tmp:
        page, js = Path(tmp) / "report.html", Path(tmp) / "render.js"
        page.write_text(html)
        js.write_text(RENDER_JS)
        subprocess.run(["node", str(js), str(page), str(PDF)], check=True)
    print("wrote", PDF)


if __name__ == "__main__":
    main()
