"""Isolated synthetic regression checks; no production evidence or reports read."""
from pathlib import Path
import collections, contextlib, copy, datetime as dt, gzip, hashlib, io, json, shutil, sys, tempfile
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
import verify, merge_retail, stage_reviewed, check_block_ranges, finalize_reviews, retail_quality_snapshot, digest, showcard, cited_titles
TEMP=tempfile.TemporaryDirectory(prefix='june-authoring-tools-')
FIX=Path(TEMP.name)
for folder in ['feeds','cards','exclusions','nonretail_drafts','retail_drafts','specs','audit','checks']:(FIX/folder).mkdir(parents=True)
verify.C=str(FIX)
for module in [digest,showcard,cited_titles]:module.C=str(FIX)
for module in [merge_retail,stage_reviewed,check_block_ranges,finalize_reviews]:module.ROOT=FIX
results=[]
def record(name,condition):
 assert condition,name
 results.append({'check':name,'pass':True})
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def canon(x):return merge_retail.digest(x)
def sha(p):return merge_retail.sha(p)
def letters(n):
 out=''
 while True:
  out=chr(65+n%26)+out;n=n//26-1
  if n<0:return out
counter=0
citations=0
def block(name,labels,words,key=None,stance=False,policy=False):
 global counter,citations
 pairs=[]
 for i,label in enumerate(labels):
  counter+=1;citations+=1
  count=words//len(labels)+(i<words%len(labels))
  tokens=['Fixture'+letters(counter)]+['analysis']*(count-1)
  pairs.append([label,' '.join(tokens)+f' [[n{(citations-1)%50+1:04d}]]'])
 b={'parts':pairs}
 if key:b['key']=key
 else:b['title']=name
 if stance:b['stance']='Mixed'
 if policy:b['label']='Synthetic fixture'
 return b
