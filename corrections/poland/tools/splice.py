#!/usr/bin/env python3
"""splice.py [dates...] — for each date whose new block passes verify_pl, replace the Poland block in edited/<date>.html."""
import sys, re, os, glob, subprocess
W = '/tmp/claude-0/-home-user/01233cf7-f758-5bad-b280-d38226412ca9/scratchpad/work'
dates = sys.argv[1:] or sorted(os.path.basename(f)[:-5] for f in glob.glob(f'{W}/pl/new/*.html'))
ok = fail = 0
for d in dates:
    r = subprocess.run([sys.executable, '-I', f'{W}/pl/verify_pl.py', d], capture_output=True, text=True)
    if r.returncode != 0 or 'WARN' in r.stdout:
        print('skip', d, '\n', r.stdout.strip()); fail += 1; continue
    new = open(f'{W}/pl/new/{d}.html', encoding='utf-8').read().strip()
    path = f'{W}/edited/{d}.html'
    s = open(path, encoding='utf-8').read()
    m = re.search(r'<div style="margin-bottom:24px;[^"]*">\s*<h3[^>]*>🇵🇱[^\n]*\n(?:.*?\n)*?</div>', s)
    if not m: print('no Poland block in', d); fail += 1; continue
    out = s[:m.start()] + new + s[m.end():]
    # structural guard: everything outside the block is unchanged
    assert out[:m.start()] == s[:m.start()] and out[m.start() + len(new):] == s[m.end():]
    open(path, 'w', encoding='utf-8').write(out); ok += 1
print(f'spliced {ok}, skipped {fail}')
