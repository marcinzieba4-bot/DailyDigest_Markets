"""Diagnose timing versus sector selection from an immutable saved simulation.

No strategy is rerun and no prices or reports are downloaded. The exact
open-to-open comparison preserves the 54 funded windows and their allocations.
A separate close-to-close random-schedule diagnostic uses saved SPY returns.
Neither comparison isolates report information from SMA/sector-risk effects.
"""
from __future__ import annotations
import argparse
import base64
import bisect
import csv
import datetime as dt
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ZIP_SHA256 = "fb38b0cc881183a9e6cba642b31beac6b640aac0f937aa90ae9235fc758a5d59"
DEFAULT_ARCHIVE = ROOT / "backtests/2022_2026_month_gaps/mapp_strategy_extended_simulated_results.zip"
FEE = 0.001
CAPITAL = 100000.0


def read_csv(bundle, name):
    return list(csv.DictReader(io.StringIO(bundle.read(name).decode("utf-8"))))


def write_csv(path, rows):
    assert rows
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def trade_factor(allocation, underlying_return):
    """Long-only fixed units; entry and exit fees, cash rate zero."""
    return 1.0 + allocation * (underlying_return - FEE * (2.0 + underlying_return))


class Mulberry32:
    """The identical unsigned arithmetic used by the independent JS check."""
    def __init__(self, seed):
        self.state = seed & 0xffffffff

    def random(self):
        mask = 0xffffffff
        self.state = (self.state + 0x6D2B79F5) & mask
        value = self.state
        value = ((value ^ (value >> 15)) * (value | 1)) & mask
        value ^= (value + (((value ^ (value >> 7)) * (value | 61)) & mask)) & mask
        return ((value ^ (value >> 14)) & mask) / 4294967296.0


