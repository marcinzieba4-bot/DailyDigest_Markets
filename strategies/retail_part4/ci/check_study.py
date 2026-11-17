"""Independent source/price/clock preflight; no portfolio simulation or production imports.

--preflight validates the exact frozen inputs and preparation before a research GO.
--ledger runs the separately recovered independent ledger verifier after simulation.
Only aggregate receipts are printed. Detailed input/output publication is controlled
separately by the repository workflow and the user's explicit data authorization.
"""
from __future__ import annotations
import argparse, csv, datetime as dt, hashlib, importlib.util, json, math, statistics
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
NY = ZoneInfo("America/New_York")
POLICIES = ["dollar_short25", "beta40_daily_short25", "unhedged25"]
SYMBOLS = ["EPOL","GLD","IEF","QQQ","SOXX","SPY","XLB","XLC","XLE","XLF","XLI","XLK","XLP","XLRE","XLU","XLV","XLY"]
EXCHANGES = {"NYQ","NMS","NGM","NCM","ASE","PCX","BTS","BATS","CBOE","NYSEArca","NasdaqGM","NasdaqGS","NasdaqCM"}
EXPECTED_CODE = {
    "engine/run_nohedge.py":"05ed248a6122db21e016f0a409b6e0f1311773c74eae26c851f4506a8a18c613",
    "engine/data.py":"abe17e5490cc748968542bdf14dbcff2679e002025cd171498e8fe0b6d0fc4b0",
}
EXPECTED_MAPPERS = {
    "map_retail.py":"7ba29285967df019e609050edc0806ee87de84764f5ee3efa7a38f6492167f7f",
    "map_retail_etf.py":"887c0f530bb667a08b421b088cfa0670b05c882fefaf613facf49ee30ca06674",
}
CASE_STARTS = {"november_continuous":"2023-11-01","september_current":"2024-09-01","september_recorded_fixture":"2024-09-01"}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):
    return json.loads(path.read_text(encoding="utf-8"))
