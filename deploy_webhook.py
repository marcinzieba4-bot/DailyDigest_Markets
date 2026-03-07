"""
Deploy the Telegram self-scheduling polling daemon:
  1. Package telegram_webhook_lambda.py into a zip
  2. Create/update the poller Lambda (timeout=15 min)
  3. Allow poller role to invoke daily-trends-digest
  4. Allow poller role to invoke itself (self-scheduling)
  5. Kick off the first invocation
"""
import boto3
import io
import json
import os
import time
import zipfile

# ── credentials from env ──────────────────────────────────────────────────────
AWS_ACCESS_KEY_ID     = os.environ['AWS_ACCESS_KEY_ID']
AWS_SECRET_ACCESS_KEY = os.environ['AWS_SECRET_ACCESS_KEY']
REGION                = 'eu-north-1'
TELEGRAM_BOT_TOKEN    = os.environ['TELEGRAM_BOT_TOKEN']
TELEGRAM_CHAT_ID      = os.environ['TELEGRAM_CHAT_ID']

POLLER_FUNCTION_NAME = 'daily-digest-telegram-webhook'
REPORT_FUNCTION_NAME = 'daily-trends-digest'
EXISTING_ROLE_ARN    = 'arn:aws:iam::905418356298:role/service-role/daily-trends-digest-role-9ru0fj04'

session = boto3.Session(
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=REGION,
)
lam = session.client('lambda')
sts = session.client('sts')

account_id = sts.get_caller_identity()['Account']
print(f"Account: {account_id}  Region: {REGION}")


# ── 1. Package Lambda code ────────────────────────────────────────────────────
print("\n[1/5] Packaging Lambda code...")
buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.write('telegram_webhook_lambda.py', 'lambda_function.py')
zip_bytes = buf.getvalue()
print(f"  zip size: {len(zip_bytes)} bytes")


# ── 2. Deploy poller Lambda (15-minute timeout for the polling loop) ──────────
print("\n[2/5] Deploying poller Lambda...")
env_vars = {
    'TELEGRAM_BOT_TOKEN': TELEGRAM_BOT_TOKEN,
    'TELEGRAM_CHAT_ID':   TELEGRAM_CHAT_ID,
    'REPORT_LAMBDA_NAME': REPORT_FUNCTION_NAME,
}

try:
    existing = lam.get_function(FunctionName=POLLER_FUNCTION_NAME)
    lam.update_function_code(FunctionName=POLLER_FUNCTION_NAME, ZipFile=zip_bytes)
    time.sleep(5)
    lam.update_function_configuration(
        FunctionName=POLLER_FUNCTION_NAME,
        Environment={'Variables': env_vars},
        Timeout=900,   # 15 minutes — Lambda max; loop runs for ~12 min then re-invokes
    )
    fn_arn = existing['Configuration']['FunctionArn']
    print(f"  Updated: {fn_arn}")
    # Wait for update to finish
    for _ in range(20):
        st = lam.get_function_configuration(FunctionName=POLLER_FUNCTION_NAME)
        if st.get('LastUpdateStatus') == 'Successful':
            break
        time.sleep(3)
except lam.exceptions.ResourceNotFoundException:
    resp = lam.create_function(
        FunctionName=POLLER_FUNCTION_NAME,
        Runtime='python3.12',
        Role=EXISTING_ROLE_ARN,
        Handler='lambda_function.lambda_handler',
        Code={'ZipFile': zip_bytes},
        Environment={'Variables': env_vars},
        Timeout=900,
        Description='Self-scheduling Telegram poller for /report command',
    )
    fn_arn = resp['FunctionArn']
    print(f"  Created: {fn_arn}")
    for _ in range(20):
        state = lam.get_function(FunctionName=POLLER_FUNCTION_NAME)['Configuration']['State']
        if state == 'Active':
            break
        time.sleep(3)


# ── 3. Allow poller role to invoke the report Lambda ─────────────────────────
print("\n[3/5] Ensuring report Lambda invoke permission...")
try:
    lam.add_permission(
        FunctionName=REPORT_FUNCTION_NAME,
        StatementId='allow-webhook-lambda-invoke',
        Action='lambda:InvokeFunction',
        Principal=EXISTING_ROLE_ARN,
    )
    print("  Added")
except lam.exceptions.ResourceConflictException:
    print("  Already exists")


# ── 4. Allow poller role to invoke itself (self-scheduling) ──────────────────
print("\n[4/5] Ensuring self-invoke permission on poller Lambda...")
try:
    lam.add_permission(
        FunctionName=POLLER_FUNCTION_NAME,
        StatementId='allow-self-invoke',
        Action='lambda:InvokeFunction',
        Principal=EXISTING_ROLE_ARN,
    )
    print("  Added")
except lam.exceptions.ResourceConflictException:
    print("  Already exists")


# ── 5. Kick off the first invocation ─────────────────────────────────────────
print("\n[5/5] Starting the polling daemon (first invocation)...")
resp = lam.invoke(
    FunctionName=POLLER_FUNCTION_NAME,
    InvocationType='Event',   # async — returns immediately
    Payload=b'{}',
)
print(f"  Dispatched — StatusCode: {resp['StatusCode']}")


# ── Done ──────────────────────────────────────────────────────────────────────
print("\n✅  Done!")
print(f"   Poller Lambda : {POLLER_FUNCTION_NAME}")
print(f"   Architecture  : self-scheduling loop (12 polls/run × 60s, re-invokes itself)")
print(f"\nSend /report in your Telegram chat — it will be picked up within ~60 seconds.")
