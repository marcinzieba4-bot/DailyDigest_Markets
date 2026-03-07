"""
Telegram Webhook Lambda
Receives Telegram updates, handles /report command by async-invoking daily-trends-digest.
"""
import json
import logging
import os
import urllib.request
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID   = os.environ.get('TELEGRAM_CHAT_ID', '')
REPORT_LAMBDA_NAME = os.environ.get('REPORT_LAMBDA_NAME', 'daily-trends-digest')


def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    body = json.dumps({
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown',
    }).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={'Content-Type': 'application/json'},
                                 method='POST')
    urllib.request.urlopen(req, timeout=10)


def lambda_handler(event, context):
    logger.info("Webhook received: %s", json.dumps(event)[:500])

    # Parse Telegram update from API Gateway body
    try:
        body = event.get('body', '{}') or '{}'
        if isinstance(body, str):
            update = json.loads(body)
        else:
            update = body
    except Exception as e:
        logger.error("Failed to parse body: %s", e)
        return {'statusCode': 200, 'body': 'ok'}

    message = update.get('message') or update.get('edited_message', {})
    if not message:
        return {'statusCode': 200, 'body': 'ok'}

    chat_id  = str(message.get('chat', {}).get('id', ''))
    text     = message.get('text', '').strip()

    logger.info("Message from chat_id=%s: %s", chat_id, text)

    # Security: only respond to authorized chat
    if chat_id != TELEGRAM_CHAT_ID:
        logger.warning("Unauthorized chat_id=%s — ignoring", chat_id)
        return {'statusCode': 200, 'body': 'ok'}

    if text.startswith('/report'):
        # Acknowledge immediately (Telegram requires response within 5 s)
        try:
            send_message(chat_id, "\u23f3 *Generating report\u2026*\nThis takes ~3\u20135 minutes. I'll send the briefing when ready.")
        except Exception as e:
            logger.error("Failed to send ack: %s", e)

        # Async-invoke the report Lambda — returns immediately
        try:
            client = boto3.client('lambda', region_name='eu-north-1')
            response = client.invoke(
                FunctionName=REPORT_LAMBDA_NAME,
                InvocationType='Event',   # fire-and-forget
                Payload=b'{}',
            )
            logger.info("Invoked %s — StatusCode=%s", REPORT_LAMBDA_NAME, response.get('StatusCode'))
        except Exception as e:
            logger.error("Failed to invoke report Lambda: %s", e)
            try:
                send_message(chat_id, "\u274c Failed to trigger report: " + str(e))
            except Exception:
                pass

    elif text.startswith('/start') or text.startswith('/help'):
        send_message(chat_id,
            "\U0001f4ca *Daily Market Digest Bot*\n\n"
            "Commands:\n"
            "`/report` \u2014 generate and send today's full market briefing\n"
            "`/help` \u2014 show this message\n\n"
            "_Reports are also delivered automatically every morning._")

    return {'statusCode': 200, 'body': 'ok'}
