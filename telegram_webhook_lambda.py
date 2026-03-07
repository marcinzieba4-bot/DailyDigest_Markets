"""
Telegram Poller Lambda
Runs on a 1-minute EventBridge schedule.
Calls getUpdates (no offset needed — deduplicates via message timestamp).
Only processes messages received in the last 90 seconds to avoid replaying
old commands after a cold start or missed invocation.
"""
import json
import logging
import os
import time
import urllib.request
import boto3
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID   = os.environ.get('TELEGRAM_CHAT_ID', '')
REPORT_LAMBDA_NAME = os.environ.get('REPORT_LAMBDA_NAME', 'daily-trends-digest')
REGION             = os.environ.get('AWS_REGION', 'eu-north-1')
MAX_AGE_SECONDS    = 90   # ignore messages older than this


def tg_post(method, payload):
    url  = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(url, data=data,
                                  headers={'Content-Type': 'application/json'},
                                  method='POST')
    resp = urllib.request.urlopen(req, timeout=15)
    return json.loads(resp.read())


def send_message(chat_id, text):
    tg_post('sendMessage', {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'})


def lambda_handler(event, context):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Telegram env vars not set")
        return

    now = int(time.time())

    # Fetch recent updates (limit 10 is plenty for a 1-minute poll window)
    result = tg_post('getUpdates', {
        'limit':   10,
        'timeout': 0,
        'allowed_updates': ['message'],
    })

    updates = result.get('result', [])
    logger.info("Got %d updates", len(updates))

    lam = boto3.client('lambda', region_name=REGION)

    for upd in updates:
        message = upd.get('message') or upd.get('edited_message')
        if not message:
            continue

        msg_time = message.get('date', 0)
        age      = now - msg_time

        if age > MAX_AGE_SECONDS:
            logger.info("Skipping old message (age=%ds)", age)
            continue

        chat_id = str(message.get('chat', {}).get('id', ''))
        text    = message.get('text', '').strip()
        logger.info("New message from chat_id=%s age=%ds: %r", chat_id, age, text)

        if chat_id != TELEGRAM_CHAT_ID:
            logger.info("Ignoring unauthorized chat_id=%s", chat_id)
            continue

        if text.startswith('/report'):
            try:
                send_message(chat_id,
                    "\u23f3 *Generating report\u2026*\n"
                    "This takes ~3\u20135 minutes. I'll send the briefing when ready.")
            except Exception as e:
                logger.error("Failed to send ack: %s", e)

            try:
                resp = lam.invoke(
                    FunctionName=REPORT_LAMBDA_NAME,
                    InvocationType='Event',
                    Payload=b'{}',
                )
                logger.info("Invoked %s — status %s", REPORT_LAMBDA_NAME, resp.get('StatusCode'))
            except Exception as e:
                logger.error("Failed to invoke report Lambda: %s", e)
                try:
                    send_message(chat_id, "\u274c Failed to trigger report: " + str(e))
                except Exception:
                    pass

        elif text.startswith('/start') or text.startswith('/help'):
            try:
                send_message(chat_id,
                    "\U0001f4ca *Daily Market Digest Bot*\n\n"
                    "Commands:\n"
                    "`/report` \u2014 generate and send today's full market briefing\n"
                    "`/help` \u2014 show this message\n\n"
                    "_Reports are also delivered automatically every morning._")
            except Exception as e:
                logger.error("Failed to send help: %s", e)
