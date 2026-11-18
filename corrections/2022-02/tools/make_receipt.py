"""make_receipt.py KIND DATE FINDINGS_JSON — write audit/independent_KIND_DATE.json for an independent review.

KIND is nonretail or retail. FINDINGS_JSON is a file the reviewer writes:
  {"reviewer": "...", "findings": [{"location","issue","severity","resolution"}, ...],
   "reviewed_validation_warnings": [{"warning","evidence_ids","rationale"}, ...],
   "scope_limits": "...", "recommended_exclusions": [{"id","reason"}, ...],
   "chronology_checked_against": [...]   # retail only: strictly earlier dates read
  }
The tool re-runs the component verifier, refuses to write while any FAIL remains or any
verifier warning lacks an exact, evidence-bound disposition, and binds the exact bytes of the
own-date feed, card and exclusions plus the reviewed component (nonretail: canonical content hash;
retail: draft file hash). Any later edit to a bound artifact makes the receipt stale."""
import hashlib, json, re, sys
from pathlib import Path
import verify

ROOT = Path(__file__).resolve().parent.parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
content_sha = lambda v: hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def main(kind, date, findings_path):
    verify.validate_date(date)
    if kind not in ('nonretail', 'retail'): raise SystemExit('KIND must be nonretail or retail')
    rec = json.loads(Path(findings_path).read_text())
    folder = 'nonretail_drafts' if kind == 'nonretail' else 'retail_drafts'
    draft_path = ROOT / folder / f'{date}.json'
    draft = json.loads(draft_path.read_text())
    fails, warns, nsrc, words = verify.verify(date, nonretail=kind == 'nonretail', retail_only=kind == 'retail')
    if fails: raise SystemExit('Refusing receipt: verifier FAILs remain: ' + '; '.join(fails[:8]))
    cited = set(re.findall(r'\[\[(n\d{4,6})\]\]', json.dumps(draft, ensure_ascii=False)))
    disp = {x.get('warning'): x for x in rec.get('reviewed_validation_warnings', [])}
    for w in warns:
        x = disp.get(w)
        if not x: raise SystemExit('Refusing receipt: undispositioned warning: ' + w)
        ev = x.get('evidence_ids') or []
        if not ev or len(ev) != len(set(ev)) or not set(ev) <= cited or len(x.get('rationale', '').strip()) < 40:
            raise SystemExit('Refusing receipt: warning disposition needs cited evidence_ids and a specific rationale: ' + w)
    stale = sorted(set(disp) - set(warns))
    excl = json.loads((ROOT / 'exclusions' / f'{date}.json').read_text())
    excluded = {x['id'] for x in excl['exclusions']}
    bad = sorted(cited & excluded)
    if bad: raise SystemExit('Refusing receipt: component cites excluded IDs ' + ', '.join(bad))
    out = {'date': date, 'kind': kind, 'status': 'accepted', 'reviewer': rec.get('reviewer', 'independent_reviewer'),
           'fatal_or_major_remaining': 0,
           'feed_sha256': sha(ROOT / 'feeds' / f'{date}.json.gz'), 'card_sha256': sha(ROOT / 'cards' / f'{date}.json'),
           'exclusions_sha256': sha(ROOT / 'exclusions' / f'{date}.json'),
           'findings': rec.get('findings', []), 'reviewed_validation_warnings': [disp[w] for w in warns],
           'stale_warning_dispositions_dropped': stale, 'scope_limits': rec.get('scope_limits', ''),
           'recommended_exclusions': rec.get('recommended_exclusions', []),
           'verifier': {'words': words, 'distinct_sources': nsrc, 'warnings': len(warns)}}
    if kind == 'nonretail': out['nonretail_content_sha256'] = content_sha(draft)
    else:
        out['retail_draft_sha256'] = sha(draft_path)
        out['chronology_checked_against'] = rec.get('chronology_checked_against', [])
    target = ROOT / 'audit' / f'independent_{kind}_{date}.json'
    target.write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n')
    print('receipt written', target.relative_to(ROOT), words, 'words', nsrc, 'sources', len(warns), 'warnings dispositioned')


if __name__ == '__main__':
    if len(sys.argv) != 4: raise SystemExit(__doc__)
    main(*sys.argv[1:])
