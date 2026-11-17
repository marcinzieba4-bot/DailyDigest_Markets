"""Fetch/extract a public current HTML snapshot; source-only, no market returns."""
from __future__ import annotations
import argparse, concurrent.futures, csv, datetime as dt, email.utils, hashlib
import importlib.util, json, re, sys, time, urllib.error, urllib.request
from collections import Counter
from pathlib import Path
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_URL="https://d7g7nkeytae81.cloudfront.net/reports/archive/{date}.html"
EXPECTED={"map_retail.py":"7ba29285967df019e609050edc0806ee87de84764f5ee3efa7a38f6492167f7f",
          "map_retail_etf.py":"887c0f530bb667a08b421b088cfa0670b05c882fefaf613facf49ee30ca06674"}
NY=ZoneInfo("America/New_York")
def utcnow(): return dt.datetime.now(dt.timezone.utc).isoformat()
def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def dump(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
def write_csv(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with p.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=keys); w.writeheader()
        for r in rows:
            w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})
def weekdays(start,end):
    d=dt.date.fromisoformat(start); last=dt.date.fromisoformat(end); result=[]
    while d<=last:
        if d.weekday()<5: result.append(d.isoformat())
        d+=dt.timedelta(days=1)
    return result
def iso_http(s):
    if not s: return ""
    parsed=email.utils.parsedate_to_datetime(s)
    if parsed.tzinfo is None: parsed=parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc).isoformat()
def retry_delay(header,attempt):
    if header:
        try: return max(0.,min(60.,float(header)))
        except ValueError:
            try: return max(0.,min(60.,(email.utils.parsedate_to_datetime(header)-dt.datetime.now(dt.timezone.utc)).total_seconds()))
            except (ValueError,TypeError): pass
    return min(2**attempt,5)
