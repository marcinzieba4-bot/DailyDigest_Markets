"""
Telegram Self-Scheduling Poller + Claude Agent Lambda

Normal mode  : polls Telegram every 60 s, passes every message to Claude
               (Anthropic API) for interpretation, and dispatches one of:
                 • run_report  — invoke daily-trends-digest Lambda
                 • reply       — send Claude's plain-text reply to the user
                 • modify_code — fetch report Lambda code, apply the change
                                 immediately and deploy without approval

Busy mode    : after triggering a report, sleeps BUSY_WAIT_S (300 s) before
               resuming, so only one report runs at a time.

DEPLOY_ID    : generation tag stamped by deploy_webhook.py — stale chains from
               previous deploys exit immediately on their next self-reinvocation.
"""
import difflib
import io
import json
import logging
import os
import time
import urllib.request
import zipfile
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
    pass

# ── Config ─────────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID   = os.environ.get('TELEGRAM_CHAT_ID', '')
REPORT_LAMBDA_NAME = os.environ.get('REPORT_LAMBDA_NAME', 'daily-trends-digest')
ANTHROPIC_API_KEY  = os.environ.get('ANTHROPIC_API_KEY', '')
REGION             = os.environ.get('AWS_REGION', 'eu-north-1')
DEPLOY_ID          = os.environ.get('DEPLOY_ID', '')

POLL_INTERVAL_S = 60    # seconds between polls in normal mode
BUSY_WAIT_S     = 300   # seconds to pause after triggering a report
CYCLES_PER_RUN  = 12    # ~12 min per Lambda invocation
MAX_AGE_SECONDS = 180   # ignore messages older than 3 min
REINVOKE_BUFFER_MS = 90_000  # bail out and self-reinvoke when less than 90s remains


# ── Telegram helpers ───────────────────────────────────────────────────────────

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


# ── Anthropic helpers ──────────────────────────────────────────────────────────

def _anthropic_post(body, timeout=60):
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data=data,
        headers={
            'x-api-key':           ANTHROPIC_API_KEY,
            'anthropic-version':   '2023-06-01',
            'content-type':        'application/json',
        },
        method='POST',
    )
    resp = urllib.request.urlopen(req, timeout=timeout)
    return json.loads(resp.read())


def classify_intent(user_text):
    """Ask Claude Haiku to pick an action for the user's message.

    Returns ('run_report'|'reply'|'modify_code', payload_str).
    payload_str is the reply text for 'reply' and a one-line summary for
    'modify_code'; it is empty for 'run_report'.
    """
    tools = [
        {
            'name': 'run_report',
            'description': (
                'User wants to trigger the daily financial-markets report '
                '(e.g. "generate report", "run report", "/report").'
            ),
            'input_schema': {'type': 'object', 'properties': {}, 'required': []},
        },
        {
            'name': 'reply',
            'description': 'Answer the user with a short text message.',
            'input_schema': {
                'type': 'object',
                'properties': {'text': {'type': 'string', 'description': 'Reply text.'}},
                'required': ['text'],
            },
        },
        {
            'name': 'modify_code',
            'description': (
                'User wants to change how the report works — e.g. different date ranges, '
                'new/removed sections, different data sources, formatting tweaks, '
                'extended backtest history, new indicators, etc.'
            ),
            'input_schema': {
                'type': 'object',
                'properties': {
                    'summary': {
                        'type': 'string',
                        'description': 'One-line human-readable summary of the requested change.',
                    },
                },
                'required': ['summary'],
            },
        },
    ]

    result = _anthropic_post({
        'model': 'claude-haiku-4-5-20251001',
        'max_tokens': 256,
        'system': (
            'You control a Telegram bot that manages a daily financial-markets digest. '
            'Choose the right tool for the user\'s message. '
            'If the user asks anything unrelated to the report or code changes, use "reply".'
        ),
        'messages': [{'role': 'user', 'content': user_text}],
        'tools': tools,
        'tool_choice': {'type': 'auto'},
    })

    for block in result.get('content', []):
        if block.get('type') == 'tool_use':
            name = block['name']
            inp  = block.get('input', {})
            if name == 'run_report':
                return 'run_report', ''
            if name == 'reply':
                return 'reply', inp.get('text', '')
            if name == 'modify_code':
                return 'modify_code', inp.get('summary', 'Code change')
        if block.get('type') == 'text':
            return 'reply', block['text']

    return 'reply', "I'm not sure how to help with that."


