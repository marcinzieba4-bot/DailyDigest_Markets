"""
Deploy the report Lambda (daily-trends-digest).

Packages lambda_function.py as a code-only zip and attaches the
'daily-digest-deps' layer (fpdf2 + anthropic).  Run this whenever
lambda_function.py changes manually.

Usage:
    export $(grep -v '^#' .env | xargs)
    python3 deploy_report.py
"""
import boto3
import io
import os
import time
import zipfile

AWS_ACCESS_KEY_ID     = os.environ['AWS_ACCESS_KEY_ID']
AWS_SECRET_ACCESS_KEY = os.environ['AWS_SECRET_ACCESS_KEY']
REGION                = 'eu-north-1'
REPORT_FUNCTION_NAME  = 'daily-trends-digest'
LAYER_NAME            = 'daily-digest-deps'

session = boto3.Session(
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=REGION,
)
lam = session.client('lambda')

# ── Find the latest version of the deps layer ─────────────────────────────────
print(f"Looking up latest version of layer '{LAYER_NAME}'...")
versions = lam.list_layer_versions(LayerName=LAYER_NAME)['LayerVersions']
if not versions:
    raise RuntimeError(
        f"Layer '{LAYER_NAME}' not found. Run this once to create it:\n"
        "  pip install fpdf2 anthropic -t /tmp/layer_pkg/python\n"
        "  # then zip /tmp/layer_pkg and publish via AWS Console or boto3"
    )
layer_arn = versions[0]['LayerVersionArn']   # list is newest-first
print(f"  Using: {layer_arn}")

# ── Wait for any in-progress update to finish ─────────────────────────────────
print("Waiting for function to be ready...")
for _ in range(20):
    st = lam.get_function_configuration(FunctionName=REPORT_FUNCTION_NAME)
    if st.get('LastUpdateStatus') != 'InProgress':
        break
    time.sleep(3)

# ── Package code-only zip ─────────────────────────────────────────────────────
print("Packaging lambda_function.py...")
buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.write('lambda_function.py')
zip_bytes = buf.getvalue()
print(f"  zip size: {len(zip_bytes):,} bytes")

# ── Deploy code ───────────────────────────────────────────────────────────────
print("Deploying code...")
lam.update_function_code(FunctionName=REPORT_FUNCTION_NAME, ZipFile=zip_bytes)

# Wait for code update
for _ in range(20):
    st = lam.get_function_configuration(FunctionName=REPORT_FUNCTION_NAME)
    if st.get('LastUpdateStatus') != 'InProgress':
        break
    time.sleep(3)

# ── Attach deps layer ─────────────────────────────────────────────────────────
print(f"Attaching layer...")
lam.update_function_configuration(
    FunctionName=REPORT_FUNCTION_NAME,
    Layers=[layer_arn],
)

# Wait
for _ in range(20):
    st = lam.get_function_configuration(FunctionName=REPORT_FUNCTION_NAME)
    if st.get('LastUpdateStatus') != 'InProgress':
        break
    time.sleep(3)

print(f"\n✅  Done!  {REPORT_FUNCTION_NAME} deployed with layer {LAYER_NAME}")
