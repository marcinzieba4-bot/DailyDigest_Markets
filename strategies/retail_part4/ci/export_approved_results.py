"""Export only authorized simulated outputs; never include source archives or raw market inputs."""
import argparse,base64,hashlib,json,shutil,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,default=ROOT);p.add_argument("--log-transport",action="store_true");a=p.parse_args();root=a.root.resolve()
    summary=json.loads((root/"results/summary.json").read_text())
    audit=json.loads((root/"diagnosis/independent_results.json").read_text())
    assert len(summary)==9 and audit["status"]=="passed"
    plot=json.loads((root/"figures/plot_manifest.json").read_text());assert plot["status"]=="passed"
    paths=[root/"research_freeze.json",root/"provenance_run.json",root/"protocol.json",root/"requirements.txt",root/"results/summary.json",root/"results/metrics.csv",root/"results/run_manifest.json",
        root/"all_trades.csv",root/"all_orders.csv",root/"all_daily_nav.csv",
        root/"diagnosis/independent_results.json",root/"diagnosis/metrics.csv",root/"diagnosis/calendar_year_returns.csv",
        root/"audit/prefreeze_review.json",root/"audit/preparation_summary.json",root/"figures/plot_manifest.json",root/"figures/layout_checks.json"]
    for m in summary:
        for kind in ["daily","orders","borrow","baskets","source_trades","exante"]:paths.append(root/"results"/m[kind+"_path"])
    paths += list((root/"figures").glob("*.png"))+list((root/"figures").glob("*.svg"))
    paths=sorted(set(paths))
    out=root/"approved_outputs"
    if out.exists():shutil.rmtree(out)
    out.mkdir()
    manifest=[]
    for source in paths:
        assert source.is_file(),source
        relative=source.relative_to(root)
        assert relative.parts[0] in ["results","diagnosis","audit","figures"] or source.name in ["all_trades.csv","all_orders.csv","all_daily_nav.csv","research_freeze.json","provenance_run.json","protocol.json","requirements.txt"]
        assert not any(x in relative.parts for x in ["source","market","inputs","raw","canonical_html","benchmarks"])
        target=out/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        manifest.append({"path":relative.as_posix(),"bytes":source.stat().st_size,"sha256":sha(source)})
    receipt={"status":"passed","kind":"authorized_simulated_outputs_only","cases":9,"files":manifest,
        "exclusions":"No rawHTML, marketresponses, prices.csv, fullsourceexcerpts, credentials or source archives."}
    (out/"output_manifest.json").write_text(json.dumps(receipt,indent=2)+"\n")
    archive=root/"retail_part4_simulated_results.zip"
    with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for source in sorted(out.rglob("*")):
            if source.is_file():z.write(source,source.relative_to(out))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    transport={"archive":{"name":archive.name,"bytes":archive.stat().st_size,"sha256":sha(archive)},"files":manifest}
    print("RETAIL_APPROVED_OUTPUT_MANIFEST_BEGIN");print(json.dumps(transport));print("RETAIL_APPROVED_OUTPUT_MANIFEST_END")
    if a.log_transport:
        selected=[("ZIP",archive),("PNG",next(iter(sorted((root/"figures").glob("*.png")))))]
        for label,path in selected:
            content=base64.b64encode(path.read_bytes()).decode("ascii");size=16000;chunks=[content[i:i+size] for i in range(0,len(content),size)]
            print("RETAIL_"+label+"_BASE64_BEGIN "+json.dumps({"name":path.name,"bytes":path.stat().st_size,"sha256":sha(path),"chunks":len(chunks)}))
            for i,chunk in enumerate(chunks):print("RETAIL_"+label+"_CHUNK "+str(i+1)+"/"+str(len(chunks))+" "+chunk)
            print("RETAIL_"+label+"_BASE64_END")
if __name__=="__main__":main()
