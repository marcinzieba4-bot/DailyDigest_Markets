"""Independent fixed-scope release-boundary and reproduced-escape regressions.

Titles here are synthetic controls, not evidence or narrative report facts.
"""
from pathlib import Path
import datetime as dt,gzip,hashlib,json,sys
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tools'));import ready_feeds as p
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
initial={'release_schedule_sha256':sha(p.SCHEDULE_PATH),'screening_tool_sha256':sha(R/'tools/ready_feeds.py'),'named_exclusions_sha256':sha(p.NAMED_PATH)}
CASES=[
('Tankan before July1 cutoff','Japan Tankan confidence rises','2024-06-30','2024-07-01',False),
('Manufacturing PMI after July1 cutoff','Japan June final manufacturing PMI rises','2024-06-30','2024-07-01',True),
('Manufacturing PMI next cutoff','Japan June final manufacturing PMI rises','2024-07-01','2024-07-02',False),
('Services PMI after July3 cutoff','Japan June final services PMI falls','2024-07-02','2024-07-03',True),
('Services PMI next cutoff','Japan June final services PMI falls','2024-07-03','2024-07-04',False),
('Flash PMI after July24 cutoff','Japan July flash PMI falls','2024-07-23','2024-07-24',True),
('Flash PMI next cutoff','Japan July flash PMI falls','2024-07-24','2024-07-25',False),
('Wages before July8 cutoff','Japan May wages rise','2024-07-07','2024-07-08',False),
('GUS wages before release day','Poland June wages rise, GUS says','2024-07-17','2024-07-18',True),
('GUS wages next cutoff','Poland June wages rise, GUS says','2024-07-18','2024-07-19',False),
('GUS output before release day','GUS: Produkcja przemysłowa w czerwcu wzrosła','2024-07-17','2024-07-18',True),
('GUS output next cutoff','GUS: Produkcja przemysłowa w czerwcu wzrosła','2024-07-18','2024-07-19',False),
('GUS retail before release day','GUS: Sprzedaż detaliczna w czerwcu wzrosła','2024-07-19','2024-07-22',True),
('GUS retail next cutoff','GUS: Sprzedaż detaliczna w czerwcu wzrosła','2024-07-22','2024-07-23',False),
('GUS unemployment before release day','GUS podał dane o bezrobociu w czerwcu','2024-07-22','2024-07-23',True),
('GUS unemployment next cutoff','GUS podał dane o bezrobociu w czerwcu','2024-07-23','2024-07-24',False),
('GUS forecast remains a forecast','GUS: prognoza sprzedaży detalicznej w czerwcu','2024-07-19','2024-07-22',False),
('Exit-poll outcome before publication','Labour exit poll forecasts landslide','2024-07-03','2024-07-04',True),
('Exit-poll projection eligible July5','Labour exit poll forecasts landslide','2024-07-04','2024-07-05',False),
('Exit-poll preview preserved','UK exit poll preview: what to expect','2024-07-03','2024-07-04',False),
('UK named PM actual mixed with projection','UK exit poll forecasts Labour landslide; Starmer is named prime minister','2024-07-04','2024-07-05',True),
('UK concession actual mixed with projection','UK exit poll projects Labour landslide as Sunak concedes defeat','2024-07-04','2024-07-05',True),
('UK sworn-in actual mixed with projection','UK exit poll projects Labour landslide, Starmer sworn in as prime minister','2024-07-04','2024-07-05',True),
('UK actual becomes with intervening country','UK exit poll predicts Labour landslide; Starmer becomes Britain’s prime minister','2024-07-04','2024-07-05',True),
('UK actual concession with election noun','UK exit poll projects Labour landslide after Sunak concedes the election','2024-07-04','2024-07-05',True),
('UK Downing Street actual with projection','UK exit poll projects Labour landslide; Starmer enters Downing Street','2024-07-04','2024-07-05',True),
('Meta top estimates actual','Meta earnings top estimates on advertising strength','2024-07-30','2024-07-31',True),
('Meta soars doubles actual','Meta profit soars as advertising revenue doubles','2024-07-30','2024-07-31',True),
('Microsoft Q4 disappoints actual','Microsoft Q4 earnings: Azure growth disappoints','2024-07-29','2024-07-30',True),
('ASML Q2 top forecasts actual','ASML Q2 earnings top forecasts','2024-07-16','2024-07-17',True),
('Meta surprise actual','Meta earnings surprise Wall Street','2024-07-30','2024-07-31',True),
('Meta neutralised comparison actual','Meta earnings were better than expected','2024-07-30','2024-07-31',True),
('Meta preview preserved','Meta earnings preview: what to expect','2024-07-30','2024-07-31',False),
('ASML pre-result price move preserved','ASML shares rise ahead of earnings','2024-07-16','2024-07-17',False),
('ASML completed result next cutoff','ASML Q2 earnings top forecasts','2024-07-17','2024-07-18',False),
('Microsoft postclose result before its day cutoff','Microsoft reports quarterly earnings beat','2024-07-29','2024-07-30',True),
('Microsoft postclose result next cutoff','Microsoft reports quarterly earnings beat','2024-07-30','2024-07-31',False),
('AMD postclose result next cutoff','AMD reports earnings beat','2024-07-30','2024-07-31',False),
('TSMC revenue before July10 release','TSMC Q2 revenue beats estimates','2024-07-09','2024-07-10',True),
('TSMC revenue known July11','TSMC Q2 revenue beats estimates','2024-07-10','2024-07-11',False),
('TSMC full profit pending July18','TSMC Q2 profit beats estimates','2024-07-17','2024-07-18',True),
('TSMC full profit known July19','TSMC Q2 profit beats estimates','2024-07-18','2024-07-19',False),
('SK hynix premature actual July24','SK hynix reports Q2 profit','2024-07-23','2024-07-24',True),
('SK hynix early-local actual July25','SK hynix reports Q2 profit','2024-07-24','2024-07-25',False),
('SK hynix preview preserved','SK hynix earnings preview: what to expect','2024-07-23','2024-07-24',False),
('Samsung full result uncertain clock omitted','Samsung second-quarter results top estimates','2024-07-30','2024-07-31',True),
('Samsung unrelated product news preserved','Samsung unveils Galaxy AI tools','2024-07-04','2024-07-05',False),
('Fed July31 completed decision unavailable','Fed holds rates unchanged, September cut could follow','2024-07-30','2024-07-31',True),
('Fed July31 preview preserved','Fed expected to hold rates; stocks rise ahead of decision','2024-07-30','2024-07-31',False),
]
rows=[]
for name,title,pub,date,expected in CASES:
 hit=p.guard_hit(title,pub,date);rows.append({'case':name,'synthetic_title':title,'published_date':pub,'edition':date,'expected_excluded':expected,'actual_guard':hit,'pass':bool(hit)==expected})
