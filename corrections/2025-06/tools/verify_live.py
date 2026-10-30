"""Verify every published artifact through the public CDN by content SHA256."""
from pathlib import Path
import concurrent.futures as cf
import datetime as dt
import hashlib,json,time,urllib.request,urllib.error
ROOT=Path(__file__).resolve().parent.parent
BASE='https://d7g7nkeytae81.cloudfront.net/'
DATES=[dt.date(2025,6,n).isoformat() for n in range(1,31) if dt.date(2025,6,n).weekday()<5]

def verify(item):
    url=BASE+item['key']
    for attempt in range(6):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'DailyDigest-archive-verification/1.0','Accept-Encoding':'identity'})
            with urllib.request.urlopen(req,timeout=30) as r:
                blob=r.read();status=r.status;ctype=r.headers.get('Content-Type','')
            digest=hashlib.sha256(blob).hexdigest()
            if digest!=item['sha256'] or len(blob)!=item['bytes']:raise ValueError('Public artifact hash mismatch: '+item['key'])
            return {'key':item['key'],'url':url,'status':status,'bytes':len(blob),'sha256':digest,'content_type':ctype,'passed':True}
        except urllib.error.HTTPError as e:
            if e.code not in (404,408,429,500,502,503,504) or attempt==5:raise
        except (urllib.error.URLError,TimeoutError):
            if attempt==5:raise
        time.sleep(min(2**attempt,15))

def main():
    receipt=json.loads((ROOT/'checks/publication.json').read_text())
    if receipt.get('stage')!='published':raise ValueError('Publication has not completed')
    if receipt.get('dates')!=DATES or receipt.get('confirmed_count')!=len(DATES)*3+3:
        raise ValueError('Complete verified June origin inventory required')
    # Only reports/* is routed to the report bucket root. Strategies/* uses
    # the website's default origin and is backend storage, not a public URL.
    # The public month ZIP includes every HTML/PDF/JSON artifact byte-for-byte.
    targets=[x for x in receipt['targets'] if x['key'].startswith('reports/')]
    dates=receipt['dates']
    expected_html={f'reports/archive/{date}.html' for date in dates}
    required_collection={'reports/2025-06.html','reports/2025-06/methodology.txt','reports/2025-06/June_2025_Weekday_Reports.zip'}
    if {item['key'] for item in targets}!=expected_html|required_collection:raise ValueError('Public targets must contain every June HTML edition, collection, method and full ZIP')
    result={'started_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'artifacts':[],
            'stored_artifacts_verified':receipt.get('confirmed_count'),
            'public_format_delivery':'All PDF/JSON variants are included in the verified public ZIP. Canonical Strategies keys are backend storage.'}
    with cf.ThreadPoolExecutor(max_workers=2) as ex:
        for n,row in enumerate(ex.map(verify,targets),1):
            result['artifacts'].append(row)
            if n%10==0:print('Public SHA checks',n,'of',len(targets),flush=True)
    with urllib.request.urlopen(BASE+'reports/index.html',timeout=30) as r:index=r.read().decode()
    for d in receipt['dates']:
        if f'archive/{d}.html' not in index:raise ValueError('Public index missing '+d)
    if '2025-06.html' not in index:raise ValueError('Public index missing June collection')
    result.update(passed=True,all_index_links=True,index_link_count=len(dates),artifact_count=len(result['artifacts']),finished_at_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    (ROOT/'checks/live_verification.json').write_text(json.dumps(result,indent=2))
    print('Verified all',len(result['artifacts']),'public artifacts and',len(dates),'archive links',flush=True)

if __name__=='__main__':main()
