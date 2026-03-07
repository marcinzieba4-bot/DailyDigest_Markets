"""
Telegram Self-Scheduling Poller Lambda
Runs in a 12-minute polling loop, then re-invokes itself before Lambda timeout.
Creates a continuous cycle without requiring EventBridge.

Architecture:
  - Lambda timeout: 15 minutes
  - Each invocation: polls Telegram every 60 s for 12 cycles (~12 min)
  - Before exiting: re-invokes itself asynchronously (fire-and-forget)
  - Net effect: continuous 60-second polling, self-sustaining

Generation / deploy-id:
  Every deploy stamps a unique DEPLOY_ID into the Lambda env.  When an old
  running instance self-reinvokes it carries its old deploy_id in the payload.
  The new invocation sees the mismatch (env DEPLOY_ID ≠ event deploy_id) and
  exits immediately, killing the stale chain.  Only the fresh chain started by
  the deploy script (which carries the current deploy_id) keeps running.
"""
import json
import logging
import os
import time
import urllib.request
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

import boto3 as _boto3, time as _time

class _CWHandler(logging.Handler):
    """Write log records to the permitted CloudWatch log group."""
    _LOG_GROUP  = '/aws/lambda/daily-trends-digest'
    _LOG_STREAM = 'telegram-poller'
    _seq_token  = None

    def __init__(self):
        super().__init__()
        self._cw = _boto3.client('logs', region_name='eu-north-1')
        self._ensure_stream()

    def _ensure_stream(self):
        try:
            self._cw.create_log_stream(
                logGroupName=self._LOG_GROUP,
                logStreamName=self._LOG_STREAM,
            )
        except self._cw.exceptions.ResourceAlreadyExistsException:
            pass
        except Exception:
            pass

    def emit(self, record):
        msg = self.format(record)
        kwargs = dict(
            logGroupName=self._LOG_GROUP,
            logStreamName=self._LOG_STREAM,
            logEvents=[{'timestamp': int(_time.time() * 1000), 'message': msg}],
        )
        if self._seq_token:
            kwargs['sequenceToken'] = self._seq_token
        try:
            resp = self._cw.put_log_events(**kwargs)
            self.__class__._seq_token = resp.get('nextSequenceToken')
        except Exception:
            pass   # never crash on logging

try:
    _cw_handler = _CWHandler()
    _cw_handler.setFormatter(logging.Formatter('[POLLER] %(levelname)s %(message)s'))
    logger.addHandler(_cw_handler)
except Exception:
    pass  # fall back to default (silent) logging if CW handler fails

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID   = os.environ.get('TELEGRAM_CHAT_ID', '')
REPORT_LAMBDA_NAME = os.environ.get('REPORT_LAMBDA_NAME', 'daily-trends-digest')
REGION             = os.environ.get('AWS_REGION', 'eu-north-1')
DEPLOY_ID          = os.environ.get('DEPLOY_ID', '')   # set by deploy script

POLL_INTERVAL_S = 60    # seconds between Telegram polls (normal mode)
BUSY_WAIT_S     = 300   # seconds to pause after triggering /report (busy mode)
CYCLES_PER_RUN  = 12    # ~12 min total, well within 15-min Lambda timeout
MAX_AGE_SECONDS = 180   # ignore messages older than this (3 min; covers busy wait)


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


def get_fresh_offset():
    """Return offset just past the latest existing update so we skip the backlog."""
    try:
        result = tg_post('getUpdates', {'limit': 1, 'timeout': 0})
        updates = result.get('result', [])
        if updates:
            return updates[-1]['update_id'] + 1
    except Exception as e:
        logger.warning("Could not fetch fresh offset: %s", e)
    return 0