source_rows=[];card_hashes={};bindings={}
for j,d in enumerate(verify.DATES):
 counter=0;citations=0
 stamp=(dt.date.fromisoformat(d)-dt.timedelta(days=1)).isoformat()+'T12:00:00Z'
 items=[{'id':f'n{i:04d}','published_at':stamp,'cat':'news','src':'Synthetic fixture','title':'Synthetic fixture evidence '+letters(i),'topics':['fixture'],'url':f'https://fixture.invalid/{d}/{i}'} for i in range(1,51)]
 fp=FIX/'feeds'/f'{d}.json.gz';fp.write_bytes(gzip.compress(json.dumps({'date':d,'items':items}).encode(),mtime=0))
 prev=(dt.date.fromisoformat(d)-dt.timedelta(days=1)).isoformat()
 old=(dt.date.fromisoformat(d)-dt.timedelta(days=29)).isoformat()
 tr={'prior_close_date':prev,'obs20_earlier_date':old,'prior_5obs_date':old,
     'prior_close_pct':{'2y':'4.00%','10y':'4.50%'},'obs20_earlier_pct':{'2y':'4.50%','10y':'4.75%'},
     'spread_10y_2y_bps':50,'spread_10y_3m_bps':-50,'spread_30y_10y_bps':25,
     'chg_20obs_bps':{'2y':-50,'10y':-25,'spread':25,'3m':-10,'30y':-15},'chg_5obs_bps':{'2y':-10,'10y':-5},
     'curve_shape':'normal','curve_move_20obs':'bull steepening (both down, 2Y down more)'}
 card={'report_date':d,'cutoff_utc':d+'T00:00:00Z','label':'Synthetic fixture','treasury':tr,
       'markets':{'AAA':{'name':'Synthetic equity','currency':'JPY','session':prev,'close':'100.00',
                          'ref_1s_session':old,'ref_5s_session':old,'ref_20s_session':old,'ref_20s_close':'100.00',
                          'chg_1s_pct':0.0,'chg_5s_pct':0.0,'chg_20s_pct':0.0}}}
 cp=FIX/'cards'/f'{d}.json';save(cp,card)
 save(FIX/'exclusions'/f'{d}.json',{'date':d,'feed_sha256':sha(fp),'exclusions':[]})
 nr={'date':d,'geo':[],'sectors':[]}
 glabels=[['Macro Stance','Rates & Curve','New / Most Important','Playbook ✓'],['Macro Stance','Activity & Inflation','New / Most Important','Playbook ✓'],verify.CN_PARTS,['Macro Stance','Activity & Currency','Playbook ✓'],['Macro Stance','Demand & Financing','Playbook ✓'],verify.PL_PARTS]
 for key,labels,words in zip(verify.GEO,glabels,[440,300,875,310,250,950]):
  b=block('',labels,words,key,True,True)
  if key in {'CN','PL'}:
   b['parts'][-1][1]=b['parts'][-1][1].replace('analysis analysis','⚠ Divergence:',1)
  nr['geo'].append(b)
 for key in verify.SECT:nr['sectors'].append(block('',verify.LABELS['sector'],185,key,True))
 nr['earnings_pattern']=block('Synthetic earnings',verify.LABELS['earnings_pattern'],400)
 nr['underowned']=[block('Synthetic theme '+letters(i),verify.LABELS['underowned'],135) for i in range(4)]
 nr['crypto']=block('Synthetic crypto',verify.LABELS['crypto'],330)
 nr['flows']=block('Synthetic funding',verify.LABELS['flows'],700)
 nr['anticipatory']=[block('Synthetic scenario '+letters(i),verify.LABELS['anticipatory'],165) for i in range(4)]
 nr['catalysts']=[block('Synthetic single name '+letters(i),verify.LABELS['catalysts'],115,stance=True) for i in range(6)]
 retail={'date':d,'retail_intro':' '.join(['Synthetic']+['narrative']*19)+'.','retail':[]}
 for i in range(4):retail['retail'].append(block('Fixture / '+letters(j*4+i+100)+' — synthetic narrative',verify.LABELS['retail_lead' if i==0 else 'retail_small'],700 if i==0 else 180))
 np=FIX/'nonretail_drafts'/f'{d}.json';rp=FIX/'retail_drafts'/f'{d}.json';save(np,nr);save(rp,retail)
 base={'date':d,'status':'accepted','fatal_or_major_remaining':0,'feed_sha256':sha(fp),'card_sha256':sha(cp),'exclusions_sha256':sha(FIX/'exclusions'/f'{d}.json')}
 save(FIX/'audit'/f'independent_nonretail_{d}.json',{**base,'nonretail_content_sha256':canon(nr)})
 save(FIX/'audit'/f'independent_retail_{d}.json',{**base,'retail_draft_sha256':sha(rp)})
 ready_path=FIX/'audit'/f'news_ready_{d}.json'
 raw_hash=hashlib.sha256(('synthetic raw '+d).encode()).hexdigest()
 save(ready_path,{'date':d,'status':'ready','ready_sha256':sha(fp),'unreviewed_sha256':raw_hash,
                  'input_items':51,'ready_items':50,'excluded_items':1,'excluded':[{'id':'n9000','reason':'synthetic removed row'}]})
 source_rows.append({'date':d,'feed_sha256':sha(fp),'raw_sha256':raw_hash,'ready_receipt_sha256':sha(ready_path),
                     'raw_items':51,'ready_items':50,'excluded':1})
 bindings[ready_path.relative_to(FIX).as_posix()]=sha(ready_path)
 card_hashes[d]=sha(cp)
