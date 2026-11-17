"""Export PnL and drawdown for the earliest-start three-policy research case.

All nine saved cases are reconciled from their own ledgers. Only the earliest
continuous three-policy group is plotted. This script never reruns a strategy.
"""
from pathlib import Path
import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/retail_part4_nov2023_mpl")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp/retail_part4_nov2023_cache")
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

CAPITAL = 100000.0
POLICIES = ["dollar_short25", "beta40_daily_short25", "unhedged25"]
COLORS = {"dollar_short25": "#167399", "beta40_daily_short25": "#008A72", "unhedged25": "#CA6D27"}
NAMES = {"dollar_short25": "Fixed-dollar SPY short", "beta40_daily_short25": "Daily beta40 SPY short or flat", "unhedged25": "No SPY hedge"}
INK, MUTED, ORANGE = "#253B49", "#647C8E", "#CA6D27"

def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    return [] if not rows or list(rows[0]) == ["empty_ledger"] else rows

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def locate(root, results, value):
    path = Path(value)
    candidates = [path] if path.is_absolute() else [results / path, root / path]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(str(value))

def close_enough(actual, expected, label, tolerance=1e-9):
    if not math.isfinite(float(actual)) or not math.isfinite(float(expected)):
        raise AssertionError("Nonfinite " + label)
    if abs(float(actual) - float(expected)) > tolerance:
        raise AssertionError(label + ": " + str(actual) + " versus " + str(expected))

def dollars(value, pos=None):
    if abs(value) < 1e-8:
        return "$0"
    return ("−" if value < 0 else "") + "$" + f"{abs(value) / 1000:g}k"

def date_label(day):
    return dt.date.fromisoformat(day).strftime("%d %B %Y").lstrip("0")

def point(rows, index):
    if index is None:
        return None
    value = float(rows[index]["nav"])
    return {"date": rows[index]["date"], "index": index, "nav": value,
            "nav_usd": CAPITAL * value, "pnl_usd": CAPITAL * (value - 1.0)}

def target_recovery(rows, target, search_start):
    values = [float(row["nav"]) for row in rows]
    candidates = [index for index, row in enumerate(rows) if row["date"] >= search_start]
    first_under = next((index for index in candidates if values[index] < target), None)
    first_cross = (next((index for index in range(first_under + 1, len(rows)) if values[index] >= target), None)
                   if first_under is not None else None)
    last_under = max((index for index in candidates if values[index] < target), default=None)
    durable = last_under + 1 if last_under is not None and last_under + 1 < len(rows) else None
    state = "never_below_target" if first_under is None else "unrecovered" if first_cross is None else "recovered"
    return {"target_nav": target, "target_usd": target * CAPITAL, "search_start": search_start, "state": state,
            "first_under": point(rows, first_under), "first_recovery": point(rows, first_cross),
            "durable_recovery_in_observed_sample": point(rows, durable)}

def case_key(metric):
    return tuple(str(metric.get(key, "")) for key in ["case_id", "case", "scope", "corpus", "family", "policy"])

def source_signature(rows):
    result = []
    for row in rows:
        sign = None
        for name in ["qty", "source_qty", "direction"]:
            if name in row and row[name] != "":
                number = float(row[name])
                sign = 1 if number > 0 else -1 if number < 0 else 0
                break
        result.append(tuple(row.get(key, "") for key in ["report_date", "symbol", "entry_date", "exit_date", "exit_kind"]) + (sign,))
    return result

