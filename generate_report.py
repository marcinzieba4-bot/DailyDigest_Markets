"""
Run DailyDigest_Markets report locally and save to HTML file.
Usage: python3 generate_report.py
"""
import os, sys

# Load API key from Claude Code session token
TOKEN_FILE = "/home/claude/.claude/remote/.session_ingress_token"
with open(TOKEN_FILE) as f:
    api_key = f.read().strip()

# Set a placeholder API key so lambda_function.py imports without error;
# the actual auth is done via auth_token (Bearer) in the patched call_claude below.
os.environ.setdefault("ANTHROPIC_API_KEY", "placeholder-not-used")
os.environ.setdefault("SENDER_EMAIL", "no-reply@example.com")
os.environ.setdefault("RECIPIENT_EMAIL", "report@example.com")

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("generate_report")

# Import lambda module (env vars already set above)
import lambda_function as lf

# Patch call_claude to use auth_token (OAuth bearer) instead of api_key.
# Must temporarily unset ANTHROPIC_API_KEY so the SDK doesn't send both
# X-Api-Key (placeholder) and Authorization (bearer) — the server rejects
# requests that contain an invalid X-Api-Key even when Bearer is valid.
import anthropic as _anthropic
def _patched_call_claude(prompt_text, max_tokens=16000):
    saved = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        client = _anthropic.Anthropic(auth_token=api_key)
        msg = client.beta.messages.create(
            model="claude-opus-4-6",
            max_tokens=max_tokens,
            betas=["output-128k-2025-02-19"],
            messages=[{"role": "user", "content": prompt_text}]
        )
    finally:
        if saved is not None:
            os.environ["ANTHROPIC_API_KEY"] = saved
    text = msg.content[0].text
    logger.info(f"Claude call done — {len(text)} chars, stop_reason={msg.stop_reason}")
    return text

lf.call_claude = _patched_call_claude

from datetime import datetime, timezone

def main():
    today = datetime.now(timezone.utc).strftime("%A, %B %-d, %Y")
    logger.info("=== DailyDigest Markets Report Generation ===")
    logger.info(f"Date: {today}")

    logger.info("Step 1/3: Compiling quant snapshot...")
    quant_snapshot = lf.compile_quant_snapshot()
    logger.info(f"Quant snapshot: {len(quant_snapshot)} chars")

    logger.info("Step 2/3: Compiling signals...")
    signals = lf.compile_signals()
    logger.info(f"Signals keys: {list(signals.keys())}")

    logger.info("Step 3/3: Generating report parts via Claude...")
    logger.info("  - Part 1: Geographic + Sectors + Quant models...")
    part1 = lf.analyze_part1(signals, today, quant_snapshot)
    logger.info(f"  Part 1 done: {len(part1)} chars")

    logger.info("  - Part 2: Crypto + Flows + Stocks...")
    part2 = lf.analyze_part2(signals, today, quant_snapshot)
    logger.info(f"  Part 2 done: {len(part2)} chars")

    logger.info("  - Part 3: Fintwit takes...")
    part3 = lf.analyze_part3(signals, today, quant_snapshot)
    logger.info(f"  Part 3 done: {len(part3)} chars")

    logger.info("  - Part 4: Retail narratives...")
    part4 = lf.analyze_part4(signals, today, quant_snapshot)
    logger.info(f"  Part 4 done: {len(part4)} chars")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DailyDigest Markets — {today}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          max-width: 900px; margin: 0 auto; padding: 20px; background: #f5f5f5; color: #222; }}
  h1   {{ color: #1a1a2e; border-bottom: 3px solid #e94560; padding-bottom: 10px; }}
  .meta {{ color: #666; font-size: 0.9em; margin-bottom: 30px; }}
  .quant {{ background: #1a1a2e; color: #eee; padding: 15px 20px; border-radius: 8px;
            font-family: monospace; white-space: pre-wrap; font-size: 0.85em; margin-bottom: 30px; }}
  .part  {{ background: white; border-radius: 8px; padding: 5px 15px;
            box-shadow: 0 2px 8px rgba(0,0,0,.08); margin-bottom: 20px; }}
</style>
</head>
<body>
<h1>📊 DailyDigest Markets</h1>
<div class="meta">Generated: {today} &nbsp;|&nbsp; Powered by Claude Opus 4.6</div>

<div class="quant"><strong>QUANT SNAPSHOT</strong>
{quant_snapshot}</div>

<div class="part">{part1}</div>
<div class="part">{part2}</div>
<div class="part">{part3}</div>
<div class="part">{part4}</div>

</body>
</html>"""

    out_file = f"report_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.html"
    with open(out_file, "w", encoding="utf-8") as fh:
        fh.write(html)
    logger.info(f"Report saved → {out_file} ({len(html):,} bytes)")
    return out_file

if __name__ == "__main__":
    out = main()
    print(f"\nDone! Report written to: {out}")
