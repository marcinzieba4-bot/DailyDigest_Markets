"""reconstruct.py <json> <out.html> — rebuild the 2026-06-24 report HTML from its archived JSON, in the exact template the
Lambda used at the time (the 06-25 original in reports/_pre_correction_backup is the reference). Text is taken verbatim
from the JSON; only the markup (containers, label <strong>s, stance colours, pills) is re-created. The result must
round-trip: the Lambda's _parse_html_paragraphs() on it gives back exactly the JSON's subheadings and body lists."""
import json, re, sys, html

J = json.load(open(sys.argv[1]))['sections'][0]
H, B = list(J['subheadings']), list(J['body'])
NB = '\xa0'
COL = {'Bullish': '#2d7a2d', 'Mixed': '#b07d00', 'Bearish': '#c0392b'}

def esc(t):
    return t.replace('<', '&lt;').replace('>', '&gt;').replace(NB, '&nbsp;').replace('\n', '<br>')   # raw '&' as the Lambda wrote it

LABEL = re.compile(r'^((?:⚡ )?)((?:⚠️ )?[^:.!?\[\]()$]{2,70}?:)(?=\s)')
def para(t, extra_labels=()):
    """<p> with the leading label bolded and in-line labels after ' | ' separators bolded (Playbook / Divergence)."""
    parts = t.split(NB + '|' + NB)
    out = []
    for i, p in enumerate(parts):
        lead = re.match(r'^(\s*)', p).group(1); body = p[len(lead):]
        m = LABEL.match(body)
        if m:
            seg = esc(lead) + esc(m.group(1)) + '<strong>' + esc(m.group(2)) + '</strong>' + esc(body[m.end():])
        else:
            seg = esc(p)
        out.append(seg)
    return '<p>' + '&nbsp;|&nbsp;'.join(out) + '</p>'

def numbered(t):            # "1. GLOBAL LIQUIDITY — Tightening, Not Just Pausing. The Warsh Fed …"
    m = re.match(r'^(\d\. [A-Z][A-Z \-/&]+ — [^.:]+[.:]|\d\. [A-Z][A-Z \-/&]+[.:])(\s)', t)
    return ('<p><strong>' + esc(m.group(1)) + '</strong>' + esc(t[m.end(1):]) + '</p>') if m else '<p>' + esc(t) + '</p>'

def model(t, first):
    m = re.match(r'^(MODEL \d — [^:]+:)', t)
    bg = '#e8f5e9' if re.search(r'→\s*(SELECTIVE )?RISK-ON', t) else '#fce4ec'
    st = f'margin-top:{14 if first else 10}px;padding:12px;background:{bg};border-radius:6px'
    inner = ('<strong>' + esc(m.group(1)) + '</strong>' + esc(t[m.end():])) if m else esc(t)
    return f'<p style="{st}">{inner}</p>'

def take(pred):
    out = []
    while B and pred(B[0], len(out)): out.append(B.pop(0))
    return out

def upto(end):              # paragraphs of one block: up to and including the one starting with `end`
    out = []
    while B:
        out.append(B.pop(0))
        if out[-1].startswith(end): return out
    raise SystemExit('block end not found: ' + end)

o = []
o.append('<html>\n<body style="font-family:Arial,sans-serif;max-width:820px;margin:auto;padding:24px;color:#222;line-height:1.6">')
o.append('  <h1 style="color:#1a1a2e;margin-bottom:4px">Market Intelligence Briefing</h1>')
date_line = B.pop(0); assert date_line.endswith('— Macro · Sectors · Flows · Crypto'), date_line
o.append('  <p style="color:#888;margin-top:0">' + esc(date_line[:date_line.index(' — ')]) + ' &mdash; Macro · Sectors · Flows · Crypto</p>')
o.append('  <hr style="border:none;border-top:3px solid #1a73e8;margin:16px 0 24px">\n  \n')

