"""render.py <dates> — turn ../specs/<date>.json into the archive page ../html/<date>.html and the machine-readable copy
../json/<date>_Market_Intelligence.json, in the inline-styled layout of the August 2026 archive briefings (no stylesheet,
one accent colour per section, the same block and rule styling).

Citation markers ([[nXXXX]]) in the spec become source links and a dated evidence ledger.
Spec format: see BRIEF.md."""
import json, os, re, sys, html, datetime as dt, gzip

T = os.path.dirname(os.path.abspath(__file__)); C = os.path.dirname(T)
CITE = re.compile(r'\s*\[\[n\d{4,6}\]\]')
COLORS = {'Bullish': '#2d7a2d', 'Bearish': '#c0392b', 'Mixed': '#b07d00'}
ARROWS = {'Bullish': '↑', 'Bearish': '↓', 'Mixed': '→'}
BODY = 'font-family:Arial,sans-serif;max-width:1280px;margin:auto;padding:36px;color:#243047;line-height:1.7;background:#f5f7fc'
CSS = '''
*{box-sizing:border-box}html{scroll-behavior:smooth}body{font-size:16px}
body>h1{font-size:42px;letter-spacing:-1.5px;line-height:1.15}h2{scroll-margin-top:70px;margin-top:40px;font-size:26px}
h3{font-size:21px;line-height:1.4}h4{font-size:18px}p{margin:12px 0}a{color:#185eb8;text-decoration:none}a:hover{text-decoration:underline}
.topline{display:flex;gap:12px;flex-wrap:wrap;align-items:center;color:#65718a;font-size:12px;letter-spacing:.07em;text-transform:uppercase}
.edition{background:#e3eaf9;padding:5px 10px;border-radius:5px;color:#35568f;font-weight:bold}
.toc{position:sticky;top:0;z-index:5;display:flex;gap:18px;flex-wrap:wrap;padding:13px 18px;background:#ffffffef;border:1px solid #dde4f2;border-radius:10px;backdrop-filter:blur(14px);font-size:13px;box-shadow:0 5px 18px #1b28520c}
.source-cite{font-size:11px;white-space:nowrap;color:#59718e;padding-left:3px}
.data-note{font-size:12px;color:#68758d;padding:12px 16px;border:1px solid #d9e2f1;border-radius:8px;background:white}
.ledger{background:white;border:1px solid #dce4ef;border-radius:10px;padding:18px 24px;margin:30px 0;font-size:13px;overflow-wrap:anywhere}
.ledger li{padding:6px 0}.ledger summary{font-size:16px;font-weight:bold;cursor:pointer}

@media(min-width:1000px){body{padding:44px 48px}body>div:not(.topline){box-shadow:0 3px 12px #19345c07}p{max-width:114ch}}
@media(max-width:700px){body{padding:20px!important;font-size:15px}body>h1{font-size:31px}h2{font-size:22px}.toc{position:static;gap:10px}h3{font-size:19px}}
@media print{body{max-width:none;padding:0!important;background:white!important;font-size:10pt;line-height:1.45}.toc{display:none}h1{font-size:27pt!important}h2{font-size:17pt;break-after:avoid}h3,h4{break-after:avoid}p{orphans:3;widows:3}.ledger{font-size:8pt}.source-cite{font-size:7pt}a{color:#245380}body>div{box-shadow:none!important}}
'''
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
    """Render cited prose and retain each source for the dated evidence ledger."""

    def __init__(self, evidence):
        self.evidence = evidence
        self.used = {}

    def text(self, s):
        chunks=[]; start=0
        for match in re.finditer(r'\[\[(n\d{4,6})\]\]',s):
            chunks.append(esc(s[start:match.start()]))
            key=match.group(1); e=self.evidence[key]
            self.used.setdefault(key,len(self.used)+1)
            chunks.append('<a class="source-cite" href="'+attr(e['url'])+'" title="'+attr(e['title'])+'">['+str(self.used[key])+']</a>')
            start=match.end()
        chunks.append(esc(s[start:]))
        return ''.join(chunks).strip()

    def parts(self, parts):
        return [f'<p><strong>{esc(lbl)}:</strong> {self.text(txt)}</p>' for lbl, txt in parts]


def block(key):
    s = BOX[key]
    return (f'margin-bottom:{s["mb"]}px;padding:{s["p"]}px;background:{s["bg"]};'
            f'border-left:{s["bl"]}px solid {s["c"]};border-radius:4px')


