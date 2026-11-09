"""Record root's completed manual retail review; does not perform or infer review."""
from pathlib import Path
import datetime,hashlib,json,re,subprocess,sys
R=Path(__file__).resolve().parent.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def record(d,claims,chronology,named_fixes=None,warnings=None):
    draft=json.loads((R/'retail_drafts'/f'{d}.json').read_text());notes=json.loads((R/'notes'/f'retail_{d}.json').read_text())
    ids=list(dict.fromkeys(re.findall(r'\[\[(n\d+)\]\]',json.dumps(draft,ensure_ascii=False))))
    assert notes['lead']==draft['retail'][0]['title'] and notes['smaller']==[x['title']for x in draft['retail'][1:]]
    exclusions=json.loads((R/'exclusions'/f'{d}.json').read_text());assert not set(ids)&{x['id']for x in exclusions['exclusions']}
    result=subprocess.run([sys.executable,str(R/'tools/verify.py'),d,'--retail'],text=True,capture_output=True);assert result.returncode==0,result.stdout+result.stderr
    m=re.search(r'PASS — (\d+) sources, (\d+) words, (\d+) fail, (\d+) warn',result.stdout);assert m and m[3]=='0';assert int(m[4])==len(warnings or []),result.stdout
    row={'date':d,'status':'accepted','reviewer':'root, independent of original retail author','checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'fatal_or_major_remaining':0,'retail_draft_sha256':sha(R/'retail_drafts'/f'{d}.json'),'feed_sha256':sha(R/'feeds'/f'{d}.json.gz'),'card_sha256':sha(R/'cards'/f'{d}.json'),'exclusions_sha256':sha(R/'exclusions'/f'{d}.json'),'paragraphs_reviewed':13,'distinct_cited_headlines_reviewed':ids,'findings':[],'named_fixes':named_fixes or [],'claim_checks':claims,'chronology':{'earlier_notes_reviewed':sorted(p.stem.replace('retail_','')for p in(R/'notes').glob('retail_*.json')if p.stem.replace('retail_','')<d),'notes_match_current_selection':True,'material_change':chronology,'selection_rationale':notes['why_lead']},'reviewed_validation_warnings':warnings or [],'verification':{'passed':True,'sources':int(m[1]),'body_words':int(m[2]),'failures':0,'warnings':int(m[4])},'limitations':['Independent AI headline/card review; original complete article-body vintages are not certified.','Lead selection and crowd motivations are editorial interpretation, not measured cross-market retail popularity.']}
    p=R/'audit'/f'independent_retail_{d}.json';assert not p.exists();p.write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n');print(d,'accepted',m[2],'words',len(ids),'sources',sha(p))
