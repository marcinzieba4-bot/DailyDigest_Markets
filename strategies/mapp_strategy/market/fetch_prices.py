"""Fetch one coherent Yahoo daily-price vintage for the fixed 17-ETF research universe.

Standard-library only. Run from the study folder or use --root.
Network fetch:
    python market/fetch_prices.py --root . --start 2023-01-01
    # End defaults to the common protocol.case_config end; --end can override explicitly.
Offline deterministic re-decode:
    python market/fetch_prices.py --root . --decode-only
No portfolio returns or entry/exit decisions are calculated here.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import email.utils
import hashlib
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

SYMBOLS = [
    "EPOL", "GLD", "IEF", "QQQ", "SOXX", "SPY", "XLB", "XLC", "XLE",
    "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY",
]
COLUMNS = ["symbol", "session_date", "open", "close", "adjusted_open", "adjclose", "volume"]
NY = ZoneInfo("America/New_York")
UTC = dt.timezone.utc
ALLOWED_EXCHANGES = {
    "NYQ", "NMS", "NGM", "NCM", "ASE", "PCX", "BTS", "BATS", "CBOE",
    "NYSEArca", "NasdaqGM", "NasdaqGS", "NasdaqCM",
}
DEFAULT_START = "2023-01-01"
FIRST_RESEARCH_DAY = "2023-11-01"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def utc_now() -> str:
    return dt.datetime.now(UTC).isoformat()


def chart_url(symbol: str, start: str, end: str) -> str:
    first = dt.datetime.combine(dt.date.fromisoformat(start), dt.time(), UTC)
    after_last = dt.datetime.combine(dt.date.fromisoformat(end) + dt.timedelta(days=1), dt.time(), UTC)
    query = urllib.parse.urlencode({
        "period1": int(first.timestamp()),
        "period2": int(after_last.timestamp()),
        "interval": "1d",
        "events": "div,splits",
        "includeAdjustedClose": "true",
    })
    return "https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(symbol, safe="") + "?" + query


def chart_result(payload: dict, symbol: str) -> dict:
    chart = payload.get("chart") or {}
    if chart.get("error") is not None:
        raise ValueError("Yahoo chart error for " + symbol + ": " + json.dumps(chart["error"], ensure_ascii=False))
    result = chart.get("result")
    if not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], dict):
        raise ValueError("Expected exactly one Yahoo chart result for " + symbol)
    return result[0]


def download_raw(symbol: str, url: str, path: Path, attempts: int = 4) -> dict:
    """Normal HTTPS client; inherited proxy and CA settings stay in effect."""
    observations = []
    for attempt in range(1, attempts + 1):
        started = utc_now()
        retry_after = None
        try:
            request = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; historical-price-research/1.0)",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(request, timeout=30) as response:
                status = response.status
                body = response.read()
            payload = json.loads(body.decode("utf-8"))
            chart_result(payload, symbol)
            if status != 200:
                raise ValueError("Unexpected HTTP status " + str(status))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
            observations.append({
                "attempt": attempt, "requested_utc": started, "completed_utc": utc_now(),
                "http_status": status, "bytes": len(body), "sha256": sha_bytes(body),
            })
            return {
                "symbol": symbol, "url": url, "raw_path": "market/raw/" + path.name,
                "bytes": len(body), "sha256": sha_bytes(body), "attempts": observations,
            }
        except urllib.error.HTTPError as exc:
            raw_wait = exc.headers.get("Retry-After") if exc.headers else None
            try:
                retry_after = max(0.0, float(raw_wait)) if raw_wait else None
            except ValueError:
                try:
                    retry_at = email.utils.parsedate_to_datetime(raw_wait)
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=UTC)
                    retry_after = max(0.0, (retry_at - dt.datetime.now(UTC)).total_seconds())
                except (TypeError, ValueError, OverflowError):
                    retry_after = None
            observations.append({
                "attempt": attempt, "requested_utc": started, "completed_utc": utc_now(),
                "http_status": exc.code, "error": str(exc),
            })
        except (urllib.error.URLError, TimeoutError, ValueError, UnicodeError, OSError) as exc:
            observations.append({
                "attempt": attempt, "requested_utc": started, "completed_utc": utc_now(),
                "error": type(exc).__name__ + ": " + str(exc),
            })
        if attempt < attempts:
            time.sleep(retry_after if retry_after is not None else min(15.0, 2.0 ** attempt))
    raise RuntimeError(json.dumps({"symbol": symbol, "url": url, "attempts": observations}, ensure_ascii=False))


def number(value, *, positive: bool) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("missing or nonnumeric value")
    value = float(value)
    if not math.isfinite(value) or (value <= 0 if positive else value < 0):
        raise ValueError("invalid finite value")
    return value


def decode_symbol(raw: bytes, symbol: str, start: str, end: str) -> tuple[list[dict], dict]:
    result = chart_result(json.loads(raw.decode("utf-8")), symbol)
    meta = result.get("meta") or {}
    provider_symbol = meta.get("symbol")
    if str(provider_symbol).upper() != symbol:
        raise ValueError("Requested/provider symbol mismatch: " + symbol + "/" + str(provider_symbol))
    if meta.get("exchangeTimezoneName") != "America/New_York":
        raise ValueError("Unexpected exchange timezone for " + symbol)
    if meta.get("currency") != "USD" or meta.get("instrumentType") != "ETF":
        raise ValueError("Unexpected currency/instrument type for " + symbol)
    if meta.get("exchangeName") not in ALLOWED_EXCHANGES:
        raise ValueError("Unapproved exchange metadata for " + symbol + ": " + str(meta.get("exchangeName")))
    timestamps = result.get("timestamp")
    indicators = result.get("indicators") or {}
    quotes = indicators.get("quote")
    adjustments = indicators.get("adjclose")
    if not isinstance(timestamps, list) or not timestamps:
        raise ValueError("Empty timestamp series for " + symbol)
    if not isinstance(quotes, list) or len(quotes) != 1 or not isinstance(adjustments, list) or len(adjustments) != 1:
        raise ValueError("Missing quote or adjusted close series for " + symbol)
    quote = quotes[0]
    arrays = [quote.get("open"), quote.get("close"), quote.get("volume"), adjustments[0].get("adjclose")]
    if any(not isinstance(a, list) or len(a) != len(timestamps) for a in arrays):
        raise ValueError("Timestamp/price-array length mismatch for " + symbol)
    rows, invalid, seen = [], [], set()
    for i, timestamp in enumerate(timestamps):
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
            raise ValueError("Invalid raw timestamp for " + symbol)
        date = dt.datetime.fromtimestamp(timestamp, UTC).astimezone(NY).date().isoformat()
        if not start <= date <= end:
            continue
        if date in seen:
            raise ValueError("Duplicate provider session " + symbol + " " + date)
        seen.add(date)
        try:
            opening = number(arrays[0][i], positive=True)
            close = number(arrays[1][i], positive=True)
            volume = number(arrays[2][i], positive=False)
            adjclose = number(arrays[3][i], positive=True)
            adjusted_open = opening * adjclose / close
            if not math.isfinite(adjusted_open) or adjusted_open <= 0:
                raise ValueError("invalid adjusted open")
        except ValueError as exc:
            invalid.append({"session_date": date, "raw_index": i, "reason": str(exc)})
            continue
        rows.append({
            "symbol": symbol, "session_date": date, "open": opening, "close": close,
            "adjusted_open": adjusted_open, "adjclose": adjclose, "volume": volume,
        })
    rows.sort(key=lambda r: r["session_date"])
    if not rows:
        raise ValueError("No valid requested daily bars for " + symbol)
    first_trade = meta.get("firstTradeDate")
    first_trade_date = (
        dt.datetime.fromtimestamp(first_trade, UTC).astimezone(NY).date().isoformat()
        if isinstance(first_trade, (int, float)) else None
    )
    series = {
        "symbol": symbol, "status": "ok", "provider_symbol": provider_symbol,
        "exchange_timezone": meta["exchangeTimezoneName"], "currency": meta["currency"],
        "quote_type": meta["instrumentType"], "exchange": meta["exchangeName"],
        "short_name": meta.get("shortName"), "long_name": meta.get("longName"),
        "provider_first_trade_date": first_trade_date,
        "first_date": rows[0]["session_date"], "last_date": rows[-1]["session_date"],
        "bars": len(rows), "invalid_bars": invalid,
        "events": result.get("events") or {}, "provider_meta": meta,
        "warmup_closes_before_research_start": sum(r["session_date"] < FIRST_RESEARCH_DAY for r in rows),
    }
    return rows, series


def validate_csv(path: Path, expected_rows: list[dict], raw_meta: dict) -> dict:
    """Second pass over written CSV; never interpolate, drop an asset or calculate portfolio returns."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != COLUMNS:
            raise AssertionError("Unexpected output CSV fields")
        actual = list(reader)
    if len(actual) != len(expected_rows):
        raise AssertionError("Decoded/output row-count mismatch")
    for got, expected in zip(actual, expected_rows):
        for key in ["symbol", "session_date"]:
            if got[key] != expected[key]:
                raise AssertionError("Decoded/output identity mismatch")
        for key in COLUMNS[2:]:
            if float(got[key]) != expected[key]:
                raise AssertionError("CSV numeric roundtrip mismatch for " + key)
        formula = float(got["open"]) * float(got["adjclose"]) / float(got["close"])
        if not math.isclose(float(got["adjusted_open"]), formula, rel_tol=1e-14, abs_tol=1e-14):
            raise AssertionError("Adjusted opening formula mismatch")
    return {
        "status": "passed", "rows": len(actual), "series": len(SYMBOLS),
        "csv_sha256": file_sha(path), "raw_response_hashes": raw_meta,
        "formula": "adjusted_open = open * adjclose / close",
        "missing_data_handling": "Invalid bars omitted and logged; no interpolation, forward-fill, replacement feed or asset deletion.",
        "scope": "Price/metadata/serialization checks only; no portfolio outcomes or signal selection.",
    }


