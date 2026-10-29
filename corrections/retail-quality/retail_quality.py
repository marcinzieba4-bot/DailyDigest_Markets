"""Chronological editorial preflight for What Retail Is Playing.

This is a review gate, not a retail popularity ranking or a forced-rotation
algorithm. Evidence membership/timing are hard checks; concentration and
price-insensitive text similarity require an explicit editorial disposition.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import gzip
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

CITE = re.compile(r"\[\[(n\d+)\]\]")
TICKER = re.compile(r"/\s*([A-Z][A-Z0-9.-]{0,9})(?=\s|$|[,—–:])")
RANKING = re.compile(r"(?<!\w)(?:the\s+)?(?:#1|number[- ]one|most[- ](?:bought|traded|popular)|top[- ]ranked)\s+(?:retail\s+)?(?:trade|stock|asset|theme)|\b(?:reddit|stocktwits|twitter)\s+(?:mentions|posts)\s+(?:rose|surged|jumped)\s+\d", re.I)
ALIASES = {
    "gold": "GLD", "silver": "SLV", "bitcoin": "BTC", "btc-usd": "BTC",
    "ethereum": "ETH", "ether": "ETH", "eth-usd": "ETH", "solana": "SOL",
    "opendoor": "OPEN", "ionq": "IONQ", "rigetti": "RGTI", "robinhood": "HOOD",
    "tesla": "TSLA", "nvidia": "NVDA", "alphabet": "GOOGL", "google": "GOOGL",
    "alibaba": "BABA", "nebius": "NBIS", "oklo": "OKLO", "coreweave": "CRWV",
    "iren": "IREN", "intel": "INTC", "palantir": "PLTR", "gamestop": "GME",
    "beyond meat": "BYND", "sandisk": "SNDK", "rocket lab": "RKLB",
    "oil": "OIL", "wti": "OIL", "crude": "OIL", "energy": "XLE",
    "rheinmetall": "RHM", "defence": "DEFENCE", "defense": "DEFENCE",
    "xrp": "XRP", "gc": "GLD", "si": "SLV", "apple": "AAPL",
    "microstrategy": "MSTR", "strategy": "MSTR", "nike": "NKE", "costco": "COST",
    "quantumscape": "QS",
    "micron": "MU", "reddit": "RDDT", "nasdaq": "QQQ", "mega-cap tech": "QQQ",
}
FAMILIES = {
    "GLD": "precious-metals", "IAU": "precious-metals", "GDX": "precious-metals",
    "GOLD": "precious-metals", "SLV": "precious-metals", "SIVR": "precious-metals",
    "IONQ": "quantum", "RGTI": "quantum", "QBTS": "quantum", "QUBT": "quantum",
    "BTC": "crypto", "ETH": "crypto", "SOL": "crypto", "BMNR": "crypto-treasury",
    "MSTR": "crypto-treasury", "COIN": "crypto-platforms",
    "NBIS": "ai-capacity", "CRWV": "ai-capacity", "IREN": "ai-capacity",
    "OKLO": "nuclear-power", "SMR": "nuclear-power", "URA": "nuclear-power",
    "HOOD": "retail-brokerage", "OPEN": "housing-turnaround",
    "OIL": "oil-energy", "XLE": "oil-energy", "RHM": "defence", "DEFENCE": "defence",
    "USO": "oil-energy", "IBIT": "crypto", "XRP": "crypto",
    "GC": "precious-metals", "SI": "precious-metals",
    "NVDA": "ai-semiconductors", "AMD": "ai-semiconductors", "SOXX": "ai-semiconductors",
    "TSM": "ai-semiconductors", "AVGO": "ai-semiconductors", "AI": "ai-theme",
    "QQQ": "mega-cap-tech", "QS": "battery-technology",
}
STOP = set("the a an and or to of in for on with at by from is are was were be been being it its that this these those as than then while when if but can could may will would should has have had their they them we our your you not into over after before up down per prior close session sessions percent point points september october november december january february march april june july august monday tuesday wednesday thursday friday saturday sunday".split())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp needs explicit timezone")
    return parsed.astimezone(dt.timezone.utc)


def asset_id(title: str) -> str:
    # The first span in the August layout holds the narrative subtitle, not
    # another asset. HTML parser inserts a dash at that boundary.
    title = re.split(r"[—–]", title, 1)[0]
    match = TICKER.search(title)
    if match:
        raw = match.group(1)
        return ALIASES.get(raw.lower(), raw)
    parenthesized = re.search(r"\(([A-Z][A-Z0-9.-]{0,9})(?=\s|[,/)]|$)", title)
    if parenthesized:
        raw = parenthesized.group(1)
        return ALIASES.get(raw.lower(), raw)
    lead = re.split(r"[—–:]", title, 1)[0].strip().lower()
    for alias in sorted(ALIASES, key=len, reverse=True):
        if re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", lead):
            return ALIASES[alias]
    return re.sub(r"[^a-z0-9]+", "-", lead).strip("-") or "unknown"


def family_id(title: str) -> str:
    asset = asset_id(title)
    if asset in FAMILIES:
        return FAMILIES[asset]
    low = title.lower()
    if re.search(r"\bquantum\b", low):
        return "quantum"
    if "precious metal" in low:
        return "precious-metals"
    if re.search(r"\bai\b", low) and any(word in low for word in ("rotation", "basket", "mega-cap", "infrastructure")):
        return "ai-basket"
    if "rate-cut" in low or "weak jobs" in low:
        return "rate-cut-risk"
    return asset


def prose(entry: dict) -> str:
    return " ".join(str(part[1]) for part in entry.get("parts", []) if len(part) > 1)


def words_without_prices(text: str) -> list[str]:
    text = CITE.sub(" ", text.lower())
    text = re.sub(r"\d[\d,.:%/+−–-]*", " ", text)
    return [word for word in re.findall(r"[a-z]+", text) if word not in STOP and len(word) > 2]


def similarity(left: str, right: str) -> float:
    """Cosine of price-stripped word counts; lexical similarity, not semantics."""
    a, b = map(collections.Counter, (words_without_prices(left), words_without_prices(right)))
    if not a or not b:
        return 0.0
    dot = sum(value * b[word] for word, value in a.items())
    return dot / ((sum(x*x for x in a.values()) * sum(x*x for x in b.values())) ** .5)


def evidence_key(item: dict) -> str:
    url = item.get("url", "")
    if url:
        parsed = urlsplit(url)
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), "", ""))
    return " ".join(re.findall(r"\w+", item.get("title", "").lower()))


def validate_evidence(date: str, entry: dict, feed: dict, cutoff_utc: str | None = None) -> tuple[list[dict], list[dict]]:
    cutoff = utc(cutoff_utc or date + "T00:00:00Z")
    ids = sorted(set(CITE.findall(prose(entry))))
    idx = {item["id"]: item for item in feed.get("items", [])}
    errors, sources = [], []
    if not ids:
        errors.append({"code": "no_cited_evidence", "message": "Retail selection has no own-date cited evidence"})
    for key in ids:
        if key not in idx:
            errors.append({"code": "missing_citation", "id": key})
            continue
        item = idx[key]
        try:
            stamp = utc(item["published_at"])
        except (KeyError, ValueError, TypeError):
            errors.append({"code": "invalid_timestamp", "id": key})
            continue
        if stamp >= cutoff:
            errors.append({"code": "after_cutoff", "id": key, "published_at": item["published_at"]})
            continue
        sources.append({"id": key, "published_at": item["published_at"], "key": evidence_key(item), "title": item.get("title", "")})
    return errors, sources


def load_feed(root: Path, date: str) -> dict:
    path = root / "feeds" / (date + ".json")
    if path.exists():
        return json.loads(path.read_text())
    with gzip.open(str(path) + ".gz", "rt") as handle:
        return json.load(handle)


def audit_reports(reports: list[dict], decisions: dict | None = None) -> dict:
    """Read each report in date order; all flags use only earlier selections."""
    decisions = decisions or {}
    previous_entries, history, results, failures, flags = {}, [], [], [], []
    decision_used = set()
    month_counts, family_counts = collections.Counter(), collections.Counter()
    last_date = None
    unverified = []
    for report in sorted(reports, key=lambda row: row["date"]):
        date, entries, feed = report["date"], report["retail"], report.get("feed")
        if date == last_date:
            raise ValueError("Duplicate report date: " + date)
        last_date = date
        assets = [asset_id(x["title"]) for x in entries]
        families = [family_id(x["title"]) for x in entries]
        cutoff = report.get("cutoff_utc", date + "T00:00:00Z")
        row = {"date": date, "cutoff_utc": cutoff, "assets": assets, "families": families, "entries": []}
        if feed is None:
            unverified.append(date)
            row["evidence_status"] = "Own-date source timing unavailable; selection diagnostics only"
        elif feed.get("date") not in (None, date):
            failures.append({"date": date, "code": "wrong_feed_date"})
        for pos, entry in enumerate(entries):
            asset, family, text = assets[pos], families[pos], prose(entry)
            if feed is None:
                errors = []
                sources = [{"id": None, "published_at": None, "key": url, "title": ""} for url in entry.get("citation_urls", [])]
            else:
                errors, sources = validate_evidence(date, entry, feed, cutoff)
            failures.extend({"date": date, "asset": asset, **error} for error in errors)
            current = {"date": date, "cutoff_utc": cutoff, "asset": asset, "family": family, "text": text, "sources": sources, "position": pos}
            previous = previous_entries.get(asset)
            own_flags = []

            def flag(code: str, **details):
                own_flags.append({"flag_id": f"{date}:{asset}:{code}", "date": date, "asset": asset, "family": family, "code": code, **details})

            if previous:
                old_keys = {x["key"] for x in previous["sources"]}
                new_sources = [x for x in sources if x["published_at"] and x["key"] not in old_keys and utc(x["published_at"]) >= utc(previous["cutoff_utc"])]
                sim = similarity(text, previous["text"])
                current["prior_appearance"] = previous["date"]
                current["fresh_evidence_ids"] = [x["id"] for x in new_sources]
                current["price_stripped_similarity"] = round(sim, 4)
                if not new_sources:
                    flag("no_new_catalyst", prior_appearance=previous["date"])
                if sim >= .88 and len(words_without_prices(text)) >= 45:
                    flag("recycled_angle", prior_appearance=previous["date"], similarity=round(sim, 4))
            else:
                current["fresh_evidence_ids"] = [x["id"] for x in sources if x["id"] and x["published_at"]]
            if history and set(assets) == set(history[-1]["assets"]) and pos == 0:
                flag("same_basket", previous_report=history[-1]["date"])
            elif history and len(set(assets) & set(history[-1]["assets"])) >= 3 and pos == 0:
                flag("basket_overlap", previous_report=history[-1]["date"], count=len(set(assets) & set(history[-1]["assets"])))
            prior4 = history[-4:]
            hits = sum(family in item["families"] for item in prior4) + 1
            if len(prior4) == 4 and hits >= 4:
                flag("family_concentration", appearances=hits, trailing_reports=5)
            if pos == 0 and len(history) >= 2 and all(item["assets"][0] == asset for item in history[-2:]):
                flag("repeated_lead", trailing_reports=3)
            for match in RANKING.finditer(text):
                # A matching source headline can justify a specific measurement;
                # it still needs editorial review of its population/time period.
                flag("ranking_claim", quote=match.group(0))
                break
            for item in own_flags:
                decision = decisions.get(item["flag_id"])
                if decision is None:
                    item["status"] = "needs_review"
                else:
                    decision_used.add(item["flag_id"])
                    problems = validate_decision(item, decision, current)
                    item["status"] = "reviewed" if not problems else "invalid_decision"
                    item["decision"] = decision
                    if problems:
                        item["decision_errors"] = problems
                flags.append(item)
            row["entries"].append({key: value for key, value in current.items() if key != "text"})
            previous_entries[asset] = current
        month_counts.update(assets)
        family_counts.update(set(families))
        history.append(row)
        results.append(row)
    unresolved = [x for x in flags if x["status"] != "reviewed"]
    stale = sorted(set(decisions) - decision_used)
    return {
        "purpose": "Chronological retail editorial review; not measured retail popularity or a forced rotation rule.",
        "method_limits": "Lexical similarity and source-index timestamps are review signals, not article-body vintage or causal-attention proof. Family concentration alone does not require removal.",
        "reports_checked": len(results), "reports": results,
        "frequency_diagnostic_only": {"assets": dict(month_counts.most_common()), "families_report_count": dict(family_counts.most_common())},
        "hard_failures": failures, "flags": flags, "unresolved_flags": len(unresolved),
        "stale_decision_ids": stale,
        "source_timing_unverified_dates": unverified,
        "evidence_checks_passed": (not failures) if not unverified else None,
        "review_gate_passed": not failures and not unresolved and not stale and not unverified,
    }


class RetailHTMLParser(HTMLParser):
    """Read the existing retail block without treating adjacent sections as retail."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active = False
        self.heading_tag = None
        self.heading = []
        self.para = None
        self.current = None
        self.entries = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag in ("h2", "h3", "h4"):
            self.heading_tag, self.heading = tag, []
        elif tag == "span" and self.heading_tag in ("h3", "h4"):
            self.heading.append(" — ")
        if self.active and tag == "p":
            self.para = []
        if self.active and tag == "a" and self.current is not None:
            href = dict(attrs).get("href", "")
            if href.startswith(("https://", "http://")):
                self.current["citation_urls"].append(href)

    def handle_data(self, data):
        if self.heading_tag:
            self.heading.append(data)
        if self.para is not None:
            self.para.append(data)

    def handle_endtag(self, tag):
        if tag == self.heading_tag:
            heading = " ".join(" ".join(self.heading).split())
            if tag == "h2":
                self.active = "what retail is playing" in heading.lower()
                self.current = None
            elif self.active:
                self.current = {"title": heading, "parts": [], "citation_urls": []}
                self.entries.append(self.current)
            self.heading_tag, self.heading = None, []
        if tag == "p" and self.para is not None:
            text = " ".join(" ".join(self.para).split())
            if self.active and self.current is not None and text:
                label, sep, body = text.partition(":")
                self.current["parts"].append([label if sep else "Narrative", body.strip() if sep else text])
            self.para = None


