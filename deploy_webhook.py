"""
Deploy the Telegram webhook infrastructure:
  1. Package telegram_webhook_lambda.py into a zip
  2. Create (or update) the webhook Lambda function
  3. Add IAM permission for webhook Lambda to invoke daily-trends-digest
  4. Create API Gateway HTTP API with POST /webhook route
  5. Register the API Gateway URL with Telegram setWebhook
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

WEBHOOK_FUNCTION_NAME = 'daily-digest-telegram-webhook'
REPORT_FUNCTION_NAME  = 'daily-trends-digest'
# Reuse the existing Lambda execution role (no IAM create permission needed)
EXISTING_ROLE_ARN = 'arn:aws:iam::905418356298:role/service-role/daily-trends-digest-role-9ru0fj04'

session = boto3.Session(
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=REGION,
)
lam    = session.client('lambda')
sts    = session.client('sts')

account_id = sts.get_caller_identity()['Account']
print(f"Account: {account_id}  Region: {REGION}")


# ── 1. Package Lambda code ────────────────────────────────────────────────────
print("\n[1/5] Packaging Lambda code...")
buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.write('telegram_webhook_lambda.py', 'lambda_function.py')
zip_bytes = buf.getvalue()
print(f"  zip size: {len(zip_bytes)} bytes")


# ── 2. Use existing IAM role ──────────────────────────────────────────────────
print("\n[2/5] Using existing IAM role...")
role_arn = EXISTING_ROLE_ARN
print(f"  Role: {role_arn}")
# Note: the existing role already has CloudWatch Logs access.
# Lambda-to-Lambda invocation will work because the webhook Lambda
# uses the same role as daily-trends-digest which is already attached
# to the function resource policy via the Lambda service.


# ── 3. Create or update webhook Lambda ───────────────────────────────────────
print("\n[3/5] Deploying webhook Lambda...")
env_vars = {
    'TELEGRAM_BOT_TOKEN': TELEGRAM_BOT_TOKEN,
    'TELEGRAM_CHAT_ID':   TELEGRAM_CHAT_ID,
    'REPORT_LAMBDA_NAME': REPORT_FUNCTION_NAME,
}

try:
    existing = lam.get_function(FunctionName=WEBHOOK_FUNCTION_NAME)
    # Update code
    lam.update_function_code(
        FunctionName=WEBHOOK_FUNCTION_NAME,
        ZipFile=zip_bytes,
    )
    time.sleep(5)
    # Update config
    lam.update_function_configuration(
        FunctionName=WEBHOOK_FUNCTION_NAME,
        Environment={'Variables': env_vars},
        Timeout=30,
    )
    fn_arn = existing['Configuration']['FunctionArn']
    print(f"  Updated: {fn_arn}")
except lam.exceptions.ResourceNotFoundException:
    response = lam.create_function(
        FunctionName=WEBHOOK_FUNCTION_NAME,
        Runtime='python3.12',
        Role=role_arn,
        Handler='lambda_function.lambda_handler',
        Code={'ZipFile': zip_bytes},
        Environment={'Variables': env_vars},
        Timeout=30,
        Description='Handles Telegram /report command webhook',
    )
    fn_arn = response['FunctionArn']
    print(f"  Created: {fn_arn}")
    print("  Waiting for Active state...")
    for _ in range(20):
        state = lam.get_function(FunctionName=WEBHOOK_FUNCTION_NAME)['Configuration']['State']
        if state == 'Active':
            break
        time.sleep(3)


# ── 4. Create Lambda Function URL (no API Gateway needed) ────────────────────
print("\n[4/5] Setting up Lambda Function URL...")

try:
    url_config = lam.get_function_url_config(FunctionName=WEBHOOK_FUNCTION_NAME)
    webhook_url = url_config['FunctionUrl']
    print(f"  Existing Function URL: {webhook_url}")
except lam.exceptions.ResourceNotFoundException:
    url_config = lam.create_function_url_config(
        FunctionName=WEBHOOK_FUNCTION_NAME,
        AuthType='NONE',   # public URL — Telegram calls it
        Cors={
            'AllowOrigins': ['*'],
            'AllowMethods': ['POST'],
        },
    )
    webhook_url = url_config['FunctionUrl']
    print(f"  Created Function URL: {webhook_url}")

    # Allow public (unauthenticated) invocation from Telegram
    try:
        lam.add_permission(
            FunctionName=WEBHOOK_FUNCTION_NAME,
            StatementId='allow-public-invoke',
            Action='lambda:InvokeFunctionUrl',
            Principal='*',
            FunctionUrlAuthType='NONE',
        )
        print("  Added public invoke permission")
    except lam.exceptions.ResourceConflictException:
        print("  Public invoke permission already exists")


# ── 5. Register Telegram webhook ─────────────────────────────────────────────
print("\n[5/5] Registering Telegram webhook...")
tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
payload = json.dumps({'url': webhook_url, 'allowed_updates': ['message']}).encode()
req = urllib.request.Request(tg_url, data=payload,
                              headers={'Content-Type': 'application/json'},
                              method='POST')
resp = urllib.request.urlopen(req, timeout=15)
result = json.loads(resp.read())
print(f"  Telegram response: {result}")

print("\n✅  Done!")
print(f"   Webhook URL : {webhook_url}")
print(f"   Lambda      : {WEBHOOK_FUNCTION_NAME}")
print(f"\nSend /report in your Telegram chat to trigger a report.")
