"""Independent public-source, price and gap-calendar audit for the extended three-book study.
No portfolio simulator imports; raw inputs remain local to the runner.
"""
from __future__ import annotations
import csv,datetime as dt,hashlib,json,math,re,statistics,sys
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
NY=ZoneInfo("America/New_York")
SYMBOLS=["EPOL","GLD","IEF","QQQ","SOXX","SPY","XLB","XLC","XLE","XLF","XLI","XLK","XLP","XLRE","XLU","XLV","XLY"]
EXCHANGES={"NYQ","NMS","NGM","NCM","ASE","PCX","BTS","BATS","CBOE","NYSEArca","NasdaqGM","NasdaqGS","NasdaqCM"}
EXPECTED_CODE={
"engine/run_nohedge.py":"05ed248a6122db21e016f0a409b6e0f1311773c74eae26c851f4506a8a18c613",
"engine/data.py":"abe17e5490cc748968542bdf14dbcff2679e002025cd171498e8fe0b6d0fc4b0",
"source_tools/frozen_mapping/map_retail.py":"7ba29285967df019e609050edc0806ee87de84764f5ee3efa7a38f6492167f7f",
"source_tools/frozen_mapping/map_retail_etf.py":"887c0f530bb667a08b421b088cfa0670b05c882fefaf613facf49ee30ca06674",
}
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
        assert a==b, 'Independent preparation mismatch'

def prices_and_metadata(root,study_start,study_end):
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
    assert manifest["requested_end"]==study_end and manifest["requested_start"]<study_start
    campaign=load(root/"market/fetch_campaign.json")
    assert campaign["requested_start"]==manifest["requested_start"] and campaign["requested_end"]==study_end
    downloads={r["symbol"]:r for r in campaign["downloads"]}
    assert len(downloads)==len(campaign["downloads"])==len(SYMBOLS) and set(downloads)==set(SYMBOLS)
    meta={r["symbol"]:r for r in manifest["series"]}
    assert set(meta)==set(SYMBOLS)
    days=sorted(d for s,d in prices if s=="SPY")
    assert days and days[-1]==study_end and any(d>=study_start for d in days)
    assert sum(d<study_start for d in days)>=41
    endpoint_close=dt.datetime.combine(dt.date.fromisoformat(days[-1]),dt.time(16),NY)
    raw_count=0
    for symbol,m in meta.items():
        assert m["status"] in ["ok","cached","success"]
        assert m["quote_type"]=="ETF" and m["currency"]=="USD"
        assert m["exchange_timezone"]=="America/New_York" and m["exchange"] in EXCHANGES
        own_days=sorted(d for s,d in prices if s==symbol)
        assert own_days and own_days[-1]==study_end
        assert sum(d<study_start for d in own_days)>=41
        raw=safe_path(root,m["raw_path"])
        assert raw.exists() and digest(raw)==m["raw_sha256"]
        download=downloads[symbol]
        assert download["raw_path"]==m["raw_path"] and download["sha256"]==m["raw_sha256"]
        successful=[a for a in download["attempts"] if a.get("http_status")==200 and a.get("sha256")==m["raw_sha256"]]
        assert len(successful)==1 and stamp(successful[0]["requested_utc"])>=endpoint_close, "Endpoint raw download began before final daily close"
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
    return prices,days,meta,{"price_rows":len(rows),"series":len(meta),"spy_sessions":len(days),"first_price_session":days[0],"last_price_session":days[-1],"prior_spy_closes_before_start":sum(d<study_start for d in days),"independently_decoded_raw_series":raw_count,"endpoint_close":endpoint_close.isoformat(),"all_raw_requests_after_endpoint_close":True}


def months_between(start,end):
    year,month=map(int,start[:7].split("-"));result=[]
    while f"{year:04d}-{month:02d}"<=end[:7]:
        result.append(f"{year:04d}-{month:02d}")
        month+=1
        if month==13:year+=1;month=1
    return result