def read(path):
    with path.open(newline="",encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
def close(a,b,tol=1e-10):
    if a is None or b is None:
        assert a is None and b is None, (a,b)
    else:
        assert math.isclose(float(a),float(b),rel_tol=tol,abs_tol=tol), (a,b)
def stamp(value):
    return dt.datetime.fromisoformat(value.replace("Z","+00:00"))
def opening(day):
    return dt.datetime.combine(dt.date.fromisoformat(day),dt.time(9,30),NY)
def truth(value):
    return value is True or str(value).lower()=="true"
def safe_path(root,rel):
    path=(root/rel).resolve()
    assert path==root or root in path.parents, "Path leaves study root"
    return path
def same(a,b):
    if isinstance(a,dict):
        assert isinstance(b,dict) and set(a)<=set(b), (set(a),set(b))
        for key,value in a.items():
            same(value,b[key])
    elif isinstance(a,list):
        assert isinstance(b,list) and len(a)==len(b), (len(a),len(b))
        for x,y in zip(a,b):same(x,y)
    elif isinstance(a,(int,float)) and not isinstance(a,bool):
        close(a,b)
    else:
        assert a==b, (a,b)

def code_and_freeze(root):
    frozen=load(root/"research_freeze.json")
    assert frozen["cases"] in (6,9)
    files=frozen["sha256"]
    assert files and all(digest(safe_path(root,p))==h for p,h in files.items())
    checks={}
    for path,wanted in EXPECTED_CODE.items():
        assert digest(root/path)==wanted, path
        assert path in files, path+" missing from freeze"
        checks[path]=wanted
    for name,wanted in EXPECTED_MAPPERS.items():
        candidates=[p for p in root.rglob(name) if p.is_file() and "__pycache__" not in p.parts]
        assert candidates, name
        assert all(digest(p)==wanted for p in candidates), name
        assert any(str(p.relative_to(root)) in files for p in candidates), name+" missing from freeze"
        checks[name]=wanted
    config=frozen["case_config"]
    assert isinstance(config,dict)
    assert set(config) in ({"november_continuous","september_current"},{"november_continuous","september_current","september_recorded_fixture"})
    assert frozen["cases"]==3*len(config)
    assert set(frozen.get("policies",POLICIES))==set(POLICIES)
    assert "protocol.json" in files
    for case,c in config.items():
        assert c["start"]==CASE_STARTS[case] and c["end"]=="2026-10-30"
        assert c["prepared_path"]=="inputs/main_"+case+"_prepared.json"
        assert c["prepared_path"] in files
        assert c["source_min"]==CASE_STARTS[case]
    assert "prices.csv" in files and "market_manifest.json" in files
    assert "inputs/archival_replay_etf_items.csv" in files
    assert not (root/"results/summary.json").exists(), "Fresh portfolio summary exists before preflight"
    return frozen,checks

def prices_and_metadata(root):
    rows=read(root/"prices.csv")
    assert rows and set(rows[0])=={"symbol","session_date","open","close","adjusted_open","adjclose","volume"}
    prices={}
    for r in rows:
        key=(r["symbol"],r["session_date"])
        assert key not in prices and key[0] in SYMBOLS, key
        values={k:float(r[k]) for k in ["open","close","adjusted_open","adjclose","volume"]}
        assert all(math.isfinite(v) for v in values.values())
        assert all(values[k]>0 for k in ["open","close","adjusted_open","adjclose"]) and values["volume"]>=0
        close(values["adjusted_open"],values["open"]*values["adjclose"]/values["close"],1e-12)
        prices[key]=values
    manifest=load(root/"market_manifest.json")
    assert manifest["output_sha256"]==digest(root/"prices.csv")
    meta={r["symbol"]:r for r in manifest["series"]}
    assert set(meta)==set(SYMBOLS)
    days=sorted(d for s,d in prices if s=="SPY")
    assert days and days[-1]=="2026-10-30" and "2023-11-01" in days
    assert sum(d<"2023-11-01" for d in days)>=41
    raw_count=0
    for symbol,m in meta.items():
        assert m["status"] in ["ok","cached","success"]
        assert m["quote_type"]=="ETF" and m["currency"]=="USD"
        assert m["exchange_timezone"]=="America/New_York" and m["exchange"] in EXCHANGES
        own_days=sorted(d for s,d in prices if s==symbol)
        assert sum(d<"2023-11-01" for d in own_days)>=41
        raw=safe_path(root,m["raw_path"])
        assert raw.exists() and digest(raw)==m["raw_sha256"]
        document=load(raw); chart=document["chart"]
        assert chart.get("error") is None and len(chart["result"])==1
        item=chart["result"][0];timestamps=item["timestamp"]
        q=item["indicators"]["quote"][0];ac=item["indicators"]["adjclose"][0]["adjclose"]
        assert all(len(q[k])==len(timestamps) for k in ["open","close","volume"])
        assert len(ac)==len(timestamps)
        expected={}
        for i,t in enumerate(timestamps):
            day=dt.datetime.fromtimestamp(t,dt.timezone.utc).astimezone(NY).date().isoformat()
            if not manifest["requested_start"]<=day<=manifest["requested_end"]:continue
            fields=[q["open"][i],q["close"][i],ac[i],q["volume"][i]]
            okay=all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in fields)
            okay=okay and all(v>0 for v in fields[:3]) and fields[3]>=0
            if not okay:continue
            assert day not in expected
            expected[day]=fields
        assert set(expected)==set(own_days), symbol+" raw/decoded calendar"
        for day,(op,cl,adj,vol) in expected.items():
            r=prices[symbol,day]
            for key,value in [("open",op),("close",cl),("adjclose",adj),("volume",vol)]:
                assert r[key]==float(value), (symbol,day,key)
            close(r["adjusted_open"],float(op)*float(adj)/float(cl),1e-12)
        raw_count+=1
    return prices,days,meta,{"price_rows":len(rows),"series":len(meta),"spy_sessions":len(days),"first_price_session":days[0],"last_price_session":days[-1],"prior_spy_closes_before_start":sum(d<"2023-11-01" for d in days),"independently_decoded_raw_series":raw_count}

