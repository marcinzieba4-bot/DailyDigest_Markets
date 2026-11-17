"""Public data availability probe; no portfolio calculations or AWS credentials."""
from __future__ import annotations
import argparse
import base64
import concurrent.futures as cf
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

OUTPUT = Path(__file__).resolve().parents[1] / "availability_probe.json"
BASE = "https://d7g7nkeytae81.cloudfront.net/"
START = int(dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc).timestamp())
END = int(dt.datetime(2026, 10, 31, tzinfo=dt.timezone.utc).timestamp())
QUERY = urllib.parse.urlencode({
    "period1": START, "period2": END, "interval": "1d",
    "events": "div,splits", "includeAdjustedClose": "true",
})
TARGETS = [
    ("archive_2023_11_01", BASE + "reports/archive/2023-11-01.html", "html"),
    ("archive_2023_12_01", BASE + "reports/archive/2023-12-01.html", "html"),
    ("archive_known_2024_09_02", BASE + "reports/archive/2024-09-02.html", "html"),
    ("latest", BASE + "reports/latest.html", "html"),
    ("index", BASE + "reports/index.html", "html"),
    ("spy_prices", "https://query1.finance.yahoo.com/v8/finance/chart/SPY?" + QUERY, "json"),
]


class Headings(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.active = None

    def handle_starttag(self, tag, attrs):
        if tag in {"h1", "h2", "h3", "h4"}:
            self.active = [tag, []]

    def handle_data(self, text):
        if self.active is not None:
            self.active[1].append(text)

    def handle_endtag(self, tag):
        if self.active is not None and tag == self.active[0]:
            self.rows.append((tag, " ".join("".join(self.active[1]).split())))
            self.active = None


def inspect_html(blob):
    headings = Headings()
    headings.feed(blob.decode("utf-8", errors="replace"))
    indexes = [i for i, (_, text) in enumerate(headings.rows)
               if "what retail is playing" in text.lower()]
    counts = []
    for index in indexes:
        count = 0
        for tag, _ in headings.rows[index + 1:]:
            if tag == "h2":
                break
            if tag in {"h3", "h4"}:
                count += 1
        counts.append(count)
    return {
        "retail_section_marker_count": len(indexes),
        "retail_topic_heading_counts": counts,
        "four_topic_section_detected": any(n == 4 for n in counts),
    }


def inspect_prices(blob):
    document = json.loads(blob)
    chart = document.get("chart", {})
    result = chart.get("result") or []
    if not result:
        return {"chart_result_present": False,
                "provider_error_code": (chart.get("error") or {}).get("code")}
    item = result[0]
    stamps = item.get("timestamp") or []
    quote = (item.get("indicators", {}).get("quote") or [{}])[0]
    adjusted = ((item.get("indicators", {}).get("adjclose") or [{}])[0]).get("adjclose") or []
    dates = [dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat() for t in stamps]
    valid = []
    for i, day in enumerate(dates):
        values = [(quote.get(k) or [])[i] if i < len(quote.get(k) or []) else None
                  for k in ["open", "close", "volume"]]
        values.append(adjusted[i] if i < len(adjusted) else None)
        okay = all(isinstance(v, (int, float)) and math.isfinite(v) for v in values)
        okay = okay and values[0] > 0 and values[1] > 0 and values[2] >= 0 and values[3] > 0
        if okay:
            valid.append(day)
    meta = item.get("meta") or {}
    return {
        "chart_result_present": True,
        "symbol": meta.get("symbol"),
        "currency": meta.get("currency"),
        "exchange_timezone": meta.get("exchangeTimezoneName"),
        "bars": len(stamps),
        "valid_price_volume_bars": len(valid),
        "first_bar_date": min(dates) if dates else None,
        "last_bar_date": max(dates) if dates else None,
        "valid_warmup_closes_before_2023_11_01": sum(d < "2023-11-01" for d in valid),
        "valid_warmup_closes_before_2023_12_01": sum(d < "2023-12-01" for d in valid),
    }


def fetch(target):
    label, url, kind = target
    row = {"label": label, "url": url}
    for attempt in range(1, 4):
        try:
            request = urllib.request.Request(url, headers={
                "User-Agent": "DailyDigest-Part4-Availability/1.0",
                "Accept-Encoding": "identity",
            })
            with urllib.request.urlopen(request, timeout=25) as response:
                limit = 4 * 1024 * 1024
                blob = response.read(limit + 1)
                truncated = len(blob) > limit
                row.update({
                    "status": response.status,
                    "content_type": response.headers.get("Content-Type"),
                    "last_modified": response.headers.get("Last-Modified"),
                    "version_id": response.headers.get("x-amz-version-id"),
                    "etag": response.headers.get("ETag"),
                    "bytes_read": len(blob),
                    "truncated": truncated,
                    "sha256": None if truncated else hashlib.sha256(blob).hexdigest(),
                    "attempts": attempt,
                })
            if not truncated and row["status"] == 200:
                try:
                    row.update(inspect_html(blob) if kind == "html" else inspect_prices(blob))
                except Exception as error:
                    row["parse_error_type"] = type(error).__name__
            return row
        except urllib.error.HTTPError as error:
            row.update(status=error.code, attempts=attempt,
                       error_type=type(error).__name__)
            if error.code not in {429, 500, 502, 503, 504} or attempt == 3:
                return row
            delay = error.headers.get("Retry-After", "")
            delay = min(int(delay), 60) if delay.isdigit() else min(2 ** attempt, 8)
            time.sleep(delay)
        except Exception as error:
            row.update(status=None, attempts=attempt, error_type=type(error).__name__)
            if attempt == 3:
                return row
            time.sleep(min(2 ** attempt, 8))
    return row


def probe():
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(fetch, TARGETS))
    by_label = {row["label"]: row for row in rows}
    required_reports = ["archive_2023_11_01", "archive_2023_12_01", "archive_known_2024_09_02"]
    reports_ready = all(by_label[label].get("status") == 200 and
                        by_label[label].get("retail_section_marker_count") == 1
                        for label in required_reports)
    prices = by_label["spy_prices"]
    price_ready = (prices.get("status") == 200 and
                   prices.get("valid_warmup_closes_before_2023_11_01", 0) >= 41 and
                   prices.get("last_bar_date") == "2026-10-30")
    output = {
        "purpose": "Public report and SPY data availability only; no portfolio return calculation",
        "started_utc": started,
        "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_commit": os.environ.get("SOURCE_COMMIT"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "aws_credentials_used": False,
        "public_data_requests_only": True,
        "required_report_probe_ready": reports_ready,
        "spy_warmup_probe_ready": price_ready,
        "candidate_data_routes_ready": reports_ready and price_ready,
        "rows": rows,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))