def poll_once(lam_client, offset):
    """Poll Telegram once and handle any new /report or /help commands.

    Returns (next_offset, report_triggered).
    Stops processing updates after the first /report so we never double-fire.
    """
    now = int(time.time())
    try:
        result = tg_post('getUpdates', {
            'offset':  offset,
            'limit':   10,
            'timeout': 0,
            'allowed_updates': ['message'],
        })
    except Exception as e:
        logger.error("getUpdates failed: %s", e)
        return offset, False

    updates = result.get('result', [])
    if not updates:
        return offset, False

    # Advance offset past all received updates (acknowledges them so they won't repeat)
    next_offset = max(upd['update_id'] for upd in updates) + 1

    report_triggered = False

    for upd in updates:
        message = upd.get('message') or upd.get('edited_message')
        if not message:
            continue

        age = now - message.get('date', 0)
        if age > MAX_AGE_SECONDS:
            logger.info("Skipping stale message (age=%ds)", age)
            continue

        chat_id = str(message.get('chat', {}).get('id', ''))
        text    = message.get('text', '').strip()
        logger.info("New message chat_id=%s age=%ds: %r", chat_id, age, text)

        if chat_id != TELEGRAM_CHAT_ID:
            continue

        if text.startswith('/report'):
            try:
                send_message(chat_id,
                    "\u23f3 *Generating report\u2026*\n"
                    "This takes ~3\u20135 minutes. I'll send the briefing when ready.")
            except Exception as e:
                logger.error("Failed to send ack: %s", e)

            try:
                resp = lam_client.invoke(
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

            report_triggered = True
            # Stop processing further updates this cycle — one report at a time.
            break

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

    return next_offset, report_triggered


def lambda_handler(event, context):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Telegram env vars not set")
        return

    # ── Generation check ──────────────────────────────────────────────────────
    # Each deploy stamps a unique DEPLOY_ID into the env.  Self-reinvocations
    # carry deploy_id in the payload.  Any invocation whose deploy_id doesn't
    # match the current env — including old chains that pre-date this feature
    # and therefore carry no deploy_id at all — exits immediately so the stale
    # chain dies and only the fresh deploy chain continues.
    event_deploy_id = event.get('deploy_id', '')
    if DEPLOY_ID and event_deploy_id != DEPLOY_ID:
        logger.info("Stale chain detected (event deploy_id=%r, current=%s) — stopping.",
                    event_deploy_id, DEPLOY_ID)
        return

    lam = boto3.client('lambda', region_name=REGION)

    # Use offset from event (continuation of existing chain).
    # If absent (fresh deploy kick-off), skip past all existing updates so we
    # never replay stale /report commands.
    offset = event.get('offset') or get_fresh_offset()

    logger.info("Starting polling loop: %d cycles × %ds (deploy_id=%s, offset=%d)",
                CYCLES_PER_RUN, POLL_INTERVAL_S, DEPLOY_ID, offset)

    for cycle in range(CYCLES_PER_RUN):
        logger.info("Cycle %d/%d (offset=%d)", cycle + 1, CYCLES_PER_RUN, offset)
        offset, report_triggered = poll_once(lam, offset)

        if report_triggered:
            # ── Busy mode ────────────────────────────────────────────────────
            # Report Lambda is now running.  Sleep so we don't respond to any
            # further messages while the report is being generated.
            logger.info("Busy mode: sleeping %ds while report generates…", BUSY_WAIT_S)
            time.sleep(BUSY_WAIT_S)
            logger.info("Busy mode over, resuming normal polling.")
        elif cycle < CYCLES_PER_RUN - 1:
            time.sleep(POLL_INTERVAL_S)

    # Re-invoke self to continue the polling loop indefinitely.
    # Pass current offset AND deploy_id so the generation check works on the
    # next invocation.
    payload = json.dumps({'offset': offset, 'deploy_id': DEPLOY_ID}).encode()
    logger.info("Re-invoking self for next run (offset=%d, deploy_id=%s)…", offset, DEPLOY_ID)
    try:
        lam.invoke(
            FunctionName=context.function_name,
            InvocationType='Event',   # fire-and-forget, don't wait
            Payload=payload,
        )
        logger.info("Self-invocation scheduled")
    except Exception as e:
        logger.error("CRITICAL: self-invocation failed — polling will stop! %s", e)
        try:
            send_message(TELEGRAM_CHAT_ID,
                "\u26a0\ufe0f *Polling daemon stopped* — self-invocation failed.\n"
                "Contact admin to restart the `/report` handler.")
        except Exception:
            pass
