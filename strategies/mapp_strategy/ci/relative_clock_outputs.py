"""Audit/export the four predeclared gate/clock variants and three hedge policies.

Only simulated outputs and validation metadata are exported. Source report prose,
HTML, mapped inputs and raw prices remain local to the execution workspace.
"""
from __future__ import annotations
import base64, csv, datetime as dt, hashlib, importlib.util, json, math, os, shutil, zipfile
from collections import defaultdict
from pathlib import Path

STRATEGY_ID = "mapp_strategy"
VARIANTS = ("absolute_reserved", "absolute_filled", "relative_reserved", "relative_filled")
POLICIES = ("unhedged25", "dollar_short25", "beta40_daily_short25")
VARIANT_LABELS = {
    "absolute_reserved": "Absolute SMA / reserve before gate",
    "absolute_filled": "Absolute SMA / reserve after fill",
    "relative_reserved": "Relative SMA / reserve before gate",
    "relative_filled": "Relative SMA / reserve after fill",
}
POLICY_LABELS = {
    "unhedged25": "No SPY hedge",
    "dollar_short25": "Fixed-dollar SPY short",
    "beta40_daily_short25": "Daily beta40 SPY short or flat",
}
COLORS = {"absolute_reserved": "#596775", "absolute_filled": "#D08A21",
          "relative_reserved": "#287DB5", "relative_filled": "#00897B"}
CAPITAL = 100000.0
KINDS = ("daily", "orders", "borrow", "baskets", "source_trades", "exante")
EXCLUDED = {"heading", "report_heading", "text", "paragraphs", "section_intro", "source_text"}

def dump(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")

def read(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle); rows = list(reader)
    return [] if reader.fieldnames == ["empty_ledger"] else rows

def write(path, rows):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys or ["empty_ledger"])
        writer.writeheader(); writer.writerows(rows)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def truth(value):
    return value is True or str(value).lower() == "true"

def case_root(root, metric):
    path = (root / metric.get("variant_root", "variants/" + metric["variant"])).resolve()
    assert path == (root / "variants" / metric["variant"]).resolve()
    return path

def rows_for(root, metric, kind):
    path = case_root(root, metric) / "results" / metric[kind + "_path"]
    assert path.parent == case_root(root, metric) / "results" and path.is_file()
    return read(path)

def clean(row):
    return {key: value for key, value in row.items() if key not in EXCLUDED}

def optional_financial_audit(root, summaries):
    spec = importlib.util.spec_from_file_location("mapp_relative_independent_ledger", root / "ci/independent_ledger.py")
    auditor = importlib.util.module_from_spec(spec); spec.loader.exec_module(auditor)
    result = {"ledger_audits": [], "beta_audits": [], "metrics": []}
    for variant in VARIANTS:
        auditor.configure(root / "variants" / variant)
        for metric in [m for m in summaries if m["variant"] == variant]:
            for name, function in (("ledger_audits", auditor.audit), ("beta_audits", auditor.audit_beta),
                                   ("metrics", auditor.case_metrics)):
                result[name].append({"variant": variant, **function(metric)})
    return result

def source_signatures(root, summaries):
    receipt = []
    for variant in VARIANTS:
        signatures = []
        for metric in [m for m in summaries if m["variant"] == variant]:
            baskets = rows_for(root, metric, "baskets")
            source = rows_for(root, metric, "source_trades")
            signatures.append([(r["basket_id"], r["report_date"], r["entry_date"], r["exit_date"],
                                r["exit_kind"], r["symbols"]) for r in baskets])
            if metric["policy"] == "unhedged25":
                assert int(metric["hedge_orders"]) == 0
                assert all(float(r["hedge_delta_qty"]) == 0 for r in rows_for(root, metric, "orders"))
                assert all(float(r["hedge_spy_qty"]) == 0 for r in rows_for(root, metric, "exante"))
            assert all(int(r["direction"]) in (-1, 1) for r in source)
        assert len(signatures) == 3 and all(s == signatures[0] for s in signatures)
        receipt.append({"variant": variant, "same_source_schedule_across_policies": True,
                        "baskets": len(signatures[0])})
    return receipt

def price_lookup(root):
    rows = read(root / "prices.csv")
    return {(r["symbol"], r["session_date"]): r for r in rows}