def github_request(url, token, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "DailyDigest-Part4-Probe-Publisher/1.0",
    }, method="GET" if payload is None else "PUT")
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def publish():
    token = os.environ.get("GH_TOKEN")
    repository = os.environ.get("GITHUB_REPOSITORY")
    branch = os.environ.get("PUBLISH_BRANCH")
    source_commit = os.environ.get("SOURCE_COMMIT")
    if not token or not repository or not branch or not source_commit:
        raise RuntimeError("Missing publication context")
    api = "https://api.github.com/repos/" + repository
    head = github_request(api + "/git/ref/heads/" + urllib.parse.quote(branch, safe="/"), token)
    if head["object"]["sha"] != source_commit:
        print("Publication skipped: branch advanced; the run artifact retains the probe result.")
        return
    path = "strategies/retail_part4/availability_probe.json"
    url = api + "/contents/" + path
    previous_sha = None
    try:
        previous = github_request(url + "?" + urllib.parse.urlencode({"ref": branch}), token)
        previous_sha = previous["sha"]
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
    payload = {
        "message": "Record public Part 4 data availability probe",
        "content": base64.b64encode(OUTPUT.read_bytes()).decode(),
        "branch": branch,
    }
    if previous_sha:
        payload["sha"] = previous_sha
    result = github_request(url, token, payload)
    print(json.dumps({"published_path": path, "commit_sha": result["commit"]["sha"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish", action="store_true")
    arguments = parser.parse_args()
    publish() if arguments.publish else probe()