source={'passed':True,'errors':[],'dates':source_rows,'card_sha256':card_hashes,'input_bindings':bindings}
save(FIX/'audit/independent_source_review.json',source)
save(FIX/'audit/independent_market_review.json',{'passed':True,'status':'accepted','errors':[],'dates':verify.DATES,'card_sha256':card_hashes})
d=verify.DATES[0];nr=json.loads((FIX/'nonretail_drafts'/f'{d}.json').read_text());rt=json.loads((FIX/'retail_drafts'/f'{d}.json').read_text());spec={**nr,**{k:rt[k] for k in ['retail_intro','retail']}}
def checked(value=spec,**kw):return verify.verify(d,spec_override=value,**kw)
f,w,n,words=checked();record('valid complete synthetic report',not f and not w and n==50 and 9500<=words<=11000)
record('all 20 weekdays including June 19',len(verify.DATES)==20 and '2024-06-19' in verify.DATES and verify.DATES[0]=='2024-06-03' and verify.DATES[-1]=='2024-06-28')
record('August date rejected',bool(verify.verify('2024-08-01',spec_override=spec)[0]))
record('valid isolated nonretail draft',not checked(nr,nonretail=True)[0])
record('valid isolated retail draft',not checked(rt,retail_only=True)[0])
for name,mutation,code in [
 ('missing citation membership',lambda s:s['geo'][0]['parts'][0].__setitem__(1,s['geo'][0]['parts'][0][1]+' [[n9999]]'),'CITATION'),
 ('unresolved citation alias',lambda s:s['geo'][0]['parts'][0].__setitem__(1,s['geo'][0]['parts'][0][1]+' [[ALIAS]]'),'CITATION'),
 ('overused citation hard failure',lambda s:s['geo'][0]['parts'][0].__setitem__(1,s['geo'][0]['parts'][0][1]+' [[n0001]] [[n0001]]'),'maximum 4'),
 ('exact geography labels',lambda s:s['geo'][0]['parts'][1].__setitem__(0,'Wrong label'),'STRUCT'),
 ('required top-level keys',lambda s:s.__setitem__('unexpected','value'),'top-level'),
 ('hard body number provenance',lambda s:s['geo'][0]['parts'][0].__setitem__(1,s['geo'][0]['parts'][0][1]+' 987654321'),'not traceable'),
 ('numeric spot FX mark',lambda s:s['geo'][0]['parts'][0].__setitem__(1,s['geo'][0]['parts'][0][1]+' USD/JPY at 160.00.'),'spot-FX'),
 ('forbidden FX ticker',lambda s:s['geo'][0]['parts'][0].__setitem__(1,s['geo'][0]['parts'][0][1]+' USDJPY=X'),'spot-FX'),
 ('exact sector lower bound',lambda s:s['sectors'][0]['parts'][0].__setitem__(1,'short [[n0001]]'),'RANGE'),
 ('retail title hook length',lambda s:s['retail'][0].__setitem__('title','Fixture / AAA — one two three four five six seven eight nine'),'hook'),
]:
 value=copy.deepcopy(spec);mutation(value);record(name,any(code in message for message in checked(value)[0]))
value=copy.deepcopy(spec);value['geo'][0]['parts'][0][1]+=' A stronger yen can affect exporters. Synthetic shares closed at 100.00 JPY.'
record('ordinary nonnumeric FX direction and JPY equity price allowed',not checked(value)[0])
fp=FIX/'feeds'/f'{d}.json.gz';original_feed=fp.read_bytes();feed=json.loads(gzip.decompress(original_feed))
for name,edit,code in [('midnight actual rejected',lambda x:x.__setitem__('published_at',d+'T00:00:00Z'),'cutoff/window'),('stale news rejected',lambda x:x.__setitem__('published_at','2024-05-22T12:00:00Z'),'cutoff/window'),('narrow semantic window enforced',lambda x:x.update(cat='monthly',semantic_window_days=7,published_at='2024-05-22T12:00:00Z'),'cutoff/window')]:
 changed=copy.deepcopy(feed);edit(changed['items'][0]);fp.write_bytes(gzip.compress(json.dumps(changed).encode(),mtime=0));record(name,any(code in message for message in checked()[0]));fp.write_bytes(original_feed)