def group_contributions(baskets, source, prices):
    """Actual-account attribution; removing a group is not a new backtest."""
    legs = defaultdict(list)
    for row in source: legs[row["basket_id"]].append(row)
    by_entry_year = {}
    by_instrument = {}
    details = []
    for basket in baskets:
        held = legs[basket["basket_id"]]
        kind = basket["exit_kind"]
        key = "adjusted_open" if kind == "open" else "adjclose"
        spy_return = (float(prices["SPY", basket["exit_date"]][key]) /
                      float(prices["SPY", basket["entry_date"]]["adjusted_open"]) - 1)
        signed_notional = sum(float(l["qty"]) * float(l["entry_price"]) for l in held)
        market = signed_notional * spy_return * CAPITAL
        source_gross = float(basket["source_gross_pnl"]) * CAPITAL
        selection = source_gross - market
        record = dict(basket_id=basket["basket_id"], entry_date=basket["entry_date"],
                      exit_date=basket["exit_date"], entry_year=basket["entry_date"][:4],
                      mapped_instruments=basket["symbols"], source_gross_pnl_usd=source_gross,
                      spy_market_component_usd=market, selection_component_usd=selection,
                      net_pnl_usd=float(basket["net_pnl"]) * CAPITAL,
                      contains_XLE=any(l["symbol"] == "XLE" for l in held),
                      source_long_legs=sum(int(l["direction"]) > 0 for l in held),
                      source_short_legs=sum(int(l["direction"]) < 0 for l in held))
        details.append(record)
        year = by_entry_year.setdefault(record["entry_year"], {
            "baskets": 0, "source_gross_pnl_usd": 0., "spy_market_component_usd": 0.,
            "selection_component_usd": 0., "net_pnl_usd": 0.})
        year["baskets"] += 1
        for name in ("source_gross_pnl_usd", "spy_market_component_usd", "selection_component_usd", "net_pnl_usd"):
            year[name] += record[name]
        # Source-leg PnL is exact by instrument; account hedge/cost is not arbitrarily allocated to legs.
        for leg in held:
            group = by_instrument.setdefault(leg["symbol"], {
                "source_legs": 0, "source_long_legs": 0, "source_short_legs": 0,
                "source_gross_pnl_usd": 0., "spy_market_component_usd": 0., "selection_component_usd": 0.})
            group["source_legs"] += 1
            group["source_long_legs"] += int(leg["direction"]) > 0
            group["source_short_legs"] += int(leg["direction"]) < 0
            gross = float(leg["gross_pnl"]) * CAPITAL
            leg_market = float(leg["qty"]) * float(leg["entry_price"]) * spy_return * CAPITAL
            group["source_gross_pnl_usd"] += gross
            group["spy_market_component_usd"] += leg_market
            group["selection_component_usd"] += gross - leg_market
    selection_total = sum(r["selection_component_usd"] for r in details)
    selection_2026 = sum(r["selection_component_usd"] for r in details if r["entry_year"] == "2026")
    selection_xle = by_instrument.get("XLE", {}).get("selection_component_usd", 0.)
    xle_baskets = [r for r in details if r["contains_XLE"]]
    non_xle_baskets = [r for r in details if not r["contains_XLE"]]
    diagnostic = {
        "method": "Additive attribution on actual account notionals. Group removal is not a separately replayed strategy.",
        "by_entry_year": by_entry_year, "by_source_instrument": by_instrument,
        "gross_selection_component_usd": selection_total,
        "gross_selection_2026_entries_usd": selection_2026,
        "gross_selection_before_2026_entries_usd": selection_total - selection_2026,
        "gross_selection_XLE_legs_usd": selection_xle,
        "selection_share_from_2026_if_positive_total": selection_2026 / selection_total if selection_total > 1e-8 else None,
        "selection_share_from_XLE_if_positive_total": selection_xle / selection_total if selection_total > 1e-8 else None,
        "XLE_containing_baskets": len(xle_baskets),
        "XLE_containing_baskets_net_contribution_usd": sum(r["net_pnl_usd"] for r in xle_baskets),
        "other_baskets_net_contribution_usd": sum(r["net_pnl_usd"] for r in non_xle_baskets),
        "net_before_2026_entry_contribution_usd": sum(r["net_pnl_usd"] for r in details if r["entry_year"] < "2026"),
        "net_2026_entry_contribution_usd": sum(r["net_pnl_usd"] for r in details if r["entry_year"] == "2026"),
    }
    return diagnostic, details