def heading(key, text):
    return f'<h2 id="{key}" style="color:#1a1a2e;border-bottom:2px solid {BOX[key]["c"]};padding-bottom:6px">{text}</h2>'


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
    if D.year != 2025 or D.month != 5 or D.weekday() >= 5 or spec.get('date') != d:
        raise ValueError('Expected a May 2025 weekday and a matching own-date spec')
    feed_path=os.path.join(C,'feeds',f'{d}.json')
    feed=json.load(open(feed_path)) if os.path.exists(feed_path) else json.load(gzip.open(feed_path+'.gz','rt'))
    exception_path=os.path.join(C,'audit','canonical_source_exceptions.json')
    exceptions=json.load(open(exception_path)).get('exceptions',[]) if os.path.exists(exception_path) else []
    availability={x['id']:x for x in exceptions if x['date']==d}
    evidence={x['id']:dict(x) for x in feed['items']}
    for key,review in availability.items():
        if key in evidence:evidence[key]['availability_review']=review
    doc = Doc(evidence); L = []
    a = L.append

    def box(key, title, parts, tag='h4', hstyle='margin:0 0 6px'):
        a(f'<div style="{block(key)}">')
        a(f'<{tag} style="{hstyle}">{title}</{tag}>')
        L.extend(doc.parts(parts))
        a('</div>')

    a('<!DOCTYPE html>')
    a('<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">')
    a(f'<title>Market Intelligence Briefing — {label}</title><style>{CSS}</style></head>')
    a(f'<body style="{BODY}">')
    a('<div class="topline"><span class="edition">DailyDigest Markets</span><span>May 2025 · Historical edition</span></div>')
    a('<h1 style="color:#1a1a2e;margin-bottom:4px">Market Intelligence Briefing</h1>')
    a(f'<p style="color:#888;margin-top:0">{label} &mdash; Macro · Sectors · Flows · Crypto</p>')
    a('<hr style="border:none;border-top:3px solid #1a73e8;margin:16px 0 24px">')
    a('<p class="data-note">Information available before '+d+' 00:00 UTC. Prices use completed prior sessions. Prepared retrospectively; later outcomes are excluded.</p>')
    a('<nav class="toc">'+''.join('<a href="#'+k+'">'+v+'</a>' for k,v in [('geo','Macro'),('sectors','Sectors'),('earnings','Earnings'),('underowned','Themes'),('crypto','Crypto'),('flows','Liquidity'),('anticipatory','Scenarios'),('catalysts','Stocks'),('retail','Retail')])+'</nav>')

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
    a(heading('underowned', '🔍 Underowned Themes — Attention and Exposure Gaps'))
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
    a(f'<p style="color:#666;font-size:13px;margin-bottom:20px">{doc.text(spec["retail_intro"])}</p>')
    for i, x in enumerate(spec['retail']):
        if i == 0:
            box('retail', hook(x['title'], 14, BOX['retail']['c']), x['parts'], tag='h3', hstyle='margin:0 0 12px;font-size:20px')
        else:
            box('retail_small', hook(x['title'], 12, '#888'), x['parts'])
    a('<hr style="border:none;border-top:1px solid #ddd;margin:24px 0 12px">')
    a(f'<p style="color:#aaa;font-size:11px">{FOOTER}</p>')
    a('<details class="ledger"><summary>Dated evidence · '+str(len(doc.used))+' sources</summary><p>Publication timestamps are from the historical news index. Claims are limited to the cited headlines; original article vintages are not independently archived.</p><ol>')
    for key,num in doc.used.items():
        e=doc.evidence[key]
        note=''
        if e.get('availability_review'):
            review=e['availability_review']
            note=('<br><span style="font-size:12px;color:#5c6e86">Timing: '+esc(review['reason'])+
                  ' Verified available before '+esc(review['known_before_utc'])+'. <a href="'+
                  attr(review['evidence_url'])+'">Timing evidence</a>.</span>')
        a('<li><a href="'+attr(e['url'])+'">'+esc(e['title'])+'</a> — '+esc(e['src'])+' · '+esc(e['published_at'])+note+'</li>')
    a('</ol></details>')
    a('</body></html>')
    page = '\n'.join(L) + '\n'
    os.makedirs(os.path.join(C, 'html'), exist_ok=True)
    open(os.path.join(C, 'html', f'{d}.html'), 'w', encoding='utf-8').write(page)
    payload = {'date': label, 'report_date': d, 'generated_at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
               'news_cutoff_utc': f'{d}T00:00:00Z', 'sections': sections(page.split('<details class="ledger">')[0]),
               'evidence':{k:doc.evidence[k] for k in doc.used}, 'spec':spec}
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
