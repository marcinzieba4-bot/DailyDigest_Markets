"""check_merged.py <date> — in-memory merge of nonretail_drafts/DATE.json and retail_drafts/DATE.json and full
verify (merged citation reuse ≤4, ≥50 distinct, 9,500–11,000 words). Writes nothing."""
import json, sys
from pathlib import Path
import verify
ROOT = Path(__file__).resolve().parent.parent
for d in sys.argv[1:]:
    nr = json.loads((ROOT/'nonretail_drafts'/f'{d}.json').read_text()); rt = json.loads((ROOT/'retail_drafts'/f'{d}.json').read_text())
    f, w, n, words = verify.verify(d, spec_override={**nr, 'retail_intro': rt['retail_intro'], 'retail': rt['retail']})
    for x in f: print('FAIL', d, x)
    for x in w: print('WARN', d, x)
    print(f'{d}: MERGED {"PASS" if not f else "FAIL"} — {n} sources, {words} words')
