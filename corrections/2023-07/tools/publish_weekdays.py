"""Publish the July 2023 historical archive using a locally configured AWS identity."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import time
from urllib.request import Request, urlopen

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
BUCKET = "s3bucketmz"
DISTRIBUTION = "E15IJW4438D21G"
INDEX = "reports/index.html"
BASE = "https://zembihf.xyz/"
DAYS = ["2023-07-" + d for d in ("03","04","05","06","07","10","11","12","13","14","17","18","19","20","21","24","25","26","27","28","31")]
MONTH = "2023-07.html"

def git_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def plan():
    manifest = json.loads((ROOT/"release/objects.json").read_text())
    assert set(manifest["days"]) == set(DAYS) and len(manifest["days"]) == len(DAYS)
    allowed = {"reports/2023-07.html","reports/2023-07/What_Retail_Is_Playing_2023-07.html",
               "reports/2023-07/July_2023_Weekday_Reports.zip","reports/2023-07/July_2023_Sources_and_Audit.zip"}
    expected = set(allowed)
    for day in DAYS:
        expected.add("reports/archive/" + day + ".html")
        for fmt in ("pdf","json"):
            fname = f"{day}_Market_Intelligence.{fmt}"
            expected.add(f"reports/2023-07/{fmt}/{fname}")
            expected.add(("Strategies/" if fmt=="pdf" else "Strategies/json/")+fname)
    assert expected == set(manifest["objects"])
    objects = {}
    for key, item in manifest["objects"].items():
        file = (ROOT/item["path"]).resolve()
        assert ROOT in file.parents
        data = file.read_bytes()
        if git_sha(data) != item["git_blob"]: raise ValueError("Incorrect checked-out bytes: "+key)
        objects[key] = (file, hashlib.sha256(data).hexdigest())
    for day in DAYS:
        data=json.loads(objects[f"reports/2023-07/json/{day}_Market_Intelligence.json"][0].read_bytes())
        assert data["report_date"]==day
        assert len(data["sections"]["retail"])==4 and len(data["sections"]["geo"])==6 and len(data["sections"]["sectors"])==13
        doc=BeautifulSoup(objects[f"reports/archive/{day}.html"][0].read_bytes(),"html.parser")
        assert len(doc.select("section[id] > h2"))==9 and len(doc.select("#retail article"))==4
    return objects

def merge_index(body):
    original = body.decode("utf-8")
    soup = BeautifulSoup(original,"html.parser")
    daily = soup.find_all("a",href=re.compile(r"^archive/\d{4}-\d{2}-\d{2}\.html$"))
    if not daily or len({id(x.find_parent("ul")) for x in daily}) != 1:
        raise ValueError("Cannot identify the dated archive list")
    ul = daily[0].find_parent("ul")
    prior = Counter(a["href"] for a in soup.select("a[href]"))
    added = []
    offsets = [0]
    for line in original.splitlines(keepends=True):offsets.append(offsets[-1]+len(line))
    def offset(tag): return offsets[tag.sourceline-1]+tag.sourcepos
    edits = {}
    if not prior[MONTH]:
        edits[offset(ul)] = '<p><a href="2023-07.html">July 2023 — Weekday editions and downloads</a></p>\n'
        added.append(MONTH)
    last = daily[-1].find_parent("li")
    tail = original.index("</li>",offset(last)) + len("</li>")
    for day in reversed(DAYS):
        href = "archive/"+day+".html"
        if prior[href]:
            if prior[href]!=1 or soup.find("a",href=href).get_text(strip=True)!=day:raise ValueError("Conflicting entry: "+href)
            continue
        after = next((a for a in daily if a["href"][8:18]<day),None)
        pos = offset(after.find_parent("li")) if after is not None else tail
        edits[pos]=edits.get(pos,"")+f'\n<li><a href="{href}">{day}</a></li>\n'
        added.append(href)
    for pos,text in sorted(edits.items(),reverse=True):original=original[:pos]+text+original[pos:]
    fresh = BeautifulSoup(original,"html.parser")
    assert Counter(a["href"] for a in fresh.select("a[href]"))==prior+Counter(added)
    assert [a.get_text(strip=True) for a in fresh.find_all("a",href=re.compile(r"^archive/2023-07-\d\d\.html$"))]==DAYS[::-1]
    return original.encode()

def public_bytes(key):
    req=Request(BASE+key,headers={"User-Agent":"DailyDigest-Archive-Verification/1.0","Accept-Encoding":"identity"})
    with urlopen(req,timeout=35) as response:
        if response.status!=200:raise ValueError(f"HTTP {response.status}: {key}")
        return response.read()

def read_public(objects):
    body=public_bytes(INDEX)
    if merge_index(body)!=body:raise ValueError("The public archive is missing July entries")
    def verify(item):
        key, (_,digest)=item
        actual=hashlib.sha256(public_bytes(key)).hexdigest()
        if digest!=actual:raise ValueError("Public content mismatch: "+key)
    with ThreadPoolExecutor(6) as pool:list(pool.map(verify,objects.items()))
    print(f"Verified {len(objects)} public objects and all {len(DAYS)} archive entries.",flush=True)

def browser_check():
    from playwright.sync_api import sync_playwright
    chrome=shutil.which("google-chrome") or shutil.which("chromium")
    with sync_playwright() as pw:
        br=pw.chromium.launch(executable_path=chrome,headless=True,args=["--no-sandbox"])
        for width in (1440,390):
            page=br.new_page(viewport={"width":width,"height":960})
            page.set_default_timeout(20000)
            page.goto(BASE+"research/",wait_until="domcontentloaded")
            page.get_by_role("button",name="Daily Summary",exact=True).click()
            page.get_by_role("button",name="Archives",exact=True).click()
            page.get_by_role("button",name=re.compile(r"^2023\b")).click()
            page.get_by_role("button",name=re.compile(r"^July\b")).click()
            for day in DAYS:
                button=page.get_by_role("button",name=day,exact=True)
                assert button.count()==1,day
            for day in (DAYS[0],DAYS[-1]):
                page.get_by_role("button",name=day,exact=True).click()
                frame=page.frame_locator(f'iframe[src="/reports/archive/{day}.html"]')
                frame.get_by_role("heading",name="Market Intelligence Briefing",exact=True).wait_for()
                assert frame.locator("#retail article").count()==4
                assert frame.locator("html").evaluate("el=>el.scrollWidth<=innerWidth+1")
            page.close()
        br.close()
    print("Verified July selection on desktop and mobile through the live Daily Summary archive.",flush=True)

def publish(objects):
    cfg=Config(connect_timeout=10,read_timeout=60,retries={"max_attempts":3},max_pool_connections=10)
    args={}
    if not os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_KEY"):
        args={"aws_access_key_id":os.environ["AWS_KEY"],"aws_secret_access_key":os.environ["AWS_SECRET"]}
    session=boto3.Session(region_name="eu-north-1",**args)
    s3=session.client("s3",endpoint_url="https://s3.eu-north-1.amazonaws.com",config=cfg)
    def get(key):
        o=s3.get_object(Bucket=BUCKET,Key=key)
        return o,o["Body"].read()
    def create(key,body,content):
        try:s3.put_object(Bucket=BUCKET,Key=key,Body=body,ContentType=content,IfNoneMatch="*",Metadata={"sha256":hashlib.sha256(body).hexdigest()})
        except ClientError as e:
            if e.response["Error"]["Code"] not in ("PreconditionFailed","412","ConditionalRequestConflict","409"):raise
        if get(key)[1]!=body:raise ValueError("An existing object differs: "+key)
    previous=get(INDEX)[1];merge_index(previous)
    def stage(key):
        path,_=objects[key]
        mime=mimetypes.guess_type(key)[0] or "application/octet-stream"
        create(key,path.read_bytes(),mime+("; charset=utf-8" if mime in ("application/json","text/html") else ""))
    with ThreadPoolExecutor(8) as pool:list(pool.map(stage,objects))
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    for i in range(8):
        meta,body=get(INDEX); replacement=merge_index(body)
        if body==replacement:break
        create(f"reports/_retrospective_backup/jul-2023-weekdays/{stamp}/{i}/reports/index.html",body,"text/html; charset=utf-8")
        kwargs={k:meta[k] for k in ("ContentType","CacheControl","ContentLanguage","ContentDisposition","Metadata","Expires") if k in meta}
        try:s3.put_object(Bucket=BUCKET,Key=INDEX,Body=replacement,IfMatch=meta["ETag"],**kwargs)
        except ClientError as e:
            if e.response["Error"]["Code"] in ("PreconditionFailed","412","ConditionalRequestConflict","409"):continue
            raise
        break
    else:raise RuntimeError("Live archive changed during all merge attempts")
    body=get(INDEX)[1];assert merge_index(body)==body
    cloudfront=session.client("cloudfront",config=cfg)
    paths=["/reports/index.html","/reports/","/reports/archive/2023-07-*","/reports/2023-07*","/Strategies/2023-07-*","/Strategies/json/2023-07-*"]
    invalidation=cloudfront.create_invalidation(DistributionId=DISTRIBUTION,InvalidationBatch={"CallerReference":"july-weekday-"+stamp,"Paths":{"Quantity":len(paths),"Items":paths}})["Invalidation"]
    print("Origin verified. CloudFront invalidation",invalidation["Id"],flush=True)
    cloudfront.get_waiter("invalidation_completed").wait(DistributionId=DISTRIBUTION,Id=invalidation["Id"],WaiterConfig={"Delay":12,"MaxAttempts":70})

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--publish",action="store_true")
    p.add_argument("--verify-public",action="store_true")
    p.add_argument("--browser",action="store_true")
    p.add_argument("--check",action="store_true")
    args=p.parse_args();objects=plan()
    fixture=b'<ul><li><a href="archive/2023-08-01.html">2023-08-01</a></li><li><a href="archive/2023-07-research-companion.html">2023-07-31 &#183; Monthly Research Companion</a></li><li><a href="archive/2023-06-30.html">2023-06-30</a></li></ul>'
    assert merge_index(merge_index(fixture))==merge_index(fixture)
    print("Validated",len(DAYS),"local issues and",len(objects),"target objects.",flush=True)
    if args.publish: publish(objects)
    if args.verify_public: read_public(objects)
    if args.browser:browser_check()