changed=copy.deepcopy(feed);changed['items'][1]['title']+=' 987654321';fp.write_bytes(gzip.compress(json.dumps(changed).encode(),mtime=0))
value=copy.deepcopy(spec);value['geo'][0]['parts'][0][1]+=' 987654321'
record('number supported only in another paragraph hard fails',any('same-paragraph support required' in message for message in checked(value)[0]))
fp.write_bytes(original_feed)
ep=FIX/'exclusions'/f'{d}.json';original_ex=ep.read_bytes();ex=json.loads(original_ex);ex['exclusions']=[{'id':'n0001','reason':'Synthetic semantic exclusion'}];save(ep,ex)
record('semantic exclusion hard failure',any('known premature/stale/ambiguous' in message for message in checked()[0]))
record('retail gate also excludes own-date semantic source',bool(retail_quality_snapshot.validate_evidence(d,{'parts':[['Narrative','fixture [[n0001]]']]},retail_quality_snapshot.load_feed(FIX,d))[0]))
ep.write_bytes(original_ex)
loose=FIX/'feeds'/f'{d}.json';save(loose,{'date':d,'items':[]})
try:verify.load_feed(d);ok=False
except ValueError:ok=True
record('conflicting loose source rejected',ok);loose.unlink()
def captured_main(module,args):
 old=sys.argv;sys.argv=[module.__name__+'.py',*args];out=io.StringIO()
 try:
  with contextlib.redirect_stdout(out):module.main()
 finally:sys.argv=old
 return out.getvalue()
changed=copy.deepcopy(feed);changed['items'][0]['title']='Synthetic '+('complete headline '*30)+'ENDMARKER';changed['items'][0]['src']='Synthetic '+('untruncated outlet '*8);changed['items'][0]['topics']=['first','fixture']
fp.write_bytes(gzip.compress(json.dumps(changed).encode(),mtime=0));ex=json.loads(original_ex);ex['feed_sha256']=sha(fp);save(ep,ex)
out=captured_main(digest,[d,'--topic','fixture','--max','1'])
record('digest includes secondary topic and full headline/outlet', 'n0001' in out and 'ENDMARKER' in out and changed['items'][0]['src'] in out)
out=captured_main(cited_titles,[d,'--nonretail'])
record('cited titles prints full exact own-date headline', 'ENDMARKER' in out and '50 distinct cited headlines' in out)
fp.write_bytes(original_feed);ep.write_bytes(original_ex)
cp=FIX/'cards'/f'{d}.json';original_cp=cp.read_bytes();card=json.loads(original_cp);card['markets']['USDJPY=X']={**card['markets']['AAA'],'name':'Forbidden FX fixture','close':'160.00'};save(cp,card)
out=captured_main(showcard,[d])
record('showcard uses own card and suppresses FX row', '100.00 JPY' in out and 'USDJPY=X' not in out and '160.00' not in out)
cp.write_bytes(original_cp)
with contextlib.redirect_stdout(io.StringIO()):code=stage_reviewed.main()
staged=json.loads((FIX/'checks/staged_reviewed.json').read_text());record('stage all20 current accepted components',code==0 and staged['all_20_ready'] and staged['ready_count']==20)
with contextlib.redirect_stdout(io.StringIO()):code=check_block_ranges.main()
ranges=json.loads((FIX/'checks/block_word_range_review.json').read_text());record('all720 exact block ranges',code==0 and ranges['total_blocks_checked']==720 and ranges['out_of_range_count']==0)
sp=FIX/'specs'/f'{d}.json';before=sp.read_bytes();np=FIX/'nonretail_drafts'/f'{d}.json';original_np=np.read_bytes();bad=copy.deepcopy(nr);bad['geo'][0]['parts'][0][1]+=' changed';save(np,bad)
try:merge_retail.merge(d);ok=False
except ValueError:ok=True
record('stale review prevents any spec write',ok and sp.read_bytes()==before)
rp=FIX/'audit'/f'independent_nonretail_{d}.json';original_rp=rp.read_bytes();bad['sectors'][0]['parts'][0][1]='short [[n0001]]';save(np,bad);review=json.loads(original_rp);review['nonretail_content_sha256']=canon(bad);save(rp,review)
try:merge_retail.merge(d);ok=False
except ValueError:ok=True
record('accepted hashes with invalid candidate still prevent spec write',ok and sp.read_bytes()==before)
np.write_bytes(original_np);rp.write_bytes(original_rp)
with contextlib.redirect_stdout(io.StringIO()):code=finalize_reviews.main()
record('complete20 final acceptance with current source hashes',code==0 and json.loads((FIX/'audit/final_editorial_review.json').read_text())['nonretail_blocks_checked']==720)
record('separate local June retail quality receipt', (FIX/'checks/retail_quality_june.json').is_file() and not (FIX/'checks/retail_quality.json').exists())
mp=FIX/'audit/independent_market_review.json';orig=mp.read_bytes();bad=json.loads(orig);bad['card_sha256'][d]='stale';save(mp,bad)
with contextlib.redirect_stdout(io.StringIO()):code=finalize_reviews.main()
record('stale market acceptance rejected at final binding',code==1);mp.write_bytes(orig)
# Current source schema failures are isolated in memory and rebound where needed.
current_source=json.loads((FIX/'audit/independent_source_review.json').read_text())
ready_path=FIX/'audit'/f'news_ready_{d}.json';ready_original=ready_path.read_bytes()
def rejects(name,action):
 try:action();ok=False
 except (ValueError,KeyError,TypeError,FileNotFoundError):ok=True
 record(name,ok)