def plot(root, summaries, coverage):
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/mapp_relative_clock_mpl")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.ticker import FuncFormatter
    fig, axes = plt.subplots(3, 1, figsize=(14, 11.4), sharex=True)
    fig.patch.set_facecolor("white")
    endpoint_checks = []
    for ax, policy in zip(axes, POLICIES):
        ax.set_facecolor("#FAFCFD")
        ax.grid(axis="y", color="#D9E0E5", linewidth=.7)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(colors="#435563", labelsize=9)
        for missing in coverage.get("missing_months", []):
            start = dt.date.fromisoformat(missing + "-01")
            end = (start.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
            ax.axvspan(start, end, color="#8C9AA3", alpha=.10, lw=0)
        for variant in VARIANTS:
            metric = next(m for m in summaries if m["policy"] == policy and m["variant"] == variant)
            rows = rows_for(root, metric, "daily")
            dates = [dt.date.fromisoformat(rows[0]["date"]) - dt.timedelta(days=1)] + [dt.date.fromisoformat(r["date"]) for r in rows]
            values = [1.] + [float(r["nav"]) for r in rows]
            peak = 1.; dd = []
            for value in values:
                peak = max(peak, value); dd.append(value / peak - 1)
            assert math.isclose(values[-1] - 1, float(metric["total_return"]), abs_tol=1e-10)
            assert math.isclose(min(dd), float(metric["max_drawdown"]), abs_tol=1e-10)
            label = VARIANT_LABELS[variant] + "  " + format(float(metric["total_return"]), "+.2%")
            ax.plot(dates, [(v - 1) * CAPITAL for v in values], lw=1.6, color=COLORS[variant], label=label)
            endpoint_checks.append({"variant": variant, "policy": policy, "end": rows[-1]["date"],
                                    "ending_nav_usd": values[-1] * CAPITAL, "max_drawdown": min(dd)})
        ax.axhline(0, color="#708391", lw=.7)
        ax.set_title(POLICY_LABELS[policy], loc="left", fontsize=12, color="#253B49", pad=7)
        ax.set_ylabel("Cumulative PnL ($)", color="#253B49")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, position: format(value, ",.0f")))
        ax.legend(loc="best", fontsize=8.2, frameon=True, facecolor="white", edgecolor="#D9E0E5")
    axes[-1].xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    first, last = summaries[0]["start"], summaries[0]["end"]
    fig.suptitle("Part 4 mapped sectors: gate and reservation-clock comparison",
                 x=.075, y=.979, ha="left", fontsize=17, fontweight="bold", color="#253B49")
    fig.text(.075, .948, first + " to " + last + " | $100,000 per account | 25% source allocation | daily-close NAV",
             fontsize=10, color="#526976")
    fig.text(.075, .061, "Four predeclared variants; no RSI, weekly gate, stop-loss, new regime filter or parameter search.",
             fontsize=9, color="#526976")
    fig.text(.075, .042, "Net of 10 bp per net physical order and 3% annual short borrow. Shaded absent-report months allow exits, not new entries.",
             fontsize=8.5, color="#526976")
    fig.text(.075, .023, "Hedges are short SPY or flat; realized market beta is reported separately. Reconstructed reports; historical availability is assumed.",
             fontsize=8, color="#697C87")
    fig.subplots_adjust(left=.075, right=.975, top=.917, bottom=.112, hspace=.24)
    destination = root / "figures"; destination.mkdir(exist_ok=True)
    png = destination / "mapp_strategy_relative_clock_pnl.png"
    svg = destination / "mapp_strategy_relative_clock_pnl.svg"
    fig.savefig(png, dpi=160, facecolor=fig.get_facecolor())
    fig.savefig(svg, facecolor=fig.get_facecolor()); plt.close(fig)
    manifest = {"strategy_id": STRATEGY_ID, "status": "passed", "start": first, "end": last,
                "endpoint_checks": endpoint_checks,
                "files": {p.name: {"bytes": p.stat().st_size, "sha256": sha(p)} for p in (png, svg)}}
    dump(destination / "relative_clock_plot_manifest.json", manifest)
    return [png, svg, destination / "relative_clock_plot_manifest.json"]