def source_rows(root):
    rows=read(root/"inputs/archival_replay_etf_items.csv")
    by_date=defaultdict(list)
    for row in rows:
        assert "2023-11-01"<=row["report_date"]<="2026-10-30"
        assert int(row["slot"]) in (1,2,3,4)
        assert len(row["source_sha256"])==64 and all(c in "0123456789abcdef" for c in row["source_sha256"])
        expected=dt.datetime.combine(dt.date.fromisoformat(row["report_date"]),dt.time(23,59,59),NY)
        assert stamp(row["available_at"])==expected
        targets=json.loads(row["targets"])
        assert isinstance(targets,list) and len({t["symbol"] for t in targets})==len(targets)
        assert all(t["symbol"] in SYMBOLS and int(t["direction"]) in (-1,1) for t in targets)
        by_date[row["report_date"]].append(row)
    expected=[];day=dt.date(2023,11,1)
    while day<=dt.date(2026,10,30):
        if day.weekday()<5:expected.append(day.isoformat())
        day+=dt.timedelta(days=1)
    assert len(expected)==783
    missing=sorted(set(expected)-set(by_date))
    assert not missing, "Missing printed weekday reports"
    assert not (set(by_date)-set(expected)), "Unexpected source report dates"
    manifest_path=root/"source/canonical_html_manifest.json"
    manifest=load(manifest_path)
    assert [m["report_date"] for m in manifest]==expected
    manifests={m["report_date"]:m for m in manifest}
    assert len(manifests)==783
    raw_verified=0
    for day,group in by_date.items():
        assert len(group)==4 and {int(r["slot"]) for r in group}=={1,2,3,4}
        metadata=manifests[day]
        assert metadata["path"]=="source/canonical_html/"+day+".html"
        raw=safe_path(root,metadata["path"])
        blob=raw.read_bytes();observed=hashlib.sha256(blob).hexdigest()
        assert observed==metadata["sha256"] and len(blob)==metadata["size"]
        assert metadata["public_url"]=="https://d7g7nkeytae81.cloudfront.net/reports/archive/"+day+".html"
        assert all(r["source_sha256"]==observed and r["source_path"]==metadata["path"] for r in group)
        assert all(r["source_version_id"]==metadata.get("version_id","") for r in group)
        assert all(r["last_modified"]==metadata["last_modified"] for r in group)
        soup=BeautifulSoup(blob,"html.parser")
        markers=[h for h in soup.find_all(["h1","h2","h3","h4"]) if "What Retail Is Playing" in h.get_text()]
        assert len(markers)==1
        cards=[]
        for element in markers[0].find_next_siblings():
            if element.name=="h2":break
            headings=element.find_all(["h3","h4"])
            if headings:
                assert len(headings)==1
                paragraphs=[p.get_text(" ",strip=True) for p in element.find_all("p")]
                assert paragraphs
                cards.append((headings[0].get_text().strip(),"\n\n".join(paragraphs)))
        assert 1<=len(cards)<=4
        for row in group:
            i=int(row["slot"])-1
            if i<len(cards):
                assert row["heading"]==cards[i][0] and row["text"]==cards[i][1]
                if "positional_slot_present" in row:assert truth(row["positional_slot_present"])
            else:
                assert row["heading"]==row["text"]=="" and json.loads(row["targets"])==[]
                if "positional_slot_present" in row:assert not truth(row["positional_slot_present"])
        raw_verified+=1
    items=[]
    for day in sorted(by_date):
        row=dict(next(r for r in by_date[day] if int(r["slot"])==4))
        legs=[]
        for target in json.loads(row["targets"]):
            legs.append({"symbol":target["symbol"],"direction":int(target["direction"]),
                         "source_eligible":target.get("source_eligible",True),
                         "source_eligibility_reason":target.get("source_eligibility_reason","fixed17_etf_mapping")})
        row["legs"]=legs;items.append(row)
    return items,{"source_reports":len(by_date),"source_rows":len(rows),"expected_weekdays":len(expected),"missing_weekday_count":len(missing),"weekday_coverage_complete":not missing,"raw_html_and_positional_bodies_verified":raw_verified,"canonical_manifest_sha256":digest(manifest_path),"mapped_part4_rows":sum(bool(r["legs"]) for r in items),"availability":"Assumed printed report date 23:59:59 America/New_York; current retrospective snapshots, not verified historical publication."}