def get_report_lambda_code(lam_client):
    """Download and return current lambda_function.py from the report Lambda."""
    resp     = lam_client.get_function(FunctionName=REPORT_LAMBDA_NAME)
    zip_data = urllib.request.urlopen(resp['Code']['Location'], timeout=30).read()
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        return zf.read('lambda_function.py').decode('utf-8')


def generate_modified_code(user_request, current_code):
    """Ask Claude Sonnet to return a fully modified lambda_function.py."""
    result = _anthropic_post({
        'model': 'claude-sonnet-4-6',
        'max_tokens': 8192,
        'system': (
            'You are a Python expert modifying an AWS Lambda function that generates a daily '
            'financial-markets digest. Return ONLY the complete modified Python source file — '
            'no explanation, no markdown fences, no commentary. '
            'Start directly with the import statements.'
        ),
        'messages': [{
            'role': 'user',
            'content': (
                f'Requested change: {user_request}\n\n'
                f'Current lambda_function.py:\n{current_code}\n\n'
                'Return the complete modified file.'
            ),
        }],
    }, timeout=120)

    for block in result.get('content', []):
        if block.get('type') == 'text':
            text = block['text'].strip()
            # Strip markdown fences if the model added them
            if text.startswith('```'):
                lines = text.split('\n')
                end   = -1 if lines[-1].strip() == '```' else len(lines)
                text  = '\n'.join(lines[1:end])
            return text

    raise RuntimeError('No text content in Claude Sonnet response')


def make_unified_diff(old_code, new_code):
    return ''.join(difflib.unified_diff(
        old_code.splitlines(keepends=True),
        new_code.splitlines(keepends=True),
        fromfile='lambda_function.py (current)',
        tofile='lambda_function.py (proposed)',
        n=3,
    ))