def check_case(root, results, metric):
    paths = {kind: locate(root, results, metric[kind + "_path"]) for kind in
             ["daily", "orders", "borrow", "baskets", "source_trades", "exante"]}
    rows = read_csv(paths["daily"])
    if not rows:
        raise AssertionError("Empty daily NAV book")
    if [row["date"] for row in rows] != sorted({row["date"] for row in rows}):
        raise AssertionError("Daily dates must be unique and sorted")
    values = np.array([float(row["nav"]) for row in rows], dtype=float)
    if np.any(~np.isfinite(values)) or np.any(values <= 0):
        raise AssertionError("Invalid daily NAV")
    drawdown = values / np.maximum.accumulate(np.r_[1.0, values])[1:] - 1.0
    orders = read_csv(paths["orders"])
    borrow = read_csv(paths["borrow"])
    baskets = read_csv(paths["baskets"])
    sources = read_csv(paths["source_trades"])
    exante = read_csv(paths["exante"])
    close_enough(values[-1] - 1.0, metric["total_return"], "ending return")
    close_enough(drawdown.min(), metric["max_drawdown"], "maximum drawdown")
    close_enough(sum(float(row["net_pnl"]) for row in baskets), metric["total_return"], "closed basket PnL")
    close_enough(sum(float(row["fee"]) for row in orders), metric["transaction_cost"], "order fees")
    close_enough(sum(float(row["borrow_cost"]) for row in borrow), metric["borrow_cost"], "borrow")
    if len(baskets) != int(metric["baskets"]):
        raise AssertionError("Trade count mismatch")
    if not all(float(row["hedge_spy_qty"]) <= 1e-12 for row in exante):
        raise AssertionError("A hedge may not be long SPY")
    peak_gross = max(max(float(row["gross_exposure_open"]), float(row["gross_exposure_close"])) for row in rows)
    close_enough(peak_gross, metric["max_gross_exposure"], "sampled gross exposure")
    if metric["policy"] == "unhedged25":
        if not all(abs(float(row["hedge_spy_qty"])) <= 1e-12 for row in exante):
            raise AssertionError("Unhedged book has a SPY hedge")
        if not all(abs(float(row.get("hedge_delta_qty", 0.0))) <= 1e-12 for row in orders):
            raise AssertionError("Unhedged orders contain a hedge change")
        if not all(abs(float(row["hedge_gross_pnl"])) <= 1e-12 for row in baskets):
            raise AssertionError("Unhedged basket contains hedge PnL")
        # A source theme may itself be SPY or short. Do not confuse that with a
        # hedge, and do not assume the newly added source history is long-only.
    for basket in baskets:
        if float(basket["entry_nav"]) <= 0:
            raise AssertionError("Nonpositive entry NAV")
        if abs(float(basket["source_entry_notional"])) > 0.25 * float(basket["entry_nav"]) + 1e-10:
            raise AssertionError("Source entry budget exceeds25% NAV")
    signatures = [(row["report_date"], row["entry_date"], row["exit_date"], row["exit_kind"], row["symbols"]) for row in baskets]
    check = {"identity": list(case_key(metric)), "scope": metric.get("scope"), "corpus": metric.get("corpus"),
             "policy": metric["policy"], "first_date": rows[0]["date"], "last_date": rows[-1]["date"],
             "daily_rows": len(rows), "baskets": len(baskets), "orders": len(orders), "borrow_rows": len(borrow),
             "total_return": float(metric["total_return"]), "max_drawdown": float(metric["max_drawdown"]),
             "ending_nav_usd": CAPITAL * values[-1], "fees_usd": CAPITAL * float(metric["transaction_cost"]),
             "borrow_usd": CAPITAL * float(metric["borrow_cost"]), "max_sampled_gross": peak_gross,
             "endpoint_cost_exposure_and_hedge_checks": True,
             "files": {kind: {"path": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
                               "sha256": sha256(path)} for kind, path in paths.items()}}
    before = [index for index, row in enumerate(rows) if row["date"] <= "2025-04-04"]
    if before:
        peak_index = max(before, key=lambda index: values[index])
        peak_nav = max(1.0, values[peak_index])
        check["own_hwm_through_april4"] = point(rows, peak_index) if values[peak_index] >= 1.0 else {
            "date": rows[0]["date"], "index": -1, "nav": 1.0, "nav_usd": CAPITAL, "pnl_usd": 0.0,
            "reference_kind": "initial_capital_before_first_close"}
        check["own_hwm_through_april4_recovery"] = target_recovery(rows, peak_nav, "2025-04-05")
    check["initial_capital_recovery"] = target_recovery(rows, 1.0, rows[0]["date"])
    trough_index = int(np.argmin(drawdown))
    historical = np.r_[1.0, values[:trough_index + 1]]
    high_index = int(np.argmax(historical)) - 1
    high = float(historical[high_index + 1])
    check["maximum_drawdown_episode"] = {
        "peak": point(rows, high_index) if high_index >= 0 else {"date": rows[0]["date"], "nav": 1.0, "nav_usd": CAPITAL, "pnl_usd": 0.0},
        "trough": point(rows, trough_index),
        "recovery": target_recovery(rows, high, rows[max(0, high_index + 1)]["date"])}
    return {"metric": metric, "rows": rows, "values": values, "drawdown": drawdown,
            "check": check, "signatures": signatures, "source_signatures": source_signature(sources)}

