"""
Deploy the Telegram self-scheduling polling daemon:
  1. Package telegram_webhook_lambda.py into a zip
  2. Create/update the poller Lambda (timeout=15 min)
  3. Allow poller role to invoke daily-trends-digest
  4. Allow poller role to invoke itself (self-scheduling)
  5. Create/update EventBridge watchdog rule (fires every 15 min as safety net)
  6. Kick off the first invocation
"""
import boto3
import io
import json
import os
import time
import uuid
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

# Unique ID stamped into the Lambda env at every deploy.
# The poller code exits immediately if the deploy_id in the event payload
# doesn't match DEPLOY_ID in its env — this kills any stale self-scheduling
# chains from previous deploys without needing to kill running instances.
DEPLOY_ID = uuid.uuid4().hex[:8]
print(f"Deploy ID: {DEPLOY_ID}")

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
ANTHROPIC_API_KEY = os.environ['ANTHROPIC_API_KEY']

env_vars = {
    'TELEGRAM_BOT_TOKEN': TELEGRAM_BOT_TOKEN,
    'TELEGRAM_CHAT_ID':   TELEGRAM_CHAT_ID,
    'REPORT_LAMBDA_NAME': REPORT_FUNCTION_NAME,
    'ANTHROPIC_API_KEY':  ANTHROPIC_API_KEY,
    'DEPLOY_ID':          DEPLOY_ID,
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


# ── 2b. Enforce reserved concurrency = 1 (only one poller instance ever runs) ─
print("\n[2b] Setting reserved concurrency = 1...")
lam.put_function_concurrency(
    FunctionName=POLLER_FUNCTION_NAME,
    ReservedConcurrentExecutions=1,
)
print("  Done")


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


# ── 5. EventBridge watchdog rule: fires every 15 min with {} payload ─────────
print("\n[5/6] Setting up EventBridge watchdog rule (every 15 min)...")
events = session.client('events')
WATCHDOG_RULE = 'daily-digest-poller-watchdog'

try:
    events.put_rule(
        Name=WATCHDOG_RULE,
        ScheduleExpression='rate(15 minutes)',
        State='ENABLED',
        Description='Watchdog: restarts poller chain if self-invocation chain dies',
    )
    print("  Rule created/updated")
except Exception as e:
    print(f"  put_rule failed: {e}")

# Allow EventBridge to invoke the poller Lambda
try:
    lam.add_permission(
        FunctionName=POLLER_FUNCTION_NAME,
        StatementId='allow-eventbridge-watchdog',
        Action='lambda:InvokeFunction',
        Principal='events.amazonaws.com',
        SourceArn=f'arn:aws:events:{REGION}:{account_id}:rule/{WATCHDOG_RULE}',
    )
    print("  Lambda permission added")
except lam.exceptions.ResourceConflictException:
    print("  Lambda permission already exists")
except Exception as e:
    print(f"  add_permission failed: {e}")

# Attach the Lambda as the rule target (empty input = {} = watchdog mode)
try:
    events.put_targets(
        Rule=WATCHDOG_RULE,
        Targets=[{
            'Id':    'poller-lambda',
            'Arn':   fn_arn,
            'Input': '{}',
        }],
    )
    print("  Target attached")
except Exception as e:
    print(f"  put_targets failed: {e}")


# ── 6. Kick off the first invocation ─────────────────────────────────────────
print("\n[6/6] Starting the polling daemon (first invocation)...")
resp = lam.invoke(
    FunctionName=POLLER_FUNCTION_NAME,
    InvocationType='Event',   # async — returns immediately
    Payload=json.dumps({'deploy_id': DEPLOY_ID}).encode(),
)
print(f"  Dispatched — StatusCode: {resp['StatusCode']}")


# ── Done ──────────────────────────────────────────────────────────────────────
print("\n✅  Done!")
print(f"   Poller Lambda  : {POLLER_FUNCTION_NAME}")
print(f"   Architecture   : self-scheduling loop (12 polls/run × 60s, re-invokes itself)")
print(f"   Watchdog       : EventBridge rule '{WATCHDOG_RULE}' fires every 15 min")
print(f"\nSend /report in your Telegram chat — it will be picked up within ~60 seconds.")
