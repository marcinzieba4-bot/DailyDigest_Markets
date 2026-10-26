"""render.py <dates> — turn ../specs/<date>.json into the archive page ../html/<date>.html and the machine-readable copy
../json/<date>_Market_Intelligence.json, in the exact layout of the March 2026 retrospective briefings.

Citations are written in the spec as [[n0123]] (an item id of ../feeds/<date>.json) and rendered as
<a href=URL title=HEADLINE>Source [Mon DD]</a>; every cited item is listed under "Dated sources" (oldest first) and
in the JSON "evidence" map. Spec format: see BRIEF.md."""
import json, os, re, sys, html, datetime as dt

T = os.path.dirname(os.path.abspath(__file__)); C = os.path.dirname(T)
CITE = re.compile(r'\s*\[\[(n\d{4})\]\]')
COLORS = {'Bullish': '#2d7a2d', 'Bearish': '#c0392b', 'Mixed': '#9a6b00'}
CSS = ('body{font-family:Arial,sans-serif;max-width:860px;margin:auto;padding:24px;color:#222;line-height:1.6}'
       'h1{color:#1a1a2e}h2{color:#1a1a2e;border-bottom:2px solid #1a73e8;padding-bottom:6px}h3{margin:0 0 10px}'
       'a{color:#1467ad}article{margin-bottom:18px;padding:16px;background:#f8f9ff;border-left:4px solid #1a73e8;'
       'border-radius:4px}.stance{font-size:13px;font-weight:normal}.meta{color:#777;font-size:13px}.sources{font-size:12px}'
       'p{margin:9px 0}')
GEO = {'US': '🇺🇸 United States', 'EU': '🇪🇺 European Union', 'CN': '🇨🇳 China', 'JP': '🇯🇵 Japan', 'AU': '🇦🇺 Australia',
       'PL': '🇵🇱 Poland'}
SECTORS = {'XLK': '💻 XLK — Technology', 'XLC': '📡 XLC — Communication Services', 'XLF': '🏦 XLF — Financials',
           'XLE': '⛽ XLE — Energy', 'XLI': '🏗️ XLI — Industrials', 'XLY': '🛍️ XLY — Consumer Discretionary',
           'XLP': '🛒 XLP — Consumer Staples', 'XLV': '💊 XLV — Healthcare', 'XLB': '🧱 XLB — Materials',
           'XLRE': '🏠 XLRE — Real Estate', 'XLU': '⚡ XLU — Utilities', 'SXAP': '🚗 European Auto — SXAP',
           'SOXX': '🔬 US–Asia Semis — SOXX / ASML / TSMC'}
FOOTER = ('Market data: Yahoo Finance, prior completed sessions; Treasury curve: US Treasury daily par yields. Changes are '
          'price changes, not total returns. Currency sessions follow exchange-local dates; crypto observations include '
          'weekends.')
esc = lambda s: html.escape(s, quote=False)
attr = lambda s: html.escape(s, quote=True)


def load_feed(d):
    """../feeds/<date>.json, or the committed gzip copy ../feeds/<date>.json.gz."""
    p = os.path.join(C, 'feeds', f'{d}.json')
    if os.path.exists(p):
        return json.load(open(p, encoding='utf-8'))
    import gzip
    return json.load(gzip.open(p + '.gz', 'rt', encoding='utf-8'))


def feed(d):
    return {x['id']: x for x in load_feed(d)['items']}


def short_date(iso):
    return dt.datetime.fromisoformat(iso).strftime('%b %d')


class Doc:
    def __init__(self, d):
        self.d, self.items, self.cited = d, feed(d), []

    def link(self, nid):
        x = self.items[nid]
        if nid not in self.cited:
            self.cited.append(nid)
        return f'<a href="{attr(x["url"])}" title="{attr(x["title"])}">{esc(x["src"])} [{short_date(x["published_at"])}]</a>'

    def text(self, s):
        out, pos = [], 0
        for m in CITE.finditer(s):
            out.append(esc(s[pos:m.start()])); out.append(' ' + self.link(m.group(1))); pos = m.end()
        out.append(esc(s[pos:]))
        return ''.join(out).strip()

    def parts(self, parts):
        return [f'<p><strong>{esc(lbl)}:</strong> {self.text(txt)}</p>' for lbl, txt in parts]


def stance(s):
    return f'<span class="stance" style="color:{COLORS[s]}">{s}</span>'


