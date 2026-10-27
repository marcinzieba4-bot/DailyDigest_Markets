"""render.py <dates> — turn ../specs/<date>.json into the archive page ../html/<date>.html and the machine-readable copy
../json/<date>_Market_Intelligence.json, in the inline-styled layout of the August 2026 archive briefings (no stylesheet,
one accent colour per section, the same block and rule styling).

Citation markers ([[nXXXX]]) in the spec are dropped: the published pages carry no citations, links or source list.
Spec format: see BRIEF.md."""
import json, os, re, sys, html, datetime as dt

T = os.path.dirname(os.path.abspath(__file__)); C = os.path.dirname(T)
CITE = re.compile(r'\s*\[\[n\d{4}\]\]')
COLORS = {'Bullish': '#2d7a2d', 'Bearish': '#c0392b', 'Mixed': '#b07d00'}
ARROWS = {'Bullish': '↑', 'Bearish': '↓', 'Mixed': '→'}
BODY = 'font-family:Arial,sans-serif;max-width:820px;margin:auto;padding:24px;color:#222;line-height:1.6'
PILL = 'font-size:12px;background:#e8f0fe;padding:2px 8px;border-radius:10px;color:#1a73e8'
TICKER = 'background:#ffe0b2;padding:2px 6px;border-radius:3px'
# Per-section accent: heading underline colour, block background, left border width / colour, block padding and spacing.
BOX = {
    'geo':           dict(c='#1a73e8', bg='#f8f9ff', bl=5, p=16, mb=24),
    'sectors':       dict(c='#34a853', bg='#f9fff9', bl=4, p=14, mb=18),
    'earnings':      dict(c='#00897b', bg='#f0faf8', bl=4, p=14, mb=18),
    'underowned':    dict(c='#f4b400', bg='#fffdf0', bl=4, p=14, mb=16),
    'crypto':        dict(c='#9c27b0', bg='#f5f0ff', bl=5, p=16, mb=20),
    'flows':         dict(c='#e91e8c', bg='#fff0f8', bl=5, p=16, mb=20),
    'anticipatory':  dict(c='#00b894', bg='#f0fff4', bl=4, p=14, mb=16),
    'catalysts':     dict(c='#e67e22', bg='#fff8f0', bl=4, p=16, mb=22),
    'retail':        dict(c='#ff6b35', bg='#fff8f5', bl=6, p=20, mb=28),
    'retail_small':  dict(c='#ff9a70', bg='#fff8f5', bl=3, p=14, mb=14),
}
GEO = {'US': '🇺🇸 United States', 'EU': '🇪🇺 European Union', 'CN': '🇨🇳 China', 'JP': '🇯🇵 Japan', 'AU': '🇦🇺 Australia',
       'PL': '🇵🇱 Poland'}
SECTORS = {'XLK': '💻 XLK — Technology', 'XLC': '📡 XLC — Communication Services', 'XLF': '🏦 XLF — Financials',
           'XLE': '⛽ XLE — Energy', 'XLI': '🏗️ XLI — Industrials', 'XLY': '🛍️ XLY — Consumer Discretionary',
           'XLP': '🛒 XLP — Consumer Staples', 'XLV': '💊 XLV — Healthcare', 'XLB': '🧱 XLB — Materials',
           'XLRE': '🏠 XLRE — Real Estate', 'XLU': '⚡ XLU — Utilities', 'SXAP': '🚗 European Auto (SXAP)',
           'SOXX': '🔬 US/Asia Semis (SOXX / ASML / TSMC)'}
FOOTER = ('Market data: Yahoo Finance, prior completed sessions; Treasury curve: US Treasury daily par yields. Changes are '
          'price changes, not total returns. Currency sessions follow exchange-local dates; crypto observations include '
          'weekends.')
esc = lambda s: html.escape(s, quote=False)
attr = lambda s: html.escape(s, quote=True)


class Doc:
    """Text without citations: the [[nXXXX]] markers in the spec are dropped, no links or source list are written."""

    def text(self, s):
        return esc(CITE.sub('', s)).strip()

    def parts(self, parts):
        return [f'<p><strong>{esc(lbl)}:</strong> {self.text(txt)}</p>' for lbl, txt in parts]


def block(key):
    s = BOX[key]
    return (f'margin-bottom:{s["mb"]}px;padding:{s["p"]}px;background:{s["bg"]};'
            f'border-left:{s["bl"]}px solid {s["c"]};border-radius:4px')


def heading(key, text):
    return f'<h2 style="color:#1a1a2e;border-bottom:2px solid {BOX[key]["c"]};padding-bottom:6px">{text}</h2>'


def rule(color='#eee'):
    return f'<hr style="border:none;border-top:2px solid {color};margin:28px 0">'


def accent_rule(color):
    return f'<hr style="border:none;border-top:3px solid {color};margin:32px 0 24px">'


def stance(s):
    return f'<span style="font-size:13px;font-weight:normal;color:{COLORS[s]}">{s}</span>'


def hook(title, size, color):
    """'Name — the hook' -> name plus the hook in quotes, as in the August retail block."""
    name, sep, text = title.partition(' — ')
    if not sep:
        return esc(title)
    return f'{esc(name)} &nbsp;<span style="font-size:{size}px;font-weight:normal;color:{color}">"{esc(text)}"</span>'


