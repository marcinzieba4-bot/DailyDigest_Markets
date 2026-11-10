"""Independent exact-code in-memory publication fixtures; no real network/write."""
import ast,contextlib,datetime as dt,hashlib,importlib.util,io,json,os,pathlib,sys,types,urllib.request
from unittest.mock import patch
from bs4 import BeautifulSoup
R=pathlib.Path('/workspace/work/april2024')
P=R/'tools/publish.py';V=R/'tools/verify_delivery.py'
def sha(b):return hashlib.sha256(b).hexdigest()
a=importlib.util.spec_from_file_location('independent_pub_final',P);pub=importlib.util.module_from_spec(a);a.loader.exec_module(pub)
checks={}
def checked(name,value):
 if not value:raise AssertionError(name)
 checks[name]=True
expected_dates=[dt.date(2024,4,n).isoformat()for n in range(1,31)if dt.date(2024,4,n).weekday()<5]
checked('22_exact_weekday_dates',pub.DATES==expected_dates and len(pub.DATES)==22)
keys=pub.protected_keys();checked('protected_snapshot_unique',len(keys)==len(set(keys))==198)
checked('april_weekend_native_keys_protected',len([k for k in keys if '2024-04-'in k])==24)
fixture=b'<html><nav><ul id="navigation"><li><a href="/">Home</a></li></ul></nav><main><ul id="archive"><li><a href="archive/2024-06-03.html">June</a></li></ul></main></html>'
merged=pub.merge_index(fixture);soup=BeautifulSoup(merged,'html.parser')
checked('nav_before_archive_correct_container',len(soup.select('#archive a[href^="archive/2024-04-"]'))==22 and not soup.select('#navigation a[href^="archive/2024-04-"]'))
checked('prior_hrefs_preserved',bool(soup.find('a',href='/'))and bool(soup.find('a',href='archive/2024-06-03.html')))
checked('merge_idempotent',pub.merge_index(merged)==merged)
for name,blob in [('ambiguous_archive_rejected',b'<ul><li><a href="archive/2024-06-03.html">June</a></li></ul><ul><li><a href="archive/2024-07-01.html">July</a></li></ul>'),('missing_archive_rejected',b'<ul><li><a href="/">Home</a></li></ul>')]:
 try:pub.merge_index(blob)
 except ValueError:checked(name,True)
 else:raise AssertionError(name)
class VirtualPath:
 def __init__(self,map,key=''):self.map=map;self.key=key
 def __truediv__(self,name):return VirtualPath(self.map,(self.key+'/'+str(name)).lstrip('/'))
 def read_bytes(self):return self.map[self.key]
 def exists(self):return self.key in self.map
review={'status':'accepted','passed':True,'fatal_or_major_remaining':0,'tool_sha256':{n:sha((R/'tools'/n).read_bytes())for n in ['publish.py','verify_delivery.py']}}
virtual={'tools/publish.py':P.read_bytes(),'tools/verify_delivery.py':V.read_bytes(),str(pub.PUBLICATION_REVIEW):json.dumps(review).encode()}
with patch.object(pub,'ROOT',VirtualPath(virtual)):
 checked('exact_engineering_gate_accepts',pub.require_publication_engineering_review()==sha(virtual[str(pub.PUBLICATION_REVIEW)]))
 for name,change in [('gate_rejects_status',{'status':'draft'}),('gate_rejects_passed',{'passed':False}),('gate_rejects_boolean_remaining',{'fatal_or_major_remaining':False}),('gate_rejects_stale_tools',{'tool_sha256':{'publish.py':'0'*64,'verify_delivery.py':review['tool_sha256']['verify_delivery.py']}})]:
  bad={**review,**change};virtual[str(pub.PUBLICATION_REVIEW)]=json.dumps(bad).encode()
  try:pub.require_publication_engineering_review()
  except ValueError:checked(name,True)
  else:raise AssertionError(name)