def independent_preparation(prices,days,meta,items,start,end,source_min):
    index={d:i for i,d in enumerate(days)};beta_cache={}
    def bar(s,d):return prices.get((s,d))
    def eligible(s,d):
        m=meta.get(s,{})
        if m.get("status") not in ["ok","cached","success"]:return False,"history_unavailable"
        if m.get("quote_type") not in {"ETF","EQUITY"}:return False,"not_equity_or_etf"
        if m.get("currency")!="USD" or m.get("exchange_timezone")!="America/New_York":return False,"not_usd_us_session"
        if m.get("exchange") not in EXCHANGES:return False,"unapproved_exchange_or_otc"
        if bar(s,d) is None:return False,"missing_entry_open"
        i=index[d];prior=[bar(s,x) for x in days[max(0,i-20):i]]
        if len(prior)<20 or any(r is None for r in prior):return False,"fewer_than_20_prior_sessions"
        dv=[r["close"]*r["volume"] for r in prior]
        if not all(math.isfinite(v) and v>=0 for v in dv):return False,"invalid_prior_dollar_volume"
        return (False,"prior_median_dollar_volume_below_10m") if statistics.median(dv)<10000000 else (True,"eligible")
    def sma(s,d,direction):
        i=index[d];prior=[bar(s,x) for x in days[max(0,i-20):i]]
        okay=len(prior)==20 and all(r is not None for r in prior)
        avg=sum(r["adjclose"] for r in prior)/20 if okay else None
        last=prior[-1]["adjclose"] if okay else None
        return bool(okay and (last>avg if direction>0 else last<avg)),last,avg
    def beta(s,d):
        if (s,d) not in beta_cache:
            prior=days[max(0,index[d]-41):index[d]]
            series=[[bar(t,x) for x in prior] for t in [s,"SPY"]]
            if len(prior)!=41 or any(v is None for group in series for v in group):v=None
            else:
                ps=[[r["adjclose"] for r in group] for group in series]
                y,x=[[b/a-1 for a,b in zip(group,group[1:])] for group in ps]
                mx,my=statistics.mean(x),statistics.mean(y)
                den=sum((a-mx)**2 for a in x)
                v=sum((a-mx)*(b-my) for a,b in zip(x,y))/den if den>0 else None
            beta_cache[s,d]=v
        return beta_cache[s,d]
    def expiry(d):
        target=index[d]+10;deadline=dt.date.fromisoformat(d)+dt.timedelta(days=21)
        if target<len(days):
            while dt.date.fromisoformat(days[target])>deadline:target-=1
        if target>=len(days) or days[target]>end:return end,"close",True
        return days[target],"open",False
    events=defaultdict(list)
    for row in items:
        if row["report_date"]<source_min:continue
        first=next((d for d in days if d>row["report_date"] and opening(d)>stamp(row["available_at"])),None)
        if first:events[first].append(row)
    opportunities=[];cohorts=[];qualifications=[];latest=None;reserved_until=None;last_exit=-1000;last_report=None
    for day in [d for d in days if d<=end]:
        i=index[day]
        for row in events.get(day,[]):
            if latest is None or row["report_date"]>latest["report_date"]:latest=row
        if day<start:continue
        if reserved_until is not None and i>=reserved_until:reserved_until=None;last_exit=i
        if reserved_until is not None or i<=last_exit+1 or latest is None or latest["report_date"]==last_report:continue
        age=(dt.date.fromisoformat(day)-dt.date.fromisoformat(latest["report_date"])).days
        candidates=latest["legs"]
        if age>4 or not candidates or not any(t.get("source_eligible") is not False and eligible(t["symbol"],day)[0] for t in candidates):continue
        ident=len(opportunities)+1;exit_day,kind,censored=expiry(day)
        opportunities.append({"clock_id":ident,"date":day,"report_date":latest["report_date"],
             "source_sha256":latest["source_sha256"],"source_version_id":latest["source_version_id"],
             "available_at":latest["available_at"],"targets":json.dumps(candidates),
             "scheduled_exit":exit_day,"exit_kind":kind})
        accepted=[]
        for target in candidates:
            symbol,direction=target["symbol"],int(target["direction"])
            okay,reason=eligible(symbol,day)
            if target.get("source_eligible") is False:okay,reason=False,target.get("source_eligibility_reason","source_ineligible_foreign_listing")
            aligned,last,avg=sma(symbol,day,direction)
            if okay and not aligned:okay,reason=False,"crowd_direction_not_sma20_aligned"
            weight=1/len(candidates)
            qualifications.append({"clock_id":ident,"date":day,"report_date":latest["report_date"],"symbol":symbol,
                 "direction":direction,"original_weight":weight,"eligible":okay,"reason":reason,
                 "prior_close":last,"prior_sma20":avg,"beta40":beta(symbol,day),
                 "available_at":latest["available_at"],"source_sha256":latest["source_sha256"]})
            if okay:accepted.append({"symbol":symbol,"direction":direction,"weight":weight})
        if accepted:cohorts.append({"basket_id":str(ident),"entry_date":day,"exit_date":exit_day,"exit_kind":kind,
             "report_date":latest["report_date"],"heading":latest["heading"],"source_sha256":latest["source_sha256"],
             "terminal_censored":censored,"legs":accepted})
        last_report=latest["report_date"];reserved_until=index[exit_day] if not censored else len(days)+1
    held_states=0
    for cohort in cohorts:
        for day in days:
            if cohort["entry_date"]<=day and (day<cohort["exit_date"] or day==cohort["exit_date"] and cohort["exit_kind"]=="close"):
                for leg in cohort["legs"]:
                    assert beta(leg["symbol"],day) is not None
                    held_states+=1
    return opportunities,cohorts,qualifications,held_states,len(beta_cache)