def collection_module():
    path=Path(__file__).with_name("collection_html.py")
    spec=importlib.util.spec_from_file_location("retail_collection_html",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
def soft_404(body):
    if b"next-error-h1" not in body or b"This page could not be found." not in body:return False
    soup=BeautifulSoup(body,"html.parser")
    return (any(h.get_text(" ",strip=True)=="404" and "next-error-h1" in h.get("class",[]) for h in soup.find_all("h1"))
        and any(h.get_text(" ",strip=True)=="This page could not be found." for h in soup.find_all("h2")))
def fetch_one(day,root,url_template):
    url=url_template.format(date=day); path=root/"source"/"canonical_html"/(day+".html")
    last_error=None
    for attempt in range(3):
        try:
            request=urllib.request.Request(url,headers={"User-Agent":"RetailResearchBacktest/1.0 (read-only archive replay)"})
            with urllib.request.urlopen(request,timeout=45) as response:
                status=response.status; body=response.read()
                if status!=200: raise ValueError("Unexpected HTTP status "+str(status))
                headers=response.headers; final_url=response.geturl()
            assert body, "empty report"
            if soft_404(body):
                return {"failure":{"report_date":day,"url":url,"http_status":status,
                    "classification":"http_200_soft_404","bytes":len(body),"sha256":sha_bytes(body),
                    "error":"HTTP200 response is an actual Next404 error document, not a report."}}
            path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(body)
            last_modified_http=headers.get("Last-Modified","")
            return {"report_date":day,"key":"reports/archive/"+day+".html",
                "path":"source/canonical_html/"+day+".html","public_url":url,"source_kind":"canonical_html",
                "final_url":final_url,"downloaded_utc":utcnow(),"size":len(body),
                "sha256":sha_bytes(body),"etag":headers.get("ETag",""),
                "last_modified_http":last_modified_http,"last_modified":iso_http(last_modified_http),
                "version_id":headers.get("x-amz-version-id",""),
                "version_selection":"Current public CDN response; reported version header retained; no historical edition selection.",
                "source_snapshot":"public_current_html_snapshot"}
        except urllib.error.HTTPError as ex:
            last_error={"report_date":day,"url":url,"http_status":ex.code,"error":str(ex)}
            if ex.code not in [429,500,502,503,504]: break
            if attempt<2: time.sleep(retry_delay(ex.headers.get("Retry-After"),attempt))
        except (urllib.error.URLError,TimeoutError,OSError,ValueError,AssertionError) as ex:
            last_error={"report_date":day,"url":url,"error":type(ex).__name__+": "+str(ex)}
            if attempt<2: time.sleep(retry_delay(None,attempt))
    return {"failure":last_error}
def mapper(root):
    folder=root/"source_tools"/"frozen_mapping"
    observed={}
    for name,expected in EXPECTED.items():
        path=folder/name; observed[name]=sha_bytes(path.read_bytes())
        assert observed[name]==expected, (name,observed[name],expected)
    sys.path.insert(0,str(folder))
    from map_retail_etf import UNIVERSE, map_etf_item as frozen_map_etf_item
    def mapping(row):
        result=frozen_map_etf_item(row)
        if str(row["slot"])=="4" and result["main_title"] in ["Platinum / PL=F","Copper / HG=F"]:
            result.update(mapping_status="unmapped",mapping_rule="complete_futures_contract_identity_exclusion",
                mapping_reason="PL=F/HG=F are complete commodity futures identifiers with no approved instrument in the fixed17ETF universe; never parse root or =F suffix as corporate equity.",
                crowd_direction="",mapped_symbols="",mapped_directions="{}",targets="[]")
        return result
    return mapping,UNIVERSE,observed
def html_items(meta,root,map_item):
    path=root/meta["path"]; assert sha_bytes(path.read_bytes())==meta["sha256"]
    soup=BeautifulSoup(path.read_bytes(),"html.parser")
    markers=[h for h in soup.find_all(["h1","h2","h3","h4"]) if "What Retail Is Playing" in h.get_text()]
    assert len(markers)==1,(meta["report_date"],"retail_marker_count",len(markers))
    marker=markers[0]; cards=[]; intro=[]
    for sibling in marker.find_next_siblings():
        if sibling.name=="h2": break
        heads=sibling.find_all(["h3","h4"])
        if heads:
            assert len(heads)==1,(meta["report_date"],"card_heading_count",len(heads))
            cards.append((sibling,heads[0]))
        elif not cards and sibling.name=="p": intro.append(sibling.get_text(" ",strip=True))
    assert 1<=len(cards)<=4,(meta["report_date"],"retail_card_count",len(cards))
    day=meta["report_date"]
    assumed=dt.datetime.combine(dt.date.fromisoformat(day),dt.time(23,59,59),NY).astimezone(dt.timezone.utc).isoformat()
    allh=soup.find_all(["h1","h2","h3","h4"]); allp=soup.find_all("p"); rows=[]
    for slot,(card,head) in enumerate(cards,1):
        paragraphs=[p.get_text(" ",strip=True) for p in card.find_all("p")]
        heading=head.get_text().strip(); assert paragraphs,(day,slot,"missing_card_paragraphs")
        row={"report_date":day,"source_key":meta["key"],"source_path":meta["path"],
            "source_sha256":meta["sha256"],"source_version_id":meta.get("version_id",""),
            "source_timestamp_status":"current_public_snapshot_historical_availability_assumed",
            "generated_at":"","last_modified":meta["last_modified"],"available_at":assumed,
            "section_heading":marker.get_text().strip(),"section_intro":"\n\n".join(intro),
            "slot":str(slot),"slot_role":"dominant_narrative" if slot==1 else "secondary_topic",
            "heading":heading,"text":"\n\n".join(paragraphs),"paragraphs":paragraphs,
            "heading_index":next(i for i,h in enumerate(allh) if h is head),
            "body_indices":[next(i for i,p in enumerate(allp) if p is c) for c in card.find_all("p")],
            "heading_dollar_tickers_raw":re.findall(r"\$([A-Z][A-Z0-9.\-_]{0,11})\b",heading),
            "heading_uppercase_tokens_raw":re.findall(r"\b[A-Z][A-Z0-9.\-_]{1,11}\b",heading),
            **{k:"" for k in ["why_retail_is_here","driving_surge","social_signal","historical_analog","smart_money_view","narrative_break"]},
            "corpus":"canonical_archive_replay",
            "availability_status":"assumed_printed_report_date_end_for_counterfactual_replay",
            "actual_available_at":meta["last_modified"],"assumed_available_at":assumed,
            "source_etag":meta["etag"],"source_url":meta["public_url"],
            "source_downloaded_utc":meta["downloaded_utc"],"source_snapshot":meta["source_snapshot"],
            "paragraph_labels":[p.find("strong").get_text(" ",strip=True) if p.find("strong") else "" for p in card.find_all("p")],
            "extraction_format":"canonical_html_four_topic_cards_v1","observed_topic_count":len(cards),
            "positional_slot_present":True,"source_kind":meta.get("source_kind","canonical_html"),
            "source_element_id":"","source_observation_method":"anonymous_http"}
        rows.append({**row,**map_item(row)})
    for slot in range(len(cards)+1,5):
        row={**rows[0],"slot":str(slot),"slot_role":"secondary_topic","heading":"","text":"","paragraphs":[],
            "heading_index":"","body_indices":[],"heading_dollar_tickers_raw":[],"heading_uppercase_tokens_raw":[],
            "observed_topic_count":len(cards),"positional_slot_present":False,
            "extraction_format":"canonical_html_absent_positional_slot_cash_v1",
            "absence_reason":"Current source contains fewer than four retail topics; no older edition is spliced into absent positional slots."}
        mapped=map_item(row); assert mapped["mapping_status"]=="unmapped" and mapped["targets"]=="[]"
        rows.append({**row,**mapped})
    return rows
def run(root,start,end,url_template,workers,extract_only,collection=None):
    source=root/"source"; source.mkdir(parents=True,exist_ok=True)
    expected=weekdays(start,end)
    if extract_only:
        metas=json.loads((source/"canonical_html_manifest.json").read_text())
        assert [m["report_date"] for m in metas]==expected,"manifest must exactly cover selected weekday dates"
    else:
        supplements=collection_module().manifest_records(root,*collection) if collection else []
        supplied_dates={r["report_date"] for r in supplements}
        assert len(supplied_dates)==len(supplements) and supplied_dates<=set(expected)
        results=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            pending=[pool.submit(fetch_one,d,root,url_template) for d in expected if d not in supplied_dates]
            for future in concurrent.futures.as_completed(pending): results.append(future.result())
        failures=[r["failure"] for r in results if "failure" in r]
        fetched=[r for r in results if "failure" not in r]
        metas=sorted(fetched+supplements,key=lambda r:r["report_date"])
        receipt={"status":"passed" if not failures else "failed","source_only_no_market_or_portfolio_outcomes":True,
            "fetched_utc":utcnow(),"start":start,"end":end,"expected_weekday_reports":len(expected),
            "fetched_reports":len(fetched),"connected_collection_reports":len(supplements),"resolved_reports":len(metas),
            "failures":sorted(failures,key=lambda r:r["report_date"]),
            "inventory_scope":"Expected weekday date enumeration; anonymous dated URLs plus an explicitly configured collection; no authenticated S3 listing.",
            "snapshot_scope":"Current public HTML and configured supplied collection bytes. Exact preceding frozen source editions are not claimed preserved."}
        dump(source/"fetch_receipt.json",receipt)
        dump(source/"canonical_html_manifest.json",metas)
        if failures:
            print(json.dumps({"source_fetch_failures":failures},indent=2),flush=True)
            raise RuntimeError(str(len(failures))+" source fetch failures; do not prepare cohorts or calculate outcomes.")
    map_item,universe,mapping_hashes=mapper(root)
    rows=[]; errors=[]
    assert [m["report_date"] for m in metas]==expected,"Resolved sources must cover every expected report date"
    connected=collection_module() if any(m.get("source_kind")=="connected_monthly_html" for m in metas) else None
    for meta in metas:
        try:
            rows.extend(connected.items(meta,root,map_item) if meta.get("source_kind")=="connected_monthly_html"
                        else html_items(meta,root,map_item))
        except Exception as ex: errors.append({"report_date":meta["report_date"],"type":type(ex).__name__,"message":str(ex)})
    dump(source/"source_schema_errors.json",errors)
    if errors:
        print(json.dumps({"source_schema_errors":errors},indent=2),flush=True)
        raise RuntimeError(str(len(errors))+" source schema errors; do not prepare cohorts or calculate outcomes.")
    assert len(rows)==4*len(metas)
    write_csv(root/"inputs"/"archival_replay_etf_items.csv",rows)
    dump(source/"archival_replay_items.json",rows)
    p4=[r for r in rows if r["slot"]=="4"]
    write_csv(source/"part4_source_excerpts.csv",p4)
    absent=[{"report_date":r["report_date"],"slot":r["slot"],"observed_topic_count":r["observed_topic_count"]} for r in rows if not r["positional_slot_present"]]
    modified=[m["last_modified"] for m in metas if m["last_modified"]]
    audit={"status":"passed","source_only_no_market_or_portfolio_outcomes":True,"created_utc":utcnow(),
        "window":[start,end],"replay_reports":len(metas),"replay_rows":len(rows),
        "first_report_date":metas[0]["report_date"],"last_report_date":metas[-1]["report_date"],
        "all_expected_weekday_urls_fetched":all(m.get("source_kind","canonical_html")=="canonical_html" for m in metas),
        "all_expected_report_dates_resolved":True,"missing_weekdays":[],"extra_dates":[],
        "source_origin_counts":dict(Counter(m.get("source_kind","canonical_html") for m in metas)),
        "reports_by_month":dict(Counter(m["report_date"][:7] for m in metas)),
        "observed_card_count_distribution":dict(Counter(r["observed_topic_count"] for r in rows if r["slot"]=="1")),
        "missing_positional_slots":absent,"part4_mapping_status":dict(Counter(r["mapping_status"] for r in p4)),
        "historical_availability_rule":"Counterfactual printed report date23:59:59 America/New_York, convertedUTC. Actual current object Last-Modified kept separately. This does not establish historical publication availability.",
        "public_snapshot_rule":"Anonymous current dated HTML plus explicitly supplied collection when configured. Only actual HTTP metadata are retained; collection SHA/element/date origin is separate. No old edition selection or complete S3 version inventory is claimed.",
        "last_modified_range":[min(modified),max(modified)] if modified else None,
        "missing_last_modified_reports":sum(not m["last_modified"] for m in metas),
        "version_header_reports":sum(bool(m["version_id"]) for m in metas),
        "same_calendar_date_last_modified_reports":sum(m["last_modified"][:10]==m["report_date"] for m in metas),
        "prior_source_vintage_identity":"Not asserted: preceding frozen raw archive is unavailable on the remote execution route.",
        "frozen_mapper":{"sha256":mapping_hashes,"universe":universe,"unchanged":True,
            "complete_futures_identity_exclusion":["PL=F","HG=F"]},
        "source_files":{"inputs/archival_replay_etf_items.csv":sha_bytes((root/"inputs"/"archival_replay_etf_items.csv").read_bytes()),
            "source/canonical_html_manifest.json":sha_bytes((source/"canonical_html_manifest.json").read_bytes()),
            "source/part4_source_excerpts.csv":sha_bytes((source/"part4_source_excerpts.csv").read_bytes())}}
    dump(source/"source_provenance_audit.json",audit)
    summary={k:v for k,v in audit.items() if k not in ["frozen_mapper","missing_positional_slots","source_files","reports_by_month"]}
    dump(source/"source_summary.json",summary)
    print(json.dumps(summary,indent=2))
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--start",default="2023-11-01"); p.add_argument("--end",default="2026-10-30")
    p.add_argument("--url-template",default=DEFAULT_URL); p.add_argument("--workers",type=int,default=8)
    p.add_argument("--root",type=Path,default=ROOT); p.add_argument("--extract-only",action="store_true")
    p.add_argument("--collection-file",type=Path)
    p.add_argument("--collection-start");p.add_argument("--collection-end");p.add_argument("--collection-sha256")
    args=p.parse_args()
    assert 1<=args.workers<=16
    supplied=[args.collection_file,args.collection_start,args.collection_end,args.collection_sha256]
    assert not any(x is not None for x in supplied) or all(x is not None for x in supplied),"Supply all collection arguments together"
    collection=tuple(supplied) if args.collection_file is not None else None
    run(args.root,args.start,args.end,args.url_template,args.workers,args.extract_only,collection)
