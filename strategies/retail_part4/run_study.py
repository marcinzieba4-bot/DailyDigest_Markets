"""Execute the nine predeclared books only after a successful frozen-input preflight."""
from __future__ import annotations
import argparse,csv,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/"engine"))
import run_nohedge as model
from data import Data
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,default=ROOT);p.add_argument("--execute",action="store_true")
    p.add_argument("--expected-freeze",required=True);a=p.parse_args();root=a.root.resolve()
    if not a.execute:raise SystemExit("Explicit --execute is required after the research GO")
    assert sha(root/"research_freeze.json")==a.expected_freeze
    frozen=json.loads((root/"research_freeze.json").read_text());receipt=json.loads((root/"audit/prefreeze_review.json").read_text())
    assert receipt["status"]=="passed" and receipt["input_freeze_sha256"]==a.expected_freeze
    assert frozen["cases"]==9 and all(sha(root/path)==h for path,h in frozen["sha256"].items())
    model.INPUT=root/"inputs";model.OUT=root/"results";model.OUT.mkdir(exist_ok=True)
    assert not (model.OUT/"summary.json").exists(),"Do not overwrite an existing research outcome"
    data=Data(root);summary=[];trades=[];orders=[];daily_rows=[]
    for case,cfg in frozen["case_config"].items():
        prepared=json.loads((root/cfg["prepared_path"]).read_text())
        cohorts={str(c["basket_id"]):c for c in prepared["cohorts"]["etf_own"]}
        for policy in frozen["policies"]:
            book=model.simulate(data,case,policy,"etf_own")
            m=book["metric"]
            if policy=="unhedged25":
                assert m["hedge_orders"]==0 and all(float(x["hedge_spy_qty"])==0 for x in book["exante"])
                assert all(abs(float(x["hedge_gross_pnl"]))<1e-12 for x in book["baskets"])
                assert all(float(x["hedge_delta_qty"])==0 for x in book["orders"])
            for kind,rows in book.items():
                if kind=="metric":continue
                name=case+"_"+policy+"_"+kind+".csv";model.write(model.OUT/name,rows);m[kind+"_path"]=name
            summary.append(m)
            for row in book["baskets"]:
                c=cohorts[str(row["basket_id"])]
                out=dict(corpus=case,policy=policy,**row,report_heading=c["heading"],mapped_etfs="|".join(t["symbol"] for t in c["legs"]),
                    source_directions=json.dumps({t["symbol"]:t["direction"] for t in c["legs"]}))
                for k in ["entry_nav","source_entry_notional","source_gross_pnl","hedge_gross_pnl","transaction_cost","borrow_cost","net_pnl"]:out[k+"_usd"]=float(row[k])*100000
                out["net_pnl_fraction_of_entry_nav"]=float(row["net_pnl"])/float(row["entry_nav"]);trades.append(out)
            for row in book["orders"]:
                out=dict(corpus=case,policy=policy,**row)
                for k in ["notional","fee"]:out[k+"_usd"]=float(row[k])*100000
                for k in ["qty_before","qty_after","delta_qty","source_delta_qty","hedge_delta_qty"]:out[k+"_units_for_100000_initial_account"]=float(row[k])*100000
                orders.append(out)
            for row in book["daily"]:daily_rows.append(dict(corpus=case,policy=policy,**row,nav_usd=row["nav"]*100000))
    assert len(summary)==9
    model.dump(model.OUT/"summary.json",summary)
    model.write(model.OUT/"metrics.csv",[{k:json.dumps(v) if isinstance(v,dict) else v for k,v in m.items()} for m in summary])
    model.write(root/"all_trades.csv",trades);model.write(root/"all_orders.csv",orders);model.write(root/"all_daily_nav.csv",daily_rows)
    model.dump(model.OUT/"run_manifest.json",dict(status="completed",cases=9,failed_cases=0,input_freeze_sha256=a.expected_freeze,no_refetch_after_freeze=True))
    print(json.dumps({"status":"completed","cases":9,"books":[{k:m[k] for k in ["corpus","policy","start","end","total_return","max_drawdown","baskets","max_gross_exposure","transaction_cost","borrow_cost","realized_all","realized_active"]} for m in summary]},indent=2))
if __name__=="__main__":main()