def build_dataset(root: Path, campaign: dict) -> dict:
    start, end = campaign["requested_start"], campaign["requested_end"]
    records = {r["symbol"]: r for r in campaign["downloads"]}
    if set(records) != set(SYMBOLS):
        raise AssertionError("A coherent campaign must contain all17 fixed symbols")
    all_rows, series = [], []
    for symbol in SYMBOLS:
        record = records[symbol]
        raw_path = root / record["raw_path"]
        if file_sha(raw_path) != record["sha256"]:
            raise AssertionError("Raw response hash mismatch for " + symbol)
        rows, info = decode_symbol(raw_path.read_bytes(), symbol, start, end)
        info.update({
            "attempts": record["attempts"], "raw_path": record["raw_path"],
            "raw_bytes": record["bytes"], "raw_sha256": record["sha256"],
        })
        all_rows.extend(rows)
        series.append(info)
    by_symbol = {symbol: [r for r in all_rows if r["symbol"] == symbol] for symbol in SYMBOLS}
    spy_days = [r["session_date"] for r in by_symbol["SPY"]]
    if len(spy_days) < 42:
        raise AssertionError("Insufficient reference calendar")
    for info in series:
        rows = by_symbol[info["symbol"]]
        dates = {r["session_date"] for r in rows}
        info["interior_missing_sessions"] = [
            d for d in spy_days if info["first_date"] <= d <= info["last_date"] and d not in dates
        ]
        info["sessions_before_first"] = sum(d < info["first_date"] for d in spy_days)
        info["sessions_after_last"] = sum(d > info["last_date"] for d in spy_days)
        if info["warmup_closes_before_research_start"] < 41:
            raise AssertionError("Insufficient strictly prior warmup for " + info["symbol"])
    output = root / "prices.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)
    manifest = {
        "provider": "Yahoo Finance v8 chart", "campaign_started_utc": campaign["started_utc"],
        "campaign_completed_utc": campaign["completed_utc"],
        "requested_start": start, "requested_end": end,
        "research_start": FIRST_RESEARCH_DAY, "series": series, "total_rows": len(all_rows),
        "controls": SYMBOLS, "control_sessions": len(spy_days),
        "actual_first_session": min(spy_days), "actual_last_session": max(spy_days),
        "controls_same_complete_calendar": all(
            [r["session_date"] for r in by_symbol[symbol]] == spy_days for symbol in SYMBOLS
        ),
        "output": "prices.csv", "output_sha256": file_sha(output),
        "adjusted_open_rule": "open*adjclose/close",
        "selection": "Single coherent full-range download campaign; all17 fixed ETFs retained.",
        "missing_data_rule": "No interpolation/forward-fill/substitution or future-completeness entry screen. Coverage diagnostics do not change the fixed universe; held missing prices remain fatal in the simulator.",
    }
    save_json(root / "market_manifest.json", manifest)
    raw_hashes = {symbol: records[symbol]["sha256"] for symbol in SYMBOLS}
    validation = validate_csv(output, all_rows, raw_hashes)
    validation["complete_common_calendar"] = manifest["controls_same_complete_calendar"]
    validation["warmup_before_2023_11_01"] = {r["symbol"]: r["warmup_closes_before_research_start"] for r in series}
    validation["market_manifest_sha256"] = file_sha(root / "market_manifest.json")
    save_json(root / "market/validation.json", validation)
    return {
        "status": "passed", "symbols": len(SYMBOLS), "rows": len(all_rows),
        "first": min(spy_days), "last": max(spy_days),
        "complete_common_calendar": manifest["controls_same_complete_calendar"],
        "prices_sha256": file_sha(output),
        "market_manifest_sha256": file_sha(root / "market_manifest.json"),
    }


