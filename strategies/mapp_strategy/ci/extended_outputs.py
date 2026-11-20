"""Audit and publish only simulated outputs for the explicit missing-month study.

Raw reports, extracted report text, mapped source inputs, raw market downloads,
and prices.csv are never included in the publication directory or ZIP.
"""
from __future__ import annotations
import base64,csv,datetime as dt,hashlib,importlib.util,json,math,os,shutil,zipfile
from pathlib import Path

STRATEGY_ID="mapp_strategy"
POLICIES=("unhedged25","dollar_short25","beta40_daily_short25")
LABELS={"unhedged25":"No SPY hedge","dollar_short25":"Fixed-dollar SPY short","beta40_daily_short25":"Daily beta40 SPY short or flat"}
COLORS={"unhedged25":"#C77522","dollar_short25":"#247BA0","beta40_daily_short25":"#27836B"}
CAPITAL=100000.0

def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")

def read(path):
    with Path(path).open(newline="",encoding="utf-8") as handle:
        reader=csv.DictReader(handle);rows=list(reader)
    return [] if reader.fieldnames==["empty_ledger"] else rows

def write(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=keys or ["empty_ledger"]);writer.writeheader()
        writer.writerows(rows)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def import_auditor(root):
    spec=importlib.util.spec_from_file_location("mapp_extended_independent_ledger",root/"ci"/"independent_ledger.py")
    auditor=importlib.util.module_from_spec(spec);spec.loader.exec_module(auditor)
    auditor.configure(root)
    return auditor

def same_source_signatures(root,summary):
    signatures=[]
    for metric in summary:
        rows=read(root/"results"/metric["baskets_path"])
        signatures.append([(r["basket_id"],r["report_date"],r["entry_date"],r["exit_date"],r["exit_kind"],r["symbols"]) for r in rows])
        if metric["policy"]=="unhedged25":
            assert int(metric["hedge_orders"])==0
            assert all(float(r["hedge_delta_qty"])==0 for r in read(root/"results"/metric["orders_path"]))
            assert all(float(r["hedge_spy_qty"])==0 for r in read(root/"results"/metric["exante_path"]))
    assert all(value==signatures[0] for value in signatures)
    return True

def plot(root,summary,coverage):
    os.environ.setdefault("MPLCONFIGDIR","/tmp/mapp_strategy_extended_mpl")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.ticker import FuncFormatter
    fig,(top,bottom)=plt.subplots(2,1,figsize=(13.5,8.0),sharex=True,gridspec_kw={"height_ratios":[3,1]})
    fig.patch.set_facecolor("white")
    for ax in (top,bottom):
        ax.set_facecolor("#FAFCFD");ax.grid(axis="y",color="#D9E0E5",linewidth=.7)
        ax.spines[["top","right"]].set_visible(False)
        ax.spines[["left","bottom"]].set_color("#AEBCC7")
        ax.tick_params(colors="#435563",labelsize=9)
    ordered=[next(m for m in summary if m["policy"]==p) for p in POLICIES]
    endpoint_labels=[]
    for metric in ordered:
        rows=read(root/"results"/metric["daily_path"]);assert rows
        dates=[dt.date.fromisoformat(r["date"]) for r in rows]
        first=dates[0]-dt.timedelta(days=1);dates=[first]+dates
        nav=[1.0]+[float(r["nav"]) for r in rows]
        peak=1.0;dd=[]
        for value in nav:
            peak=max(peak,value);dd.append((value/peak-1)*100)
        pnl=[(value-1)*CAPITAL for value in nav]
        policy=metric["policy"]
        label=LABELS[policy]+"  "+format(float(metric["total_return"]),"+.2%")
        top.plot(dates,pnl,color=COLORS[policy],lw=1.7,label=label)
        bottom.plot(dates,dd,color=COLORS[policy],lw=1.2)
        endpoint_labels.append({"policy":policy,"date":rows[-1]["date"],"nav_usd":nav[-1]*CAPITAL,"pnl_usd":pnl[-1],"drawdown_pct":dd[-1]})
        assert math.isclose(pnl[-1],float(metric["total_return"])*CAPITAL,rel_tol=1e-10,abs_tol=1e-7)
        assert math.isclose(min(dd),float(metric["max_drawdown"])*100,rel_tol=1e-10,abs_tol=1e-8)
    top.axhline(0,color="#708391",lw=.8)
    bottom.axhline(0,color="#708391",lw=.7)
    top.set_ylabel("Cumulative PnL (USD)",color="#253B49")
    bottom.set_ylabel("Drawdown (%)",color="#253B49")
    top.yaxis.set_major_formatter(FuncFormatter(lambda value,position:format(value,",.0f")))
    bottom.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    bottom.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    top.legend(loc="best",frameon=True,facecolor="white",edgecolor="#D9E0E5",fontsize=9)
    first,last=summary[0]["start"],summary[0]["end"]
    fig.suptitle("Part 4 mapped sectors: "+first+" to "+last,x=.075,y=.97,ha="left",fontsize=16,fontweight="bold",color="#253B49")
    missing=coverage.get("missing_months",[])
    fig.text(.075,.919,"$100,000 initial account | 25% source allocation | 10-session hold | SMA20 entry gate",fontsize=10,color="#526976")
    fig.text(.075,.035,"Net of 10 bp/order and 3% annual short borrow. Missing months: no new entries; existing exits continue.",fontsize=9,color="#526976")
    fig.text(.075,.013,"Counterfactual replay of current reports; historical publication time is assumed. "+str(len(missing))+" missing months.",fontsize=8,color="#697C87")
    fig.subplots_adjust(left=.075,right=.975,top=.895,bottom=.105,hspace=.1)
    destination=root/"figures";destination.mkdir(exist_ok=True)
    png=destination/"mapp_strategy_extended_pnl.png";svg=destination/"mapp_strategy_extended_pnl.svg"
    fig.savefig(png,dpi=160,facecolor=fig.get_facecolor())
    fig.savefig(svg,facecolor=fig.get_facecolor())
    plt.close(fig)
    result={"status":"passed","strategy_id":STRATEGY_ID,"start":first,"end":last,"initial_capital_usd":CAPITAL,"policies":list(POLICIES),"endpoint_checks":endpoint_labels,"files":{p.name:{"bytes":p.stat().st_size,"sha256":sha(p)} for p in [png,svg]}}
    dump(destination/"plot_manifest.json",result)
    return [png,svg,destination/"plot_manifest.json"]