# ── Part 1: Geographic Macro Overview ──
h = H.pop(0); assert h == '🌍 Geographic Macro Overview'
o.append(f'<h2 style="color:#1a1a2e;border-bottom:2px solid #1a73e8;padding-bottom:6px">{esc(h)}</h2>\n')
while H[0] != '📊 Sector Deep Dive':
    name, stance, pill = H.pop(0).split(' ' + NB)
    ps = take(lambda b, n: n == 0 or not (b.startswith('Macro Stance:') or b.startswith('Narrative:')))
    sc = COL.get(stance, '#2d7a2d' if 'Bullish' in stance else '#c0392b' if 'Bearish' in stance else '#b07d00')
    o.append('<div style="margin-bottom:24px;padding:16px;background:#f8f9ff;border-left:5px solid #1a73e8;border-radius:4px">')
    o.append(f'  <h3 style="margin:0 0 10px">{esc(name)} &nbsp;<span style="font-size:13px;font-weight:normal;color:{sc}">{esc(stance)}</span> &nbsp;<span style="font-size:12px;background:#e8f0fe;padding:2px 8px;border-radius:10px;color:#1a73e8">{esc(pill)}</span></h3>')
    for p in ps: o.append('  ' + para(p))
    o.append('</div>\n')
o.append('<hr style="border:none;border-top:2px solid #eee;margin:28px 0">\n')

# ── Sector Deep Dive ──
h = H.pop(0)
o.append(f'<h2 style="color:#1a1a2e;border-bottom:2px solid #34a853;padding-bottom:6px">{esc(h)}</h2>\n')
while not H[0].startswith('🔍 Underowned Themes'):
    name, stance = H.pop(0).split(' ' + NB)
    ps = upto('⚡ Breaking Convention:')
    o.append('<div style="margin-bottom:18px;padding:14px;background:#f9fff9;border-left:4px solid #34a853;border-radius:4px">')
    o.append(f'  <h3 style="margin:0 0 8px">{esc(name)} &nbsp;<span style="font-size:13px;font-weight:normal;color:{COL[stance]}">{esc(stance)}</span></h3>')
    for p in ps:
        if p.startswith('⚡ Breaking Convention:'):
            o.append('  <p>⚡ <strong>Breaking Convention:</strong>' + esc(p[len('⚡ Breaking Convention:'):]) + '</p>')
        else: o.append('  ' + para(p))
    o.append('</div>\n')
o.append('<hr style="border:none;border-top:2px solid #eee;margin:28px 0">\n')

# ── Underowned Themes ──
h = H.pop(0)
o.append(f'<h2 style="color:#1a1a2e;border-bottom:2px solid #f4b400;padding-bottom:6px">{esc(h)}</h2>\n')
while not H[0].startswith('₿'):
    t = H.pop(0); ps = upto('Instrument:')
    o.append('<div style="margin-bottom:16px;padding:14px;background:#fffdf0;border-left:4px solid #f4b400;border-radius:4px">')
    o.append(f'  <h4 style="margin:0 0 6px">{esc(t)}</h4>')
    for p in ps: o.append('  ' + para(p))
    o.append('</div>\n')
o[-1] = o[-1].rstrip('\n')
o.append('  <hr style="border:none;border-top:3px solid #9c27b0;margin:32px 0 24px">\n  \n')

# ── Part 2: Crypto ──
h = H.pop(0); h3 = H.pop(0)
o.append(f'<h2 style="color:#1a1a2e;border-bottom:2px solid #9c27b0;padding-bottom:6px">{esc(h)}</h2>\n')
o.append('<div style="margin-bottom:20px;padding:16px;background:#f5f0ff;border-left:5px solid #9c27b0;border-radius:4px">')
o.append(f'  <h3 style="margin:0 0 10px">{esc(h3)}</h3>\n')
for p in take(lambda b, n: not b.startswith('1. ')): o.append(para(p) + '\n')
o[-1] = o[-1].rstrip('\n'); o.append('</div>\n')
o.append('<hr style="border:none;border-top:2px solid #eee;margin:28px 0">\n')

# ── Capital Flows ──
h = H.pop(0); h3 = H.pop(0)
o.append(f'<h2 style="color:#1a1a2e;border-bottom:2px solid #e91e8c;padding-bottom:6px">{esc(h)}</h2>\n')
o.append('<div style="margin-bottom:20px;padding:16px;background:#fff0f8;border-left:5px solid #e91e8c;border-radius:4px">')
o.append(f'  <h3 style="margin:0 0 10px">{esc(h3)}</h3>\n')
for p in take(lambda b, n: re.match(r'\d\. ', b) is not None): o.append(numbered(p) + '\n')
for i, p in enumerate(take(lambda b, n: b.startswith('MODEL '))): o.append(model(p, i == 0) + '\n')
o.append('</div>\n')
o.append('<hr style="border:none;border-top:2px solid #eee;margin:28px 0">\n')