def export_attempts(root, publication):
    attempts = []; qualifications = []
    for variant in VARIANTS:
        prepared = json.loads((root / "variants" / variant / "inputs/main_archive_replay_prepared.json").read_text())
        funded = {str(b["basket_id"]) for b in prepared["cohorts"]["etf_own"]}
        for row in prepared.get("etf_opportunities", []):
            attempt = {key: row.get(key, "") for key in ("clock_id", "date", "report_date", "available_at",
                      "source_sha256", "source_version_id", "scheduled_exit", "exit_kind")}
            held = str(row["clock_id"]) in funded
            targets = json.loads(row["targets"]) if isinstance(row["targets"], str) else row["targets"]
            targets = [{key: leg[key] for key in ("symbol", "direction", "source_eligible", "source_eligibility_reason") if key in leg}
                       for leg in targets]
            attempt.update(strategy_id=STRATEGY_ID, variant=variant, funded=held,
                           actually_reserved=variant.endswith("_reserved") or held, targets=json.dumps(targets))
            attempts.append(attempt)
        for row in prepared.get("etf_qualification", []):
            qualifications.append({"strategy_id": STRATEGY_ID, "variant": variant, "trend_gate": variant.split("_")[0], "prior_value_kind": "ratio_to_SPY" if variant.startswith("relative") else "adjusted_close", **clean(row)})
    write(publication / "entry_attempts.csv", attempts)
    write(publication / "entry_qualification.csv", qualifications)
    return {"attempt_rows": len(attempts), "qualification_rows": len(qualifications)}

def stream_payload(path, kind):
    payload = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    chunks = [payload[i:i + 14000] for i in range(0, len(payload), 14000)]
    print("MAPP_RELATIVE_" + kind + "_BASE64_BEGIN " +
          json.dumps({"name": Path(path).name, "bytes": Path(path).stat().st_size,
                      "sha256": sha(path), "chunks": len(chunks)}, sort_keys=True), flush=True)
    for i, chunk in enumerate(chunks, 1):
        print("MAPP_RELATIVE_" + kind + "_CHUNK " + str(i) + "/" + str(len(chunks)) + " " + chunk, flush=True)
    print("MAPP_RELATIVE_" + kind + "_BASE64_END", flush=True)