def screened_reject(name,receipt_change=None,source_change=None,rebind=True):
 changed_source=copy.deepcopy(current_source)
 rows={row['date']:row for row in changed_source['dates']}
 try:
  if receipt_change:
   current=json.loads(ready_original);receipt_change(current);save(ready_path,current)
   if rebind:
    changed_source['input_bindings'][ready_path.relative_to(FIX).as_posix()]=sha(ready_path)
    rows[d]['ready_receipt_sha256']=sha(ready_path)
  if source_change:source_change(changed_source,rows)
  rejects(name,lambda:finalize_reviews.frozen_source_exclusions(changed_source,rows))
 finally:ready_path.write_bytes(ready_original)
ids,stable=finalize_reviews.frozen_source_exclusions(current_source,{row['date']:row for row in current_source['dates']})
record('current screening schema binds all20 real receipt byte hashes',len(stable)==20 and len(ids)==20 and all(ids[date]=={'n9000'} for date in verify.DATES))
screened_reject('missing current bindings cannot become empty exclusions',source_change=lambda s,r:s.pop('input_bindings'))
screened_reject('malformed input_bindings rejected',source_change=lambda s,r:s.__setitem__('input_bindings',[]))
screened_reject('missing screening binding rejected',source_change=lambda s,r:s['input_bindings'].pop(ready_path.relative_to(FIX).as_posix()))
screened_reject('stale accepted screening receipt hash rejected',source_change=lambda s,r:r[d].__setitem__('ready_receipt_sha256','stale'))
screened_reject('receipt byte edits require both current bindings',lambda r:r.__setitem__('audit_note','changed'),rebind=False)
screened_reject('wrong screening date rejected after rebind',lambda r:r.__setitem__('date',verify.DATES[1]))
screened_reject('pending screening state rejected after rebind',lambda r:r.__setitem__('status','pending'))
screened_reject('wrong ready feed hash rejected after rebind',lambda r:r.__setitem__('ready_sha256','stale'))
screened_reject('wrong raw feed hash rejected after rebind',lambda r:r.__setitem__('unreviewed_sha256','stale'))
screened_reject('missing excluded list rejected',lambda r:r.pop('excluded'))
screened_reject('object excluded payload rejected',lambda r:r.__setitem__('excluded',{}))
screened_reject('duplicate screened identity rejected',lambda r:r['excluded'].append(copy.deepcopy(r['excluded'][0])))
screened_reject('alias screened identity rejected',lambda r:r['excluded'][0].__setitem__('id','ALIAS'))
screened_reject('empty screened identity rejected',lambda r:r['excluded'][0].__setitem__('id',''))
screened_reject('boolean ready count rejected',lambda r:r.__setitem__('ready_items',True))
screened_reject('negative raw count rejected',lambda r:r.__setitem__('input_items',-1))
screened_reject('string excluded count rejected',lambda r:r.__setitem__('excluded_items','1'))
screened_reject('boolean accepted count rejected',source_change=lambda s,r:r[d].__setitem__('excluded',True))
screened_reject('negative accepted count rejected',source_change=lambda s,r:r[d].__setitem__('raw_items',-1))
screened_reject('accepted and receipt counts must match',source_change=lambda s,r:r[d].__setitem__('ready_items',49))
screened_reject('matching counts still must balance',lambda r:r.__setitem__('input_items',52),lambda s,r:r[d].__setitem__('raw_items',52))
screened_reject('matching excluded counts still equal actual removed rows',lambda r:r.__setitem__('excluded_items',2),lambda s,r:r[d].__setitem__('excluded',2))
def injected_legacy(source,rows):
 empty={day:{'feed_sha256':rows[day]['feed_sha256'],'exclusions':[]} for day in verify.DATES}
 source.update(known_semantic_exclusions={'by_date':empty},known_timing_exclusions={'by_date':empty})