def select_main(cases, args):
    selected = cases
    if args.main_scope is not None:
        selected = [case for case in selected if str(case["metric"].get("scope", "")) == args.main_scope]
    if args.main_corpus is not None:
        selected = [case for case in selected if str(case["metric"].get("corpus", "")) == args.main_corpus]
    if args.main_scope is None and args.main_corpus is None:
        earliest = min(case["rows"][0]["date"] for case in selected)
        selected = [case for case in selected if case["rows"][0]["date"] == earliest]
    if len(selected) != len(POLICIES) or {case["metric"]["policy"] for case in selected} != set(POLICIES):
        raise AssertionError("Select exactly one main continuous three-policy group with --main-scope/--main-corpus")
    result = {case["metric"]["policy"]: case for case in selected}
    reference = result[POLICIES[0]]
    for policy in POLICIES:
        case = result[policy]
        if [row["date"] for row in case["rows"]] != [row["date"] for row in reference["rows"]]:
            raise AssertionError("Main policies use different daily calendars")
        if case["signatures"] != reference["signatures"] or case["source_signatures"] != reference["source_signatures"]:
            raise AssertionError("Main policies have different source trade schedules/signs")
    common_nav = reference["check"].get("own_hwm_through_april4", {}).get("nav")
    if common_nav is not None:
        for case in result.values():
            case["check"]["common_static_hwm_through_april4_recovery"] = target_recovery(case["rows"], common_nav, "2025-04-05")
    return result

def reconcile_independent(cases, audit_path):
    if audit_path is None:
        return {"status": "not_supplied", "note": "Independent audit remains a separate required release check."}
    audited = json.loads(audit_path.read_text(encoding="utf-8"))
    if audited.get("status") != "passed":
        raise AssertionError("Independent result audit has not passed")
    metrics = audited.get("metrics", [])
    if isinstance(metrics, dict):
        metrics = list(metrics.values())
    lookup = {case_key(metric): metric for metric in metrics}
    matched = 0
    for case in cases:
        candidate = lookup.get(case_key(case["metric"]))
        if candidate is None:
            compatible = [metric for metric in metrics
                          if str(metric.get("policy")) == case["metric"]["policy"]
                          and str(metric.get("corpus", "")) == str(case["metric"].get("corpus", ""))
                          and str(metric.get("scope", "")) == str(case["metric"].get("scope", ""))]
            if len(compatible) != 1:
                raise AssertionError("Independent audit case identity is ambiguous")
            candidate = compatible[0]
        for field in ["total_return", "max_drawdown"]:
            close_enough(case["check"][field], candidate[field], "independent " + field)
        if "ending_nav_usd" in candidate:
            close_enough(case["check"]["ending_nav_usd"], candidate["ending_nav_usd"], "independent ending NAV", 1e-7)
        matched += 1
    return {"status": "passed", "path": str(audit_path), "sha256": sha256(audit_path), "matched_cases": matched}

def style():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10.2,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.edgecolor": "#B9C7D0", "axes.labelcolor": INK, "text.color": INK,
                         "svg.hashsalt": "retail_part4_nov2023_fixed",
                         "xtick.color": MUTED, "ytick.color": MUTED, "grid.color": "#E1E8ED"})

