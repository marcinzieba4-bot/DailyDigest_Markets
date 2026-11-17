"""Parse a supplied monthly retail collection without changing frozen mapping.

This module contains format logic and a digest, never the collection contents.
Historical availability remains an explicit EOD-New-York replay assumption.
"""
from __future__ import annotations
import datetime as dt, hashlib, json, re
from pathlib import Path
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
NY=ZoneInfo("America/New_York")
_CACHE={}
def sha_bytes(body):return hashlib.sha256(body).hexdigest()
def expected_days(start,end):
    day=dt.date.fromisoformat(start);last=dt.date.fromisoformat(end);out=[]
    assert day<=last
    while day<=last:
        if day.weekday()<5:out.append(day.isoformat())
        day+=dt.timedelta(days=1)
    return out
def document(root,relpath,wanted,dates):
    root=Path(root).resolve();path=(root/relpath).resolve()
    assert root in path.parents and path.is_file(),"Collection must be a local file below the study root"
    body=path.read_bytes();actual=sha_bytes(body)
    assert re.fullmatch(r"[0-9a-f]{64}",wanted) and actual==wanted,("Collection digest mismatch",actual,wanted)
    key=(str(path),actual,tuple(dates))
    if key not in _CACHE:
        soup=BeautifulSoup(body,"html.parser")
        markers=[h for h in soup.find_all("h1")
                 if " ".join(h.get_text(" ",strip=True).split()).casefold()=="what retail is playing"]
        assert len(markers)==1,"Collection must identify the intended retail section exactly once"
        sections=soup.find_all("section",class_="day")
        assert len(sections)==len(dates)
        ids=[s.get("id") for s in sections]
        assert ids==dates,"Collection must contain exactly the supplied ordered weekday dates"
        bydate={}
        for section in sections:
            cards=section.find_all("article",class_="trade",recursive=False)
            assert len(cards)==4,(section.get("id"),"collection_card_count",len(cards))
            assert all(len(c.find_all("h3",recursive=False))==1 for c in cards)
            assert all(c.find_all("p") for c in cards)
            header=section.find("header",class_="dayhead",recursive=False)
            assert header is not None and header.find("p",class_="intro") is not None
            assert header.find("p",class_="kicker") is not None
            bydate[section["id"]]=(section,cards,header)
        _CACHE[key]=(soup,bydate,markers[0])
    return _CACHE[key]
def manifest_records(root,collection_path,start,end,expected_sha256):
    root=Path(root).resolve();path=Path(collection_path)
    if not path.is_absolute():path=root/path
    path=path.resolve()
    assert root in path.parents,"Collection path leaves study root"
    rel=path.relative_to(root).as_posix()
    dates=expected_days(start,end)
    soup,bydate,marker=document(root,rel,expected_sha256,dates)
    observed=dt.datetime.now(dt.timezone.utc).isoformat()
    records=[]
    for day in dates:
        section,cards,header=bydate[day]
        records.append({"report_date":day,
            "key":"connected_monthly_html/"+path.name+"#"+day,"path":rel,
            "source_kind":"connected_monthly_html","source_element_id":day,
            "public_url":"","final_url":"","downloaded_utc":observed,
            "size":path.stat().st_size,"sha256":expected_sha256,"etag":"",
            "collection_start":start,"collection_end":end,
            "last_modified_http":"","last_modified":"","version_id":"",
            "version_selection":"Exact supplied collection bytes verified by SHA256; no HTTP object version or historical publication timestamp is asserted.",
            "source_snapshot":"connected_month_collection_current_reconstruction",
            "source_observation_method":"local_collection_read",
            "reported_information_cutoff":header.find("p",class_="kicker").get_text(" ",strip=True)})
    return records
def items(meta,root,map_item):
    assert meta["source_kind"]=="connected_monthly_html"
    dates=expected_days(meta["collection_start"],meta["collection_end"])
    soup,bydate,marker=document(root,meta["path"],meta["sha256"],dates)
    day=meta["report_date"]
    assert meta["source_element_id"]==day and day in bydate
    section,cards,header=bydate[day]
    assumed=dt.datetime.combine(dt.date.fromisoformat(day),dt.time(23,59,59),NY).astimezone(dt.timezone.utc).isoformat()
    allh=soup.find_all(["h1","h2","h3","h4"]);allp=soup.find_all("p");rows=[]
    for slot,card in enumerate(cards,1):
        head=card.find("h3",recursive=False);heading=head.get_text().strip()
        ps=card.find_all("p");paragraphs=[p.get_text(" ",strip=True) for p in ps]
        labels=[]
        for p in ps:
            label=p.parent.find("h4",recursive=False)
            labels.append(label.get_text(" ",strip=True) if label is not None else "")
        row={"report_date":day,"source_key":meta["key"],"source_path":meta["path"],
            "source_sha256":meta["sha256"],"source_version_id":"",
            "source_timestamp_status":"connected_collection_current_reconstruction_historical_availability_assumed",
            "generated_at":"","last_modified":"","available_at":assumed,
            "section_heading":marker.get_text().strip(),
            "section_intro":header.find("p",class_="intro").get_text(" ",strip=True),
            "slot":str(slot),"slot_role":"dominant_narrative" if slot==1 else "secondary_topic",
            "heading":heading,"text":"\n\n".join(paragraphs),"paragraphs":paragraphs,
            "heading_index":next(i for i,h in enumerate(allh) if h is head),
            "body_indices":[next(i for i,p in enumerate(allp) if p is c) for c in ps],
            "heading_dollar_tickers_raw":re.findall(r"\$([A-Z][A-Z0-9.\-_]{0,11})\b",heading),
            "heading_uppercase_tokens_raw":re.findall(r"\b[A-Z][A-Z0-9.\-_]{1,11}\b",heading),
            **{k:"" for k in ["why_retail_is_here","driving_surge","social_signal","historical_analog","smart_money_view","narrative_break"]},
            "corpus":"connected_collection_replay",
            "availability_status":"assumed_printed_report_date_end_for_counterfactual_replay",
            "actual_available_at":"","assumed_available_at":assumed,
            "source_etag":"","source_url":"","source_downloaded_utc":meta["downloaded_utc"],
            "source_snapshot":meta["source_snapshot"],"paragraph_labels":labels,
            "extraction_format":"connected_monthly_html_four_trade_articles_v1",
            "observed_topic_count":4,"positional_slot_present":True,
            "source_kind":meta["source_kind"],"source_element_id":day,
            "source_observation_method":meta["source_observation_method"],
            "reported_information_cutoff":meta["reported_information_cutoff"]}
        rows.append({**row,**map_item(row)})
    return rows