recommendations=json.loads((Path(__file__).with_name('named_omission_recommendations.json')).read_text())['exclusions']
named_checks=[]
for rec in recommendations:
 date=rec['date'];raw_path=R/rec['unreviewed_path'];raw=json.load(gzip.open(raw_path,'rt'))
 target=next(x for x in raw['items']if x['id']==rec['id'])
 identity=all(target[key]==rec[key]for key in ['id','title','url','published_at'])
 result=p.screen(dt.date.fromisoformat(date),raw=raw,persist=False)
 ready_ids={x['id']for x in result['_payload']['items']};excluded={x['id']:x for x in result['excluded']}
 named_checks.append({'date':date,'id':rec['id'],'raw_identity_matches_recommendation':identity,'unreviewed_sha256':sha(raw_path),'excluded_by_current_screen':rec['id']not in ready_ids and rec['id']in excluded,'guard':excluded.get(rec['id'],{}).get('guard'),'pass':identity and rec['id']not in ready_ids and rec['id']in excluded})
focus=json.loads(Path(__file__).with_name('focused_staged_headline_scan.json').read_text())
observed=[]
for needle in ['Await Earnings for Clarity','The \'great rotation\' faces its biggest test yet','Microsoft’s earnings report will offer','TSMC second-quarter profit seen jumping']:
 hits=[x for x in focus['headlines']if needle in x['title']];assert len(hits)==1
 x=hits[0];first=x['appearances'][0];hit=p.guard_hit(x['title'],x['published_at'][:10],first['date'])
 observed.append({'case':'Observed pending preview preserved','title':x['title'],'date':first['date'],'id':first['id'],'url':x['url'],'actual_guard':hit,'pass':hit is None})
owner_path=R/'audit_work/july_guard_regressions.json';owner=json.loads(owner_path.read_text());owner_replay=[]
for x in owner['results']:
 hit=p.guard_hit(x['title'],x['published_date'],x['edition'])
 owner_replay.append({'title':x['title'],'published_date':x['published_date'],'edition':x['edition'],'expected_excluded':x['expected_excluded'],'actual_guard':hit,'pass':bool(hit)==x['expected_excluded']})
final={'release_schedule_sha256':sha(p.SCHEDULE_PATH),'screening_tool_sha256':sha(R/'tools/ready_feeds.py'),'named_exclusions_sha256':sha(p.NAMED_PATH)}
if initial!=final:raise RuntimeError('Policy changed during independent test; rerun against stable inputs')
obj={'purpose':'Independent fixed-scope synthetic release-boundary tests and exact actual-record omission checks; no authoring acceptance.',**final,'cases':rows,'named_record_checks':named_checks,'observed_preview_controls':observed,'owner_regression_replay':{'source_path':str(owner_path.relative_to(R)),'source_sha256':sha(owner_path),'cases':owner_replay,'case_count':len(owner_replay)},'failures':[x for x in rows+named_checks+observed+owner_replay if not x['pass']],'case_count':len(rows),'passed':all(x['pass']for x in rows+named_checks+observed+owner_replay)}
Path(__file__).with_name('independent_guard_cases.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'synthetic_cases':len(rows),'named_records':len(named_checks),'observed_preview_controls':len(observed),'owner_regressions_replayed':len(owner_replay),'passed':obj['passed'],'failures':obj['failures']},ensure_ascii=False,indent=2))
