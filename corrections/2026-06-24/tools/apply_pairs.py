"""apply_pairs.py <in.html> <edits.json> <out.html> — exact [old, new] replacements; each old must occur exactly once."""
import sys, json
s = open(sys.argv[1], encoding='utf-8').read()
for old, new in json.load(open(sys.argv[2], encoding='utf-8')):
    n = s.count(old)
    if n != 1: sys.exit(f'not unique ({n}x): {old[:90]}')
    s = s.replace(old, new)
open(sys.argv[3], 'w', encoding='utf-8').write(s); print('applied', sys.argv[2])