def run_preflight(root):
    frozen,code=code_and_freeze(root)
    prices,days,meta,price_report=prices_and_metadata(root)
    items,source_report=source_rows(root)
    checks=[]
    for case,cfg in frozen["case_config"].items():
        prepared=load(root/cfg["prepared_path"])
        for key in ["start","end","source_min"]:assert prepared[key]==cfg[key]
        cohorts=prepared["cohorts"]["etf_own"]
        assert len({str(c["basket_id"]) for c in cohorts})==len(cohorts)
        assert len({c["entry_date"] for c in cohorts})==len(cohorts)
        assert all(c["entry_date"]<=c["exit_date"]<=cfg["end"] for c in cohorts)
        assert all(c["entry_date"]<c["exit_date"] or (c["exit_kind"]=="close" and truth(c["terminal_censored"])) for c in cohorts)
        assert all(len({t["symbol"] for t in c["legs"]})==len(c["legs"]) for c in cohorts)
        if case=="september_recorded_fixture":
            assert len(cohorts)==25 and not prepared["etf_opportunities"] and not prepared["etf_qualification"]
            check={"case":case,"source_mode":"Recorded economic decisions repriced; not original prepared bytes or original price vintage.","funded_cohorts":len(cohorts)}
        else:
            opp,expected,qual,held,beta_count=independent_preparation(prices,days,meta,items,cfg["start"],cfg["end"],cfg["source_min"])
            same(opp,prepared["etf_opportunities"]);same(expected,cohorts);same(qual,prepared["etf_qualification"])
            check={"case":case,"reserved_opportunities":len(opp),"funded_cohorts":len(expected),"qualification_rows":len(qual),"held_lagged_beta_states":held,"unique_beta_estimates":beta_count}
        check["source_directions"]=sorted({int(t["direction"]) for c in cohorts for t in c["legs"]})
        check["source_spy_cohorts"]=sum(any(t["symbol"]=="SPY" for t in c["legs"]) for c in cohorts)
        checks.append(check)
    receipt={"status":"passed","reviewed_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
       "phase":"Before fresh portfolio outcomes","cases":frozen["cases"],"runtime_and_mapper_identities":code,
       "frozen_file_count":len(frozen["sha256"]),"frozen_input_hashes_unchanged":True,
       "input_freeze_sha256":digest(root/"research_freeze.json"),
       "market":price_report,"source":source_report,"prepared_cases":checks,
       "method":"No production imports or portfolio simulation. Independent raw-price decoding, source/date/target checks, metadata/liquidity-before-reservation, pre-SMA calendar, qualification and strictly prior40-return OLS.",
       "publication":"Aggregate audit receipt only; detailed source decisions/results require their own publication authorization."}
    out=root/"audit/prefreeze_review.json";out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(receipt,indent=2))

def main():
    parser=argparse.ArgumentParser()
    phase=parser.add_mutually_exclusive_group(required=True)
    phase.add_argument("--preflight",action="store_true");phase.add_argument("--ledger",action="store_true")
    parser.add_argument("--root",type=Path,default=ROOT)
    args=parser.parse_args();root=args.root.resolve()
    if args.preflight:run_preflight(root)
    else:
        script=root/"ci/independent_ledger.py"
        assert script.exists(),"Independent ledger verifier missing"
        spec=importlib.util.spec_from_file_location("independent_ledger",script)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.run(root,expected_cases=load(root/"research_freeze.json")["cases"])

if __name__=="__main__":main()
