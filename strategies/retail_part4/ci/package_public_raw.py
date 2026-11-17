"""Copy a strict public-raw allowlist; never transfer derived cohorts or trade records."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,default=ROOT);a=p.parse_args();root=a.root.resolve()
    source=json.loads((root/"source/canonical_html_manifest.json").read_text())
    prices=json.loads((root/"market_manifest.json").read_text())
    assert len(source)==783 and len(prices["series"])==17
    paths=["source/canonical_html_manifest.json","source/fetch_receipt.json","market/fetch_campaign.json","prices.csv","market_manifest.json","market/validation.json"]
    for r in source:
        name="source/canonical_html/"+r["report_date"]+".html"
        assert r["path"]==name and sha(root/name)==r["sha256"]
        paths.append(name)
    for r in prices["series"]:
        name="market/raw/"+r["symbol"]+".json"
        assert r["raw_path"]==name and sha(root/name)==r["raw_sha256"]
        paths.append(name)
    assert len(paths)==len(set(paths))
    out=root/"public_raw"
    if out.exists():shutil.rmtree(out)
    out.mkdir()
    records=[]
    for name in sorted(paths):
        target=(root/name).resolve()
        assert root in target.parents and target.is_file()
        assert not any(x in Path(name).parts for x in ["inputs","results","benchmarks","cohorts"])
        dest=out/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(target,dest)
        records.append({"path":name,"sha256":sha(target),"bytes":target.stat().st_size})
    try:commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
    except (OSError,subprocess.CalledProcessError):commit="local-unrecorded"
    manifest={"status":"passed","source_commit":commit,"kind":"anonymous_public_raw_only","reports":len(source),"price_series":len(prices["series"]),"files":records,"exclusions":"No derived mappings, prepared cohorts, positions, old fixtures, trades or orders."}
    (out/"public_raw_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps({"status":"passed","reports":len(source),"series":len(prices["series"]),"files":len(records),"raw_manifest_sha256":sha(out/"public_raw_manifest.json")}))
if __name__=="__main__":main()