def quantile(sorted_values, q):
    position = (len(sorted_values) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (position - low)


def groups(records, key):
    result = {}
    for row in records:
        name = row[key]
        group = result.setdefault(name, {
            "baskets": 0, "source_gross_pnl_usd": 0.0,
            "spy_market_component_usd": 0.0, "selection_component_usd": 0.0,
            "mapped_net_factor": 1.0, "matched_spy_net_factor": 1.0,
        })
        group["baskets"] += 1
        group["source_gross_pnl_usd"] += row["source_gross_pnl_usd"]
        group["spy_market_component_usd"] += row["spy_market_component_usd"]
        group["selection_component_usd"] += row["selection_component_usd"]
        group["mapped_net_factor"] *= 1.0 + row["mapped_account_trade_return"]
        group["matched_spy_net_factor"] *= 1.0 + row["spy_account_trade_return"]
    for group in result.values():
        group["mapped_net_return"] = group.pop("mapped_net_factor") - 1.0
        group["matched_spy_net_return"] = group.pop("matched_spy_net_factor") - 1.0
    return result


def exact_comparison(all_trades, daily):
    original = sorted(
        (row for row in all_trades if row["policy"] == "unhedged25"),
        key=lambda row: row["entry_date"],
    )
    hedged = {row["basket_id"]: row for row in all_trades if row["policy"] == "dollar_short25"}
    assert len(original) == len(hedged) == 54
    dates = [row["date"] for row in daily]
    indexes = {day: i for i, day in enumerate(dates)}
    closes = []
    close = 1.0
    for row in daily:
        close *= 1.0 + float(row["spy_daily_return"])
        closes.append(close)
    mapped_nav = spy_nav = 1.0
    records = []
    for row in original:
        assert all(int(value) == 1 for value in json.loads(row["source_directions"]).values())
        hedge = hedged[row["basket_id"]]
        assert (row["entry_date"], row["exit_date"], row["symbols"]) == (
            hedge["entry_date"], hedge["exit_date"], hedge["symbols"]
        )
        amount = float(row["source_entry_notional"])
        allocation = amount / float(row["entry_nav"])
        mapped_return = float(row["source_gross_pnl"]) / amount
        spy_return = -float(hedge["hedge_gross_pnl"]) / float(hedge["source_entry_notional"])
        mapped_factor = trade_factor(allocation, mapped_return)
        spy_factor = trade_factor(allocation, spy_return)
        assert abs(mapped_factor - 1.0 - float(row["net_pnl_fraction_of_entry_nav"])) < 1e-12
        i, j = indexes[row["entry_date"]], indexes[row["exit_date"]]
        assert j - i == 10 and row["exit_kind"] == "open"
        mapped_nav *= mapped_factor
        spy_nav *= spy_factor
        records.append({
            "basket_id": row["basket_id"],
            "report_date": row["report_date"],
            "entry_date": row["entry_date"],
            "exit_date": row["exit_date"],
            "entry_year": row["entry_date"][:4],
            "mapped_etfs": row["symbols"],
            "funded_fraction_of_entry_nav": allocation,
            "mapped_window_return": mapped_return,
            "spy_window_return": spy_return,
            "selection_excess_return": mapped_return - spy_return,
            "mapped_account_trade_return": mapped_factor - 1.0,
            "spy_account_trade_return": spy_factor - 1.0,
            "mapped_nav_usd": mapped_nav * CAPITAL,
            "matched_spy_nav_usd": spy_nav * CAPITAL,
            "original_source_entry_notional_usd": amount * CAPITAL,
            "spy_market_component_usd": amount * spy_return * CAPITAL,
            "selection_component_usd": amount * (mapped_return - spy_return) * CAPITAL,
            "source_gross_pnl_usd": amount * mapped_return * CAPITAL,
            "source_fees_usd": float(row["transaction_cost_usd"]),
            "source_net_pnl_usd": float(row["net_pnl_usd"]),
            "spy_close_to_close_window_return": closes[j] / closes[i] - 1.0,
            "entry_session_index": i,
            "exit_session_index": j,
        })
    assert abs(mapped_nav - 1.1945343548131713) < 1e-12
    assert abs(spy_nav - 1.0861699355152386) < 1e-12
    return records, dates, closes


def make_sampler(candidates, quota):
    """DP counts all eligible ordered sets with >=12 sessions between starts."""
    n = len(candidates)
    following = [bisect.bisect_left(candidates, index + 12) for index in candidates]
    counts = [[0.0] * (n + 1) for _ in range(quota + 1)]
    counts[0] = [1.0] * (n + 1)
    for need in range(1, quota + 1):
        for position in range(n - 1, -1, -1):
            counts[need][position] = (
                counts[need][position + 1] + counts[need - 1][following[position]]
            )
    assert counts[quota][0] > 0.0
    return candidates, following, counts, quota


def sample_year(sampler, rng):
    candidates, following, counts, need = sampler
    position = 0
    chosen = []
    while need:
        take = counts[need - 1][following[position]]
        total = counts[need][position]
        if rng.random() < take / total:
            chosen.append(candidates[position])
            position = following[position]
            need -= 1
        else:
            position += 1
    return chosen


def timing_null(records, dates, closes, coverage, trials, seed):
    allowed = set(coverage["available_months"])
    years = sorted({row["entry_year"] for row in records})
    samplers = []
    quotas = {}
    for year in years:
        quota = sum(row["entry_year"] == year for row in records)
        quotas[year] = quota
        candidates = [
            i for i, day in enumerate(dates)
            if day[:4] == year and day[:7] in allowed
            and i + 10 < len(dates) and day > coverage["first_report"]
        ]
        samplers.append(make_sampler(candidates, quota))
    allocations = [row["funded_fraction_of_entry_nav"] for row in records]
    rng = Mulberry32(seed)
    actual_factor = 1.0
    for row in records:
        actual_factor *= trade_factor(
            row["funded_fraction_of_entry_nav"], row["spy_close_to_close_window_return"]
        )
    actual_return = actual_factor - 1.0
    values = []
    attempts = rejected = 0
    while len(values) < trials:
        attempts += 1
        starts = [index for sampler in samplers for index in sample_year(sampler, rng)]
        if any(starts[i] - starts[i - 1] < 12 for i in range(1, len(starts))):
            rejected += 1
            continue  # Reject the WHOLE combined schedule to retain uniform conditioning.
        nav = 1.0
        for i, allocation in zip(starts, allocations):
            underlying_return = closes[i + 10] / closes[i] - 1.0
            nav *= trade_factor(allocation, underlying_return)
        values.append(nav - 1.0)
    ordered = sorted(values)
    receipt = {
        "diagnostic": "Separate close-to-close timing control; not an open-to-open simulation.",
        "random_generator": "Mulberry32",
        "seed": seed, "trials": trials, "attempts": attempts,
        "cross_year_schedule_rejections": rejected,
        "entry_year_quotas": quotas,
        "holding_sessions": 10, "minimum_entry_spacing_sessions": 12,
        "missing_months": coverage["missing_months"],
        "actual_schedule_spy_net_return_close_to_close": actual_return,
        "random_mean_net_return": sum(values) / trials,
        "random_median_net_return": quantile(ordered, 0.5),
        "random_5pct_net_return": quantile(ordered, 0.05),
        "random_95pct_net_return": quantile(ordered, 0.95),
        "random_2_5pct_net_return": quantile(ordered, 0.025),
        "random_97_5pct_net_return": quantile(ordered, 0.975),
        "fraction_random_at_least_actual": sum(v >= actual_return for v in values) / trials,
        "actual_schedule_percentile": sum(v < actual_return for v in values) / trials,
        "limitations": [
            "This is an exploratory schedule diagnostic, not significance adjusted for prior strategy research.",
            "Random dates match year counts, holding duration, spacing, allocations and missing-month restrictions.",
            "Random dates do not match the original SMA gate, volatility or within-year market regimes.",
            "The exact same-window comparison and this close-only null use different execution conventions.",
            "The source archive is retrospective and historical report availability remains assumed.",
        ],
    }
    if trials == 20000 and seed == 20261121:
        assert attempts == 230607 and rejected == 210607, "RNG/sampling replication differs"
        assert abs(actual_return - 0.082783430087223) < 1e-12
        assert abs(receipt["random_mean_net_return"] - 0.06809624057019767) < 1e-12
        assert abs(receipt["fraction_random_at_least_actual"] - 0.35535) < 1e-12
    return receipt, values


def plot_results(out, records, dates, null_receipt, random_returns):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter, StrMethodFormatter
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(12, 9.4), gridspec_kw={"height_ratios": [1.1, 1]})
    fig.set_facecolor("#F7F9FB")
    fig.suptitle("mapp_strategy: timing versus sector selection", x=.085, y=.974, ha="left", fontsize=18, weight="bold", color="#173042")
    fig.text(.085, .94, "$100,000 accounts | same 54 funded windows | same allocations | 10 bp entry/exit fees", color="#526976", fontsize=10)
    marks = [dt.date.fromisoformat(dates[0])] + [dt.date.fromisoformat(row["exit_date"]) for row in records]
    sector = [CAPITAL] + [row["mapped_nav_usd"] for row in records]
    spy = [CAPITAL] + [row["matched_spy_nav_usd"] for row in records]
    for axis in (top, bottom):
        axis.set_facecolor("white")
        axis.grid(True, color="#DCE4EA", alpha=.7)
        axis.spines[["top", "right"]].set_visible(False)
    top.plot(marks, sector, color="#087F8C", linewidth=2.2, marker="o", markersize=2.4, label=f"Mapped sectors: {sector[-1] / CAPITAL - 1:+.2%}")
    top.plot(marks, spy, color="#C57718", linewidth=2.0, marker="o", markersize=2.4, label=f"SPY on identical signals: {spy[-1] / CAPITAL - 1:+.2%}")
    top.set_title("Exact open-to-open returns; account marks at trade exits", loc="left", fontsize=11, pad=10)
    top.set_ylabel("Account value ($)")
    top.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    top.legend(loc="upper left", frameon=True)
    top.text(.01, .02, "Lines join trade-exit marks; they do not show intratrade drawdowns.", transform=top.transAxes, fontsize=8.5, color="#697C87")
    actual = null_receipt["actual_schedule_spy_net_return_close_to_close"]
    median = null_receipt["random_median_net_return"]
    bottom.hist(random_returns, bins=65, color="#86ADB7", edgecolor="white", linewidth=.4)
    bottom.axvline(actual, color="#C57718", linewidth=2.5, label=f"Actual schedule, close-to-close: {actual:+.2%}")
    bottom.axvline(median, color="#173042", linewidth=1.8, linestyle="--", label=f"Random median: {median:+.2%}")
    bottom.set_title(f"Separate timing diagnostic: {null_receipt['trials']:,} random schedules, all measured close-to-close", loc="left", fontsize=11, pad=10)
    bottom.set_xlabel("Net account return")
    bottom.set_ylabel("Random schedules")
    bottom.xaxis.set_major_formatter(PercentFormatter(1.0))
    bottom.legend(loc="upper left", frameon=True)
    tail = null_receipt["fraction_random_at_least_actual"]
    bottom.text(.99, .96, f"{tail:.1%} of random schedules matched or beat actual", transform=bottom.transAxes, ha="right", va="top", fontsize=9, color="#173042")
    fig.text(.085, .048, "Random schedules preserve entry-year counts, funded allocations, 10-session holds, spacing and missing-month entry restrictions.", fontsize=8.5, color="#526976")
    fig.text(.085, .028, "They do not match SMA conditions or within-year regimes. Exploratory comparison; historical report availability remains assumed.", fontsize=8.5, color="#697C87")
    fig.subplots_adjust(left=.085, right=.975, top=.89, bottom=.12, hspace=.34)
    png = out / "timing_selection.png"
    fig.savefig(png, dpi=160, facecolor=fig.get_facecolor())
    fig.savefig(out / "timing_selection.svg", facecolor=fig.get_facecolor())
    plt.close(fig)
    return png


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--out", type=Path, default=ROOT / "backtests/2022_2026_timing_selection")
    parser.add_argument("--trials", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20261121)
    parser.add_argument("--stream-figure", action="store_true", help="Print base64 PNG chunks for an execution receipt.")
    args = parser.parse_args()
    assert args.trials > 0
    raw = args.archive.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ZIP_SHA256, "Saved archive identity differs"
    assert not args.out.exists(), "Use a new output directory; never overwrite an existing analysis"
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        assert bundle.testzip() is None, "Saved archive CRC failure"
        all_trades = read_csv(bundle, "all_trades.csv")
        daily = read_csv(bundle, "results/archive_replay_unhedged25_daily.csv")
        coverage = json.loads(bundle.read("coverage.json"))
    records, dates, closes = exact_comparison(all_trades, daily)
    null_receipt, random_returns = timing_null(records, dates, closes, coverage, args.trials, args.seed)
    source_gross = sum(row["source_gross_pnl_usd"] for row in records)
    market = sum(row["spy_market_component_usd"] for row in records)
    selection = sum(row["selection_component_usd"] for row in records)
    fees = sum(row["source_fees_usd"] for row in records)
    assert abs(source_gross - market - selection) < 1e-8
    by_year = groups(records, "entry_year")
    by_instrument = groups(records, "mapped_etfs")
    summary = {
        "strategy_id": "mapp_strategy",
        "analysis": "Timing versus sector selection, using only immutable saved simulated results.",
        "saved_archive_sha256": ZIP_SHA256,
        "start": dates[0], "end": dates[-1], "baskets": len(records),
        "initial_capital_usd": CAPITAL, "fee_per_order": FEE, "cash_interest": 0.0,
        "exact_matched_windows": {
            "execution": "Original entry open to original exit open, fixed funded units.",
            "mapped_net_return": records[-1]["mapped_nav_usd"] / CAPITAL - 1.0,
            "spy_net_return": records[-1]["matched_spy_nav_usd"] / CAPITAL - 1.0,
            "mapped_positive_gross_windows": sum(row["mapped_window_return"] > 0 for row in records),
            "spy_positive_gross_windows": sum(row["spy_window_return"] > 0 for row in records),
            "mapped_beats_spy_windows": sum(row["selection_excess_return"] > 1e-12 for row in records),
            "equal_windows": sum(abs(row["selection_excess_return"]) <= 1e-12 for row in records),
            "average_mapped_underlying_window_return": statistics.mean(row["mapped_window_return"] for row in records),
            "average_spy_underlying_window_return": statistics.mean(row["spy_window_return"] for row in records),
            "average_underlying_selection_excess": statistics.mean(row["selection_excess_return"] for row in records),
        },
        "gross_attribution_on_original_source_notionals": {
            "spy_market_component_usd": market, "selection_component_usd": selection,
            "source_gross_pnl_usd": source_gross, "source_fees_usd": fees,
            "source_net_pnl_usd": source_gross - fees,
            "selection_share_from_2026_entry_cohorts": by_year["2026"]["selection_component_usd"] / selection,
            "selection_share_from_XLE": by_instrument["XLE"]["selection_component_usd"] / selection,
            "note": "Additive attribution on the original account; not separate compounded accounts or net hedged PnL.",
        },
        "by_entry_year": by_year,
        "by_mapped_instrument": by_instrument,
        "timing_null": null_receipt,
        "limitations": [
            "Entry-year cohort returns are not calendar returns; December 2025 entry basket 71 exits January 2026.",
            "Selection includes sector trend gating and sector/beta risk differences; it is not isolated report-specific alpha.",
            "Positive SPY returns during actual windows are market contribution, not by themselves timing alpha.",
            "All source legs in this saved sample are long. No change to the general strategy direction rules is implied.",
            "There is no new raw input, strategy optimization, or full portfolio backtest in this analysis.",
        ],
    }
    args.out.mkdir(parents=True)
    write_csv(args.out / "matched_windows.csv", records)
    write_csv(args.out / "timing_null_returns.csv", [
        {"trial": i + 1, "net_account_return": value} for i, value in enumerate(random_returns)
    ])
    save_json(args.out / "summary.json", summary)
    figure = plot_results(args.out, records, dates, null_receipt, random_returns)
    manifest = {
        path.name: {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in sorted(args.out.iterdir()) if path.is_file()
    }
    save_json(args.out / "manifest.json", manifest)
    print("MAPP_TIMING_SELECTION_SUMMARY " + json.dumps(summary, sort_keys=True, allow_nan=False), flush=True)
    if args.stream_figure:
        payload = base64.b64encode(figure.read_bytes()).decode("ascii")
        chunks = [payload[i:i + 14000] for i in range(0, len(payload), 14000)]
        print("MAPP_TIMING_SELECTION_PNG_BEGIN " + json.dumps(manifest[figure.name]), flush=True)
        for i, chunk in enumerate(chunks, 1):
            print(f"MAPP_TIMING_SELECTION_PNG_CHUNK {i}/{len(chunks)} {chunk}", flush=True)
        print("MAPP_TIMING_SELECTION_PNG_END", flush=True)
        for filename in ("matched_windows.csv",):
            file_bytes = (args.out / filename).read_bytes()
            encoded = base64.b64encode(file_bytes).decode("ascii")
            file_chunks = [encoded[i:i + 14000] for i in range(0, len(encoded), 14000)]
            print("MAPP_TIMING_SELECTION_CSV_BEGIN " + json.dumps({"name": filename, **manifest[filename]}), flush=True)
            for i, chunk in enumerate(file_chunks, 1):
                print(f"MAPP_TIMING_SELECTION_CSV_CHUNK {i}/{len(file_chunks)} {chunk}", flush=True)
            print("MAPP_TIMING_SELECTION_CSV_END", flush=True)


if __name__ == "__main__":
    main()