def render(d):
    spec = json.load(open(os.path.join(C, 'specs', f'{d}.json')))
    D = dt.date.fromisoformat(d); label = D.strftime('%A, %B %d %Y')
    doc = Doc(); L = []
    a = L.append

    def box(key, title, parts, tag='h4', hstyle='margin:0 0 6px'):
        a(f'<div style="{block(key)}">')
        a(f'<{tag} style="{hstyle}">{title}</{tag}>')
        L.extend(doc.parts(parts))
        a('</div>')

    a('<!DOCTYPE html>')
    a('<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">')
    a(f'<title>Market Intelligence Briefing — {label}</title></head>')
    a(f'<body style="{BODY}">')
    a('<h1 style="color:#1a1a2e;margin-bottom:4px">Market Intelligence Briefing</h1>')
    a(f'<p style="color:#888;margin-top:0">{label} &mdash; Macro · Sectors · Flows · Crypto</p>')
    a('<hr style="border:none;border-top:3px solid #1a73e8;margin:16px 0 24px">')

    a(heading('geo', '🌍 Geographic Macro Overview'))
    for g in spec['geo']:
        a(f'<div style="{block("geo")}">')
        a(f'<h3 style="margin:0 0 10px">{GEO[g["key"]]} &nbsp;{stance(g["stance"])} &nbsp;'
          f'<span style="{PILL}">{esc(g["label"])}</span></h3>')
        L.extend(doc.parts(g['parts'])); a('</div>')

    a(rule())
    a(heading('sectors', '📊 Sector Deep Dive'))
    for s in spec['sectors']:
        a(f'<div style="{block("sectors")}">')
        a(f'<h3 style="margin:0 0 8px">{SECTORS[s["key"]]} &nbsp;{stance(s["stance"])}</h3>')
        L.extend(doc.parts(s['parts'])); a('</div>')

    a(rule())
    a(heading('earnings', '🧮 Earnings Pattern — What the Market Pays For'))
    ep = spec['earnings_pattern']
    box('earnings', esc(ep['title']), ep['parts'])

    a(rule())
    a(heading('underowned', '🔍 Underowned Themes — Active on X, Underweight in Portfolios'))
    for u in spec['underowned']:
        box('underowned', esc(u['title']), u['parts'])

    a(accent_rule(BOX['crypto']['c']))
    a(heading('crypto', '₿ Crypto & Digital Assets'))
    b = spec['crypto']
    box('crypto', esc(b['title']), b['parts'], tag='h3', hstyle='margin:0 0 10px')

    a(rule())
    a(heading('flows', '💰 Capital Flows & Liquidity Framework'))
    b = spec['flows']
    box('flows', esc(b['title']), b['parts'], tag='h3', hstyle='margin:0 0 10px')

    a(rule())
    a(heading('anticipatory', '🔮 Anticipatory Positioning — Markets Pricing In Future Events'))
    for x in spec['anticipatory']:
        box('anticipatory', esc(x['title']), x['parts'])

    a(rule())
    a(heading('catalysts', '⚡ High-Conviction Stock Catalysts'))
    for x in spec['catalysts']:
        m = re.match(r'\$(\w+)\s+—\s+(.*)$', x['title'])
        arrow = f'<span style="font-size:13px;color:{COLORS[x["stance"]]}">{ARROWS[x["stance"]]}</span>'
        if m:
            title = f'<code style="{TICKER}">${esc(m.group(1))}</code> &nbsp;{esc(m.group(2))} &nbsp;{arrow}'
        else:
            title = f'{esc(x["title"])} &nbsp;{arrow}'
        box('catalysts', title, x['parts'], tag='h3', hstyle='margin:0 0 6px')

    a(accent_rule(BOX['retail']['c']))
    a(heading('retail', '🔥 What Retail Is Playing'))
    for i, x in enumerate(spec['retail']):
        if i == 0:
            box('retail', hook(x['title'], 14, BOX['retail']['c']), x['parts'], tag='h3', hstyle='margin:0 0 12px;font-size:20px')
        else:
            box('retail_small', hook(x['title'], 12, '#888'), x['parts'])
    a('<hr style="border:none;border-top:1px solid #ddd;margin:24px 0 12px">')
    a(f'<p style="color:#aaa;font-size:11px">{FOOTER}</p>')
    a('</body></html>')
    page = '\n'.join(L) + '\n'
    os.makedirs(os.path.join(C, 'html'), exist_ok=True)
    open(os.path.join(C, 'html', f'{d}.html'), 'w', encoding='utf-8').write(page)
    payload = {'date': label, 'report_date': d, 'generated_at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
               'news_cutoff_utc': f'{d}T00:00:00Z', 'sections': sections(page)}
    os.makedirs(os.path.join(C, 'json'), exist_ok=True)
    json.dump(payload, open(os.path.join(C, 'json', f'{d}_Market_Intelligence.json'), 'w'), ensure_ascii=False, indent=2)
    return page


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
        print(d, len(render(d)), 'bytes')