def apply_and_deploy(new_code, lam_client):
    """Zip the new code and push it to the report Lambda."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('lambda_function.py', new_code)
    lam_client.update_function_code(
        FunctionName=REPORT_LAMBDA_NAME,
        ZipFile=buf.getvalue(),
    )
    logger.info("Deployed new code to %s", REPORT_LAMBDA_NAME)


# ── Message dispatcher ─────────────────────────────────────────────────────────

def _invoke_report(chat_id, lam_client):
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


def handle_message(text, chat_id, lam_client):
    """Process one incoming message.  Returns report_triggered: bool."""

    # ── Classify intent via Claude ─────────────────────────────────────────────
    if not ANTHROPIC_API_KEY:
        # Graceful fallback when API key is missing
        if text.startswith('/report'):
            _invoke_report(chat_id, lam_client)
            return True
        send_message(chat_id, '\u274c ANTHROPIC_API_KEY not configured in Lambda env.')
        return False

    try:
        action, payload_str = classify_intent(text)
    except Exception as e:
        logger.error("classify_intent failed: %s", e)
        send_message(chat_id, f'\u274c Could not interpret request: {e}')
        return False

    # ── run_report ─────────────────────────────────────────────────────────────
    if action == 'run_report':
        _invoke_report(chat_id, lam_client)
        return True

    # ── reply ──────────────────────────────────────────────────────────────────
    if action == 'reply':
        try:
            send_message(chat_id, payload_str or '\U0001f914')
        except Exception as e:
            logger.error("send_message (reply) failed: %s", e)
        return False

    # ── modify_code ────────────────────────────────────────────────────────────
    if action == 'modify_code':
        summary = payload_str
        try:
            send_message(chat_id,
                f'\U0001f50d Fetching current code and generating change\u2026\n'
                f'_{summary}_')
            current_code = get_report_lambda_code(lam_client)
            new_code     = generate_modified_code(text, current_code)
            diff         = make_unified_diff(current_code, new_code)

            # Telegram message limit is 4096 chars; keep diff readable
            diff_preview = diff[:3200]
            if len(diff) > 3200:
                diff_preview += '\n\u2026 _(diff truncated)_'

            send_message(chat_id,
                f'\U0001f4dd *Applying change*: {summary}\n\n'
                f'```\n{diff_preview}\n```')

            apply_and_deploy(new_code, lam_client)
            send_message(chat_id, '\u2705 Deployed. Running report now\u2026')
            _invoke_report(chat_id, lam_client)
            return True

        except Exception as e:
            logger.error("modify_code failed: %s", e)
            send_message(chat_id, f'\u274c Failed to generate change: {e}')
            return False

    return False


# ── Polling loop ───────────────────────────────────────────────────────────────

def poll_once(lam_client, offset):
    """Poll Telegram once.  Returns (next_offset, report_triggered)."""
    now = int(time.time())
    try:
        result = tg_post('getUpdates', {
            'offset':          offset,
            'limit':           10,
            'timeout':         0,
            'allowed_updates': ['message'],
        })
    except Exception as e:
        logger.error("getUpdates failed: %s", e)
        return offset, False

    updates = result.get('result', [])
    if not updates:
        return offset, False

    next_offset      = max(upd['update_id'] for upd in updates) + 1
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
        logger.info("Message chat_id=%s age=%ds: %r", chat_id, age, text)

        if chat_id != TELEGRAM_CHAT_ID:
            continue

        # /help is handled locally; everything else flows through the agent
        if text.startswith('/start') or text.startswith('/help'):
            try:
                send_message(chat_id,
                    '\U0001f4ca *Daily Market Digest Bot*\n\n'
                    'Just write naturally \u2014 I understand plain English:\n'
                    '\u2022 _"Generate the report"_ or `/report`\n'
                    '\u2022 _"Extend backtest history to 2012 and re-run"_\n'
                    '\u2022 _"Add a crypto section to the report"_\n'
                    '\u2022 _"What data sources does the report use?"_\n'
                    '\u2022 `/help` \u2014 show this message')
            except Exception as e:
                logger.error("Failed to send help: %s", e)
            continue

        if handle_message(text, chat_id, lam_client):
            report_triggered = True
            break   # one action per poll cycle

    return next_offset, report_triggered


# ── Lambda entrypoint ──────────────────────────────────────────────────────────

def lambda_handler(event, context):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Telegram env vars not set")
        return

    # ── Generation check ───────────────────────────────────────────────────────
    # Each deploy stamps DEPLOY_ID into the env.  Any invocation whose
    # deploy_id doesn't match — including old chains with no deploy_id at all
    # — exits immediately, killing stale chains from previous deploys.
    event_deploy_id = event.get('deploy_id', '')
    if DEPLOY_ID and event_deploy_id != DEPLOY_ID:
        logger.info("Stale chain detected (event deploy_id=%r, current=%s) — stopping.",
                    event_deploy_id, DEPLOY_ID)
        return

    lam = boto3.client('lambda', region_name=REGION)

    offset = event.get('offset') or get_fresh_offset()

    logger.info("Starting loop: %d cycles × %ds  deploy_id=%s  offset=%d",
                CYCLES_PER_RUN, POLL_INTERVAL_S, DEPLOY_ID, offset)

    for cycle in range(CYCLES_PER_RUN):
        # Safety: if less than REINVOKE_BUFFER_MS remains, break now so the
        # self-reinvocation has time to complete before the Lambda times out.
        remaining_ms = context.get_remaining_time_in_millis()
        if remaining_ms < REINVOKE_BUFFER_MS:
            logger.info("Low time remaining (%dms) — breaking early to self-reinvoke.", remaining_ms)
            break

        logger.info("Cycle %d/%d (offset=%d)", cycle + 1, CYCLES_PER_RUN, offset)
        offset, report_triggered = poll_once(lam, offset)

        if report_triggered:
            # Sleep in small increments so we can bail out if time is running low
            slept = 0
            while slept < BUSY_WAIT_S:
                if context.get_remaining_time_in_millis() < REINVOKE_BUFFER_MS:
                    logger.info("Low time during busy wait (%dms left) — breaking early.",
                                context.get_remaining_time_in_millis())
                    break
                chunk = min(30, BUSY_WAIT_S - slept)
                time.sleep(chunk)
                slept += chunk
            logger.info("Busy mode over, resuming.")
        elif cycle < CYCLES_PER_RUN - 1:
            time.sleep(POLL_INTERVAL_S)

    payload = {'offset': offset, 'deploy_id': DEPLOY_ID}
    logger.info("Re-invoking self (offset=%d, deploy_id=%s)\u2026", offset, DEPLOY_ID)
    try:
        lam.invoke(
            FunctionName=context.function_name,
            InvocationType='Event',
            Payload=json.dumps(payload).encode(),
        )
        logger.info("Self-invocation scheduled")
    except Exception as e:
        logger.error("CRITICAL: self-invocation failed — polling will stop! %s", e)
        try:
            send_message(TELEGRAM_CHAT_ID,
                "\u26a0\ufe0f *Polling daemon stopped* \u2014 self-invocation failed.\n"
                "Contact admin to restart.")
        except Exception:
            pass
