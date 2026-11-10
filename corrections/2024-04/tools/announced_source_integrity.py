"""Verify exact announced source and acceptance bytes before any rewrite."""
import hashlib,json
from pathlib import Path
from fetch_news import ROOT,json_bytes

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def check_announced(stamp,old):
    for label,relative,expected in [
        ('ready',f'feeds/{stamp}.json.gz',old['feed_sha256']),
        ('raw',f'work/unreviewed_feeds/{stamp}.json.gz',old['raw_sha256']),
        ('provenance',f'audit/news_provenance/{stamp}.json.gz',old['provenance_sha256'])]:
        p=ROOT/relative
        assert p.is_file()and sha(p)==expected,('Announced source bytes changed',stamp,label)
    if old.get('independent_review'):
        cp=ROOT/old['candidate_manifest'];rp=ROOT/old['independent_review']
        assert cp.is_file()and sha(cp)==old['candidate_manifest_sha256'],('Accepted candidate changed',stamp)
        assert rp.is_file()and sha(rp)==old['independent_review_sha256'],('Independent acceptance changed',stamp)
        candidate=json.loads(cp.read_text());review=json.loads(rp.read_text())
        assert candidate['raw_sha256']==old['raw_sha256']and candidate['provenance_sha256']==old['provenance_sha256']and candidate['ready_sha256']==old['feed_sha256']
        assert candidate['ready_receipt']['ready_sha256']==old['feed_sha256']
        assert candidate['date']==stamp and review['date']==stamp and review['candidate_sha256']==sha(cp)
        assert review.get('passed')is True and type(review.get('fatal_or_major_remaining'))is int and review['fatal_or_major_remaining']==0
        expected_receipt=hashlib.sha256(json_bytes(candidate['ready_receipt'])).hexdigest()
        receipt=ROOT/'audit'/('news_ready_'+stamp+'.json')
        assert receipt.is_file()and sha(receipt)==expected_receipt,('Announced ready receipt changed',stamp)
        if old.get('ready_receipt_sha256'):assert old['ready_receipt_sha256']==expected_receipt
    elif old.get('ready_receipt_sha256'):
        assert sha(ROOT/'audit'/('news_ready_'+stamp+'.json'))==old['ready_receipt_sha256']
    if old.get('candidate_manifest')and old.get('candidate_manifest_sha256'):
        assert sha(ROOT/old['candidate_manifest'])==old['candidate_manifest_sha256'],('Final candidate manifest changed',stamp)
    preserved=old.get('progressive_acceptance_preservation')
    if preserved:
        assert sha(ROOT/preserved['path'])==preserved['sha256'],('Acceptance preservation manifest changed',stamp)
        manifest=json.loads((ROOT/preserved['path']).read_text())
        assert manifest['date']==stamp and manifest['files']==preserved['files']
        for row in preserved['files']:assert sha(ROOT/row['preserved_path'])==row['sha256'],('Preserved acceptance bytes changed',stamp,row['preserved_path'])
    return True

def preserve_progressive_acceptance(stamp,old):
    """Exact prior bytes and chain survive the full-month ledger transition."""
    check_announced(stamp,old)
    if not old.get('independent_review'):return old.get('progressive_acceptance_preservation')
    out=ROOT/'audit/source_amendments/progressive'/stamp
    names=[f'audit/news_frozen_{stamp}.json',f'audit/news_ready_{stamp}.json',old['candidate_manifest'],old['independent_review']]
    rows=[]
    for relative in names:
        source=ROOT/relative;target=out/relative
        data=source.read_bytes();target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert target.read_bytes()==data,('Preserved acceptance bytes changed',stamp,relative)
        else:target.write_bytes(data)
        rows.append(dict(original_path=relative,preserved_path=str(target.relative_to(ROOT)),sha256=sha(target)))
    receipt=dict(date=stamp,scope='Exact progressive acceptance chain retained before full-month replay finalization',files=rows)
    target=out/'preservation_manifest.json';data=json_bytes(receipt)
    if target.exists():assert target.read_bytes()==data
    else:target.write_bytes(data)
    return dict(path=str(target.relative_to(ROOT)),sha256=sha(target),files=rows)