def compare_prior_prices(current_path: Path, prior_path: Path) -> dict:
    """Describe vintage changes; never splice, rescale or replace either dataset."""
    def load(path):
        with path.open(newline="", encoding="utf-8") as handle:
            records = list(csv.DictReader(handle))
        return {(r["symbol"], r["session_date"]): r for r in records}
    current, prior = load(current_path), load(prior_path)
    common = sorted(set(current) & set(prior))
    checks = []
    for symbol in SYMBOLS:
        keys = [k for k in common if k[0] == symbol]
        stats = {}
        for field in COLUMNS[2:]:
            differences = [(float(current[k][field]), float(prior[k][field])) for k in keys]
            stats[field] = {
                "exactly_changed_rows": sum(a != b for a, b in differences),
                "materially_changed_rows": sum(not math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-12) for a, b in differences),
                "max_absolute_difference": max((abs(a - b) for a, b in differences), default=0.0),
                "max_relative_difference": max((abs(a - b) / abs(b) for a, b in differences if b), default=0.0),
            }
        ratios = [
            float(current[k]["adjclose"]) / float(prior[k]["adjclose"])
            for k in keys if float(prior[k]["adjclose"]) > 0
        ]
        checks.append({
            "symbol": symbol, "common_sessions": len(keys), "fields": stats,
            "adjusted_close_scale_ratio_min": min(ratios) if ratios else None,
            "adjusted_close_scale_ratio_max": max(ratios) if ratios else None,
        })
    return {
        "status": "descriptive_comparison_completed",
        "current_prices_sha256": file_sha(current_path), "prior_prices_sha256": file_sha(prior_path),
        "common_rows": len(common), "new_only_rows": len(set(current) - set(prior)),
        "prior_only_rows": len(set(prior) - set(current)), "series": checks,
        "policy": "Separate vintages retained; no stitching or data-dependent universe selection. Repricing bridge books are a separate engine responsibility.",
    }


