"""Four predeclared Part 4 tests: absolute/relative SMA20 x reservation clock.

The original mapped universe, sizing, holding period, net physical-order costs,
borrow and three hedge policies remain unchanged. Raw research and price inputs
stay local. All four schedules share one source/price campaign.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ("absolute_reserved", "absolute_filled", "relative_reserved", "relative_filled")
POLICIES = ("unhedged25", "dollar_short25", "beta40_daily_short25")
CORPUS = "archive_replay"
FAMILY = "etf_own"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def relative_sma(data, symbol, day, direction):
    """Strictly prior 20 completed adjusted-close ratios; no entry/held future."""
    index = data.index[day]
    days = data.days[max(0, index - 20):index]
    values = []
    for prior in days:
        sector = data.maybe(symbol, prior, "close")
        spy = data.maybe("SPY", prior, "close")
        if sector is None or spy is None:
            return False, None, None
        values.append(sector / spy)
    if len(values) != 20:
        return False, None, None
    latest = values[-1]
    average = sum(values) / 20.0
    aligned = latest > average if direction > 0 else latest < average
    return bool(aligned), latest, average


def qualify(helper, data, row, day, clock_id, trend):
    if trend == "absolute":
        return helper.qualify(data, row, day, clock_id, "etf")
    assert trend == "relative"
    count = len(row["legs"])
    accepted, records = [], []
    for target in row["legs"]:
        symbol, direction = target["symbol"], int(target["direction"])
        eligible, reason = data.eligible(symbol, day, "etf")
        if target.get("source_eligible") is False:
            eligible, reason = False, target.get("source_eligibility_reason", "source_ineligible_foreign_listing")
        aligned, latest, average = relative_sma(data, symbol, day, direction)
        if eligible and not aligned:
            eligible, reason = False, "crowd_direction_not_relative_sma20_aligned"
        weight = 1.0 / count
        records.append(dict(
            clock_id=clock_id, date=day, report_date=row["report_date"],
            symbol=symbol, direction=direction, original_weight=weight,
            eligible=eligible, reason=reason,
            prior_close=latest, prior_sma20=average,
            beta40=data.beta(symbol, day), available_at=row["available_at"],
            source_sha256=row["source_sha256"],
        ))
        if eligible:
            accepted.append(dict(symbol=symbol, direction=direction, weight=weight))
    return accepted, records


def variant_clock(helper, data, items, start, end, allowed_months, trend, reservation):
    """A failed SMA attempt consumes that report, never manufacturing a trade.

    Under 'filled', a failed attempt creates neither reservation nor cooldown.
    The basic metadata/liquidity prescreen stays identical to the frozen clock.
    """
    assert trend in ("absolute", "relative")
    assert reservation in ("reserved", "filled")
    events = defaultdict(list)
    for row in items:
        first = next((day for day in data.days
                      if day > row["report_date"] and helper.opening(day) > helper.stamp(row["available_at"])), None)
        if first:
            events[first].append(row)
    opportunities, cohorts, qualifications = [], [], []
    latest = None
    reserved_until = None
    last_exit = -1000
    last_report = None
    allowed = set(allowed_months)
    for day in (day for day in data.days if day <= end):
        index = data.index[day]
        for row in events.get(day, []):
            if latest is None or row["report_date"] > latest["report_date"]:
                latest = row
        if day < start:
            continue
        if reserved_until is not None and index >= reserved_until:
            reserved_until = None
            last_exit = index
        if day[:7] not in allowed:
            continue
        if reserved_until is not None or index <= last_exit + 1 or latest is None or latest["report_date"] == last_report:
            continue
        age = (dt.date.fromisoformat(day) - dt.date.fromisoformat(latest["report_date"])).days
        if age > 4 or not latest["legs"] or not any(
            target.get("source_eligible") is not False
            and data.eligible(target["symbol"], day, "etf")[0]
            for target in latest["legs"]
        ):
            continue
        ident = len(opportunities) + 1
        exit_day, exit_kind, censored = helper.expiry(data, day, end)
        opportunities.append(dict(
            clock_id=ident, date=day, report_date=latest["report_date"],
            source_sha256=latest["source_sha256"], source_version_id=latest["source_version_id"],
            available_at=latest["available_at"], targets=json.dumps(latest["legs"]),
            scheduled_exit=exit_day, exit_kind=exit_kind,
        ))
        accepted, records = qualify(helper, data, latest, day, ident, trend)
        qualifications.extend(records)
        if accepted:
            cohorts.append(dict(
                basket_id=str(ident), entry_date=day, exit_date=exit_day, exit_kind=exit_kind,
                report_date=latest["report_date"], heading=latest["heading"],
                source_sha256=latest["source_sha256"], terminal_censored=censored, legs=accepted,
            ))
        last_report = latest["report_date"]
        if reservation == "reserved" or accepted:
            reserved_until = data.index[exit_day] if not censored else len(data.days) + 1
    assert all(cohort["entry_date"][:7] in allowed for cohort in cohorts)
    return opportunities, cohorts, qualifications


def prepare_variant(extension, helper, data, items, start, end, coverage, variant):
    trend, reservation = variant.split("_")
    attempt, cohort, qualification = variant_clock(
        helper, data, items, start, end, coverage["available_months"], trend, reservation
    )
    if variant == "absolute_reserved":
        original = extension.monthly_clock(helper, data, items, start, end, coverage["available_months"])
        assert (attempt, cohort, qualification) == original, "Original reservation/filter control changed"
        # The control is the untouched original implementation, after proving equivalence.
        attempt, cohort, qualification = original
    return dict(
        scope="main", start=start, end=end, source_min=start,
        cohorts={FAMILY: cohort}, etf_opportunities=attempt,
        etf_qualification=qualification, available_entry_months=coverage["available_months"],
        missing_months=coverage["missing_months"],
    )


def link_shared(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    assert not target.exists()
    try:
        os.link(source, target)
    except OSError:
        shutil.copyfile(source, target)
    assert sha(source) == sha(target)


def baseline_comparison(root, summaries, prepared_by_variant):
    """Disclose refreshed public-vintage differences rather than reuse old PnL."""
    path = root / "backtests/2022_2026_month_gaps"
    result = {
        "reference": "Committed January 2022–November 20, 2026 simulation.",
        "reference_path": str(path.relative_to(root)),
        "current_control": "absolute_reserved",
        "prior_price_vintage_identity_claimed": False,
        "fresh_all_four_variants_share_one_input_campaign": True,
        "reference_available": (path / "all_trades.csv").is_file() and (path / "summary.json").is_file(),
    }
    if not result["reference_available"]:
        result.update(status="reference_unavailable", message="Current control is still a full unchanged-rule rerun.")
        dump(root / "baseline_comparison.json", result)
        return result
    import csv
    with (path / "all_trades.csv").open(newline="", encoding="utf-8") as handle:
        old_trades = list(csv.DictReader(handle))
    old_summary = json.loads((path / "summary.json").read_text(encoding="utf-8"))
    if isinstance(old_summary, dict):
        old_summary = old_summary.get("books", old_summary.get("summary", []))
    fresh = {metric["policy"]: metric for metric in summaries if metric["variant"] == "absolute_reserved"}
    cohorts = prepared_by_variant["absolute_reserved"]["cohorts"][FAMILY]
    current_signature = [
        (cohort["basket_id"], cohort["report_date"], cohort["entry_date"], cohort["exit_date"],
         cohort["exit_kind"], "|".join(leg["symbol"] for leg in cohort["legs"]),
         tuple(sorted((leg["symbol"], int(leg["direction"])) for leg in cohort["legs"])))
        for cohort in cohorts
    ]
    cases = []
    for policy in POLICIES:
        old_rows = [row for row in old_trades if row["policy"] == policy]
        old_signature = [
            (row["basket_id"], row["report_date"], row["entry_date"], row["exit_date"], row["exit_kind"],
             row["symbols"], tuple(sorted((symbol, int(direction)) for symbol, direction in json.loads(row["source_directions"]).items())))
            for row in old_rows
        ]
        previous = next((row for row in old_summary if row["policy"] == policy), None)
        now = fresh[policy]
        delta = {}
        for key in ("total_return", "max_drawdown", "transaction_cost", "borrow_cost", "baskets"):
            if previous is not None and key in previous:
                delta[key] = float(now[key]) - float(previous[key])
        cases.append(dict(
            policy=policy, same_funded_schedule_and_directions=(current_signature == old_signature),
            reference_baskets=len(old_rows), current_baskets=len(cohorts),
            metric_deltas=delta,
        ))
    exact = all(case["same_funded_schedule_and_directions"] and all(abs(value) < 1e-10 for value in case["metric_deltas"].values()) for case in cases)
    result.update(
        status="matching_saved_control" if exact else "refreshed_input_vintage_difference",
        cases=cases,
        message="This study reports its current unchanged-rule control alongside all three new schedules; earlier saved returns are not substituted.",
    )
    dump(root / "baseline_comparison.json", result)
    print("MAPP_RELATIVE_CLOCK_BASELINE " + json.dumps(result, sort_keys=True), flush=True)
    return result


def run(root, start, end, coverage):
    extension = module("mapp_relative_extension", root / "ci/run_extended_history.py")
    sys.path.insert(0, str(root / "engine"))
    import data as helper
    import run_nohedge as model
    helper.ROOT = root
    data = helper.Data(root)
    assert end in data.index and start <= end
    assert all(sum(day < start for day in series) >= 41 for series in data.rows.values()), "Missing warmup"
    assert all(data.maybe(symbol, end, "close") is not None for symbol in data.rows), "Incomplete endpoint"
    coverage["actual_end"] = end
    items, _ = helper.load_items(data, CORPUS, "etf", start)
    prepared = {
        variant: prepare_variant(extension, helper, data, items, start, end, coverage, variant)
        for variant in VARIANTS
    }
    # Existing source/raw-price preflight reads the original shared-root control.
    dump(root / "inputs/main_archive_replay_prepared.json", prepared["absolute_reserved"])
    protocol = dict(
        strategy_id="mapp_strategy", experiment="relative_strength_and_fill_clock_v1",
        start=start, end=end, variants=list(VARIANTS), policies=list(POLICIES),
        cases=12, primary_policy="dollar_short25", initial_capital_usd=100000,
        source_allocation=.25, source_slot=4, sma_sessions=20,
        absolute_gate="Previous adjusted close strictly above prior20-close mean for longs; inverse for shorts.",
        relative_gate="Previous sector/SPY adjusted-close ratio strictly above prior20-ratio mean for longs; inverse for shorts. SPY ratio is constant and fails the strict test.",
        reserved_clock="Reserve before SMA even if all legs fail; after release skip release session and following session.",
        filled_clock="A rejected basic-eligible SMA attempt consumes its report without reservation/cooldown. Next new report may qualify. A funded basket retains original reservation and cooldown.",
        unchanged_basic_prescreen="Latest ready report at most four calendar days old; at least one metadata/liquidity-eligible mapped leg before qualification.",
        weights="Original distinct mapped-target weights; rejected weights remain cash, without renormalization.",
        exit="Opening of tenth subsequent SPY session, at most21 calendar days; terminal endpoint-close liquidation is flagged.",
        fees_per_net_physical_order=.001, short_borrow_act365=.03, cash_interest=0.,
        hedges="No hedge; fixed entry-dollar SPY short; daily strictly-prior40-return beta SPY short/flat. Hedge never buys SPY.",
        no_parameter_search=True, filters_excluded=["RSI", "weekly", "new stop", "regime filter"],
        monthly_gap_rule=coverage["missing_month_rule"],
        source_availability=coverage["source_availability"],
        baseline_comparison_path="baseline_comparison.json",
        qualification_columns="For relative variants prior_close and prior_sma20 are ratio values; for absolute variants they are adjusted prices.",
        frozen_core_sha256=extension.FROZEN,
    )
    dump(root / "relative_clock_protocol.json", protocol)
    input_paths = [
        "prices.csv", "market_manifest.json", "market/fetch_campaign.json",
        "inputs/archival_replay_etf_items.csv", "inputs/main_archive_replay_prepared.json",
        "source/archive_inventory.json", "source/canonical_html_manifest.json",
        "source/public_date_inventory_metadata.json", "source/public_date_inventory.json",
        "source/archive_index_metadata.json", "source/archive_index.html", "relative_clock_protocol.json",
    ]
    for variant, value in prepared.items():
        case_root = root / "variants" / variant
        assert not case_root.exists(), "Use a fresh directory for each run"
        (case_root / "results").mkdir(parents=True)
        dump(case_root / "inputs/main_archive_replay_prepared.json", value)
        for name in ("prices.csv", "market_manifest.json"):
            link_shared(root / name, case_root / name)
        input_paths += [
            str((case_root / "inputs/main_archive_replay_prepared.json").relative_to(root)),
            str((case_root / "prices.csv").relative_to(root)),
            str((case_root / "market_manifest.json").relative_to(root)),
        ]
    frozen = {path: sha(root / path) for path in input_paths}
    dump(root / "relative_clock_input_freeze.json", dict(
        created_utc=dt.datetime.now(dt.timezone.utc).isoformat(), sha256=frozen,
        variants=list(VARIANTS), policies=list(POLICIES), cases=12,
        declaration="All four schedules fixed before their portfolio returns; no parameter search.",
    ))
    source_auditor = module("mapp_relative_source_audit", root / "ci/extended_input_audit.py")
    original_receipt = source_auditor.audit_inputs(root, start, end, coverage["available_months"])
    schedule_auditor = module("mapp_relative_schedule_audit", root / "ci/relative_clock_audit.py")
    schedule_receipt = schedule_auditor.audit_variants(root, prepared)
    assert all(sha(root / path) == value for path, value in frozen.items()), "Input changed in preflight"
    dump(root / "relative_clock_schedule_audit.json", schedule_receipt)
    summaries, trades, orders, daily_nav = [], [], [], []
    ledger_receipts = dict(ledger_audits=[], beta_audits=[], metrics=[])
    auditor = module("mapp_relative_independent_ledger", root / "ci/independent_ledger.py")
    for variant in VARIANTS:
        case_root = root / "variants" / variant
        model.INPUT = case_root / "inputs"
        model.OUT = case_root / "results"
        source_by_id = {cohort["basket_id"]: cohort for cohort in prepared[variant]["cohorts"][FAMILY]}
        case_summaries = []
        signatures = {}
        for policy in POLICIES:
            book = model.simulate(data, CORPUS, policy, FAMILY)
            metric = book["metric"]
            metric.update(strategy_id="mapp_strategy", variant=variant, variant_root="variants/" + variant)
            for kind, rows in book.items():
                if kind == "metric":
                    continue
                for row in rows:
                    row["strategy_id"] = "mapp_strategy"
                filename = CORPUS + "_" + policy + "_" + kind + ".csv"
                model.write(model.OUT / filename, rows)
                metric[kind + "_path"] = filename
            signatures[policy] = [
                (row["basket_id"], row["report_date"], row["entry_date"], row["exit_date"], row["exit_kind"], row["symbols"])
                for row in book["baskets"]
            ]
            if policy == "unhedged25":
                assert metric["hedge_orders"] == 0
                assert all(float(row["hedge_delta_qty"]) == 0. for row in book["orders"])
                assert all(float(row["hedge_spy_qty"]) == 0. for row in book["exante"])
            for row in book["baskets"]:
                cohort = source_by_id[str(row["basket_id"])]
                record = dict(
                    variant=variant, corpus=CORPUS, policy=policy, **row,
                    mapped_etfs="|".join(leg["symbol"] for leg in cohort["legs"]),
                    source_directions=json.dumps({leg["symbol"]: leg["direction"] for leg in cohort["legs"]}),
                )
                for key in ("entry_nav", "source_entry_notional", "source_gross_pnl", "hedge_gross_pnl", "transaction_cost", "borrow_cost", "net_pnl"):
                    record[key + "_usd"] = float(row[key]) * 100000
                record["net_pnl_fraction_of_entry_nav"] = float(row["net_pnl"]) / float(row["entry_nav"])
                trades.append(record)
            for row in book["orders"]:
                record = dict(variant=variant, corpus=CORPUS, policy=policy, **row)
                for key in ("notional", "fee"):
                    record[key + "_usd"] = float(row[key]) * 100000
                for key in ("qty_before", "qty_after", "delta_qty", "source_delta_qty", "hedge_delta_qty"):
                    record[key + "_units_for_100000_initial_account"] = float(row[key]) * 100000
                orders.append(record)
            daily_nav.extend(dict(variant=variant, corpus=CORPUS, policy=policy, **row, nav_usd=float(row["nav"]) * 100000) for row in book["daily"])
            summaries.append(metric)
            case_summaries.append(metric)
        assert all(signature == signatures["unhedged25"] for signature in signatures.values()), "Hedge policy changed source schedule"
        model.dump(model.OUT / "summary.json", case_summaries)
        auditor.configure(case_root)
        for metric in case_summaries:
            for key, call in (("ledger_audits", auditor.audit), ("beta_audits", auditor.audit_beta), ("metrics", auditor.case_metrics)):
                receipt = call(metric)
                receipt["variant"] = variant
                ledger_receipts[key].append(receipt)
        print("MAPP_RELATIVE_CLOCK_VARIANT_DONE " + json.dumps(dict(
            variant=variant, attempts=len(prepared[variant]["etf_opportunities"]),
            funded_baskets=len(source_by_id),
            metrics=[{key: metric[key] for key in ("policy", "total_return", "max_drawdown", "baskets")} for metric in case_summaries],
        ), sort_keys=True), flush=True)
    assert len(summaries) == 12
    model.write(root / "all_trades.csv", trades)
    model.write(root / "all_orders.csv", orders)
    model.write(root / "all_daily_nav.csv", daily_nav)
    dump(root / "relative_clock_summary.json", summaries)
    dump(root / "relative_clock_ledger_audits.json", ledger_receipts)
    baseline = baseline_comparison(root, summaries, prepared)
    assert all(sha(root / path) == value for path, value in frozen.items()), "Input changed after freeze"
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "local-unrecorded"
    dump(root / "relative_clock_provenance.json", dict(
        strategy_id="mapp_strategy", code_commit=commit,
        input_freeze_sha256=sha(root / "relative_clock_input_freeze.json"),
        frozen_input_hashes_unchanged=True, frozen_core_sha256=extension.FROZEN,
        runner_sha256=sha(Path(__file__)), source_input_audit_status=original_receipt["status"],
        schedule_audit_status=schedule_receipt["status"],
        baseline_comparison_status=baseline["status"],
        sources="One freshly fetched public archive campaign shared by all four schedules; historical availability assumed.",
        market="One freshly fetched Yahoo adjusted-price campaign shared by all twelve portfolios.",
    ))
    outputs = module("mapp_relative_outputs", root / "ci/relative_clock_outputs.py")
    return outputs.publish_outputs(root, summaries, coverage, protocol, schedule_receipt, ledger_receipts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--start", default="2022-01-01")
    parser.add_argument("--end", default="2026-11-20")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--prices-ready", action="store_true", help="Use an already downloaded campaign; still fully audited.")
    args = parser.parse_args()
    root = args.root.resolve()
    assert args.start == "2022-01-01" and dt.date.fromisoformat(args.start) <= dt.date.fromisoformat(args.end)
    assert 1 <= args.workers <= 16
    assert not (root / "variants").exists() and not (root / "relative_clock_summary.json").exists(), "Use a fresh checkout/directory"
    extension = module("mapp_relative_source_extension", root / "ci/run_extended_history.py")
    assert all(sha(root / path) == expected for path, expected in extension.FROZEN.items()), "Frozen economic engine or mapping changed"
    schedule_self_test = module("mapp_relative_schedule_self_test", root / "ci/relative_clock_audit.py")
    schedule_self_test.self_test()
    coverage = extension.source_inputs(root, args.start, args.end, args.workers)
    if not args.prices_ready:
        extension.fetch_market(root, args.start, args.end)
    run(root, args.start, args.end, coverage)


if __name__ == "__main__":
    main()
