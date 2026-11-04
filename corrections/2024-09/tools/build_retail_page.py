"""build_retail_page.py — one wide, self-contained page for the September 2024 "What Retail Is Playing" sections.

Reads only the edition texts (specs/<date>.json, notes/<date>.json) and, to label citations, each edition's own
frozen feed (feeds/<date>.json.gz). Each edition's section is shown exactly as written for its report date, in
date order. Nothing from a later edition is used to change an earlier one, and no outcome data is added.

Output: retail/What_Retail_Is_Playing_2024-09.html (inline CSS, no scripts, no external assets).
"""
from __future__ import annotations

import datetime as dt
import gzip
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATES = [dt.date(2024, 9, n).isoformat() for n in range(1, 31) if dt.date(2024, 9, n).weekday() < 5]
CITE = re.compile(r"\s*\[\[(n\d{4,6})\]\]")


def load_feed(d):
    path = ROOT / "feeds" / f"{d}.json.gz"
    if not path.exists():
        return {}
    data = json.loads(gzip.decompress(path.read_bytes()))
    return {x["id"]: x for x in data["items"]}


def esc(s):
    return html.escape(s, quote=True)


def cite_html(text, feed):
    """Escape the text and turn [[nXXXX]] markers into superscript source chips with the headline on hover."""
    for token in re.findall(r'\[\[([^\]]+)\]\]', text):
        if not re.fullmatch(r'n\d{4,6}', token) or token not in feed:
            raise ValueError('Unresolved retail citation marker [['+token+']]')
    out, pos = [], 0
    for m in CITE.finditer(text):
        out.append(esc(text[pos:m.start()]))
        item = feed.get(m.group(1), {})
        tip = " · ".join(x for x in [item.get("published_at", "")[:16].replace("T", " "), item.get("src", ""),
                                     item.get("title", "")] if x)
        url = item.get("url", "")
        chip = esc(m.group(1))
        if url.startswith(("https://", "http://")):
            chip = f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{chip}</a>'
        out.append(f'<sup class="cite" title="{esc(tip)}">{chip}</sup>')
        pos = m.end()
    out.append(esc(text[pos:]))
    return "".join(out)


def load_edition(d):
    spec = json.loads((ROOT / "specs" / f"{d}.json").read_text(encoding="utf-8"))
    notes_path = ROOT / "notes" / f"{d}.json"
    notes = json.loads(notes_path.read_text(encoding="utf-8")) if notes_path.exists() else {}
    return spec, notes


def trade_card(item, feed, lead=False):
    parts = "".join(
        f'<div class="part"><h4>{esc(label)}</h4><p>{cite_html(text, feed)}</p></div>'
        for label, text in item.get("parts", [])
    )
    cls = "trade lead" if lead else "trade"
    return f'<article class="{cls}"><h3>{esc(item["title"])}</h3>{parts}</article>'


def source_ledger(spec, feed):
    texts = [spec.get("retail_intro", "")]
    texts.extend(text for item in spec.get("retail", []) for _, text in item.get("parts", []))
    ids = sorted({key for text in texts for key in CITE.findall(text)})
    rows = []
    for key in ids:
        item = feed[key]
        title = esc(item["title"])
        url = item.get("url", "")
        if url.startswith(("https://", "http://")):
            title = f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{title}</a>'
        stamp = item.get("published_at", "").replace("T", " ")
        rows.append(f'<li><strong>{esc(key)}</strong> · {title}<small>{esc(item.get("src", ""))} · {esc(stamp)}</small></li>')
    return f'<details class="sources"><summary>Dated sources · {len(ids)} headlines</summary><ol>{"".join(rows)}</ol></details>'


