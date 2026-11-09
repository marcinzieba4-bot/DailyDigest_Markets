"""Isolated synthetic regression checks; no production evidence or reports read."""
from pathlib import Path
import collections, contextlib, copy, datetime as dt, gzip, hashlib, io, json, shutil, sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
import verify, merge_retail, stage_reviewed, check_block_ranges, finalize_reviews, retail_quality_snapshot, digest, showcard, cited_titles
FIX=ROOT/'engineering_scratch/fixtures'
if FIX.exists():shutil.rmtree(FIX)
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
source_rows=[];card_hashes={};bydate={}
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
 base={'date':d,'status':'accepted','fatal_or_major_remaining':0,'feed_sha256':sha(fp),'card_sha256':sha(cp)}
 save(FIX/'audit'/f'independent_nonretail_{d}.json',{**base,'nonretail_content_sha256':canon(nr)})
 save(FIX/'audit'/f'independent_retail_{d}.json',{**base,'retail_draft_sha256':sha(rp)})
 source_rows.append({'date':d,'feed_sha256':sha(fp)})
 card_hashes[d]=sha(cp);bydate[d]={'feed_sha256':sha(fp),'exclusions':[]}
source={'passed':True,'dates':source_rows,'card_sha256':card_hashes,'known_semantic_exclusions':{'by_date':bydate},'known_timing_exclusions':{'by_date':bydate}}
save(FIX/'audit/independent_source_review.json',source)
save(FIX/'audit/independent_market_review.json',{'passed':True,'status':'accepted','errors':[],'dates':verify.DATES,'card_sha256':card_hashes})
d=verify.DATES[0];nr=json.loads((FIX/'nonretail_drafts'/f'{d}.json').read_text());rt=json.loads((FIX/'retail_drafts'/f'{d}.json').read_text());spec={**nr,**{k:rt[k] for k in ['retail_intro','retail']}}
def checked(value=spec,**kw):return verify.verify(d,spec_override=value,**kw)
f,w,n,words=checked();record('valid complete synthetic report',not f and not w and n==50 and 9500<=words<=11000)
record('all 23 weekdays including July 4 and July 5',len(verify.DATES)==23 and '2024-07-04' in verify.DATES and '2024-07-05' in verify.DATES)
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
fp=FIX/'feeds'/f'{d}.json.gz';original=fp.read_bytes();feed=json.loads(gzip.decompress(original))
for name,edit,code in [('midnight actual rejected',lambda x:x.__setitem__('published_at',d+'T00:00:00Z'),'cutoff/window'),('stale news rejected',lambda x:x.__setitem__('published_at','2024-06-22T12:00:00Z'),'cutoff/window'),('narrow semantic window enforced',lambda x:x.update(cat='monthly',semantic_window_days=7,published_at='2024-06-22T12:00:00Z'),'cutoff/window')]:
 changed=copy.deepcopy(feed);edit(changed['items'][0]);fp.write_bytes(gzip.compress(json.dumps(changed).encode(),mtime=0));record(name,any(code in message for message in checked()[0]));fp.write_bytes(original)
changed=copy.deepcopy(feed);changed['items'][1]['title']+=' 987654321';fp.write_bytes(gzip.compress(json.dumps(changed).encode(),mtime=0))
value=copy.deepcopy(spec);value['geo'][0]['parts'][0][1]+=' 987654321'
record('number supported only in another paragraph hard fails',any('same-paragraph support required' in message for message in checked(value)[0]))
fp.write_bytes(original)
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
fp.write_bytes(original);ep.write_bytes(original_ex)
cp=FIX/'cards'/f'{d}.json';original_cp=cp.read_bytes();card=json.loads(original_cp);card['markets']['USDJPY=X']={**card['markets']['AAA'],'name':'Forbidden FX fixture','close':'160.00'};save(cp,card)
out=captured_main(showcard,[d])
record('showcard uses own card and suppresses FX row', '100.00 JPY' in out and 'USDJPY=X' not in out and '160.00' not in out)
cp.write_bytes(original_cp)
with contextlib.redirect_stdout(io.StringIO()):code=stage_reviewed.main()
staged=json.loads((FIX/'checks/staged_reviewed.json').read_text());record('stage all23 current accepted components',code==0 and staged['all_23_ready'] and staged['ready_count']==23)
with contextlib.redirect_stdout(io.StringIO()):code=check_block_ranges.main()
ranges=json.loads((FIX/'checks/block_word_range_review.json').read_text());record('all828 exact block ranges',code==0 and ranges['total_blocks_checked']==828 and ranges['out_of_range_count']==0)
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
record('complete23 final acceptance with current source hashes',code==0 and json.loads((FIX/'audit/final_editorial_review.json').read_text())['nonretail_blocks_checked']==828)
record('separate local July retail quality receipt', (FIX/'checks/retail_quality_july.json').is_file() and not (FIX/'checks/retail_quality.json').exists())
mp=FIX/'audit/independent_market_review.json';orig=mp.read_bytes();bad=json.loads(orig);bad['card_sha256'][d]='stale';save(mp,bad)
with contextlib.redirect_stdout(io.StringIO()):code=finalize_reviews.main()
record('stale market acceptance rejected at final binding',code==1);mp.write_bytes(orig)
summary={'purpose':'Synthetic toolkit regression; no financial report authoring or production source reads.','checks':results,'passed':len(results),'failed':0,'dates':len(verify.DATES),'nonretail_blocks':828}
save(ROOT/'engineering_scratch/toolkit_regression.json',summary)
print(json.dumps({'passed':len(results),'failed':0,'fixtures':str(FIX),'production_evidence_read':False},indent=2))
