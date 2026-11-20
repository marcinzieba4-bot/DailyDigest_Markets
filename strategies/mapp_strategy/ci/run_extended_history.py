"""Run the fixed Part 4 mapped strategy on extended public history.

Missing archive months block NEW entries; an existing position still has its
normal exit. No RSI, weekly filter, new stop, or parameter search is introduced.
Raw public reports and raw market responses remain local to this execution.
"""
from __future__ import annotations
import argparse, concurrent.futures, datetime as dt, hashlib, importlib.util
import json, re, subprocess, sys, time, urllib.parse, urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
STRATEGY_ID="mapp_strategy"
INDEX_URL="https://d7g7nkeytae81.cloudfront.net/reports/index.html"
REPORT_URL="https://d7g7nkeytae81.cloudfront.net/reports/archive/{date}.html"
POLICIES=["unhedged25","dollar_short25","beta40_daily_short25"]
FROZEN={
    "engine/data.py":"abe17e5490cc748968542bdf14dbcff2679e002025cd171498e8fe0b6d0fc4b0",
    "engine/run_nohedge.py":"05ed248a6122db21e016f0a409b6e0f1311773c74eae26c851f4506a8a18c613",
    "source_tools/frozen_mapping/map_retail.py":"7ba29285967df019e609050edc0806ee87de84764f5ee3efa7a38f6492167f7f",
    "source_tools/frozen_mapping/map_retail_etf.py":"887c0f530bb667a08b421b088cfa0670b05c882fefaf613facf49ee30ca06674",
}
FUTURE=re.compile(r"(?<![A-Za-z0-9_.])([A-Z0-9]{1,6})=F(?![A-Za-z0-9_.])",re.I)

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value
def months(start,end):
    day=dt.date.fromisoformat(start).replace(day=1); last=dt.date.fromisoformat(end)
    result=[]
    while day<=last:
        result.append(day.strftime("%Y-%m"))
        day=(day.replace(day=28)+dt.timedelta(days=4)).replace(day=1)
    return result

def mapping(root):
    """Only complete futures identifiers receive the declared identity repair.

    GC=F is gold, represented by GLD. Other futures remain unsupported in the
    fixed universe. Their '=F' suffix must never become Ford ticker F.
    Original headings remain intact in the extracted source rows.
    """
    public=module("mapp_public_sources",root/"source_tools/fetch_public_sources.py")
    frozen,universe,hashes=public.mapper(root)
    def safe_map(row):
        original=row["heading"];contracts=sorted({m.group(0).upper() for m in FUTURE.finditer(original)})
        normalized=original
        if contracts:
            normalized=FUTURE.sub(lambda m:"GLD" if m.group(0).upper()=="GC=F" else m.group(0),original)
        result=frozen({**row,"heading":normalized})
        fix=""
        if contracts:
            if any(c!="GC=F" for c in contracts):
                result.update(mapping_status="unmapped",mapping_rule="complete_unsupported_futures_identity_exclusion",
                    mapping_reason="Complete futures identifier has no approved representation in the fixed17ETF universe; its suffix is never a corporate stock ticker.",
                    crowd_direction="",mapped_symbols="",mapped_directions="{}",targets="[]")
                fix="unsupported_complete_futures_excluded_v1"
            else:
                fix="complete_GC_F_identity_to_GLD_v1"
        result.update(normalized_mapping_heading=normalized,mapping_identity_fix=fix,
                      futures_contracts=json.dumps(contracts))
        return result
    # Source identity tests only: no prices or outcomes are read.
    for heading,expected in [
        ("Gold / GC=F — gold continuation",["GLD"]),
        ("Ford / F — US automaker",["XLY"]),
        ("Copper / HG=F — equities continuation",[]),
        ("Platinum / PL=F — miners continuation",[]),
        ("Wheat / ZW=F — grain continuation",[]),
    ]:
        observed=[x["symbol"] for x in json.loads(safe_map({"slot":"4","heading":heading})["targets"])]
        assert observed==expected,(heading,observed,expected)
    return safe_map,universe,hashes