screened_reject('injected legacy maps cannot override current screening exclusions',source_change=injected_legacy)
def legacy_without_bindings(source,rows):injected_legacy(source,rows);source.pop('input_bindings')
screened_reject('legacy maps cannot substitute missing current screening bindings',source_change=legacy_without_bindings)
# Canonical receipt keys and all three source-artifact bindings.
record('canonical nonretail digest is ordered UTF8 JSON with compact separators',canon(nr)==hashlib.sha256(json.dumps(nr,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest())
nreview_path=FIX/'audit'/f'independent_nonretail_{d}.json';nreview_bytes=nreview_path.read_bytes()
rreview_path=FIX/'audit'/f'independent_retail_{d}.json';rreview_bytes=rreview_path.read_bytes()
for name,path,original,change in [
 ('legacy nonretail field cannot substitute canonical content hash',nreview_path,nreview_bytes,lambda r:r.__setitem__('component_sha256',r.pop('nonretail_content_sha256'))),
 ('legacy retail field cannot substitute canonical draft hash',rreview_path,rreview_bytes,lambda r:r.__setitem__('draft_sha256',r.pop('retail_draft_sha256'))),
 ('stale nonretail exclusions binding rejected',nreview_path,nreview_bytes,lambda r:r.__setitem__('exclusions_sha256','stale')),
 ('missing retail exclusions binding rejected',rreview_path,rreview_bytes,lambda r:r.pop('exclusions_sha256')),
 ('boolean component zero is not accepted',nreview_path,nreview_bytes,lambda r:r.__setitem__('fatal_or_major_remaining',False)),
 ('missing nonretail status is not accepted',nreview_path,nreview_bytes,lambda r:r.pop('status')),
 ('missing retail status is not accepted',rreview_path,rreview_bytes,lambda r:r.pop('status')),
]:
 changed=json.loads(original);change(changed);save(path,changed)
 rejects(name,lambda:merge_retail.merge(d));record(name+' preserves staged spec',sp.read_bytes()==before)
 path.write_bytes(original)
exclusion_path=FIX/'exclusions'/f'{d}.json';exclusion_bytes=exclusion_path.read_bytes()
value=json.loads(exclusion_bytes);value.pop('feed_sha256');save(exclusion_path,value)
record('verifier rejects missing exclusions feed hash',any('Missing or stale source exclusions feed binding' in message for message in checked()[0]))
rejects('local retail gate rejects missing exclusions feed hash',lambda:retail_quality_snapshot.load_feed(FIX,d))
exclusion_path.write_bytes(exclusion_bytes)
# Raw warning diagnostic and specific, cited evidence are required.
warning='geo:US Macro Stance: calendar wording "next week" — needs a dated headline'
valid={'warning':warning,'evidence_ids':['n0001'],'rationale':'This synthetic dated preview supports the exact calendar phrase under review.'}
def warning_errors(decision):return finalize_reviews.reviewed_warnings([warning],[{'reviewed_validation_warnings':[decision]}],{'n0001'})[0]
record('exact raw warning receipt accepted',not warning_errors(valid))
for name,change in [
 ('message field cannot substitute warning key',lambda r:r.__setitem__('message',r.pop('warning'))),
 ('CLI WARN date prefix is not raw warning',lambda r:r.__setitem__('warning','WARN '+d+' '+warning)),
 ('short warning rationale rejected',lambda r:r.__setitem__('rationale','approved')),
 ('uncited warning evidence rejected',lambda r:r.__setitem__('evidence_ids',['n9999'])),
 ('empty warning evidence rejected',lambda r:r.__setitem__('evidence_ids',[])),
 ('string warning evidence rejected',lambda r:r.__setitem__('evidence_ids','n0001')),
 ('duplicate warning evidence rejected',lambda r:r.__setitem__('evidence_ids',['n0001','n0001'])),
 ('noncanonical warning evidence rejected',lambda r:r.__setitem__('evidence_ids',['ALIAS'])),
]:
 changed=copy.deepcopy(valid);change(changed);record(name,bool(warning_errors(changed)))
rejects('malformed warning decision array rejected',lambda:finalize_reviews.reviewed_warnings([warning],[{'reviewed_validation_warnings':{}}],{'n0001'}))
# FX direction and DXY remain available; numerical spot pairs do not.
for phrase in ['Dollar/yen at 100.00.','USDJPY rose 4.00%.','The yen fell 4.00%.']:
 value=copy.deepcopy(spec);value['geo'][0]['parts'][0][1]+=' '+phrase
 record('numeric spot FX lexical form rejected: '+phrase,any('spot-FX' in x for x in checked(value)[0]))
value=copy.deepcopy(spec);value['geo'][0]['parts'][0][1]+=' DXY closed at 100.00 index points; the yen remained under pressure.'
record('DXY index number and currency direction remain allowed',not checked(value)[0])
changed=copy.deepcopy(feed);changed['items'][1]['id']='ALIAS';fp.write_bytes(gzip.compress(json.dumps(changed).encode(),mtime=0))
rejects('noncanonical own-date feed identity rejected',lambda:verify.load_feed(d));fp.write_bytes(original_feed)
changed=copy.deepcopy(feed);changed['items'][1]['id']='n0001';fp.write_bytes(gzip.compress(json.dumps(changed).encode(),mtime=0))
rejects('duplicate own-date feed identity rejected',lambda:verify.load_feed(d));fp.write_bytes(original_feed)
value=copy.deepcopy(spec);value['geo'][0]['parts'][0][1]+=' [[ALIAS]]';save(sp,value)
try:captured_main(cited_titles,[d]);ok=False
except SystemExit as exc:ok=exc.code==1
record('cited titles fails unresolved aliases instead of silently omitting them',ok);sp.write_bytes(before)
# Retail persistence dispositions must cite real evidence and satisfy their scope.
flag={'code':'repeated_lead'}
current={'sources':[{'id':'n0001'}],'fresh_evidence_ids':['n0001'],'text':'Synthetic brief carryover','position':0}
decision={'disposition':'material_update','reviewer':'Synthetic independent reviewer','evidence_ids':['n0001'],
          'changed_angle':'The newly eligible synthetic source changes the catalyst being evaluated for this lead.'}
record('material repeat update accepts newly eligible cited evidence',not retail_quality_snapshot.validate_decision(flag,decision,current))
stale=copy.deepcopy(current);stale['fresh_evidence_ids']=[]
record('material repeat update rejects old evidence',bool(retail_quality_snapshot.validate_decision(flag,decision,stale)))
changed=copy.deepcopy(decision);changed['disposition']='reviewed_selection'
record('generic reviewed selection cannot clear repeated full lead',bool(retail_quality_snapshot.validate_decision(flag,changed,current)))
changed=copy.deepcopy(decision);changed['disposition']='brief_carryover'
record('brief carryover cannot clear full lead',bool(retail_quality_snapshot.validate_decision(flag,changed,current)))
secondary=copy.deepcopy(current);secondary['position']=1
record('brief secondary carryover with specific cited rationale accepted',not retail_quality_snapshot.validate_decision(flag,changed,secondary))
secondary['text']=' '.join(['synthetic']*161)
record('long secondary carryover rejected',bool(retail_quality_snapshot.validate_decision(flag,changed,secondary)))
changed=copy.deepcopy(decision);changed['evidence_ids']=['n9999']
record('retail update evidence must be cited in actual entry',bool(retail_quality_snapshot.validate_decision(flag,changed,current)))
changed=copy.deepcopy(decision);changed['changed_angle']='approved'
record('generic short retail repeat rationale rejected',bool(retail_quality_snapshot.validate_decision(flag,changed,current)))
record('retail evidence rejects noncanonical aliases',any(x['code']=='noncanonical_citation' for x in retail_quality_snapshot.validate_evidence(d,{'parts':[['Why Retail Is Here','Synthetic [[ALIAS]]']]},feed)[0]))
retail=retail_quality_snapshot.require_review(FIX)
record('local retail receipt binds all20 specs feeds cards exclusions',len(retail['spec_sha256'])==20 and all(set(hashes)=={'feed_sha256','card_sha256','exclusions_sha256'} for hashes in retail['source_sha256'].values()))
kept=sp.read_bytes();sp.unlink()
partial=retail_quality_snapshot.audit_month(FIX)
record('local retail gate rejects incomplete20 chronology',not partial['review_gate_passed'] and partial['scope_missing_dates']==[d]);sp.write_bytes(kept)
# Finalizer hard rejects every out-of-scope/missing date rather than shrinking its scope.
source_path=FIX/'audit/independent_source_review.json';source_bytes=source_path.read_bytes()
changed=json.loads(source_bytes);changed['dates'].pop();save(source_path,changed)
rejects('finalizer rejects missing source acceptance date',finalize_reviews.main);source_path.write_bytes(source_bytes)
market_path=FIX/'audit/independent_market_review.json';market_bytes=market_path.read_bytes()
changed=json.loads(market_bytes);changed['dates'][-1]='2024-07-01';save(market_path,changed)
rejects('finalizer rejects out-of-scope market acceptance date',finalize_reviews.main);market_path.write_bytes(market_bytes)
with contextlib.redirect_stdout(io.StringIO()):code=finalize_reviews.main()
record('all20 current-schema finalizer still passes after adversarial inputs restored',code==0)

summary={'purpose':'Synthetic toolkit regression; no financial report authoring or production source reads.','checks':results,'passed':len(results),'failed':0,'dates':len(verify.DATES),'nonretail_blocks':720}
summary['fixture_scope']='Temporary synthetic inputs only, automatically removed; no factual reports read.'
summary['tool_sha256']={name:sha(ROOT/'tools'/name) for name in ['verify.py','digest.py','showcard.py','cited_titles.py','check_block_ranges.py','merge_retail.py','stage_reviewed.py','finalize_reviews.py','retail_quality_snapshot.py']}
save(ROOT/'audit_work/authoring_tools_regression.json',summary)
TEMP.cleanup()
print(json.dumps({'passed':len(results),'failed':0,'temporary_fixture_removed':not FIX.exists(),'production_evidence_read':False},indent=2))