def configured_end(root: Path, explicit: str | None) -> str:
    """Use an explicit end or the protocol's one common end; never the wall clock."""
    if explicit is not None:
        return dt.date.fromisoformat(explicit).isoformat()
    protocol = json.loads((root / "protocol.json").read_text(encoding="utf-8"))
    cases = protocol.get("case_config")
    if not isinstance(cases, dict) or not cases:
        raise ValueError("Supply --end or a nonempty protocol.case_config")
    ends = {dt.date.fromisoformat(case["end"]).isoformat() for case in cases.values()}
    if len(ends) != 1:
        raise ValueError("Supply --end when protocol cases have different endpoints")
    return next(iter(ends))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", help="Inclusive endpoint; otherwise use the common protocol case_config end")
    parser.add_argument("--decode-only", action="store_true")
    parser.add_argument("--prior-prices", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    record_path = root / "market/fetch_campaign.json"
    if args.decode_only:
        campaign = json.loads(record_path.read_text(encoding="utf-8"))
        if args.end is not None and dt.date.fromisoformat(args.end).isoformat() != campaign["requested_end"]:
            raise ValueError("--decode-only must retain the saved campaign endpoint")
    else:
        args.end = configured_end(root, args.end)
        start_date, end_date = dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end)
        if start_date >= dt.date.fromisoformat(FIRST_RESEARCH_DAY) or end_date < dt.date.fromisoformat(FIRST_RESEARCH_DAY):
            raise ValueError("Keep sufficient approved warmup and an endpoint on or after the research start")
        campaign = {
            "started_utc": utc_now(), "requested_start": args.start, "requested_end": args.end,
            "research_start": FIRST_RESEARCH_DAY, "symbols": SYMBOLS, "downloads": [],
        }
        for index, symbol in enumerate(SYMBOLS):
            url = chart_url(symbol, args.start, args.end)
            try:
                record = download_raw(symbol, url, root / "market/raw" / (symbol + ".json"))
            except Exception as exc:
                save_json(root / "market/fetch_failure.json", {
                    "status": "failed", "symbol": symbol, "error": str(exc),
                    "completed_utc": utc_now(), "downloaded_symbols": [r["symbol"] for r in campaign["downloads"]],
                })
                raise
            campaign["downloads"].append(record)
            if index + 1 < len(SYMBOLS):
                time.sleep(0.75)
        campaign["completed_utc"] = utc_now()
        save_json(record_path, campaign)
    result = build_dataset(root, campaign)
    if args.prior_prices is not None:
        overlap = compare_prior_prices(root / "prices.csv", args.prior_prices)
        save_json(root / "market/prior_overlap_comparison.json", overlap)
        result["prior_overlap_rows"] = overlap["common_rows"]
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