def layout_checks(fig, axes, legend):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    width, height = fig.canvas.get_width_height()
    checks = []
    for text in fig.texts:
        bounds = text.get_window_extent(renderer)
        if bounds.x0 < -1 or bounds.y0 < -1 or bounds.x1 > width + 1 or bounds.y1 > height + 1:
            raise AssertionError("Figure text exceeds canvas: " + text.get_text())
        checks.append({"text": text.get_text(), "bounds_px": [float(v) for v in bounds.bounds]})
    legend_box = legend.get_window_extent(renderer)
    if legend_box.x0 < 0 or legend_box.x1 > width or legend_box.y0 < 0 or legend_box.y1 > height:
        raise AssertionError("Legend exceeds canvas")
    boxes = [axis.get_window_extent(renderer) for axis in axes]
    if boxes[1].y1 >= boxes[0].y0:
        raise AssertionError("PnL and drawdown panels overlap")
    if any(sum(line.get_label().startswith("policy:") for line in axis.lines) != 3 for axis in axes):
        raise AssertionError("Expected3identifiedpolicycurves in each panel")
    return {"status": "passed", "canvas_px": [width, height], "figure_text_bounds": checks,
            "legend_bounds_px": [float(v) for v in legend_box.bounds], "policy_curves_per_panel": 3,
            "panels_separate": True, "visual_preview": "not_performed_by_this_script"}

