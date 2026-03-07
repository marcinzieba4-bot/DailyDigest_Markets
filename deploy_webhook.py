"""
Deploy the Telegram polling infrastructure:
  1. Package telegram_webhook_lambda.py into a zip
  2. Create/update the poller Lambda function
  3. Add resource-based policy so poller can invoke daily-trends-digest
  4. Create SSM parameter for offset tracking
  5. Create EventBridge rule to run poller every 1 minute
"""
import boto3
import io
import json
import os
import sys
import time
import urllib.request
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
lam      = session.client('lambda')
events   = session.client('events')
sts      = session.client('sts')

account_id = sts.get_caller_identity()['Account']
print(f"Account: {account_id}  Region: {REGION}")


# ── 1. Package Lambda code ────────────────────────────────────────────────────
print("\n[1/5] Packaging Lambda code...")
buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.write('telegram_webhook_lambda.py', 'lambda_function.py')
zip_bytes = buf.getvalue()
print(f"  zip size: {len(zip_bytes)} bytes")


# ── 2. Deploy poller Lambda ───────────────────────────────────────────────────
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
        Timeout=30,
    )
    fn_arn = existing['Configuration']['FunctionArn']
    print(f"  Updated: {fn_arn}")
except lam.exceptions.ResourceNotFoundException:
    resp = lam.create_function(
        FunctionName=POLLER_FUNCTION_NAME,
        Runtime='python3.12',
        Role=EXISTING_ROLE_ARN,
        Handler='lambda_function.lambda_handler',
        Code={'ZipFile': zip_bytes},
        Environment={'Variables': env_vars},
        Timeout=30,
        Description='Polls Telegram for /report command and invokes daily-trends-digest',
    )
    fn_arn = resp['FunctionArn']
    print(f"  Created: {fn_arn}")
    for _ in range(20):
        state = lam.get_function(FunctionName=POLLER_FUNCTION_NAME)['Configuration']['State']
        if state == 'Active':
            break
        time.sleep(3)


# ── 3. Allow poller to invoke the report Lambda ───────────────────────────────
print("\n[3/5] Ensuring invoke permission on report Lambda...")
try:
    lam.add_permission(
        FunctionName=REPORT_FUNCTION_NAME,
        StatementId='allow-webhook-lambda-invoke',
        Action='lambda:InvokeFunction',
        Principal=EXISTING_ROLE_ARN,
    )
    print("  Added invoke permission")
except lam.exceptions.ResourceConflictException:
    print("  Permission already exists")


# ── 4. Create EventBridge rule — run every 1 minute ─────────────────────────
print("\n[4/5] Setting up EventBridge schedule (every 1 minute)...")
rule_name = 'daily-digest-telegram-poll'

try:
    rule_arn = events.put_rule(
        Name=rule_name,
        ScheduleExpression='rate(1 minute)',
        State='ENABLED',
        Description='Polls Telegram for /report command every minute',
    )['RuleArn']
    print(f"  Rule: {rule_arn}")
except Exception as e:
    print(f"  put_rule error: {e}")
    sys.exit(1)

# Allow EventBridge to invoke the Lambda
try:
    lam.add_permission(
        FunctionName=POLLER_FUNCTION_NAME,
        StatementId='allow-eventbridge-invoke',
        Action='lambda:InvokeFunction',
        Principal='events.amazonaws.com',
        SourceArn=rule_arn,
    )
    print("  Added EventBridge invoke permission")
except lam.exceptions.ResourceConflictException:
    print("  EventBridge invoke permission already exists")

# Attach Lambda as target of the rule
events.put_targets(
    Rule=rule_name,
    Targets=[{
        'Id':  'daily-digest-telegram-poller',
        'Arn': fn_arn,
    }],
)
print("  Attached Lambda as EventBridge target")


# ── Done ──────────────────────────────────────────────────────────────────────
print("\n✅  Done!")
print(f"   Poller Lambda    : {POLLER_FUNCTION_NAME}")
print(f"   Schedule         : every 1 minute via EventBridge")
print(f"\nSend /report in your Telegram chat — it will be picked up within 1 minute.")