# ── Anticipatory Positioning ──
h = H.pop(0)
o.append(f'<h2 style="color:#1a1a2e;border-bottom:2px solid #00b894;padding-bottom:6px">{esc(h)}</h2>\n')
while H[0].startswith('🔮'):
    t = H.pop(0); ps = upto('Risk if wrong:')
    o.append('<div style="margin-bottom:16px;padding:14px;background:#f0fff4;border-left:4px solid #00b894;border-radius:4px">')
    o.append(f'  <h4 style="margin:0 0 6px">{esc(t)}</h4>')
    for p in ps: o.append('  ' + para(p))
    o.append('</div>\n')
o.append('<hr style="border:none;border-top:2px solid #eee;margin:28px 0">\n')

# ── High-Conviction Stock Catalysts ──
h = H.pop(0)
o.append(f'<h2 style="color:#1a1a2e;border-bottom:2px solid #e67e22;padding-bottom:6px">{esc(h)}</h2>\n')
while not H[0].startswith('🔥'):
    tick, name, arrow = H.pop(0).split(' ' + NB)
    ps = upto('Risk:')
    ac = '#2d7a2d' if arrow == '↑' else '#c0392b'
    o.append('<div style="margin-bottom:22px;padding:16px;background:#fff8f0;border-left:4px solid #e67e22;border-radius:4px">')
    o.append(f'  <h3 style="margin:0 0 6px"><code style="background:#ffe0b2;padding:2px 6px;border-radius:3px">{esc(tick)}</code> &nbsp;{esc(name)} &nbsp;<span style="font-size:13px;color:{ac}">{esc(arrow)}</span></h3>')
    for p in ps: o.append('  ' + para(p))
    o.append('</div>\n')
sig = B.pop(0); assert sig.startswith('Signals:')
o.append(f'<p style="color:#aaa;font-size:11px;margin-top:24px">{esc(sig)}</p>')
o.append('  <hr style="border:none;border-top:3px solid #ff6b35;margin:32px 0 24px">\n  \n')

# ── Part 3: What Retail Is Playing ──
h = H.pop(0)
o.append(f'<h2 style="color:#1a1a2e;border-bottom:2px solid #ff6b35;padding-bottom:6px">{esc(h)}</h2>')
o.append(f'<p style="color:#666;font-size:13px;margin-bottom:20px">{esc(B.pop(0))}</p>\n')
title, quote = H.pop(0).split(' ' + NB)
ps = take(lambda b, n: n < 6)
o.append('<div style="margin-bottom:28px;padding:20px;background:#fff8f5;border-left:6px solid #ff6b35;border-radius:4px">')
o.append(f'  <h3 style="margin:0 0 12px;font-size:20px">{esc(title)} &nbsp;<span style="font-size:14px;font-weight:normal;color:#ff6b35">{esc(quote)}</span></h3>')
for p in ps: o.append('  ' + para(p))
o.append('</div>\n')
while H:
    title, quote = H.pop(0).split(' ' + NB)
    o.append('<div style="margin-bottom:14px;padding:14px;background:#fff8f5;border-left:3px solid #ff9a70;border-radius:4px">')
    o.append(f'  <h4 style="margin:0 0 6px">{esc(title)} &nbsp;<span style="font-size:12px;font-weight:normal;color:#888">{esc(quote)}</span></h4>')
    o.append('  <p>' + esc(B.pop(0)) + '</p>')
    o.append('</div>\n')
o[-1] = o[-1].rstrip('\n')
foot = B.pop(0); assert foot.startswith('Powered by'), foot
o.append('  <hr style="border:none;border-top:1px solid #ddd;margin:24px 0 12px">')
o.append('  <p style="color:#aaa;font-size:11px">Powered by AWS Lambda + Claude Opus &mdash; for informational purposes only, not financial advice.</p>')
o.append('</body>\n</html>')
assert not B and not H, (B[:2], H[:2])
open(sys.argv[2], 'w', encoding='utf-8').write('\n'.join(o) + '\n')
print('written', sys.argv[2])
