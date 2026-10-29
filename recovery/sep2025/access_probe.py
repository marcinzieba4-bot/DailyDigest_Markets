from pathlib import Path
import json,os,subprocess,urllib.request
out={}
for key,url in [('public_archive','https://d7g7nkeytae81.cloudfront.net/reports/index.html'),('google_news','https://news.google.com/rss/search?q=retail+investors')]:
 try:
  with urllib.request.urlopen(url,timeout=15) as response:out[key]={'status':response.status}
 except Exception as error:out[key]={'error_type':type(error).__name__}
pairs=[('standard','AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY'),('runtime_names','AWS_KEY','AWS_SECRET'),('legacy_documented','AWS_KEY','AWS_PASS')]
selected=next((p for p in pairs if os.environ.get(p[1]) and os.environ.get(p[2])),None)
out['existing_repository_aws_credentials_configured']=selected is not None
out['configured_pair_label']=selected[0] if selected else None
if selected:
 env=dict(os.environ);env['AWS_ACCESS_KEY_ID']=env[selected[1]];env['AWS_SECRET_ACCESS_KEY']=env[selected[2]]
 try:
  p=subprocess.run(['aws','s3api','head-bucket','--bucket','s3bucketmz','--region','eu-north-1'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=25)
  out['authorized_bucket_head_passed']=p.returncode==0
 except Exception as error:out['aws_probe_error_type']=type(error).__name__
Path('recovery/sep2025/access_probe.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out))
