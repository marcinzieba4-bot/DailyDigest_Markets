"""Print section-format diagnostics for three May reports and one boundary control.

Only structural counts, short generic section labels and HTTP/raw hash metadata
are emitted. No raw HTML, topic paragraphs, mapped decisions or market returns.
"""
from __future__ import annotations
import collections, hashlib, json, re, urllib.request
from bs4 import BeautifulSoup
DATES = ("2024-04-30", "2024-05-01", "2024-05-15", "2024-05-31")
URL = "https://d7g7nkeytae81.cloudfront.net/reports/archive/{date}.html"
def label(tag):
    text = tag.get_text(" ", strip=True)
    return {"tag": tag.name, "class": tag.get("class", []),
            "text": text if len(text) <= 160 else "[long heading: " + str(len(text)) + " characters]"}
def main():
    results = []
    for day in DATES:
        request = urllib.request.Request(URL.format(date=day), headers={
            "User-Agent": "RetailResearchBacktest/1.0 (read-only schema diagnosis)"})
        with urllib.request.urlopen(request, timeout=45) as response:
            assert response.status == 200
            body = response.read()
            last_modified = response.headers.get("Last-Modified", "")
        soup = BeautifulSoup(body, "html.parser")
        headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
        retail = [label(h) for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "strong", "b"])
                  if "retail" in h.get_text().casefold() and len(h.get_text(" ", strip=True)) <= 160]
        nearby = []
        for node in soup.find_all(string=True):
            text = str(node).strip()
            if len(text) <= 160 and re.search(r"what\s+retail", text, re.I):
                parent = node.parent
                ancestors = []
                for _ in range(4):
                    if parent is None: break
                    ancestors.append({"tag": parent.name, "class": parent.get("class", [])})
                    parent = parent.parent
                nearby.append({"section_label": text, "ancestors": ancestors})
        results.append({"report_date": day, "http_status": 200, "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(), "last_modified_http": last_modified,
            "heading_tag_counts": dict(collections.Counter(h.name for h in headings)),
            "normalized_exact_h1_h6_marker_tags": [h.name for h in headings
                if " ".join(h.get_text(" ", strip=True).split()).casefold() == "what retail is playing"],
            "h1_h2_labels": [label(h) for h in headings if h.name in ["h1", "h2"]],
            "case_insensitive_retail_heading_candidates": retail,
            "what_retail_text_node_structure": nearby[:8],
            "what_retail_text_node_count": len(nearby)})
    print(json.dumps({"source_schema_diagnostics_only": True, "reports": results},
                     indent=2, ensure_ascii=True), flush=True)
if __name__ == "__main__":
    main()