def parse_retail_html(html: str) -> list[dict]:
    parser = RetailHTMLParser()
    parser.feed(html)
    return parser.entries


def audit_published(snapshot: Path, decision_path: Path | None = None) -> dict:
    """Snapshot layout is html/DATE.html plus optional json/DATE.json.

    Canonical spec-bearing JSON retains its explicit historical cutoff; legacy
    JSON retains generated_at. No new midnight boundary is imposed on legacy
    live editions, and missing source vintages remain explicitly unverified.
    """
    reports, hashes = [], {}
    for path in sorted((snapshot / "html").glob("????-??-??.html")):
        date = path.stem
        entries = parse_retail_html(path.read_text())
        if not entries:
            continue
        json_path = snapshot / "json" / (date + ".json")
        payload = json.loads(json_path.read_text()) if json_path.exists() else {}
        spec = payload.get("spec", {})
        cutoff = payload.get("news_cutoff_utc") if spec else payload.get("generated_at")
        if cutoff:
            utc(cutoff)
        report = {"date": date, "retail": entries, "feed": None}
        if cutoff:
            report["cutoff_utc"] = cutoff
        else:
            # There is no source timestamp proof in this fallback. The field
            # records a date boundary for chronology diagnostics only.
            report["cutoff_basis"] = "Date-only diagnostic; original generated_at unavailable"
        reports.append(report)
        hashes[date] = {"html_sha256": sha(path), "json_sha256": sha(json_path) if json_path.exists() else None}
    if not reports:
        raise ValueError("No retail sections found in snapshot")
    output = audit_reports(reports, load_decisions(decision_path))
    output["snapshot_sha256"] = hashes
    output["checked_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    return output


def validate_decision(flag: dict, decision: dict, current: dict) -> list[str]:
    errors = []
    disposition = decision.get("disposition")
    rationale = decision.get("changed_angle", decision.get("rationale", ""))
    if not isinstance(rationale, str) or len(rationale.strip()) < 40:
        errors.append("Specific editorial rationale of at least 40 characters required")
    if not decision.get("reviewer"):
        errors.append("Reviewer required")
    evidence = decision.get("evidence_ids", [])
    cited = {x["id"] for x in current["sources"]}
    if not evidence or not set(evidence) <= cited:
        errors.append("Decision evidence must be nonempty and cited in this entry's eligible own-date feed")
    if disposition == "material_update":
        if not set(evidence) & set(current["fresh_evidence_ids"]):
            errors.append("Material update needs a new source published since this asset's prior appearance cutoff")
    elif disposition == "brief_carryover":
        if len(re.findall(r"\b\w+\b", CITE.sub("", current["text"]))) > 160:
            errors.append("Unchanged carryover must be brief (at most 160 words)")
        if current["position"] == 0:
            errors.append("An unchanged carryover cannot retain the full lead essay")
    elif disposition == "reviewed_selection":
        if flag["code"] in {"no_new_catalyst", "recycled_angle", "repeated_lead"}:
            errors.append("Persistence requires a material update or a shortened carryover")
    else:
        errors.append("Unknown editorial disposition")
    if flag["code"] == "ranking_claim" and not decision.get("measurement_scope"):
        errors.append("Ranking/quantity claim requires an explicit dated measurement scope, not inferred popularity")
    return errors


def load_decisions(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    records = json.loads(path.read_text()).get("decisions", [])
    ids = [x["flag_id"] for x in records]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate editorial decision ID")
    return {x["flag_id"]: x for x in records}


def audit_month(root: Path, decision_path: Path | None = None) -> dict:
    reports = []
    hashes = {}
    for path in sorted((root / "specs").glob("????-??-??.json")):
        spec = json.loads(path.read_text())
        if not spec.get("retail"):
            continue
        date = spec["date"]
        reports.append({"date": date, "retail": spec["retail"], "feed": load_feed(root, date)})
        hashes[date] = sha(path)
    if not reports:
        raise ValueError("No retail specs found under " + str(root))
    output = audit_reports(reports, load_decisions(decision_path))
    output["spec_sha256"] = hashes
    output["checked_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    output["decision_file_sha256"] = sha(decision_path) if decision_path and decision_path.exists() else None
    return output


def require_review(root: Path) -> dict:
    """Build/publish precondition for a reconstructed month, never live rotation."""
    result = audit_month(root, root / 'checks/retail_editorial_decisions.json')
    output = root / 'checks/retail_quality.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2))
    if not result['review_gate_passed']:
        raise ValueError('Retail evidence or cross-edition review remains unresolved: '+str(root))
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("month", type=Path)
    ap.add_argument("--decisions", type=Path)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--require-reviewed", action="store_true", help="Fail on unresolved review flags as well as hard evidence errors")
    ap.add_argument("--published-snapshot", action="store_true", help="Read html/DATE.html and optional json/DATE.json; legacy timing remains unverified")
    args = ap.parse_args()
    result = audit_published(args.month, args.decisions) if args.published_snapshot else audit_month(args.month, args.decisions)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2))
    summary = {key: result[key] for key in ["reports_checked", "evidence_checks_passed", "unresolved_flags", "review_gate_passed"]}
    summary["top_assets_diagnostic"] = dict(list(result["frequency_diagnostic_only"]["assets"].items())[:12])
    summary["top_families_diagnostic"] = dict(list(result["frequency_diagnostic_only"]["families_report_count"].items())[:12])
    print(json.dumps(summary, indent=2))
    if result["hard_failures"] or (args.require_reviewed and not result["review_gate_passed"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
