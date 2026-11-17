"""Reprice only the three predeclared recorded-25 controls; never a November 2023 backtest.

Uses the existing current-vintage price snapshot. It fetches no data, reads no
report archive, and does not change the complete-source gate for the nine-book study.
"""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for folder in [ROOT,ROOT/"engine",ROOT/"ci"]:sys.path.insert(0,str(folder))
import check_study as checks
import independent_ledger as verifier
import prepare_study
import run_nohedge as model
from data import Data
POLICIES=["dollar_short25","beta40_daily_short25","unhedged25"]
CASE="september_recorded_fixture"
STRATEGY_ID="mapp_strategy"
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+"\n")
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,default=ROOT);p.add_argument("--execute",action="store_true")
    args=p.parse_args();root=args.root.resolve()
    if not args.execute:raise SystemExit("Explicit --execute is required for the recorded-control research GO")
    target=root/"recorded_controls"
    assert not target.exists(),"Do not overwrite an earlier control result"
    protocol=json.loads((root/"protocol.json").read_text())
    assert protocol["cases"]==9 and protocol["policies"]==POLICIES
    assert set(protocol["case_config"])=={"november_continuous","september_current",CASE}
    cfg=protocol["case_config"][CASE]
    assert cfg["start"]==cfg["source_min"]=="2024-09-01"
    assert cfg["end"]==protocol["source_calendar"]["end"]
    assert cfg["prepared_path"]=="inputs/main_"+CASE+"_prepared.json"
    for path,wanted in checks.EXPECTED_CODE.items():assert sha(root/path)==wanted,path
    _,_,_,market_review=checks.prices_and_metadata(root)
    prepared=prepare_study.recorded_fixture(root,cfg)
    fixture_review=checks.recorded_fixture(root,prepared)
    assert len(prepared["cohorts"]["etf_own"])==25
    fixed=[root/"protocol.json",root/"prices.csv",root/"market_manifest.json",root/"market/fetch_campaign.json",
        root/"market/fetch_prices.py",root/"prepare_study.py",root/"ci/check_study.py",
        root/"ci/independent_ledger.py",root/"ci/run_recorded_controls.py",
        root/"benchmarks/september_2024_recorded/trades.csv",root/"benchmarks/september_2024_recorded/orders.csv"]
    fixed += [root/path for path in checks.EXPECTED_CODE]
    manifest=json.loads((root/"market_manifest.json").read_text())
    fixed += [checks.safe_path(root,row["raw_path"]) for row in manifest["series"]]
    hashes={path.relative_to(root).as_posix():sha(path) for path in sorted(set(fixed))}
    frozen={"status":"Frozen before recorded-control outcomes","kind":"recorded25_repricing_only",
        "case":CASE,"policies":POLICIES,"start":cfg["start"],"end":cfg["end"],"sha256":hashes}
    dump(target/"input_freeze.json",frozen)
    freeze_sha=sha(target/"input_freeze.json")
    dump(root/cfg["prepared_path"],prepared)
    hashes[cfg["prepared_path"]]=sha(root/cfg["prepared_path"])
    frozen["sha256"]=hashes;dump(target/"input_freeze.json",frozen);freeze_sha=sha(target/"input_freeze.json")
    assert all(sha(root/path)==wanted for path,wanted in hashes.items())
    model.INPUT=root/"inputs";model.OUT=target/"results";model.OUT.mkdir()
    data=Data(root);summary=[]
    for policy in POLICIES:
        book=model.simulate(data,CASE,policy,"etf_own")
        metric=book["metric"];metric["strategy_id"]=STRATEGY_ID
        for kind,rows in book.items():
            if kind=="metric":continue
            for row in rows:row["strategy_id"]=STRATEGY_ID
            name=CASE+"_"+policy+"_"+kind+".csv";model.write(model.OUT/name,rows);metric[kind+"_path"]=name
        summary.append(metric)
    dump(model.OUT/"summary.json",summary)
    verifier.configure(root);verifier.OUT=model.OUT
    ledger_reviews=[verifier.audit(metric) for metric in summary]
    beta_reviews=[verifier.audit_beta(metric) for metric in summary]
    metrics=[verifier.case_metrics(metric) for metric in summary]
    signatures=[[(row["basket_id"],row["report_date"],row["entry_date"],row["exit_date"],row["symbols"])
        for row in verifier.read(model.OUT/metric["baskets_path"])] for metric in summary]
    assert all(signature==signatures[0] for signature in signatures) and len(signatures[0])==25
    unhedged=next(metric for metric in summary if metric["policy"]=="unhedged25")
    assert unhedged["hedge_orders"]==0
    assert all(float(row["hedge_delta_qty"])==0 for row in verifier.read(model.OUT/unhedged["orders_path"]))
    assert all(float(row["hedge_spy_qty"])==0 for row in verifier.read(model.OUT/unhedged["exante_path"]))
    assert all(sha(root/path)==wanted for path,wanted in hashes.items())
    receipt={"strategy_id":STRATEGY_ID,"status":"passed","kind":"recorded25_repricing_only","cases":3,"source_reports_read":0,
        "description":"Only the existing 25 recorded September-2024 decisions, repriced on current prices through the protocol endpoint. This is not the November-2023 backtest and does not validate missing report history.",
        "input_freeze_sha256":freeze_sha,"market":market_review,"fixture":fixture_review,
        "ledger_audits":ledger_reviews,"beta_audits":beta_reviews,"metrics":metrics,
        "full_nine_book_source_gate_unchanged":True,"no_refetch":True}
    dump(target/"independent_results.json",receipt)
    public_keys=["corpus","policy","start","end","baskets","total_return","max_drawdown","transaction_cost","borrow_cost","realized_all","realized_active"]
    print(json.dumps({"strategy_id":STRATEGY_ID,"status":"passed","kind":receipt["kind"],"description":receipt["description"],
        "cases":3,"input_freeze_sha256":freeze_sha,"metrics":[{key:metric[key] for key in public_keys} for metric in summary]},indent=2))
if __name__=="__main__":main()