def audit_source(root,start,end,available_months):
    index_path=root/"source/archive_index.html"
    inventory=load(root/"source/archive_inventory.json")
    soup=BeautifulSoup(index_path.read_bytes(),"html.parser")
    indexed=[]
    for anchor in soup.find_all("a",href=True):
        matched=re.fullmatch(r"archive/(\d{4}-\d{2}-\d{2})\.html",anchor["href"])
        if matched:
            day=matched[1]
            assert dt.date.fromisoformat(day).isoformat()==day
            if start<=day<=end:indexed.append(day)
    indexed=sorted(set(indexed))
    assert indexed and inventory["canonical_index_dates"]==indexed
    # A newer canonical index omitted known later reports. The pinned public
    # retail JSON supplies dates/URLs only; all mapped content comes from each
    # independently parsed canonical HTML document below.
    public_path=root/"source/public_date_inventory.json"
    public_blob=public_path.read_bytes()
    public_meta=load(root/"source/public_date_inventory_metadata.json")
    pinned_url="https://raw.githubusercontent.com/marcinzieba4-bot/PlayOnRetailReport/4a9c04e3604eee7ee0ce83e27e6491531f5996ae/data/retail_plays.json"
    assert public_meta["url"]==pinned_url and public_meta["role"]=="dates_only_no_mapping"
    assert public_meta["bytes"]==len(public_blob)
    assert public_meta["sha256"]==hashlib.sha256(public_blob).hexdigest()
    git_header=b"blob "+str(len(public_blob)).encode("ascii")+bytes([0])
    assert hashlib.sha1(git_header+public_blob).hexdigest()=="53c05fde782652973678f831f4cb430613afa486"
    public_document=json.loads(public_blob)
    assert isinstance(public_document,list) and len(public_document)==778
    all_public_dates=[record["date"] for record in public_document]
    assert len(all_public_dates)==len(set(all_public_dates))
    assert all(dt.date.fromisoformat(day).isoformat()==day for day in all_public_dates)
    public_dates=sorted(day for day in all_public_dates if start<=day<=end)
    assert public_meta["dates"]==public_dates==inventory["public_inventory_dates"]
    known=sorted(set(indexed)|set(public_dates));assert known
    tail=[];cursor=dt.date.fromisoformat(known[-1])+dt.timedelta(days=1)
    while cursor<=dt.date.fromisoformat(end):
        tail.append(cursor.isoformat());cursor+=dt.timedelta(days=1)
    assert inventory["tail_probe_dates"]==tail
    expected=sorted(set(known)|set(tail))
    assert inventory["dates"]==expected
    valid=inventory["valid_dates"];missing=inventory["missing_dates"]
    assert valid==sorted(set(valid)) and missing==sorted(set(missing))
    assert set(valid).isdisjoint(missing) and sorted(valid+missing)==expected
    observed_months=sorted({day[:7] for day in valid})
    assert list(available_months)==observed_months==inventory["available_months"]
    missing_months=sorted(set(months_between(start,end))-set(observed_months))
    assert inventory["missing_months"]==missing_months
    manifest_path=root/"source/canonical_html_manifest.json"
    manifest=load(manifest_path)
    assert [m["report_date"] for m in manifest]==valid
    rows=read(root/"inputs/archival_replay_etf_items.csv")
    grouped=defaultdict(list)
    for row in rows:
        day=row["report_date"];assert day in valid
        assert int(row["slot"]) in (1,2,3,4)
        assert len(row["source_sha256"])==64 and all(c in "0123456789abcdef" for c in row["source_sha256"])
        expected=dt.datetime.combine(dt.date.fromisoformat(day),dt.time(23,59,59),NY)
        assert stamp(row["available_at"])==expected
        targets=json.loads(row["targets"])
        assert len({t["symbol"] for t in targets})==len(targets)
        assert all(t["symbol"] in SYMBOLS and int(t["direction"]) in (-1,1) for t in targets)
        grouped[day].append(row)
    assert sorted(grouped)==valid
    sys.path.insert(0,str(root/"source_tools/frozen_mapping"))
    from map_retail_etf import map_etf_item
    # Independent identity normalization, specified before any outcome reads.
    # Frozen dictionary and title mapper remain byte-identical.
    contracts=re.compile(r"(?<![A-Za-z0-9_.])([A-Z0-9]{1,6})=F(?![A-Za-z0-9_.])",re.I)
    futures_counts=defaultdict(int);mapped_part4=absent_part4=0
    for metadata in manifest:
        day=metadata["report_date"];group=grouped[day]
        assert len(group)==4 and {int(r["slot"]) for r in group}=={1,2,3,4}
        assert metadata["path"]=="source/canonical_html/"+day+".html"
        assert metadata["public_url"]=="https://d7g7nkeytae81.cloudfront.net/reports/archive/"+day+".html"
        raw=safe_path(root,metadata["path"]);blob=raw.read_bytes();observed=hashlib.sha256(blob).hexdigest()
        assert observed==metadata["sha256"] and len(blob)==metadata["size"]
        assert all(r["source_sha256"]==observed and r["source_path"]==metadata["path"] for r in group)
        assert all(r["source_version_id"]==metadata.get("version_id","") for r in group)
        assert all(r["last_modified"]==metadata["last_modified"] for r in group)
        document=BeautifulSoup(blob,"html.parser")
        markers=[h for h in document.find_all(["h1","h2","h3","h4"]) if "What Retail Is Playing" in h.get_text()]
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
            slot=int(row["slot"]);i=slot-1
            if i<len(cards):
                assert row["heading"]==cards[i][0] and row["text"]==cards[i][1]
                if "positional_slot_present" in row:assert truth(row["positional_slot_present"])
            else:
                assert row["heading"]==row["text"]=="" and json.loads(row["targets"])==[]
                if "positional_slot_present" in row:assert not truth(row["positional_slot_present"])
            # Mapping is heading-only. Independently reapply frozen specification
            # to the original heading after explicit complete-contract handling.
            found=[value.upper() for value in contracts.findall(row["heading"])]
            unsupported=[root_token for root_token in found if root_token!="GC"]
            if unsupported:
                assert json.loads(row["targets"])==[]
            else:
                normalized=contracts.sub(lambda match:"GLD" if match[1].upper()=="GC" else match[0],row["heading"])
                candidate=dict(row);candidate["heading"]=normalized
                expected_map=map_etf_item(candidate)
                assert json.loads(row["targets"])==json.loads(expected_map["targets"])
            if slot==4:
                for root_token in found:futures_counts[root_token+"=F"]+=1
                mapped_part4+=bool(json.loads(row["targets"]))
                absent_part4+=i>=len(cards)
    items=[]
    for day in valid:
        row=dict(next(r for r in grouped[day] if int(r["slot"])==4))
        row["legs"]=[dict(symbol=t["symbol"],direction=int(t["direction"]),
            source_eligible=t.get("source_eligible",True),
            source_eligibility_reason=t.get("source_eligibility_reason","fixed17_etf_mapping"))
            for t in json.loads(row["targets"])]
        items.append(row)
    receipt=dict(source_reports=len(valid),indexed_report_dates=len(indexed),known_public_inventory_dates=len(public_dates),
        requested_union_report_dates=len(expected),tail_probe_dates=tail,missing_requested_dates=missing,
        missing_months=missing_months,available_months=observed_months,
        source_report_sections_verified=len(valid),mapped_part4_reports=mapped_part4,absent_part4_reports=absent_part4,
        canonical_manifest_sha256=digest(manifest_path),archive_index_sha256=digest(index_path),
        public_dates_inventory_sha256=digest(public_path),
        public_dates_inventory_git_blob_sha1="53c05fde782652973678f831f4cb430613afa486",
        public_dates_inventory_role="Date/URL inventory only; JSON research bodies never used for signals.",
        complete_futures_part4_counts=dict(futures_counts),
        mapping_identity_rule="Complete GC=F normalized to GLD before frozen heading mapper; all other complete =F futures unmapped.",
        availability="Current reconstructed snapshots; assumed printed-date 23:59:59 America/New_York, not verified historical availability.")
    return items,receipt

