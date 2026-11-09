import sys,pathlib,json,hashlib,datetime,copy
ROOT=pathlib.Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT/'tools'));import verify
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
checks={
'2024-07-09':[
'Read intro, all13 prose paragraphs, all9 exact cited headlines/times/categories, own BA/BTC numeric fields and selection notes; all sources July8 before July9 cutoff.',
'GLW guidance increase and generative-AI connection explicitly supported by Investopedia; investor-accessible mover/comparison coverage supports attention interpretation without fabricated social counts, GLW quote or buying flows.',
'Paramount has an agreed merger, not completed integration. Deadline5% is attributed headline reaction; Barrons shareholder criticism remains opinion. Material change from prior negotiation lead justifies secondary reuse.',
'Boeing DoD plea-impact talks remain unresolved source-reported talks; FAA inspections are separate operational risk, without quantified loss. BA185.84USD/+0.55% are July8 own-card fields.',
'BTC German-government approximately2bUSD holding is CNBC-reported anxiety, not all-sold claim.56705.10USD/+1.53%daily/-5.76%five observations correctly use completedUTCJuly8. No invented liquidation total.',
'General supplier-rerating analogy, hypothetical professional valuation discipline and falsifiable risks add analysis without unsupported historical episodes, named positions or forecasts.'
],
'2024-07-10':[
'Read intro, all13 paragraphs, all9 full cited headlines/times/categories, TSLA/AAPL/BIDU own fields and chronological selection notes. Sources July4/5/9 remain within seven-day window.',
'Tesla262.33USD/+3.71%session/+25.00%five sessions are July9 own-card values. UtilityDive explicitly supplies9.4GWh quarterly deployment record; deployments are kept distinct from revenue/profit.',
'Investopedia/NYT US EV share below50% remains competition evidence, not profitability claim. Forbes high-for-year coverage and Yahoo surge analysis supply actual attention channels without fabricated retail purchases.',
'Tesla repeat lead advances July3 delivery relief and July5 eligibility story using newly eligible energy record plus new market-share contradiction; it does not repeat prior essay with changed prices.',
'Nike executive return is an action to mend partnerships, not completed turnaround. Adidas set-to-benefit wording preserves expectation stage. Apple13%AppStore rise is explicitly a seen/expected metric, not reported actual result.',
'AAPL228.68USD/+5.50%five/+16.15%twenty and BIDU USADR95.40USD/+8.47%session match July9 card; patent-ranking CNBC July4 claim is not attributed as cause of latest BIDU rally or proof of commercial profit.',
'General multi-business analogy and hypothetical valuation discipline contain no invented institutions, posts, targets or later outcome.'
],
'2024-07-11':[
'Read intro, all13 paragraphs, all11 full cited headlines/times/categories, all TSM/PLTR/BTC/TSLA numeric claims and notes. Cited July10 publications precede July11 cutoff.',
'TSM40%YoY quarterly revenue growth is exact Investopedia headline; SCMP supports demand/revenue connection. Reuters Taiwan share peak/trillion-dollar valuation remains distinct from USADR191.05USD/+3.54%session/+13.61%twentyJuly10 fields.',
'Barrons panic-rotation phrase remains attributed attention language, not measured retail flows. MotleyFool stock-choice coverage supplies attention channel; supplier confirmation/extrapolation analogy asserts no unsupported historical episode.',
'TSM possible10%wafer pricing increase for2025 is explicitly possible/report-based, not implemented price or profit forecast.',
'Oracle/Palantir partnership is current eligible headline, with no invented sales/bookings/margins. PLTR28.42USD/+3.76%session/+22.87%twenty match July10card; CMC feature is attention without ownership inference.',
'Reuters scheduled TrumpJuly27 conference appearance supports exact future date, not policy commitment. BTC57742.50USD/-0.46%completedUTCJuly10 fields match card.',
'BillGross new-meme-stock framing and MorganStanley storage bullishness stay attributed assessments. TSLA263.26USD/+0.35%July10 regular close correct. Secondary advances prior energy lead with fresh specific characterization and named analyst view.',
'No numericspotFX, later result, invented social counts/flows/positions/targets or original-article-body claim introduced.'
]}
for date,claims in checks.items():
 p=ROOT/'retail_drafts'/f'{date}.json';draft=json.loads(p.read_text());fixes=[]
 if date=='2024-07-10':
  prior=copy.deepcopy(draft);loc=draft['retail'][0]['parts'][4];sentence=' Neither view requires an invented claim about institutional buying.';assert sentence in loc[1];loc[1]=loc[1].replace(sentence,'');hist=ROOT/'audit/review_history'/f'retail_{date}_before_root_style_fix.json';hist.write_bytes(p.read_bytes());p.write_text(json.dumps(draft,ensure_ascii=False,indent=2)+'\n');assert all(prior[k]==draft[k] for k in prior if k!='retail');fixes=[{'location':'lead/Smart Money View','change':'Removed author-process aside; operating competition, valuation argument and sources unchanged.'}]
 # Use CLI equivalent explicitly on the current component scope.
 import subprocess,re
 run=subprocess.run([sys.executable,str(ROOT/'tools/verify.py'),date,'--retail'],capture_output=True,text=True);assert run.returncode==0,run.stdout+run.stderr
 m=re.search(r'PASS — (\d+) sources, (\d+) words, (\d+) fail, (\d+) warn',run.stdout);assert m and m[3]=='0' and m[4]=='0',run.stdout
 feed=verify.load_feed(date);ids=list(dict.fromkeys(verify.CITE.findall(json.dumps(draft,ensure_ascii=False))));notes=json.loads((ROOT/'notes'/f'retail_{date}.json').read_text());assert notes['lead']==draft['retail'][0]['title'];assert notes['smaller']==[x['title'] for x in draft['retail'][1:]]
 rec={'date':date,'status':'accepted','reviewer':'root, independent of original retail author','checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'retail_draft_sha256':sha(p),'feed_sha256':sha(ROOT/'feeds'/f'{date}.json.gz'),'card_sha256':sha(ROOT/'cards'/f'{date}.json'),'fatal_or_major_remaining':0,'paragraphs_reviewed':13,'distinct_cited_headlines_reviewed':ids,'findings':[],'fixes':fixes,'claim_checks':claims,'chronology':{'earlier_notes_reviewed':[x for x in verify.DATES if x<date],'material_change':notes['why_lead'],'notes_match_current_selection':True},'verification':{'passed':True,'body_words':int(m[2]),'sources':int(m[1]),'failures':0,'warnings':0},'limitations':['AI headline/card review; exact original article-body vintages not independently certified.','Crowd motives and lead importance are editorial interpretations, not measured popularity rankings.']}
 (ROOT/'audit'/f'independent_retail_{date}.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n');print(date,'accepted',m[2],'words',len(ids),'sources')
