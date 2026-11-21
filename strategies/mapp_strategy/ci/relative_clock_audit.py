"""Independent clock and entry-filter audit for the four relative-strength variants.

Reads frozen prices, ETF metadata and mapped Part 4 inputs directly. It imports
no production clock, qualification, SMA or portfolio-simulation function.
Raw research and market data remain on the execution runner.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
VARIANTS = (
    "absolute_reserved", "absolute_filled", "relative_reserved", "relative_filled"
)
EXCHANGES = {
    "NYQ", "NMS", "NGM", "NCM", "ASE", "PCX", "BTS", "BATS", "CBOE",
    "NYSEArca", "NasdaqGM", "NasdaqGS", "NasdaqCM",
}


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def timestamp(value):
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def opening(day):
    return dt.datetime.combine(dt.date.fromisoformat(day), dt.time(9, 30), NY)


def same(expected, actual, trail=""):
    """Check every independently expected field, permitting descriptive extras."""
    if isinstance(expected, dict):
        assert isinstance(actual, dict) and set(expected) <= set(actual), trail
        for key, value in expected.items():
            same(value, actual[key], trail + "/" + str(key))
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(expected) == len(actual), (
            trail, len(expected), len(actual)
        )
        for i, (left, right) in enumerate(zip(expected, actual)):
            same(left, right, trail + "/" + str(i))
    elif isinstance(expected, bool):
        assert expected is actual, (trail, expected, actual)
    elif isinstance(expected, (int, float)):
        assert actual is not None and not isinstance(actual, bool), trail
        assert math.isclose(float(expected), float(actual), rel_tol=1e-10, abs_tol=1e-10), (
            trail, expected, actual
        )
    else:
        assert expected == actual, (trail, expected, actual)


class IndependentInputs:
    def __init__(self, prices, days, metadata):
        self.prices = prices
        self.days = days
        self.index = {day: i for i, day in enumerate(days)}
        self.metadata = metadata
        self.beta_cache = {}

    def bar(self, symbol, day):
        return self.prices.get((symbol, day))

    def eligible(self, symbol, day):
        meta = self.metadata.get(symbol, {})
        if meta.get("status") not in ("ok", "cached", "success"):
            return False, "history_unavailable"
        if meta.get("quote_type") not in ("ETF", "EQUITY"):
            return False, "not_equity_or_etf"
        if meta.get("currency") != "USD" or meta.get("exchange_timezone") != "America/New_York":
            return False, "not_usd_us_session"
        if meta.get("exchange") not in EXCHANGES:
            return False, "unapproved_exchange_or_otc"
        entry = self.bar(symbol, day)
        if entry is None or not math.isfinite(entry["adjusted_open"]) or entry["adjusted_open"] <= 0:
            return False, "missing_entry_open"
        i = self.index[day]
        prior = [self.bar(symbol, d) for d in self.days[max(0, i - 20):i]]
        if len(prior) != 20 or any(bar is None for bar in prior):
            return False, "fewer_than_20_prior_sessions"
        dollars = [bar["close"] * bar["volume"] for bar in prior]
        if any(not math.isfinite(value) or value < 0 for value in dollars):
            return False, "invalid_prior_dollar_volume"
        if statistics.median(dollars) < 10000000:
            return False, "prior_median_dollar_volume_below_10m"
        return True, "eligible"

    def trend(self, symbol, day, direction, relative):
        i = self.index[day]
        prior = self.days[max(0, i - 20):i]
        values = []
        for d in prior:
            own = self.bar(symbol, d)
            spy = self.bar("SPY", d) if relative else None
            if own is None or relative and spy is None:
                return False, None, None
            value = own["adjclose"] / spy["adjclose"] if relative else own["adjclose"]
            if not math.isfinite(value) or value <= 0:
                return False, None, None
            values.append(value)
        if len(values) != 20:
            return False, None, None
        latest, average = values[-1], sum(values) / 20
        aligned = latest > average if direction > 0 else latest < average
        return bool(aligned), latest, average

    def beta(self, symbol, day):
        key = symbol, day
        if key not in self.beta_cache:
            i = self.index[day]
            prior = self.days[max(0, i - 41):i]
            bars = [[self.bar(s, d) for d in prior] for s in (symbol, "SPY")]
            if len(prior) != 41 or any(bar is None for group in bars for bar in group):
                value = None
            else:
                prices = [[bar["adjclose"] for bar in group] for group in bars]
                own, spy = [[b / a - 1 for a, b in zip(group, group[1:])] for group in prices]
                own_mean, spy_mean = statistics.mean(own), statistics.mean(spy)
                denominator = sum((x - spy_mean) ** 2 for x in spy)
                value = (
                    sum((x - spy_mean) * (y - own_mean) for x, y in zip(spy, own)) / denominator
                    if denominator > 0 else None
                )
            self.beta_cache[key] = value
        return self.beta_cache[key]

    def expiry(self, day, end):
        target = self.index[day] + 10
        deadline = dt.date.fromisoformat(day) + dt.timedelta(days=21)
        if target < len(self.days):
            while dt.date.fromisoformat(self.days[target]) > deadline:
                target -= 1
        if target >= len(self.days) or self.days[target] > end:
            return end, "close", True
        return self.days[target], "open", False


def independent_clock(inputs, items, start, end, allowed_months, variant):
    assert variant in VARIANTS
    relative = variant.startswith("relative_")
    reserve_rejections = variant.endswith("_reserved")
    allowed = set(allowed_months)
    events = defaultdict(list)
    for row in items:
        first = next((
            d for d in inputs.days
            if d > row["report_date"] and opening(d) > timestamp(row["available_at"])
        ), None)
        if first is not None:
            events[first].append(row)
    opportunities, cohorts, qualifications = [], [], []
    latest = None
    busy_through = None
    last_release = -1000
    consumed_report = None
    for day in inputs.days:
        if day > end:
            break
        i = inputs.index[day]
        for report in events.get(day, ()):
            if latest is None or report["report_date"] > latest["report_date"]:
                latest = report
        if day < start:
            continue
        if busy_through is not None and i >= busy_through:
            busy_through = None
            last_release = i
        if day[:7] not in allowed:
            continue
        if busy_through is not None or i <= last_release + 1 or latest is None:
            continue
        if latest["report_date"] == consumed_report:
            continue
        age = (dt.date.fromisoformat(day) - dt.date.fromisoformat(latest["report_date"])).days
        targets = latest["legs"]
        basic_eligible = any(
            t.get("source_eligible") is not False and inputs.eligible(t["symbol"], day)[0]
            for t in targets
        )
        if age > 4 or not targets or not basic_eligible:
            continue
        ident = len(opportunities) + 1
        exit_day, kind, censored = inputs.expiry(day, end)
        opportunities.append({
            "clock_id": ident, "date": day, "report_date": latest["report_date"],
            "source_sha256": latest["source_sha256"],
            "source_version_id": latest["source_version_id"],
            "available_at": latest["available_at"], "targets": json.dumps(targets),
            "scheduled_exit": exit_day, "exit_kind": kind,
        })
        accepted = []
        for target in targets:
            symbol, direction = target["symbol"], int(target["direction"])
            okay, reason = inputs.eligible(symbol, day)
            if target.get("source_eligible") is False:
                okay, reason = False, target.get(
                    "source_eligibility_reason", "source_ineligible_foreign_listing"
                )
            aligned, latest_value, average = inputs.trend(symbol, day, direction, relative)
            if okay and not aligned:
                okay = False
                reason = (
                    "crowd_direction_not_relative_sma20_aligned"
                    if relative else "crowd_direction_not_sma20_aligned"
                )
            weight = 1.0 / len(targets)
            qualifications.append({
                "clock_id": ident, "date": day, "report_date": latest["report_date"],
                "symbol": symbol, "direction": direction, "original_weight": weight,
                "eligible": okay, "reason": reason, "prior_close": latest_value,
                "prior_sma20": average, "beta40": inputs.beta(symbol, day),
                "available_at": latest["available_at"], "source_sha256": latest["source_sha256"],
            })
            if okay:
                accepted.append({"symbol": symbol, "direction": direction, "weight": weight})
        if accepted:
            cohorts.append({
                "basket_id": str(ident), "entry_date": day, "exit_date": exit_day,
                "exit_kind": kind, "report_date": latest["report_date"],
                "heading": latest["heading"], "source_sha256": latest["source_sha256"],
                "terminal_censored": censored, "legs": accepted,
            })
        # Consuming an attempted report is separate from reserving its window.
        consumed_report = latest["report_date"]
        if accepted or reserve_rejections:
            busy_through = inputs.index[exit_day] if not censored else len(inputs.days) + 1
    return opportunities, cohorts, qualifications


def source_items(root, start):
    items = []
    for source in read_csv(root / "inputs/archival_replay_etf_items.csv"):
        if int(source["slot"]) != 4 or source["report_date"] < start:
            continue
        row = dict(source)
        row["legs"] = [
            {
                "symbol": target["symbol"], "direction": int(target["direction"]),
                "source_eligible": target.get("source_eligible", True),
                "source_eligibility_reason": target.get(
                    "source_eligibility_reason", "fixed17_etf_mapping"
                ),
            }
            for target in json.loads(source["targets"])
        ]
        assert len({t["symbol"] for t in row["legs"]}) == len(row["legs"])
        items.append(row)
    assert len({row["report_date"] for row in items}) == len(items)
    return sorted(items, key=lambda row: row["report_date"])


def self_test():
    """Economically distinct edge cases, using no market or report outcomes."""
    days = []
    date = dt.date(2022, 1, 3)
    while len(days) < 100:
        if date.weekday() < 5:
            days.append(date.isoformat())
        date += dt.timedelta(days=1)
    prices = {}
    for i, day in enumerate(days):
        for symbol, value in (("AAA", 90.0 if i == 49 else 100.0),
                              ("BBB", 100.0 + i), ("SPY", 120.0)):
            prices[symbol, day] = {
                "adjclose": value, "adjusted_open": value,
                "open": value, "close": value, "volume": 1000000.0,
            }
    metadata = {
        s: {"status": "ok", "quote_type": "ETF", "currency": "USD",
            "exchange_timezone": "America/New_York", "exchange": "PCX"}
        for s in ("AAA", "BBB", "SPY")
    }
    inputs = IndependentInputs(prices, days, metadata)
    def report(i, symbols):
        day = days[i]
        return {
            "report_date": day, "available_at": dt.datetime.combine(
                dt.date.fromisoformat(day), dt.time(23, 59, 59), NY
            ).isoformat(),
            "source_sha256": "0" * 64, "source_version_id": "",
            "heading": "Invented source identity",
            "legs": [
                {"symbol": s, "direction": 1, "source_eligible": True,
                 "source_eligibility_reason": "fixed17_etf_mapping"} for s in symbols
            ],
        }
    items = [report(49, ["AAA"]), report(50, ["BBB"]),
             report(60, ["BBB"]), report(61, ["BBB"]), report(62, ["BBB"])]
    start, end = days[49], days[85]
    months = sorted({day[:7] for day in days})
    reserved = independent_clock(inputs, items, start, end, months, "absolute_reserved")
    filled = independent_clock(inputs, items, start, end, months, "absolute_filled")
    assert reserved[0][0]["date"] == days[50] and reserved[1][0]["entry_date"] == days[62]
    assert [c["entry_date"] for c in filled[1]][:2] == [days[51], days[63]]
    assert filled[0][0]["report_date"] == days[49] and filled[0][1]["report_date"] == days[50]
    # A failed report cannot be reconsidered daily even in the filled clock.
    once = independent_clock(inputs, [report(49, ["AAA"])], start, end, months, "absolute_filled")
    assert len(once[0]) == 1 and not once[1]
    partial = independent_clock(
        inputs, [report(49, ["AAA", "BBB"])], start, end, months, "relative_filled"
    )
    assert len(partial[1]) == 1 and partial[1][0]["legs"] == [
        {"symbol": "BBB", "direction": 1, "weight": 0.5}
    ]
    for direction in (-1, 1):
        aligned, last, average = inputs.trend("SPY", days[50], direction, True)
        assert not aligned and last == average == 1.0
    before = inputs.trend("AAA", days[50], 1, False)
    old = prices["AAA", days[50]]["adjclose"]
    prices["AAA", days[50]]["adjclose"] = 99999.0
    assert inputs.trend("AAA", days[50], 1, False) == before
    prices["AAA", days[50]]["adjclose"] = old
    return {
        "rejected_report_consumed_without_reservation": True,
        "reserved_rejections_and_actual_fill_cooldown_distinguished": True,
        "rejected_target_weight_not_renormalized": True,
        "constant_spy_relative_ratio_rejects_both_directions": True,
        "entry_day_close_excluded": True,
    }


def audit_variants(root, prepared_by_variant):
    root = Path(root).resolve()
    assert set(prepared_by_variant) == set(VARIANTS)
    first = prepared_by_variant["absolute_reserved"]
    start, end = first["start"], first["end"]
    coverage = load_json(root / "source/archive_inventory.json")
    allowed = sorted(set(coverage["available_months"]))
    prices = {}
    for row in read_csv(root / "prices.csv"):
        key = row["symbol"], row["session_date"]
        assert key not in prices
        values = {k: float(row[k]) for k in (
            "open", "close", "adjusted_open", "adjclose", "volume"
        )}
        assert all(math.isfinite(value) for value in values.values())
        assert all(values[k] > 0 for k in ("open", "close", "adjusted_open", "adjclose"))
        assert values["volume"] >= 0
        prices[key] = values
    days = sorted(day for symbol, day in prices if symbol == "SPY")
    assert days and days[-1] == end
    metadata = {
        row["symbol"]: row for row in load_json(root / "market_manifest.json")["series"]
    }
    inputs = IndependentInputs(prices, days, metadata)
    items = source_items(root, start)
    assert [row["report_date"] for row in items] == coverage["valid_dates"]
    results = {}
    for variant in VARIANTS:
        actual = prepared_by_variant[variant]
        assert actual["start"] == actual["source_min"] == start and actual["end"] == end
        assert actual["available_entry_months"] == allowed
        assert actual["missing_months"] == coverage["missing_months"]
        opportunities, cohorts, qualifications = independent_clock(
            inputs, items, start, end, allowed, variant
        )
        same(opportunities, actual["etf_opportunities"], variant + "/opportunities")
        same(cohorts, actual["cohorts"]["etf_own"], variant + "/cohorts")
        same(qualifications, actual["etf_qualification"], variant + "/qualification")
        assert all(o["date"][:7] in allowed for o in opportunities)
        assert all(c["entry_date"][:7] in allowed for c in cohorts)
        assert len({o["report_date"] for o in opportunities}) == len(opportunities)
        for previous, following in zip(cohorts, cohorts[1:]):
            assert inputs.index[following["entry_date"]] >= inputs.index[previous["exit_date"]] + 2
        results[variant] = {
            "attempted_opportunities": len(opportunities),
            "funded_baskets": len(cohorts),
            "unfunded_opportunities": len(opportunities) - len(cohorts),
            "source_legs": sum(len(c["legs"]) for c in cohorts),
            "qualifications": len(qualifications),
            "terminal_censored_baskets": sum(c["terminal_censored"] for c in cohorts),
            "held_exits_in_missing_months": sum(c["exit_date"][:7] not in allowed for c in cohorts),
            "relative_gate": variant.startswith("relative_"),
            "rejections_reserve_window": variant.endswith("_reserved"),
        }
    result = {
        "strategy_id": "mapp_strategy", "status": "passed", "start": start, "end": end,
        "method": "Independent direct-price/metadata/source-CSV replay; no production clock, qualification or SMA imports.",
        "price_sha256": digest(root / "prices.csv"),
        "mapped_source_csv_sha256": digest(root / "inputs/archival_replay_etf_items.csv"),
        "variants": results, "self_tests": self_test(),
        "relative_qualification_field_semantics": (
            "prior_close and prior_sma20 contain ETF/SPY ratio and its preceding20-completed-session mean."
        ),
        "held_price_and_financial_accounting": "Checked separately by the unchanged independent ledger auditor.",
    }
    destination = root / "audit/relative_clock_inputs.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("MAPP_RELATIVE_CLOCK_INPUT_AUDIT " + json.dumps(result, sort_keys=True, allow_nan=False), flush=True)
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.parse_args()
    print(json.dumps(self_test(), sort_keys=True))