def render(root, output, main):
    reference = main[POLICIES[0]]
    start, end = reference["rows"][0]["date"], reference["rows"][-1]["date"]
    period = date_label(start) + "–" + date_label(end)
    style()
    fig, (ax, ddax) = plt.subplots(2, 1, figsize=(14.5, 10.0), sharex=True,
                                 gridspec_kw={"height_ratios": [3.2, 1.1]})
    fig.subplots_adjust(left=.085, right=.97, top=.742, bottom=.232, hspace=.15)
    fig.suptitle("Part 4 PnL with and without the SPY hedge", x=.075, y=.982,
                 ha="left", fontsize=18.5, fontweight="bold")
    fig.text(.075, .934, "$100,000 separate accounts · same source trade schedule · 25% NAV source entry budget", fontsize=10.2, color=MUTED)
    fig.text(.075, .891, period + " · unchanged ETF SMA20 and ten-session exits · no RSI · no weekly filter · no stop", fontsize=10.0, color=MUTED)
    handles = [Line2D([], [], color=COLORS[policy], lw=2.5, label=NAMES[policy]) for policy in POLICIES]
    legend = fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(.074, .858),
                        ncol=3, frameon=False, fontsize=10.0, handlelength=3, columnspacing=2)
    fig.text(.075, .795, "RECONSTRUCTED REPORT ARCHIVE — historical publication timing is assumed",
             fontsize=10.4, color=ORANGE, fontweight="bold")
    xs = [dt.datetime.fromisoformat(row["date"]) for row in reference["rows"]]
    for policy in POLICIES:
        case = main[policy]
        ax.plot(xs, CAPITAL * (case["values"] - 1), color=COLORS[policy],
                lw=2.3 if policy == "unhedged25" else 2.0, label="policy:" + policy)
        ddax.plot(xs, case["drawdown"] * 100, color=COLORS[policy], lw=1.8, label="policy:" + policy)
        ddax.fill_between(xs, case["drawdown"] * 100, 0, color=COLORS[policy], alpha=.055)
    earlier_cutoff = dt.datetime(2024, 9, 1)
    if xs[0] < earlier_cutoff < xs[-1]:
        for panel in [ax, ddax]:
            panel.axvspan(xs[0], earlier_cutoff, color="#FFF0D7", alpha=.45, zorder=-2)
            panel.axvline(earlier_cutoff, color=MUTED, lw=.8, ls="--", alpha=.6)
        ax.text(.014, .955, "Added earlier history through August2024", transform=ax.transAxes, color=MUTED,
                fontsize=9.2, va="top", bbox={"fc": "white", "ec": "none", "alpha": .90, "pad": 3})
    for panel in [ax, ddax]:
        panel.axhline(0, color=MUTED, lw=.8)
        panel.grid(alpha=.75)
        panel.margins(x=.008)
    ax.set_ylabel("Net portfolio PnL (USD)")
    ax.yaxis.set_major_formatter(FuncFormatter(dollars))
    ax.margins(y=.18)
    ddax.set_ylabel("Drawdown from\nrunning peak (%)")
    ddax.yaxis.set_major_formatter(FuncFormatter(lambda value, pos: f"{value:g}"))
    ddax.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
    ddax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    for index, policy in enumerate(POLICIES):
        metric = main[policy]["metric"]
        label = (NAMES[policy] + ": PnL " + f"{CAPITAL * metric['total_return']:+,.0f}"
                 + " USD (" + f"{metric['total_return']:+.2%}" + ")  |  "
                 + f"{abs(metric['max_drawdown']):.2%}" + " max DD  |  "
                 + f"{metric['max_gross_exposure']:.1%}" + " peak gross")
        fig.text(.075, .179 - index * .032, label, color=COLORS[policy], fontsize=10.1, fontweight="bold")
    fig.text(.075, .065, "Removing SPY keeps the source entry budget unchanged. Units are fixed within each trade; later entries compound each account’s own NAV.", color=MUTED, fontsize=9.0)
    fig.text(.075, .036, "Fees:10bps per net order; short borrow:3% annually on actual short holdings; cash:0%. Gross samples opens after fills and daily closes.", color=MUTED, fontsize=9.0)
    fig.text(.075, .007, "No SPY hedge retains directional exposure. Daily beta hedge sizing is uncapped. Earlier history is exploratory.", color=MUTED, fontsize=9.0)
    review = layout_checks(fig, [ax, ddax], legend)
    stem = "nov2023_hedge_comparison"
    for extension in ["png", "svg"]:
        fig.savefig(output / (stem + "." + extension), dpi=190, bbox_inches="tight", pad_inches=.18,
                    metadata={"Date": None} if extension == "svg" else {})
    plt.close(fig)
    return review

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--main-scope")
    parser.add_argument("--main-corpus")
    parser.add_argument("--expected-cases", type=int, default=9)
    parser.add_argument("--audit-json", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    summary_path = (args.summary or root / "results" / "summary.json").resolve()
    output = root / "figures"
    output.mkdir(exist_ok=True, parents=True)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if isinstance(summary, dict):
        summary = summary.get("cases", summary.get("metrics", summary.get("summary")))
    if not isinstance(summary, list) or len(summary) != args.expected_cases:
        raise AssertionError("Unexpected saved case count")
    if not all(metric.get("status") == "ok" and metric.get("policy") in POLICIES for metric in summary):
        raise AssertionError("Failed or unknown-policy case")
    cases = [check_case(root, summary_path.parent, metric) for metric in summary]
    main_cases = select_main(cases, args)
    audit_path = args.audit_json.resolve() if args.audit_json else None
    if audit_path is None:
        for candidate in [root / "diagnosis" / "independent_results.json", root / "audit" / "results_audit.json"]:
            if candidate.is_file():
                audit_path = candidate
                break
    independent = reconcile_independent(cases, audit_path)
    review = render(root, output, main_cases)
    manifest = {"status": "passed", "saved_cases_checked": len(cases), "main_policies": POLICIES,
                "starting_capital_usd": CAPITAL, "source_summary_sha256": sha256(summary_path),
                "main_start": main_cases[POLICIES[0]]["rows"][0]["date"],
                "main_end": main_cases[POLICIES[0]]["rows"][-1]["date"],
                "main_case_selection": "earliest actual saved daily calendar unless explicit scope/corpus selected",
                "identical_source_trade_schedule_and_signs": True,
                "independent_audit": independent, "cases": [case["check"] for case in cases],
                "outputs": {path.name: sha256(path) for path in sorted(output.glob("nov2023_hedge_comparison.*"))
                            if path.suffix in [".png", ".svg"]}}
    (output / "plot_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output / "layout_checks.json").write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "saved_cases_checked": len(cases), "main_start": manifest["main_start"],
                      "main_end": manifest["main_end"], "main_source_trades": len(main_cases[POLICIES[0]]["signatures"]),
                      "independent_audit_status": independent["status"], "figures": 1}))

if __name__ == "__main__":
    main()