bindings={n:sha((R/n).read_bytes())for n in ['source/lambda_function.py','code_provenance.json']}
baseline=pub.deployment_baseline({'input_bindings':bindings})
checked('accepted_provenance_baseline',baseline['code_provenance_sha256']==bindings['code_provenance.json'] and baseline['retained_source_sha256']==bindings['source/lambda_function.py'])
bad={'input_bindings':{**bindings,'code_provenance.json':'0'*64}}
try:pub.deployment_baseline(bad)
except ValueError:checked('provenance_binding_change_rejected',True)
else:raise AssertionError('provenance_binding_change_rejected')
expected_paths=['/reports/index.html','/reports/archive/2024-04-*','/reports/2024-04*','/Strategies/json/2024-04-*','/Strategies/2024-04-*']
def main_fixture(blob,existing=False):
 store={'reports/index.html':fixture};writes=[];invalidations=[];clients=[]
 item={'path':'artifact.html','key':'reports/archive/2024-04-01.html','bytes':len(b'accepted-plan'),'sha256':sha(b'accepted-plan'),'content_type':'text/html'}
 if existing:store[item['key']]=b'existing'
 class BodyPath:
  def exists(self):return False
  def read_bytes(self):return blob
 class Root:
  def __truediv__(self,name):return BodyPath()
 class S3:
  def put_object(self,**k):
   checked('all_origin_writes_correct_bucket',k['Bucket']==pub.BUCKET)
   if k['Key']=='reports/index.html':checked('index_write_compare_and_swap',k.get('IfMatch')=='"fixture-etag"')
   else:checked('new_object_write_if_absent',k.get('IfNoneMatch')=='*' and k['Key']not in store)
   store[k['Key']]=k['Body'];writes.append(k)
 class CF:
  def create_invalidation(self,**k):
   invalidations.append(k)
   return {'Invalidation':{'Id':'fixture','Status':'InProgress'}}
 class Session:
  def client(self,name,**kwargs):clients.append(name);return S3()if name=='s3'else CF()
 def read(s3,key):
  if key not in store:return None
  b=store[key];return {'body':b,'etag':'"fixture-etag"','sha256':sha(b),'bytes':len(b)}
 error=None
 with patch.object(pub,'plan',return_value=([item],'fixture-manifest')),patch.object(pub,'deployment_baseline',return_value={'fixture':True}),patch.object(pub,'require_publication_engineering_review',return_value='fixture-review'),patch.object(pub,'ROOT',Root()),patch.object(pub,'RECEIPT',BodyPath()),patch.object(pub,'read',side_effect=read),patch.object(pub,'snapshot',return_value={}),patch.object(pub,'save'),patch.object(pub.boto3,'Session',return_value=Session()),patch.dict(os.environ,{'AWS_KEY':'fixture','AWS_SECRET':'fixture'}),patch.object(sys,'argv',['publish.py','--go']),contextlib.redirect_stdout(io.StringIO()):
  try:pub.main()
  except ValueError as e:error=str(e)
 return store,writes,invalidations,clients,error,item
store,writes,inv,clients,error,item=main_fixture(b'mutated-after-plan')
checked('postplan_mutation_rejected_before_artifact_put',error is not None and error.startswith('Artifact changed before upload')and item['key']not in store and all('/_retrospective_backup/'in x['Key']for x in writes))
store,writes,inv,clients,error,item=main_fixture(b'accepted-plan',existing=True)
checked('existing_target_rejected_before_writes',error is not None and error.startswith('Refusing to overwrite')and not writes)
store,writes,inv,clients,error,item=main_fixture(b'accepted-plan')
checked('conditional_upload_index_and_invalidation_success',error is None and store[item['key']]==b'accepted-plan'and len(writes)==3 and len(inv)==1)
checked('cdn_invalidation_exact_scoped_paths',inv[0]['DistributionId']==pub.DIST and inv[0]['InvalidationBatch']['Paths']=={'Quantity':5,'Items':expected_paths})
checked('no_lambda_client_in_publisher',clients==['s3','cloudfront'])
tree=ast.parse(V.read_text());main=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='main');verify=next(n for n in main.body if isinstance(n,ast.FunctionDef)and n.name=='verify')
item={'key':'reports/archive/2024-04-01.html','sha256':sha(b'accepted'),'bytes':len(b'accepted')}
class Response:
 status=200
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self):return b'wrong-body'
ns={'pub':types.SimpleNamespace(read=lambda s3,key:{'sha256':item['sha256'],'bytes':item['bytes']}),'s3':None,'urllib':__import__('urllib'),'hashlib':hashlib,'public_bundle':{},'bundle_key':'reports/2024-04/April_2024_Weekday_Reports.zip'}
exec(compile(ast.Module(body=[verify],type_ignores=[]),str(V),'exec'),ns)
with patch('urllib.request.urlopen',return_value=Response()):row=ns['verify'](item)
checked('https_status200_same_url_wrong_body_rejected',row['origin_sha256_pass']and row['public_sha256_pass']is False and row['public_status']==200)
guard=next(n for n in main.body if isinstance(n,ast.If)and any(isinstance(x,ast.Constant)and x.value=='Publication receipt or manifest changed during delivery verification'for x in ast.walk(n)))
for name,receipt_body,manifest_body,expect_error in [('delivery_stable_receipt_manifest_pass',b'receipt',b'manifest',False),('delivery_receipt_mutation_rejected',b'changed',b'manifest',True),('delivery_manifest_mutation_rejected',b'receipt',b'changed',True)]:
 vm={'publication.json':receipt_body,'checks/artifact_manifest.json':manifest_body};scope={'hashlib':hashlib,'pub':types.SimpleNamespace(RECEIPT=VirtualPath(vm,'publication.json')),'ROOT':VirtualPath(vm),'receipt_sha256':sha(b'receipt'),'manifest_sha256':sha(b'manifest')};raised=False
 try:exec(compile(ast.Module(body=[guard],type_ignores=[]),str(V),'exec'),scope)
 except ValueError:raised=True
 checked(name,raised==expect_error)
result={'status':'passed','checks':checks,'count':len(checks),'tool_sha256':{n:sha((R/'tools'/n).read_bytes())for n in ['publish.py','verify_delivery.py']},'no_real_network_or_publication':True,'no_checkpoint_execution':True,'author_inputs_read':False}
print(json.dumps(result,indent=2))
