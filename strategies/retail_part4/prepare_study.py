"""Prepare fixed public-source cases and an authorized recorded-decision bridge, without portfolio returns."""
from __future__ import annotations
import argparse,collections,csv,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/"engine"))
import data as helper
POLICIES=["dollar_short25","beta40_daily_short25","unhedged25"]
FIXTURE_SHA="59fc98f15cfab32b8918b644e7e48db5dc30855821c24c86ceb4527f8a2fcc96"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
def read(p):
    with p.open(newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
def write(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    if not rows:p.write_text("empty_ledger\n");return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with p.open("w",newline="") as f:
        w=csv.DictWriter(f,keys);w.writeheader();w.writerows(rows)
def recorded_fixture(root,cfg):
    path=root/"benchmarks/september_2024_recorded/trades.csv"
    assert sha(path)==FIXTURE_SHA,"Recorded CSV identity changed"
    rows=read(path)
    assert len(rows)==75
    signatures={}
    for policy in POLICIES:
        group=[r for r in rows if r["policy"]==policy]
        assert len(group)==25
        signatures[policy]=[(r["basket_id"],r["report_date"],r["entry_date"],r["exit_date"],r["symbols"]) for r in group]
    assert all(v==signatures["unhedged25"] for v in signatures.values())
    cohorts=[]
    for r in [x for x in rows if x["policy"]=="dollar_short25"]:
        directions=json.loads(r["source_directions"]);symbol=r["symbols"]
        assert len(directions)==1 and directions[symbol]==1 and "|" not in symbol
        assert abs(float(r["source_entry_notional"])*1.001/(float(r["entry_nav"])*.25)-1)<1e-10
        cohorts.append(dict(basket_id=r["basket_id"],report_date=r["report_date"],entry_date=r["entry_date"],
            exit_date=r["exit_date"],exit_kind=r["exit_kind"],heading=r["report_heading"],
            terminal_censored=str(r["terminal_censored"]).lower()=="true",legs=[dict(symbol=symbol,direction=1,weight=1.0)]))
    return dict(scope="main",start=cfg["start"],end=cfg["end"],source_min=cfg["source_min"],
        cohorts={"etf_own":cohorts},etf_opportunities=[],etf_qualification=[],source_items=25,
        source_corpus="recorded_economic_fixture",fixture_provenance=dict(csv_sha256=FIXTURE_SHA,
        reconstructed_from_recorded_trades=True,not_original_prepared_json_bytes=True,
        note="Economic decisions only; original source hashes/versions and reserved gate history were not recovered. Repriced on current fresh prices, never claimed old-vintage identity."))
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,default=ROOT);a=p.parse_args();root=a.root.resolve()
    assert not (root/"results/summary.json").exists(),"Use a fresh study output directory for preflight"
    helper.ROOT=root;data=helper.Data(root)
    protocol=json.loads((root/"protocol.json").read_text());config=protocol["case_config"]
    assert set(config)=={"november_continuous","september_current","september_recorded_fixture"}
    assert protocol["policies"]==POLICIES and protocol["cases"]==9
    checks=[]
    for case,cfg in config.items():
        if case=="september_recorded_fixture":
            prepared=recorded_fixture(root,cfg)
        else:
            items,excluded=helper.load_items(data,"archive_replay","etf",cfg["source_min"])
            assert not excluded
            opportunities,cohorts,qualification=helper.clock(data,items,cfg["start"],cfg["end"],"etf")
            prepared=dict(scope="main",start=cfg["start"],end=cfg["end"],source_min=cfg["source_min"],
                cohorts={"etf_own":cohorts},etf_opportunities=opportunities,etf_qualification=qualification,
                source_items=len(items),source_corpus="current_public_archive_replay")
        dump(root/cfg["prepared_path"],prepared)
        write(root/"inputs"/(case+"_opportunities.csv"),prepared["etf_opportunities"])
        write(root/"inputs"/(case+"_qualification.csv"),prepared["etf_qualification"])
        cohorts=prepared["cohorts"]["etf_own"]
        checks.append(dict(case=case,source_items=prepared["source_items"],reserved_opportunities=len(prepared["etf_opportunities"]),
            funded_cohorts=len(cohorts),source_directions=dict(collections.Counter(str(t["direction"]) for c in cohorts for t in c["legs"])),
            source_instruments=dict(collections.Counter(t["symbol"] for c in cohorts for t in c["legs"])),
            source_spy_cohorts=sum(any(t["symbol"]=="SPY" for t in c["legs"]) for c in cohorts)))
    fixed=[root/"protocol.json",root/"requirements.txt",root/"prices.csv",root/"market_manifest.json",root/"market/fetch_campaign.json",root/"market/fetch_prices.py",
        root/"source/canonical_html_manifest.json",root/"inputs/archival_replay_etf_items.csv",
        root/"benchmarks/september_2024_recorded/trades.csv",root/"benchmarks/september_2024_recorded/orders.csv"]
    source_manifest=json.loads((root/"source/canonical_html_manifest.json").read_text())
    for meta in source_manifest:
        actual=(root/meta["path"]).resolve()
        assert root in actual.parents and actual.is_file(),"Source manifest path must stay in the study"
        fixed.append(actual)
    fixed+=list(root.glob("*.py"))
    for folder in ["engine","ci","source_tools","market/raw","source/canonical_html"]:
        fixed += [x for x in (root/folder).rglob("*") if x.is_file() and "__pycache__" not in x.parts and (x.suffix in [".py",".json",".html"])]
    fixed += [x for x in (root/"inputs").glob("*") if x.is_file() and x.suffix in [".json",".csv"]]
    fixed=sorted(set(fixed))
    campaign=json.loads((root/"market/fetch_campaign.json").read_text())
    frozen=dict(status="Before portfolio outcomes; guarded job requires independent preflight and explicit execution GO",
        frozen_utc=campaign["completed_utc"],cases=9,policies=POLICIES,case_config=config,
        sha256={x.relative_to(root).as_posix():sha(x) for x in fixed})
    dump(root/"research_freeze.json",frozen)
    receipt=dict(status="prepared_without_portfolio_outcomes",cases=9,prepared_cases=checks,
        input_freeze_sha256=sha(root/"research_freeze.json"),frozen_file_count=len(fixed),
        price_snapshot_sha256=sha(root/"prices.csv"),source_extraction_sha256=sha(root/"inputs/archival_replay_etf_items.csv"))
    dump(root/"audit/preparation_summary.json",receipt);print(json.dumps(receipt,indent=2))
if __name__=="__main__":main()