def build():
    sections, index = [], []
    for d in DATES:
        if not (ROOT / 'specs' / f'{d}.json').exists():
            continue
        spec, notes = load_edition(d)
        feed = load_feed(d)
        retail = spec.get("retail", [])
        if not retail:
            continue
        date_label = dt.date.fromisoformat(d).strftime("%A %d %B %Y")
        lead, smaller = retail[0], retail[1:]
        index.append((d, lead["title"], [x["title"] for x in smaller]))
        small_html = "".join(trade_card(x, feed) for x in smaller)
        sections.append(
            f'<section class="day" id="{d}">'
            f'<header class="dayhead"><p class="kicker">Report cutoff 00:00 UTC · {esc(date_label)}</p>'
            f'<p class="intro">{cite_html(spec.get("retail_intro", ""), feed)}</p></header>'
            f'{trade_card(lead, feed, lead=True)}'
            f'<div class="smalls">{small_html}</div>'
            f'{source_ledger(spec, feed)}'
            "</section>"
        )
    toc = "".join(
        f'<a class="tocrow" href="#{d}"><span class="tocdate">{dt.date.fromisoformat(d).strftime("%a %d %b")}</span>'
        f'<span class="toclead">{esc(lead)}</span></a>'
        for d, lead, _ in index
    )
    page = PAGE.replace("{toc}", toc).replace("{sections}", "".join(sections)).replace("{count}", str(len(index)))
    out = ROOT / "retail" / "What_Retail_Is_Playing_2024-09.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out, len(index)


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>What Retail Is Playing · September 2024</title>
<style>
:root{--bg:#f6f7fb;--panel:#ffffff;--ink:#16203a;--muted:#5b6780;--line:#dfe4ef;--accent:#e4572e;--accent2:#2f6fde;--chip:#eef2fb;--lead:#fff7f2}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#0f1424;--panel:#171d31;--ink:#e9edf7;--muted:#9aa6c2;--line:#2a3350;--accent:#ff8a5b;--accent2:#7aa7ff;--chip:#202843;--lead:#231a1f}}
:root[data-theme="dark"]{--bg:#0f1424;--panel:#171d31;--ink:#e9edf7;--muted:#9aa6c2;--line:#2a3350;--accent:#ff8a5b;--accent2:#7aa7ff;--chip:#202843;--lead:#231a1f}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
.wrap{max-width:1240px;margin:0 auto;padding:32px 16px 64px}
.masthead{padding:28px 28px 22px;background:linear-gradient(135deg,var(--panel),var(--lead));border:1px solid var(--line);border-radius:18px;margin-bottom:24px}
.masthead h1{margin:0 0 6px;font-size:clamp(28px,4vw,40px);letter-spacing:-.02em}
.masthead .sub{margin:0;color:var(--muted)}
.masthead .note{margin:14px 0 0;color:var(--muted);font-size:14px}
.toc{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:8px;margin:0 0 32px}
.tocrow{display:flex;gap:10px;align-items:baseline;text-decoration:none;color:inherit;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px 12px}
.tocrow:hover{border-color:var(--accent2)}
.tocdate{font-variant-numeric:tabular-nums;color:var(--accent2);font-weight:600;white-space:nowrap;font-size:14px}
.toclead{font-size:14px;color:var(--ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.day{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:26px 26px 20px;margin:0 0 26px}
.dayhead .kicker{margin:0;color:var(--accent);font-size:12px;letter-spacing:.12em;text-transform:uppercase;font-weight:700}
.dayhead .intro{margin:8px 0 18px;font-size:18px;color:var(--ink);border-left:4px solid var(--accent);padding-left:14px}
.trade{border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin:0 0 16px;background:var(--panel)}
.trade.lead{background:var(--lead);border-color:color-mix(in srgb,var(--accent) 40%,var(--line));padding:22px 24px}
.trade h3{margin:0 0 10px;font-size:20px;letter-spacing:-.01em}
.trade.lead h3{font-size:24px}
.part{margin:0 0 12px}
.part h4{margin:0 0 4px;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--accent2)}
.part p{margin:0;font-size:15.5px;line-height:1.65}
.smalls{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,380px),1fr));gap:16px}
.smalls .trade{margin:0}
.cite{font-size:10.5px;color:var(--muted);background:var(--chip);border-radius:4px;padding:0 4px;margin-left:2px;cursor:help;font-variant-numeric:tabular-nums}
.cite a{color:inherit;text-decoration:none}.cite a:hover{text-decoration:underline}
.sources{margin-top:20px;border-top:1px solid var(--line);padding-top:14px;font-size:13px;color:var(--muted)}
.sources summary{cursor:pointer;font-weight:600}.sources ol{padding-left:22px}.sources li{padding:7px 0;overflow-wrap:anywhere}
.sources a{color:var(--accent2)}.sources small{display:block;margin-top:3px}
.foot{margin-top:28px;color:var(--muted);font-size:13px;line-height:1.6}
@media (max-width:600px){.wrap{padding:16px 16px 40px}.day{padding:18px 16px}.trade{padding:14px 14px}.masthead{padding:20px 18px}}
</style>
</head>
<body>
<main class="wrap">
<header class="masthead">
<h1>What Retail Is Playing</h1>
<p class="sub">September 2024 · {count} weekday editions · 2–30 September 2024</p>
<p class="note">Each section is shown as it was written for its own report date, with information available before 00:00 UTC on that date. Prices are completed sessions before the cutoff. Source numbers link to the cited reporting; open the dated sources below each edition for headline details. Nothing from a later edition or a later outcome appears in an earlier section.</p>
</header>
<nav class="toc" aria-label="Editions">{toc}</nav>
{sections}
<footer class="foot">Sources: Google News RSS headlines published strictly before each report date's 00:00 UTC cutoff (7/14/35-day windows); Yahoo Finance completed closes and the US Treasury daily par curve before the cutoff. Headlines describe what was reported, not verified facts. Retrospective reconstruction; no trading recommendation.</footer>
</main>
</body>
</html>
"""

if __name__ == "__main__":
    out, n = build()
    print("wrote", out, "editions:", n)