def audit_inputs(root,start,end,available_months):
    root=Path(root).resolve();available_months=sorted(set(available_months))
    assert start=="2022-01-01" and end>=start
    for rel,expected in EXPECTED_CODE.items():
        assert digest(root/rel)==expected, "Frozen strategy component changed: "+rel
    prices,days,meta,price_receipt=prices_and_metadata(root,start,end)
    items,source_receipt=audit_source(root,start,end,available_months)
    path=root/"inputs/main_archive_replay_prepared.json";prepared=load(path)
    assert prepared["start"]==prepared["source_min"]==start and prepared["end"]==end
    assert prepared["available_entry_months"]==available_months
    opportunities,cohorts,qualifications,held_states,beta_cache_entries,unknown_held_states=independent_preparation(
        prices,days,meta,items,start,end,start,set(available_months))
    same(opportunities,prepared["etf_opportunities"])
    same(cohorts,prepared["cohorts"]["etf_own"])
    same(qualifications,prepared["etf_qualification"])
    assert all(o["date"][:7] in available_months for o in opportunities)
    assert all(c["entry_date"][:7] in available_months for c in cohorts)
    carried=[c for c in cohorts if c["exit_date"][:7] not in available_months]
    result=dict(strategy_id="mapp_strategy",status="passed",start=start,end=end,
        prices=price_receipt,sources=source_receipt,
        independently_replayed_reserved_opportunities=len(opportunities),
        independently_replayed_filled_baskets=len(cohorts),
        independently_verified_held_beta_states=held_states,
        independently_observed_unknown_beta_states=unknown_held_states,
        independent_beta_cache_entries=beta_cache_entries,
        missing_month_entries=0,carried_baskets_exiting_in_missing_months=len(carried),
        missing_month_rule="No entry/reservation in absent report months; release/cooldown and held exits retain continuous US-session clock.",
        prepared_sha256=digest(path))
    destination=root/"audit/extended_inputs.json";destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print("MAPP_STRATEGY_EXTENDED_INPUT_AUDIT "+json.dumps(result,sort_keys=True,allow_nan=False),flush=True)
    return result
def independent_preparation(prices,days,meta,items,start,end,source_min,available_months):
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
        if day[:7] not in available_months:continue
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
    held_states=0;unknown_held_states=0
    for cohort in cohorts:
        for day in days:
            if cohort["entry_date"]<=day and (day<cohort["exit_date"] or day==cohort["exit_date"] and cohort["exit_kind"]=="close"):
                for leg in cohort["legs"]:
                    unknown_held_states+=beta(leg["symbol"],day) is None
                    held_states+=1
    return opportunities,cohorts,qualifications,held_states,len(beta_cache),unknown_held_states