def publish_outputs(root, summaries, coverage, protocol, schedule_receipt, ledger_receipts=None):
    root = Path(root).resolve()
    expected = {(v, p) for v in VARIANTS for p in POLICIES}
    assert len(summaries) == 12 and {(m["variant"], m["policy"]) for m in summaries} == expected
    assert all(m["status"] == "ok" and m["scope"] == "main" and m["family"] == "etf_own" for m in summaries)
    assert len({(m["start"], m["end"], m["corpus"]) for m in summaries}) == 1
    if ledger_receipts is None: ledger_receipts = optional_financial_audit(root, summaries)
    assert all(len(ledger_receipts[name]) == 12 for name in ("ledger_audits", "beta_audits", "metrics"))
    assert all(r["status"] == "passed" for name in ("ledger_audits", "beta_audits") for r in ledger_receipts[name])
    source_checks = source_signatures(root, summaries)
    diagnostic = {"strategy_id": STRATEGY_ID, "status": "passed", "cases": 12,
                  "method": "Independent physical-order, cash/NAV, ACT365 borrow and beta reconstruction; separate entry-clock audit.",
                  "same_source_schedule_within_each_variant": source_checks, **ledger_receipts}
    publication = root / "publication_relative_clock"
    assert not publication.exists(), "Do not overwrite an existing publication directory"
    publication.mkdir()
    dump(publication / "summary.json", summaries)
    dump(publication / "coverage.json", coverage)
    dump(publication / "protocol.json", protocol)
    dump(publication / "diagnosis/independent_results.json", diagnostic)
    dump(publication / "diagnosis/entry_clock_audit.json", schedule_receipt)
    prices = price_lookup(root)
    metrics = []; year_rows = []; concentration = []; entry_details = []
    for metric in summaries:
        variant, policy = metric["variant"], metric["policy"]
        independent = next(m for m in ledger_receipts["metrics"] if m["variant"] == variant and m["policy"] == policy)
        baskets = rows_for(root, metric, "baskets"); source = rows_for(root, metric, "source_trades")
        daily = rows_for(root, metric, "daily")
        assert daily and math.isclose(float(daily[-1]["nav"]) - 1, float(metric["total_return"]), abs_tol=1e-10)
        assert math.isclose(sum(float(b["net_pnl"]) for b in baskets), float(metric["total_return"]), abs_tol=1e-10)
        attribution, detail = group_contributions(baskets, source, prices)
        concentration.append({"variant": variant, "policy": policy, **attribution})
        entry_details.extend({"strategy_id": STRATEGY_ID, "variant": variant, "policy": policy, **row} for row in detail)
        duration = (dt.date.fromisoformat(metric["end"]) - dt.date.fromisoformat(metric["start"])).days / 365.25
        row = {key: value for key, value in independent.items() if not isinstance(value, (dict, list))}
        row.update(strategy_id=STRATEGY_ID, variant=variant, policy=policy,
                   annualized_return=(1 + float(metric["total_return"])) ** (1 / duration) - 1,
                   net_pnl_usd=float(metric["total_return"]) * CAPITAL,
                   transaction_cost_usd=float(metric["transaction_cost"]) * CAPITAL,
                   borrow_cost_usd=float(metric["borrow_cost"]) * CAPITAL,
                   all_day_realized_beta=independent["realized_all"]["beta"],
                   active_day_realized_beta=independent["realized_active"]["beta"],
                   source_legs=len(source),
                   source_long_legs=sum(int(l["direction"]) > 0 for l in source),
                   source_short_legs=sum(int(l["direction"]) < 0 for l in source),
                   winning_baskets=sum(float(b["net_pnl"]) > 0 for b in baskets),
                   max_abs_net_exposure=float(metric["max_abs_net_exposure"]),
                   average_signed_exposure_open=sum(float(d["signed_exposure_open"]) for d in daily) / len(daily),
                   average_abs_net_exposure_open=sum(abs(float(d["signed_exposure_open"])) for d in daily) / len(daily),
                   net_before_2026_entry_contribution_usd=attribution["net_before_2026_entry_contribution_usd"],
                   net_2026_entry_contribution_usd=attribution["net_2026_entry_contribution_usd"],
                   XLE_containing_baskets_net_contribution_usd=attribution["XLE_containing_baskets_net_contribution_usd"],
                   other_baskets_net_contribution_usd=attribution["other_baskets_net_contribution_usd"])
        metrics.append(row)
        year_rows.extend({"strategy_id": STRATEGY_ID, "variant": variant, "policy": policy, **yr}
                         for yr in independent["calendar_year_returns"])
        for kind in KINDS:
            rows = rows_for(root, metric, kind)
            write(publication / "results" / variant / metric[kind + "_path"],
                  [{"strategy_id": STRATEGY_ID, "variant": variant, **clean(r)} for r in rows])
    write(publication / "metrics.csv", metrics)
    write(publication / "calendar_year_returns.csv", year_rows)
    write(publication / "entry_cohort_attribution.csv", entry_details)
    dump(publication / "concentration.json", concentration)
    for name in ("all_trades.csv", "all_orders.csv", "all_daily_nav.csv"):
        assert (root / name).is_file(), str(root / name)
        write(publication / name, [clean(row) for row in read(root / name)])
    attempt_receipt = export_attempts(root, publication)
    for name in ("relative_clock_protocol.json", "relative_clock_input_freeze.json", "relative_clock_provenance.json",
                 "baseline_comparison.json", "relative_clock_schedule_audit.json", "relative_clock_ledger_audits.json",
                 "audit/extended_inputs.json", "audit/relative_clock_inputs.json"):
        if (root / name).exists():
            target = publication / name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / name, target)
    figures = plot(root, summaries, coverage)
    for path in figures:
        target = publication / "figures" / path.name; target.parent.mkdir(exist_ok=True); shutil.copyfile(path, target)
    lines = [
        "# mapp_strategy: relative-strength gate and fill-only reservation\n",
        "Four predeclared variants are compared on one coherent source/price campaign: absolute_reserved (existing control), absolute_filled (clock change), relative_reserved (gate change), relative_filled (both changes). Each is simulated with the three unchanged hedge policies.\n",
        "All use Part 4 only, the frozen stock-to-ETF mapping, 25% source allocation, 10-session maximum holding clock (21 calendar-day cap), 10 bp per net physical order, 3% ACT365 net-short borrow and zero cash yield. Rejected original target weights remain cash.\n",
        "Relative strength is the adjusted ETF/SPY ratio, measured strictly before entry: the last completed ratio must be above its previous-20-close average for longs and below it for shorts. SPY/SPY is constant and fails either strict inequality. This is a replacement for the absolute gate, not an additional filter.\n",
        "Fill-only reservation consumes a rejected report without starting a reservation or cooldown. The next new report may qualify. A funded trade retains its ordinary time exit, release-day exclusion and full following-session cooldown. Reserved variants consume the full window after rejection.\n",
        "## Net results\n",
        "| Policy | Variant | Net return | Max drawdown | Baskets | Realized all-day SPY beta |\n",
        "|---|---|---:|---:|---:|---:|\n",
    ]
    for policy in POLICIES:
        for variant in VARIANTS:
            row = next(r for r in metrics if r["policy"] == policy and r["variant"] == variant)
            beta = "n/a" if row["all_day_realized_beta"] is None else format(row["all_day_realized_beta"], ".3f")
            lines.append("| " + POLICY_LABELS[policy] + " | " + variant + " | " + format(float(row["total_return"]), "+.2%") +
                         " | " + format(float(row["max_drawdown"]), ".2%") + " | " + str(row["baskets"]) + " | " + beta + " |\n")
    lines += [
        "\n![Daily-close PnL for all twelve accounts](figures/mapp_strategy_relative_clock_pnl.png)\n",
        "Hedges never buy SPY. Dollar neutrality and beta neutrality differ; source shorts or negative-beta sources can leave exposure that a short-only hedge cannot remove. The metrics report all-day and active-day realized beta and short-only constraints.\n",
        "Annual returns are calendar returns. Entry-cohort and instrument diagnostics are attribution on the actual compounded account, not new backtests with 2026 or XLE removed. Source-leg instrument PnL excludes arbitrary allocation of account-level hedge PnL and costs.\n",
        "Missing months create no new entries; normal exits and hedges continue. Source reports are current reconstructed snapshots with assumed printed-date historical availability. Comparison to an earlier saved control is reported separately; a new price/source vintage is not silently treated as identical.\n",
        "There is no RSI, weekly filter, new stop-loss, added macro-regime filter or parameter search. The reports, raw prices and extracted prose remain local. Published data are code, simulated trades/orders/NAV and audit metadata.\n",
        "Entry attempts and qualification CSVs retain rejected-candidate dates, mapped targets, gate inputs and reasons without report prose. A scheduled exit on an unfunded fill-only attempt is hypothetical; actually_reserved distinguishes it from a real lockout.\n",
        "[All trades](all_trades.csv) · [All orders](all_orders.csv) · [Metrics](metrics.csv) · [Calendar returns](calendar_year_returns.csv) · [Concentration](concentration.json) · [Entry attempts](entry_attempts.csv) · [Qualification](entry_qualification.csv)\n",
    ]
    (publication / "README.md").write_text("\n".join(lines), encoding="utf-8")
    manifest = {"strategy_id": STRATEGY_ID, "status": "passed", "files": {}}
    for path in sorted(publication.rglob("*")):
        if path.is_file(): manifest["files"][str(path.relative_to(publication))] = {"bytes": path.stat().st_size, "sha256": sha(path)}
    dump(publication / "manifest.json", manifest)
    archive = root / "mapp_strategy_relative_clock_simulated_results.zip"
    assert not archive.exists()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(publication.rglob("*")):
            if path.is_file(): bundle.write(path, path.relative_to(publication))
    receipt = {"strategy_id": STRATEGY_ID, "status": "passed", "cases": 12,
               "start": summaries[0]["start"], "end": summaries[0]["end"], "books": metrics,
               "missing_months": coverage.get("missing_months", []), "entry_audit": attempt_receipt,
               "concentration": concentration,
               "archive": {"name": archive.name, "bytes": archive.stat().st_size, "sha256": sha(archive)}}
    print("MAPP_RELATIVE_SUMMARY_JSON " + json.dumps(receipt, sort_keys=True, allow_nan=False), flush=True)
    stream_payload(root / "figures/mapp_strategy_relative_clock_pnl.png", "PNG")
    stream_payload(archive, "ZIP")
    for name, kind in (("metrics.csv", "METRICS"), ("calendar_year_returns.csv", "YEARS"),
                       ("all_trades.csv", "TRADES")):
        stream_payload(publication / name, kind)
    return receipt