def render(d):
    spec = json.load(open(os.path.join(C, 'specs', f'{d}.json')))
    D = dt.date.fromisoformat(d); label = D.strftime('%A, %B %d %Y')
    doc = Doc(d); L = []
    a = L.append
    a('<!DOCTYPE html>')
    a('<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">')
    a(f'<title>Market Intelligence Briefing — {label}</title>')
    a(f'<style>{CSS}</style></head><body>')
    a('<h1>Market Intelligence Briefing</h1>')
    a(f'<p>{label} — Macro · Sectors · Flows · Crypto</p>')
    a(f'<p class="meta">Information cutoff: {d} 00:00 UTC. Market figures use completed observations before this date.</p>')
    a('<hr>')
    a('<h2>🌍 Geographic Macro Overview</h2>')
    for g in spec['geo']:
        a('<article>')
        a(f'<h3>{GEO[g["key"]]} {stance(g["stance"])} <span class="stance">{esc(g["label"])}</span></h3>')
        L.extend(doc.parts(g['parts'])); a('</article>')
    a('<h2>📊 Sector Deep Dive</h2>')
    for s in spec['sectors']:
        a('<article>')
        a(f'<h3>{SECTORS[s["key"]]} {stance(s["stance"])}</h3>')
        L.extend(doc.parts(s['parts'])); a('</article>')
    a('<h2>🧮 Earnings Pattern — What the Market Pays For</h2>')
    ep = spec['earnings_pattern']
    a('<article>'); a(f'<h3>{esc(ep["title"])}</h3>'); L.extend(doc.parts(ep['parts'])); a('</article>')
    a('<h2>🔍 Underowned Themes — Attention and Exposure Gaps</h2>')
    for u in spec['underowned']:
        a('<article>'); a(f'<h3>{esc(u["title"])}</h3>'); L.extend(doc.parts(u['parts'])); a('</article>')
    for key, h2 in (('crypto', '₿ Crypto & Digital Assets'), ('flows', '💰 Capital Flows & Liquidity Framework')):
        b = spec[key]
        a(f'<h2>{esc(h2)}</h2>'); a('<article>'); a(f'<h3>{esc(b["title"])}</h3>'); L.extend(doc.parts(b['parts'])); a('</article>')
    a('<h2>🔮 Anticipatory Positioning — Markets Pricing In Future Events</h2>')
    for x in spec['anticipatory']:
        a('<article>'); a(f'<h3>{esc(x["title"])}</h3>'); L.extend(doc.parts(x['parts'])); a('</article>')
    a('<h2>⚡ High-Conviction Stock Catalysts</h2>')
    for x in spec['catalysts']:
        a('<article>'); a(f'<h3>{esc(x["title"])} {stance(x["stance"])}</h3>'); L.extend(doc.parts(x['parts'])); a('</article>')
    a('<h2>🔥 What Retail Is Playing</h2>')
    for x in spec['retail']:
        a('<article>'); a(f'<h3>{esc(x["title"])}</h3>'); L.extend(doc.parts(x['parts'])); a('</article>')
    a('<hr>')
    a(f'<p class="meta">{FOOTER}</p>')
    a('<details class="sources"><summary>Dated sources</summary><ol>')
    for nid in sorted(doc.cited, key=lambda n: (doc.items[n]['published_at'], doc.cited.index(n))):
        x = doc.items[nid]
        a(f'<li><a href="{attr(x["url"])}">{attr(x["title"])}</a> — {esc(x["src"])}, {x["published_at"][:10]}</li>')
    a('</ol></details>')
    a('</body></html>')
    page = '\n'.join(L) + '\n'
    os.makedirs(os.path.join(C, 'html'), exist_ok=True)
    open(os.path.join(C, 'html', f'{d}.html'), 'w', encoding='utf-8').write(page)
    evidence = {}
    for i, nid in enumerate(doc.cited, 1):
        x = doc.items[nid]
        evidence[f'e{i}'] = {'title': x['title'], 'published_at': x['published_at'], 'source': x['src'], 'url': x['url'],
                             'category': x['cat'], 'feed_id': nid}
    payload = {'date': label, 'report_date': d, 'generated_at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
               'news_cutoff_utc': f'{d}T00:00:00Z', 'sections': sections(page), 'evidence': evidence}
    os.makedirs(os.path.join(C, 'json'), exist_ok=True)
    json.dump(payload, open(os.path.join(C, 'json', f'{d}_Market_Intelligence.json'), 'w'), ensure_ascii=False, indent=2)
    return page, doc


def parse_html_paragraphs(full_html):
    """Verbatim copy of lambda_function._parse_html_paragraphs (the Lambda's JSON / PDF paragraph parser)."""
    clean = re.sub(r'<style[^>]*>.*?</style>', '', full_html, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<script[^>]*>.*?</script>', '', clean, flags=re.DOTALL | re.IGNORECASE)

    tag_re = re.compile(r'<(/?)(\w+)[^>]*>', re.IGNORECASE)
    buf, paragraphs, in_skip, tag_stack = [], [], 0, []
    BLOCK_TAGS = {'p', 'div', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'td', 'th', 'blockquote'}

    def flush(tag='body'):
        text = html.unescape(''.join(buf)).strip()
        buf.clear()
        if not text:
            return
        style = 'h1' if tag == 'h1' else ('h2' if tag in ('h2', 'h3', 'h4', 'h5') else 'body')
        paragraphs.append((style, text))

    for token in re.split(r'(<[^>]+>)', clean):
        m = tag_re.match(token)
        if m:
            tag, closing = m.group(2).lower(), m.group(1) == '/'
            if tag in ('head', 'style', 'script'):
                in_skip += -1 if closing else 1
            elif in_skip > 0:
                pass
            elif not closing:
                tag_stack.append(tag)
                if tag == 'hr':
                    flush(); paragraphs.append(('hr', ''))
                elif tag == 'br':
                    buf.append('\n')
            else:
                if tag_stack and tag_stack[-1] == tag:
                    tag_stack.pop()
                if tag in BLOCK_TAGS:
                    flush(tag)
        elif in_skip == 0:
            buf.append(token)

    flush()
    return paragraphs


def sections(page):
    out, cur = [], None
    for style, text in parse_html_paragraphs(page):
        if style == 'h1':
            cur = {'heading': text, 'subheadings': [], 'body': []}; out.append(cur)
        elif style in ('h2', 'body') and text:
            if cur is None:
                cur = {'heading': '', 'subheadings': [], 'body': []}; out.append(cur)
            cur['subheadings' if style == 'h2' else 'body'].append(text)
    return out


if __name__ == '__main__':
    for d in sys.argv[1:]:
        page, doc = render(d)
        print(d, len(page), 'bytes,', len(doc.cited), 'sources')
