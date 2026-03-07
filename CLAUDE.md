# DailyDigest Markets — Claude Context

## Credentials & Environment

All secrets live in `.env` in the project root. Load before running any script:

```bash
export $(grep -v '^#' .env | xargs)
```

`.env` contains:
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — IAM user `mzieba`, account `905418356298`, region `eu-north-1`
- `ANTHROPIC_API_KEY`
- `SENDER_EMAIL` / `RECIPIENT_EMAIL`
- Telegram credentials are passed explicitly on the command line (not in `.env`):
  - `TELEGRAM_BOT_TOKEN=8604889252:AAF-q8y62MyaBfCG7xqZXAnyn8V1CfpMOTE`
  - `TELEGRAM_CHAT_ID=7366508056`

Deploy command:
```bash
export $(grep -v '^#' .env | xargs) && \
TELEGRAM_BOT_TOKEN=8604889252:AAF-q8y62MyaBfCG7xqZXAnyn8V1CfpMOTE \
TELEGRAM_CHAT_ID=7366508056 \
python3 deploy_webhook.py
```

## AWS Resources

| Resource | Name / ARN |
|---|---|
| Region | `eu-north-1` |
| Account | `905418356298` |
| IAM role (shared) | `arn:aws:iam::905418356298:role/service-role/daily-trends-digest-role-9ru0fj04` |
| Report Lambda | `daily-trends-digest` (timeout 870 s) |
| Poller Lambda | `daily-digest-telegram-webhook` (timeout 900 s, reserved concurrency **1**) |
| CW log group | `/aws/lambda/daily-trends-digest` (stream `telegram-poller`) |

## Architecture

```
Telegram user
    │  /report
    ▼
daily-digest-telegram-webhook   ← self-scheduling poller (12 × 60 s per run)
    │  async invoke
    ▼
daily-trends-digest             ← report generator (~3-5 min)
    │  sendMessage
    ▼
Telegram user  (full briefing)
```

### Poller design notes
- **Reserved concurrency = 1** — only one instance ever runs simultaneously.
- **DEPLOY_ID** (uuid hex, stamped into env at each deploy) — every self-reinvocation carries the current `deploy_id`. If it doesn't match the env var, the invocation exits immediately, killing stale chains from previous deploys.
- **Two modes**:
  - *Normal*: polls Telegram every 60 s.
  - *Busy*: after triggering `/report`, sleeps `BUSY_WAIT_S` (300 s) before resuming — poller is unresponsive during report generation by design.
- `MAX_AGE_SECONDS = 180` — ignores messages older than 3 min (covers the busy-wait period).
- `get_fresh_offset()` — called on fresh starts (no offset in event) to skip the existing Telegram backlog.

## Key Files

| File | Purpose |
|---|---|
| `telegram_webhook_lambda.py` | Poller Lambda source |
| `deploy_webhook.py` | Packages + deploys the poller, sets concurrency, kicks off first run |
| `lambda_function.py` | Report Lambda source (main digest logic) |
| `.env` | All secrets (gitignored) |