def stream_payload(path,kind):
    payload=base64.b64encode(path.read_bytes()).decode("ascii");width=14000
    chunks=[payload[i:i+width] for i in range(0,len(payload),width)]
    print("MAPP_STRATEGY_"+kind+"_BASE64_BEGIN "+json.dumps({"name":path.name,"bytes":path.stat().st_size,"sha256":sha(path),"chunks":len(chunks)},sort_keys=True),flush=True)
    for i,chunk in enumerate(chunks,1):
        print("MAPP_STRATEGY_"+kind+"_CHUNK "+str(i)+"/"+str(len(chunks))+" "+chunk,flush=True)
    print("MAPP_STRATEGY_"+kind+"_BASE64_END",flush=True)

def publish_outputs(root,summary,coverage,protocol):
    """Return a public artifact receipt after independent reconstruction succeeds."""
    root=Path(root).resolve()
    assert len(summary)==3 and {m["policy"] for m in summary}==set(POLICIES)
    assert len({(m["corpus"],m["scope"],m["family"],m["start"],m["end"]) for m in summary})==1
    assert all(m["status"]=="ok" and m["scope"]=="main" and m["family"]=="etf_own" for m in summary)
    auditor=import_auditor(root)
    ledgers=[auditor.audit(m) for m in summary]
    betas=[auditor.audit_beta(m) for m in summary]
    metrics=[auditor.case_metrics(m) for m in summary]
    same_source_signatures(root,summary)
    diagnosis={"strategy_id":STRATEGY_ID,"status":"passed","cases":3,
        "method":"Independent physical-order cash/NAV and ACT365 borrow reconstruction, virtual source/hedge attribution, exposure and 40-return beta diagnostics. Production engine is not imported by the auditor.",
        "same_source_signatures_across_policies":True,"ledger_audits":ledgers,"beta_audits":betas,"metrics":metrics}
    dump(root/"diagnosis"/"independent_results.json",diagnosis)
    years=[dict(strategy_id=STRATEGY_ID,corpus=m["corpus"],policy=m["policy"],**r) for m in metrics for r in m["calendar_year_returns"]]
    write(root/"diagnosis"/"calendar_year_returns.csv",years)
    flat=[]
    for metric in metrics:
        row={k:v for k,v in metric.items() if not isinstance(v,(dict,list))}
        row["strategy_id"]=STRATEGY_ID
        row.update(all_day_realized_beta=metric["realized_all"]["beta"],active_day_realized_beta=metric["realized_active"]["beta"],
            net_pnl_usd=metric["total_return"]*CAPITAL,transaction_cost_usd=metric["transaction_cost"]*CAPITAL,borrow_cost_usd=metric["borrow_cost"]*CAPITAL)
        flat.append(row)
    write(root/"diagnosis"/"metrics.csv",flat)
    figures=plot(root,summary,coverage)
    publication=root/"publication"
    assert not publication.exists(),"Do not overwrite an existing publication directory"
    publication.mkdir()
    dump(publication/"summary.json",summary)
    dump(publication/"coverage.json",coverage)
    dump(publication/"protocol.json",protocol)
    for path in [root/"diagnosis"/"independent_results.json",root/"diagnosis"/"calendar_year_returns.csv",root/"diagnosis"/"metrics.csv",
        root/"provenance_run.json",root/"extended_input_freeze.json",root/"audit"/"extended_inputs.json"]+figures:
        target=publication/path.relative_to(root);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    # Consolidated simulated trade/order outputs may contain source prose in a
    # local convenience column; exclude it from the publication copies.
    excluded={"report_heading","heading","text","paragraphs","section_intro","source_text"}
    for name in ("all_trades.csv","all_orders.csv","all_daily_nav.csv"):
        path=root/name
        assert path.is_file(),str(path)
        write(publication/name,[{k:v for k,v in row.items() if k not in excluded} for row in read(path)])
    for metric in summary:
        for kind in ("daily","orders","borrow","baskets","source_trades","exante"):
            path=root/"results"/metric[kind+"_path"]
            assert path.parent==root/"results" and path.is_file()
            target=publication/"results"/path.name;target.parent.mkdir(exist_ok=True)
            write(target,[{k:v for k,v in row.items() if k not in excluded} for row in read(path)])
    readme=(
        "# mapp_strategy extended-history simulation\n\n"
        "Only the fourth topic of What Retail Is Playing is mapped into the frozen ETF universe. "
        "This study preserves the existing 25% allocation, previous-close SMA20 trend gate, "
        "10-session reservation/holding clock and complete flat-session cooldown. "
        "Three accounts compare no SPY hedge, an entry-fixed SPY short, and a daily 40-return beta SPY short or flat. "
        "Hedges never buy SPY. Source trades may include SPY and may be short when the report mapping says so.\n\n"
        "A pre-outcome parsing correction recognizes the complete GC=F gold-futures identity as GLD, "
        "and rejects other unsupported complete =F futures identities so their F suffix is never read as Ford. "
        "The frozen 153-stock sector dictionary and economic engine remain unchanged.\n\n"
        "A month absent from the available public report inventory creates no new entries during that month. "
        "Positions already open retain their normal exits. The account continues across all US sessions. "
        "The coverage file lists missing months and partial-month/date coverage separately.\n\n"
        "Accounts start with $100,000, flat. PnL is net of 10 bp on net physical orders and 3% ACT365 short borrow. "
        "There is no RSI/weekly filter, stop-loss, optimization or added regime filter.\n\n"
        "Reports are current reconstructed archive snapshots. Availability at printed date 23:59:59 New York "
        "is assumed for counterfactual replay and is not evidence of contemporaneous availability. "
        "Terminal liquidations, if any, are flagged as censored.\n\n"
        "This archive contains code-independent accounting diagnostics and simulated results only. "
        "Raw reports, extracted report prose and price downloads remain on the ephemeral execution runner. "
        "The public input-freeze file contains hashes only; the audit/input receipt contains aggregate validation checks.\n\n"
        "Per-policy results CSVs use normalized initial NAV 1. Consolidated USD columns are explicitly suffixed _usd, "
        "and order quantities scaled to the $100,000 account are explicitly labeled in their column names.\n"
    )
    (publication/"README.md").write_text(readme,encoding="utf-8")
    manifest={"strategy_id":STRATEGY_ID,"status":"passed","files":{}}
    for path in sorted(publication.rglob("*")):
        if path.is_file():manifest["files"][str(path.relative_to(publication))]={"bytes":path.stat().st_size,"sha256":sha(path)}
    dump(publication/"manifest.json",manifest)
    archive=root/"mapp_strategy_extended_simulated_results.zip"
    assert not archive.exists()
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as bundle:
        for path in sorted(publication.rglob("*")):
            if path.is_file():bundle.write(path,path.relative_to(publication))
    receipt={"strategy_id":STRATEGY_ID,"status":"passed","start":summary[0]["start"],"end":summary[0]["end"],
        "books":flat,"missing_months":coverage.get("missing_months",[]),"archive":{"name":archive.name,"bytes":archive.stat().st_size,"sha256":sha(archive)}}
    print("MAPP_STRATEGY_SUMMARY_JSON "+json.dumps(receipt,sort_keys=True,allow_nan=False),flush=True)
    stream_payload(root/"figures"/"mapp_strategy_extended_pnl.png","PNG")
    stream_payload(archive,"ZIP")
    return receipt
