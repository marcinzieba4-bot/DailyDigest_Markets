"""Make a self-contained review bundle; does not publish or access AWS."""
from pathlib import Path
import hashlib
import html
import json
import zipfile

ROOT=Path(__file__).resolve().parent


def main():
    manifest=json.loads((ROOT/'audit/revision_artifacts.json').read_text())
    final=json.loads((ROOT/'audit/final_validation.json').read_text())
    if not manifest.get('reviewed') or not final['prepublication_passed']:
        raise ValueError('Final review is required before packaging')
    cards=[]
    for date in manifest['dates']:
        cards.append(f'<a href="html/{date}.html"><strong>{date}</strong><span>Read the briefing</span></a>')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Reviewed retrospective retail editions</title><style>*{box-sizing:border-box}body{font-family:Arial,sans-serif;max-width:1400px;margin:auto;padding:50px 35px;background:#f5f7fc;color:#243047;line-height:1.6}h1{font-size:clamp(34px,5vw,64px);line-height:1.1;letter-spacing:-1.5px}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:15px;margin:30px 0}.grid a{display:flex;flex-direction:column;padding:22px;background:white;border:1px solid #dce4f1;border-top:4px solid #1a73e8;border-radius:8px;text-decoration:none;color:inherit}.grid span{font-size:12px;color:#185eb8;margin-top:12px}.note{max-width:1000px;color:#60708a}@media(max-width:900px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:500px){body{padding:25px 18px}.grid{grid-template-columns:1fr}}</style><h1>Retrospective retail editions.</h1><p class="note">Reviewed historical briefings with dated catalysts, explicit continuation decisions and shorter unchanged carryovers. Live editions, including August 2026, are preserved. This local review package contains the revised exports; publication status is recorded separately in the audit.</p><p><a href="methodology.txt">Method and limits</a> · <a href="audit/final_validation.json">Validation record</a></p><div class="grid">'''+''.join(cards)+'</div></html>'
    (ROOT/'review.html').write_text(page)
    method='''Retrospective retail revision review package

The package contains checked HTML/PDF/JSON exports for the reconstructed
editions being republished, including unchanged editions needed to keep the
September/October/November month downloads internally consistent.

Selection uses each report's eligible own-date headlines and earlier editorial
history. A continuing theme can remain when new evidence changes its story;
frequency alone is not a defect and no ticker-variety quota is used.
Unchanged carryovers are shortened. New claims are attributed to dated evidence;
no complete retail popularity ranking is asserted. Original article vintages
and full intraday publisher-body histories are not independently archived.

Canonical historical months use strict report-date00:00UTC news cutoffs.
Legacy original cutoffs/metadata are preserved; all newly introduced legacy
headlines independently satisfy midnight/7-day eligibility. Prior market
observations and source uncertainty retain the original method's limits.

All145 live editions, including August2026, are protected from revision.
Three explicitly reviewed pre-existing December source-timing errors were
corrected alongside the retail edits; exact scopes are in the source audit.

See audit/final_validation.json for actual publication status. Local package
readiness does not mean the public archive has been updated.
'''
    path=ROOT/'Retrospective_Retail_Revisions.zip'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr('index.html',page);bundle.writestr('methodology.txt',method)
        for date in manifest['dates']:
            for fmt in ['html','json','pdf']:
                p=ROOT/fmt/(date+'.'+fmt);bundle.write(p,fmt+'/'+p.name)
        for name in ['final_validation.json','retail_canonical_dates.json','legacy_independent_review.json',
                     'retrospective_scope.json','publication.json','live_verification.json',
                     'delivery_verification.json','external_revised_public_verification.json',
                     'external_live_html_verification.json','external_specials_verification.json']:
            path_in_audit = ROOT/'audit'/name
            if path_in_audit.exists():
                bundle.write(path_in_audit,'audit/'+name)
    receipt={'path':str(path),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
             'reports':len(manifest['dates']),'entries':len(zipfile.ZipFile(path).namelist()),'remote_calls':False}
    (ROOT/'audit/review_package.json').write_text(json.dumps(receipt,indent=2))
    print('Local review bundle:',receipt['reports'],'reports;',receipt['bytes'],'bytes;',receipt['entries'],'entries')


if __name__=='__main__':main()