def fetch_inventory(root,start,end):
    req=urllib.request.Request(INDEX_URL,headers={"User-Agent":"MappStrategyResearch/1.0 (read-only public archive)"})
    last=None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req,timeout=45) as response:
                assert response.status==200
                body=response.read()
                meta={"url":INDEX_URL,"final_url":response.geturl(),"downloaded_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
                      "etag":response.headers.get("ETag",""),"last_modified":response.headers.get("Last-Modified",""),
                      "bytes":len(body),"sha256":hashlib.sha256(body).hexdigest()}
            break
        except Exception as ex:
            last=ex
            if attempt==2:raise
            time.sleep(2**attempt)
    path=root/"source/archive_index.html";path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
    dates=[]
    for link in BeautifulSoup(body,"html.parser").find_all("a",href=True):
        url=urllib.parse.urljoin(INDEX_URL,link["href"])
        parsed=urllib.parse.urlparse(url)
        found=re.fullmatch(r"/reports/archive/(\d{4}-\d{2}-\d{2})\.html",parsed.path)
        if found and parsed.netloc==urllib.parse.urlparse(INDEX_URL).netloc:
            day=dt.date.fromisoformat(found.group(1)).isoformat()
            if start<=day<=end:dates.append(day)
    dates=sorted(set(dates))
    assert dates,"Public index contains no dated report links in the requested window"
    index_dates=dates
    # The live index can regress when older months are uploaded. A pinned
    # public inventory contributes dates only; all report fields still come
    # from the canonical dated HTML independently fetched below.
    inventory_url="https://raw.githubusercontent.com/marcinzieba4-bot/PlayOnRetailReport/4a9c04e3604eee7ee0ce83e27e6491531f5996ae/data/retail_plays.json"
    inventory_request=urllib.request.Request(inventory_url,headers={"User-Agent":"MappStrategyResearch/1.0 (read-only public date inventory)"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(inventory_request,timeout=45) as response:
                assert response.status==200
                inventory_body=response.read()
                inventory_meta={"url":inventory_url,"final_url":response.geturl(),
                    "downloaded_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
                    "bytes":len(inventory_body),"sha256":hashlib.sha256(inventory_body).hexdigest(),
                    "role":"dates_only_no_mapping"}
            break
        except Exception:
            if attempt==2:raise
            time.sleep(2**attempt)
    document=json.loads(inventory_body.decode("utf-8"))
    assert isinstance(document,list) and document,"Invalid pinned public date inventory"
    public_dates=[]
    for record in document:
        day=dt.date.fromisoformat(record["date"]).isoformat()
        if start<=day<=end:public_dates.append(day)
    public_dates=sorted(set(public_dates))
    assert public_dates,"Pinned public inventory contains no requested dates"
    inventory_meta.update(dates=public_dates,first_date=public_dates[0],last_date=public_dates[-1])
    (root/"source/public_date_inventory.json").write_bytes(inventory_body)
    dump(root/"source/public_date_inventory_metadata.json",inventory_meta)
    known=sorted(set(index_dates)|set(public_dates))
    tail=[]
    day=dt.date.fromisoformat(known[-1])+dt.timedelta(days=1)
    while day<=dt.date.fromisoformat(end):
        tail.append(day.isoformat());day+=dt.timedelta(days=1)
    dates=sorted(set(known)|set(tail))
    meta["inventory_sources"]={
        "canonical_index":{"url":INDEX_URL,"sha256":meta["sha256"],"count":len(index_dates),
                           "first_date":index_dates[0],"last_date":index_dates[-1]},
        "pinned_public_date_inventory":{"url":inventory_url,"sha256":inventory_meta["sha256"],
                           "count":len(public_dates),"first_date":public_dates[0],"last_date":public_dates[-1],
                           "role":"dates_only_no_mapping"},
        "tail_probe":{"dates":tail,"rule":"Every calendar day after the maximum known public report date through requested end; only real canonical reports become signals."}}
    meta["canonical_index_dates"]=index_dates
    meta["public_inventory_dates"]=public_dates
    meta["tail_probe_dates"]=tail
    dump(root/"source/archive_index_metadata.json",meta)
    return dates,meta

def source_inputs(root,start,end,workers):
    public=module("mapp_source_fetch",root/"source_tools/fetch_public_sources.py")
    mapper,universe,mapping_hashes=mapping(root)
    expected,index_meta=fetch_inventory(root,start,end)
    resolved=[];missing=[];fatal=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures=[pool.submit(public.fetch_one,day,root,REPORT_URL) for day in expected]
        for future in concurrent.futures.as_completed(futures):
            record=future.result()
            if "failure" not in record:resolved.append(record)
            else:
                failure=record["failure"]
                if failure.get("http_status")==404 or failure.get("classification")=="http_200_soft_404":missing.append(failure)
                else:fatal.append(failure)
    resolved.sort(key=lambda x:x["report_date"]);missing.sort(key=lambda x:x["report_date"])
    dump(root/"source/source_fetch_failures.json",fatal)
    assert not fatal,("Source transport failure is not an absent report/month",fatal[:5])
    assert len(resolved)+len(missing)==len(expected)
    assert resolved,"No valid public archive reports"
    rows=[];errors=[]
    for meta in resolved:
        try:rows.extend(public.html_items(meta,root,mapper))
        except Exception as ex:errors.append({"report_date":meta["report_date"],"error":type(ex).__name__+": "+str(ex)})
    dump(root/"source/source_schema_errors.json",errors)
    assert not errors,("A real report schema failure must not be treated as a no-trade gap",errors[:10])
    assert len(rows)==4*len(resolved)
    assert all(t["symbol"] in universe for r in rows for t in json.loads(r["targets"]))
    public.write_csv(root/"inputs/archival_replay_etf_items.csv",rows)
    dump(root/"source/canonical_html_manifest.json",resolved)
    available=sorted({m["report_date"][:7] for m in resolved})
    absent=[m for m in months(start,end) if m not in available]
    valid_dates=[m["report_date"] for m in resolved]
    missing_dates=[m["report_date"] for m in missing]
    all_weekdays=public.weekdays(start,end)
    coverage={"strategy_id":STRATEGY_ID,"start":start,"requested_end":end,"index_url":INDEX_URL,
        "dates":expected,"valid_dates":valid_dates,"missing_dates":missing_dates,
        "canonical_index_dates":index_meta["canonical_index_dates"],"public_inventory_dates":index_meta["public_inventory_dates"],
        "tail_probe_dates":index_meta["tail_probe_dates"],"inventory_sources":index_meta["inventory_sources"],
        "indexed_report_count":len(expected),"valid_report_count":len(resolved),"indexed_missing_report_count":len(missing),
        "first_report":valid_dates[0],"last_report":valid_dates[-1],
        "available_months":available,"missing_months":absent,
        "reports_by_month":dict(sorted(Counter(m["report_date"][:7] for m in resolved).items())),
        "indexed_missing_by_month":dict(sorted(Counter(m["report_date"][:7] for m in missing).items())),
        "calendar_weekdays_without_report":[d for d in all_weekdays if d not in set(valid_dates)],
        "inventory_rule":"Union of current public archive index, pinned public report-date inventory, and calendar-day tail probes after their latest known date. Inventory bodies supply no mappings. Every candidate date is fetched from canonical HTML; only HTTP404 and verified Next.js soft404 are unavailable. Other network/schema errors are fatal.",
        "missing_month_rule":"Zero valid public reports in a month means no new entries in that month, including spillover from the preceding month. Existing positions and hedges keep their ordinary time exits/rebalances.",
        "partial_month_rule":"Unlisted/unavailable days create no new report; actual latest-report age and reservation rules remain unchanged. Missing dates are listed without synthesizing signals.",
        "source_availability":"Counterfactual printed report date 23:59:59 America/New_York; current objects are reconstructed snapshots, not verified historical publication times.",
        "source_index_sha256":index_meta["sha256"],"fixed_mapper_sha256":mapping_hashes,
        "identity_fix_version":"complete_futures_identity_v1",
        "identity_fix_counts":dict(Counter(r["mapping_identity_fix"] for r in rows if str(r["slot"])=="4" and r["mapping_identity_fix"])),
        "part4_mapping_status":dict(Counter(r["mapping_status"] for r in rows if str(r["slot"])=="4"))}
    dump(root/"source/archive_inventory.json",coverage)
    dump(root/"source/absent_indexed_reports.json",missing)
    print(json.dumps({"source_phase":"passed","reports":len(resolved),"first_report":valid_dates[0],
                      "last_report":valid_dates[-1],"missing_months":absent,
                      "indexed_missing_reports":len(missing),"identity_fixes":coverage["identity_fix_counts"]}),flush=True)
    return coverage

def fetch_market(root,start,end):
    market=module("mapp_market_fetch",root/"market/fetch_prices.py")
    market.FIRST_RESEARCH_DAY=start
    warmup=(dt.date.fromisoformat(start)-dt.timedelta(days=370)).isoformat()
    campaign={"started_utc":market.utc_now(),"requested_start":warmup,"requested_end":end,
              "research_start":start,"symbols":market.SYMBOLS,"downloads":[]}
    for index,symbol in enumerate(market.SYMBOLS):
        campaign["downloads"].append(market.download_raw(symbol,market.chart_url(symbol,warmup,end),
                                                       root/"market/raw"/(symbol+".json")))
        if index+1<len(market.SYMBOLS):time.sleep(.75)
    campaign["completed_utc"]=market.utc_now()
    market.save_json(root/"market/fetch_campaign.json",campaign)
    receipt=market.build_dataset(root,campaign)
    print(json.dumps({"market_phase":"passed",**receipt}),flush=True)

def monthly_clock(helper,data,items,start,end,allowed_months):
    """Frozen clock with one explicit, pre-reservation missing-month gate."""
    events=defaultdict(list)
    for row in items:
        first=next((d for d in data.days if d>row["report_date"] and helper.opening(d)>helper.stamp(row["available_at"])),None)
        if first:events[first].append(row)
    opportunities=[];cohorts=[];audit=[];latest=None;reserved_until=None;last_exit=-1000;last_report=None
    allowed=set(allowed_months)
    for day in [d for d in data.days if d<=end]:
        i=data.index[day]
        for row in events.get(day,[]):
            if latest is None or row["report_date"]>latest["report_date"]:latest=row
        if day<start:continue
        if reserved_until is not None and i>=reserved_until:reserved_until=None;last_exit=i
        # This guard neither changes an existing position's expiry nor restarts
        # the opportunity clock. No report is manufactured for an absent month.
        if day[:7] not in allowed:continue
        if reserved_until is not None or i<=last_exit+1 or latest is None or latest["report_date"]==last_report:continue
        age=(dt.date.fromisoformat(day)-dt.date.fromisoformat(latest["report_date"])).days
        if age>4 or not latest["legs"] or not any(t.get("source_eligible") is not False and data.eligible(t["symbol"],day,"etf")[0] for t in latest["legs"]):continue
        ident=len(opportunities)+1;exit_day,kind,censored=helper.expiry(data,day,end)
        opportunities.append(dict(clock_id=ident,date=day,report_date=latest["report_date"],source_sha256=latest["source_sha256"],
            source_version_id=latest["source_version_id"],available_at=latest["available_at"],targets=json.dumps(latest["legs"]),scheduled_exit=exit_day,exit_kind=kind))
        legs,records=helper.qualify(data,latest,day,ident,"etf");audit+=records
        if legs:cohorts.append(dict(basket_id=str(ident),entry_date=day,exit_date=exit_day,exit_kind=kind,
            report_date=latest["report_date"],heading=latest["heading"],source_sha256=latest["source_sha256"],terminal_censored=censored,legs=legs))
        last_report=latest["report_date"];reserved_until=data.index[exit_day] if not censored else len(data.days)+1
    assert all(c["entry_date"][:7] in allowed and c["report_date"][:7] in allowed for c in cohorts)
    return opportunities,cohorts,audit

def simulate(root,start,end,coverage):
    sys.path.insert(0,str(root/"engine"))
    import data as helper
    import run_nohedge as model
    helper.ROOT=root;model.INPUT=root/"inputs";model.OUT=root/"results";model.OUT.mkdir(exist_ok=True)
    data=helper.Data(root)
    eligible_end=[d for d in data.days if start<=d<=end]
    assert eligible_end
    actual_end=eligible_end[-1]
    assert actual_end==end,("Requested completed endpoint is unavailable from SPY; use an explicit earlier end rather than silently truncate",end,actual_end)
    for symbol in data.rows:
        assert sum(d<start for d in data.rows[symbol])>=41,("Insufficient 2021 warmup",symbol)
    assert all(data.maybe(s,actual_end,"close") is not None for s in data.rows),"Incomplete fixed-universe endpoint"
    coverage["actual_end"]=actual_end
    items,_=helper.load_items(data,"archive_replay","etf",start)
    opportunities,cohorts,qualification=monthly_clock(helper,data,items,start,actual_end,coverage["available_months"])
    prepared={"scope":"main","start":start,"end":actual_end,"source_min":start,
              "cohorts":{"etf_own":cohorts},"etf_opportunities":opportunities,
              "etf_qualification":qualification,"available_entry_months":coverage["available_months"],
              "missing_months":coverage["missing_months"]}
    dump(root/"inputs/main_archive_replay_prepared.json",prepared)
    protocol={"strategy_id":STRATEGY_ID,"version":"extended_history_missing_months_v1",
        "start":start,"end":actual_end,"requested_end":end,"policies":POLICIES,
        "initial_capital_usd":100000,"source_allocation":.25,"source_slot":4,"entry_trend_gate":"previous completed adjusted close > prior20 completed adjusted close average for longs; inverse for shorts",
        "exit":"Open tenth subsequent SPY session, maximum21 calendar days; endpoint close liquidates and flags censored baskets.",
        "cooldown":"Opportunity reserved before SMA20; complete flat following session, then next eligible opening; each report used at most once.",
        "fees_per_net_physical_order":.001,"short_borrow_act365":.03,"cash_interest":0,
        "filters_excluded":["RSI","weekly","new stop","parameter optimization"],
        "hedges":"Short SPY or flat only; static signed-dollar hedge or lagged40-return beta at each held opening; unhedged is third book.",
        "monthly_gap_rule":coverage["missing_month_rule"],"identity_fix_version":coverage["identity_fix_version"],
        "source_availability":coverage["source_availability"],"frozen_core_sha256":FROZEN}
    dump(root/"extended_protocol.json",protocol)
    input_paths=["prices.csv","market_manifest.json","market/fetch_campaign.json","inputs/archival_replay_etf_items.csv",
                 "inputs/main_archive_replay_prepared.json","source/archive_inventory.json","source/canonical_html_manifest.json","source/public_date_inventory_metadata.json",
                 "source/public_date_inventory.json","source/archive_index_metadata.json","source/archive_index.html","extended_protocol.json"]
    frozen={p:sha(root/p) for p in input_paths}
    dump(root/"extended_input_freeze.json",{"created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"sha256":frozen,"policies":POLICIES,"cases":3})
    audit_module=module("mapp_extended_input_audit",root/"ci/extended_input_audit.py")
    audit_module.audit_inputs(root,start,actual_end,coverage["available_months"])
    assert all(sha(root/p)==value for p,value in frozen.items()),"Input changed during independent preflight"
    summary=[];all_trades=[];all_orders=[];all_daily=[]
    source_by_id={c["basket_id"]:c for c in cohorts}
    for policy in POLICIES:
        book=model.simulate(data,"archive_replay",policy,"etf_own")
        metric=book["metric"];metric["strategy_id"]=STRATEGY_ID
        for kind,rows in book.items():
            if kind=="metric":continue
            for row in rows:row["strategy_id"]=STRATEGY_ID
            name="archive_replay_"+policy+"_"+kind+".csv";model.write(model.OUT/name,rows);metric[kind+"_path"]=name
        summary.append(metric)
        for row in book["baskets"]:
            c=source_by_id[str(row["basket_id"])]
            out=dict(corpus="archive_replay",policy=policy,**row,report_heading=c["heading"],
                     mapped_etfs="|".join(x["symbol"] for x in c["legs"]),source_directions=json.dumps({x["symbol"]:x["direction"] for x in c["legs"]}))
            for key in ["entry_nav","source_entry_notional","source_gross_pnl","hedge_gross_pnl","transaction_cost","borrow_cost","net_pnl"]:
                out[key+"_usd"]=float(row[key])*100000
            out["net_pnl_fraction_of_entry_nav"]=float(row["net_pnl"])/float(row["entry_nav"])
            all_trades.append(out)
        for row in book["orders"]:
            out=dict(corpus="archive_replay",policy=policy,**row)
            for key in ["notional","fee"]:out[key+"_usd"]=float(row[key])*100000
            for key in ["qty_before","qty_after","delta_qty","source_delta_qty","hedge_delta_qty"]:out[key+"_units_for_100000_initial_account"]=float(row[key])*100000
            all_orders.append(out)
        for row in book["daily"]:all_daily.append(dict(corpus="archive_replay",policy=policy,**row,nav_usd=row["nav"]*100000))
    model.dump(model.OUT/"summary.json",summary)
    model.write(root/"all_trades.csv",all_trades);model.write(root/"all_orders.csv",all_orders);model.write(root/"all_daily_nav.csv",all_daily)
    assert all(sha(root/p)==value for p,value in frozen.items()),"Input changed after freeze"
    try:commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
    except (OSError,subprocess.CalledProcessError):commit="local-unrecorded"
    dump(root/"provenance_run.json",{"strategy_id":STRATEGY_ID,"code_commit":commit,
        "input_freeze_sha256":sha(root/"extended_input_freeze.json"),"input_hashes_unchanged":True,
        "frozen_core_sha256":FROZEN,"adapter_sha256":sha(Path(__file__)),
        "source_snapshot":"Current publicly available retrospective reports; assumed printed-date end-of-day availability.",
        "market_snapshot":"One coherent Yahoo adjusted-price campaign; synthetic adjusted opening=open*adjclose/close.",
        "missing_month_rule":coverage["missing_month_rule"],"identity_fix_version":coverage["identity_fix_version"]})
    outputs=module("mapp_extended_outputs",root/"ci/extended_outputs.py")
    outputs.publish_outputs(root,summary,coverage,protocol)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,default=ROOT);p.add_argument("--start",default="2022-01-01")
    p.add_argument("--end",default="2026-11-20");p.add_argument("--workers",type=int,default=12)
    p.add_argument("--prices-ready",action="store_true",help="Use locally saved coherent campaign; still independently audited")
    a=p.parse_args();root=a.root.resolve()
    assert dt.date.fromisoformat(a.start)<=dt.date.fromisoformat(a.end)
    assert 1<=a.workers<=16
    assert all(sha(root/path)==expected for path,expected in FROZEN.items()),"Frozen core identity changed"
    assert not (root/"results/summary.json").exists(),"Use a fresh execution directory; never overwrite an existing outcome"
    coverage=source_inputs(root,a.start,a.end,a.workers)
    if not a.prices_ready:fetch_market(root,a.start,a.end)
    simulate(root,a.start,a.end,coverage)

if __name__=="__main__":main()
