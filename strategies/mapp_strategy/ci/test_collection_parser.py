"""Check the generic collection adapter with invented HTML only.

No real source collection, historical title or private identity metadata appears.
"""
from __future__ import annotations
import hashlib, importlib.util, json, tempfile
from pathlib import Path
MODULE=Path(__file__).resolve().parents[1]/"source_tools/collection_html.py"
def must_reject(action,label):
    try:action()
    except AssertionError:return
    raise AssertionError("Invalid synthetic input accepted: "+label)
def main():
    spec=importlib.util.spec_from_file_location("synthetic_collection_adapter",MODULE)
    adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
    days=("2020-01-06","2020-01-07")
    sections=[]
    for day in days:
        cards=[]
        for slot in range(1,5):
            cards.append('<article class="trade"><h3>Synthetic theme '+str(slot)+'</h3>'
                '<div class="part"><h4>Context</h4><p>Invented paragraph.</p></div>'
                '<div class="part"><h4>Alternative view</h4><p>Another invented paragraph.</p></div></article>')
        sections.append('<section class="day" id="'+day+'"><header class="dayhead">'
            '<p class="kicker">Report cutoff 00:00 UTC</p><p class="intro">Synthetic fixture only.</p>'
            '</header>'+"".join(cards)+'<details><summary>Citation ledger</summary>'
            '<h4>Ledger heading is not a retail topic</h4></details></section>')
    body=('<!doctype html><html><body><h1>What Retail Is Playing</h1>'
          +"".join(sections)+'</body></html>').encode("utf-8")
    digest=hashlib.sha256(body).hexdigest()
    with tempfile.TemporaryDirectory(prefix="retail-collection-check-") as directory:
        root=Path(directory);rel="source/invented_collection.html"
        path=root/rel;path.parent.mkdir();path.write_bytes(body)
        records=adapter.manifest_records(root,rel,days[0],days[-1],digest)
        assert [r["report_date"] for r in records]==list(days)
        assert all(r["sha256"]==digest and r["path"]==rel for r in records)
        assert all(r["last_modified"]==r["version_id"]==r["public_url"]=="" for r in records)
        for meta in records:
            rows=adapter.items(meta,root,lambda _:{"mapping_status":"unmapped","targets":"[]"})
            assert len(rows)==4 and [r["slot"] for r in rows]==["1","2","3","4"]
            assert [r["heading"] for r in rows]==["Synthetic theme "+str(i) for i in range(1,5)]
            assert all(len(r["paragraphs"])==2 and r["observed_topic_count"]==4 for r in rows)
            assert all(r["source_element_id"]==meta["report_date"] and r["actual_available_at"]=="" for r in rows)
        assert adapter.items(records[0],root,lambda _:{} )[0]["available_at"]=="2020-01-07T04:59:59+00:00"
        must_reject(lambda:adapter.manifest_records(root,rel,days[0],days[-1],"0"*64),"digest mismatch")
        must_reject(lambda:adapter.manifest_records(root,rel,days[0],"2020-01-08",digest),"missing expected weekday")
        extra=b'<article class="trade"><h3>Unexpected fifth topic</h3><p>Invented extra topic.</p></article>'
        bad=body.replace(b"</section>",extra+b"</section>",1)
        bad_rel="source/extra_topic.html";(root/bad_rel).write_bytes(bad)
        must_reject(lambda:adapter.manifest_records(root,bad_rel,days[0],days[-1],hashlib.sha256(bad).hexdigest()),"fifth topic")
    print(json.dumps({"status":"passed","synthetic_only":True,
        "checks":["four positional topics despite nested H4 and citation ledger",
                  "truthful non-HTTP provenance","assumed EOD New York availability",
                  "mismatched digest rejected","missing expected weekday rejected","fifth topic rejected"]}),flush=True)
if __name__=="__main__":main()
