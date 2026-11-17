"""Extract only the four positional topics in What Retail Is Playing.

Original historical source JSON is authoritative; rewritten HTML and other report
sections are never signal inputs. No price or outcome data enters this extractor.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INTRO_PREFIX = "The dominant popular-narrative trade capturing retail attention right now"
LEAD_FIELDS = [
    ("why_retail_is_here", "Why retail is here:"),
    ("driving_surge", "What's driving the surge"),
    ("social_signal", "The social signal:"),
    ("historical_analog", "Historical analog:"),
    ("smart_money_view", "Smart money view:"),
    ("narrative_break", "When the narrative breaks:"),
]


def timestamp(value):
    if not value:
        return None
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timezone required")
    return parsed.astimezone(dt.timezone.utc)


def resolve_source(meta, manifest):
    path = Path(meta["path"])
    if path.exists():
        return path
    candidates = [manifest.parent / "verified_originals" / path.name,
                  manifest.parent / "original_reports" / path.name,
                  ROOT / "original_reports" / path.name]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(path)


def extract(meta, manifest):
    source = resolve_source(meta, manifest)
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == meta["sha256"], (meta["report_date"], "source hash mismatch")
    assert meta.get("version_id") and meta["timestamp_status"] == "contemporaneous_s3_version"
    content = json.loads(raw)
    headings = [text for section in content["sections"] for text in section.get("subheadings", [])]
    body = [text for section in content["sections"] for text in section.get("body", [])]
    indices = [i for i, text in enumerate(headings) if re.search(r"\bWhat Retail Is Playing\b", text)]
    assert len(indices) == 1, (meta["report_date"], "ambiguous section heading")
    heading_start = indices[0]
    topic_headings = headings[heading_start + 1:]
    assert len(topic_headings) == 4, (meta["report_date"], len(topic_headings))
    intro_indices = [i for i, text in enumerate(body) if text.startswith(INTRO_PREFIX)]
    assert len(intro_indices) == 1, (meta["report_date"], "ambiguous section intro")
    intro_index = intro_indices[0]
    section_body = body[intro_index + 1:]
    assert len(section_body) == 10, (meta["report_date"], len(section_body))
    for i, (_, prefix) in enumerate(LEAD_FIELDS):
        assert section_body[i].startswith(prefix), (meta["report_date"], i, section_body[i][:100])
    assert section_body[-1].startswith("Powered by AWS Lambda"), (meta["report_date"], "unexpected footer")
    generated = content.get("generated_at")
    modified = meta["last_modified"]
    assert timestamp(modified).date().isoformat() == meta["report_date"]
    available = max(x for x in [timestamp(generated), timestamp(modified)] if x is not None)
    fields = {
        "report_date": meta["report_date"],
        "source_key": meta["key"],
        "source_path": str(source),
        "source_sha256": digest,
        "source_version_id": meta["version_id"],
        "source_timestamp_status": meta["timestamp_status"],
        "generated_at": generated or "",
        "last_modified": modified,
        "available_at": available.isoformat(),
        "section_heading": headings[heading_start],
        "section_intro": body[intro_index],
    }
    slots = []
    for slot in range(1, 5):
        paragraphs = section_body[:6] if slot == 1 else [section_body[slot + 4]]
        body_indices = list(range(intro_index + 1, intro_index + 7)) if slot == 1 else [intro_index + slot + 5]
        heading = topic_headings[slot - 1]
        item = {
            **fields,
            "slot": slot,
            "slot_role": "dominant_narrative" if slot == 1 else "secondary_topic",
            "heading": heading,
            "text": "\n\n".join(paragraphs),
            "paragraphs": paragraphs,
            "heading_index": heading_start + slot,
            "body_indices": body_indices,
            "heading_dollar_tickers_raw": re.findall(r"\$([A-Z][A-Z0-9.\-_]{0,11})\b", heading),
            "heading_uppercase_tokens_raw": re.findall(r"\b[A-Z][A-Z0-9.\-_]{1,11}\b", heading),
        }
        for i, (field, _) in enumerate(LEAD_FIELDS):
            item[field] = paragraphs[i] if slot == 1 else ""
        slots.append(item)
    return {**fields, "slots": slots}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT)
    args = parser.parse_args()
    manifest = args.manifest
    if manifest is None:
        manifest = next((p for p in [ROOT / "original_manifest.json",
                                    ROOT / "sources/original_manifest.json",
                                    ROOT.parent / "report_strategy/original_manifest.json"] if p.exists()), None)
    if manifest is None:
        raise FileNotFoundError("Pass --manifest with the historical original manifest")
    args.output.mkdir(exist_ok=True, parents=True)
    metadata = json.loads(manifest.read_text())
    records = [extract(meta, manifest) for meta in sorted(metadata, key=lambda row: row["report_date"])]
    dates = [row["report_date"] for row in records]
    assert len(dates) == len(set(dates))
    with (args.output / "retail_sections.jsonl").open("w") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    items = [item for row in records for item in row["slots"]]
    with (args.output / "retail_items.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(items[0]))
        writer.writeheader()
        for item in items:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v for k, v in item.items()})
    audit = {
        "extractor_version": "1.0-four-positional-retail-topics",
        "source_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "source_reports": len(records),
        "slot_items": len(items),
        "first_report_date": min(dates),
        "last_report_date": max(dates),
        "slots_per_report": dict(Counter(len(row["slots"]) for row in records)),
        "slot_counts": dict(Counter(item["slot"] for item in items)),
        "all_source_hashes_verified": True,
        "all_sources_contemporaneous_s3_versions": True,
        "all_four_topics_extracted": True,
        "slot_1_schema": [field for field, _ in LEAD_FIELDS],
        "slot_2_to_4_schema": "Exact own heading plus one paragraph each; positional slots are not fixed themes.",
        "excluded_original_pdf_reports": ["2026-03-08", "2026-03-09"],
        "pdf_exclusion_reason": "Uniform original JSON structure supports exact quote and four-part alignment; earlier PDFs are excluded rather than inferred from rewritten content.",
        "signal_inputs": "Only the section heading, its four topic headings, six lead-topic fields and three secondary-topic paragraphs. Footer is excluded.",
        "unresolved_extraction_cases": [],
    }
    (args.output / "retail_extraction_audit.json").write_text(json.dumps(audit, indent=2))
    (args.output / "retail_item_schema.json").write_text(json.dumps({
        "primary_key": ["report_date", "slot"],
        "source": "Exact earliest same-day original S3 report JSON version",
        "slot": "1 dominant narrative; 2, 3, 4 secondary topics in the source's original order. Topic themes may move between slots.",
        "text": "Exact source paragraph(s) for that slot only",
        "available_at": "max(source generated_at, historical S3 version LastModified), UTC",
        "heading_dollar_tickers_raw": "Literal dollar-prefixed uppercase strings, without tradability or ticker validation",
        "heading_uppercase_tokens_raw": "Literal uppercase strings, not an inferred instrument list",
        "source_path": "Source retrieval path, remapped by the extractor after a portable package is moved",
        "heading_index_and_body_indices": "Zero-based positions in the flattened original JSON subheadings and body arrays",
        "lead_fields": dict(LEAD_FIELDS),
    }, indent=2))
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
