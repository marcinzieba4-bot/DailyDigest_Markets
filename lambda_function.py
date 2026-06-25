import json, boto3, urllib.request, re, os, logging, csv, io
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
import anthropic
import html as html_lib

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ANTHROPIC_API_KEY  = os.environ['ANTHROPIC_API_KEY']
SENDER_EMAIL       = os.environ['SENDER_EMAIL']
RECIPIENT_EMAIL    = os.environ['RECIPIENT_EMAIL']
REGION             = 'eu-north-1'
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID   = os.environ.get('TELEGRAM_CHAT_ID', '')
S3_BUCKET          = os.environ.get('S3_BUCKET', 's3bucketmz')

HEADERS        = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
FRESHNESS_DAYS = 7   # drop any RSS/Reddit item older than this

# ── HTTP helper ───────────────────────────────────────────────────────────────

def fetch_url(url, timeout=12):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='ignore')
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return ""

# ── Date helpers ──────────────────────────────────────────────────────────────

def parse_date(s):
    """Parse RSS (RFC 2822) or Atom (ISO 8601) date string → UTC datetime or None."""
    if not s:
        return None
    s = s.strip()
    if 'T' in s:
        try:
            dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    s = s.replace('GMT', '+0000')
    for fmt in ('%a, %d %b %Y %H:%M:%S %z', '%a, %d %b %Y %H:%M:%S +0000',
                '%d %b %Y %H:%M:%S %z', '%d %b %Y %H:%M:%S +0000'):
        try:
            dt = datetime.strptime(s, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None

def is_fresh(dt):
    if dt is None:
        return True   # no date → let through (better than blanket-dropping)
    return (datetime.now(timezone.utc) - dt).days < FRESHNESS_DAYS

# ── Source 1: X / Twitter trends ─────────────────────────────────────────────

def get_twitter_trends():
    html = fetch_url("https://trends24.in/united-states/")
    if not html:
        return []
    trends = re.findall(r'<a[^>]+class=trend-link>([^<]+)</a>', html)
    if not trends:
        trends = re.findall(r'<a[^>]+class="[^"]*trend-name[^"]*"[^>]*>([^<]+)</a>', html)
    result = [t.strip() for t in trends[:60] if t.strip()]
    logger.info(f"Twitter trends: {len(result)} items")
    return result

# ── Source 2: Reddit ──────────────────────────────────────────────────────────

def get_reddit_posts(subreddit, limit=25):
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}&raw_json=1"
    raw = fetch_url(url)
    if not raw:
        return []
    try:
        data  = json.loads(raw)
        posts = data['data']['children']
        cutoff = datetime.now(timezone.utc) - timedelta(days=FRESHNESS_DAYS)
        titles = []
        for p in posts:
            d = p['data']
            if d.get('stickied'):
                continue
            ts = d.get('created_utc', 0)
            if ts and datetime.fromtimestamp(ts, tz=timezone.utc) < cutoff:
                continue                       # too old
            age_h = int((datetime.now(timezone.utc).timestamp() - ts) / 3600) if ts else 0
            titles.append(f"{d['title']} [{age_h}h ago]")
        logger.info(f"r/{subreddit}: {len(titles)} fresh posts")
        return titles
    except Exception as e:
        logger.warning(f"Reddit parse error for {subreddit}: {e}")
        return []

# ── Source 3: RSS ─────────────────────────────────────────────────────────────

def get_rss_titles(url, max_items=20):
    raw = fetch_url(url)
    if not raw:
        return []
    try:
        root = ET.fromstring(raw)
        ns   = {'atom': 'http://www.w3.org/2005/Atom'}
        titles = []

        for item in root.findall('.//item'):
            if len(titles) >= max_items:
                break
            t = item.findtext('title', '').strip()
            if not t:
                continue
            dt = parse_date(item.findtext('pubDate', ''))
            if not is_fresh(dt):
                continue           # older than FRESHNESS_DAYS → drop
            tag = f" [{dt.strftime('%b %d')}]" if dt else ''
            titles.append(f"{t}{tag}")

        if not titles:
            for entry in root.findall('.//atom:entry', ns):
                if len(titles) >= max_items:
                    break
                t = entry.findtext('atom:title', '', ns).strip()
                if not t:
                    continue
                pub = (entry.findtext('atom:published', '', ns) or
                       entry.findtext('atom:updated',   '', ns))
                dt = parse_date(pub)
                if not is_fresh(dt):
                    continue
                tag = f" [{dt.strftime('%b %d')}]" if dt else ''
                titles.append(f"{t}{tag}")

        logger.info(f"RSS {url[:60]}: {len(titles)} fresh items")
        return titles
    except Exception as e:
        logger.warning(f"RSS parse error for {url}: {e}")
        return []

# ── Real-time market data: stooq (primary) + Yahoo Finance (fallback) ────────

# Ticker map: stooq_ticker → Yahoo Finance ticker
_YF_FALLBACK = {
    "dxy.f":   "DX=F",
    "^vix":    "^VIX",
    "10us.b":  "^TNX",    # Yahoo TNX = 10Y yield in %
    "2us.b":   "^IRX",    # Yahoo IRX = 13W T-bill, close enough for short rate
    "^spx":    "^GSPC",
    "^rut":    "^RUT",
    "^ndq":    "^NDX",
    "cl.f":    "CL=F",
    "hg.f":    "HG=F",
    "xauusd":  "GC=F",
    "btcusd":  "BTC-USD",
}

def _stooq_rows(ticker, days_back=35):
    d2  = datetime.utcnow().strftime('%Y%m%d')
    d1  = (datetime.utcnow() - timedelta(days=days_back)).strftime('%Y%m%d')
    url = f"https://stooq.com/q/d/l/?s={ticker}&d1={d1}&d2={d2}&i=d"
    raw = fetch_url(url)
    if not raw or 'no data' in raw.lower() or '<' in raw[:20]:
        return []
    try:
        rows = [r for r in csv.DictReader(io.StringIO(raw))
                if r.get('Date') and r.get('Close') and r['Close'].strip()]
        rows.sort(key=lambda r: r['Date'])
        return rows
    except Exception as e:
        logger.warning(f"Stooq parse error {ticker}: {e}")
        return []

def _yahoo_rows(yf_ticker, days_back=35):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_ticker}"
           f"?interval=1d&range=60d&includePrePost=false")
    yf_headers = {**HEADERS, 'Accept': 'application/json',
                  'Accept-Language': 'en-US,en;q=0.9'}
    try:
        req = urllib.request.Request(url, headers=yf_headers)
        with urllib.request.urlopen(req, timeout=12) as r:
            raw = r.read().decode('utf-8', errors='ignore')
    except Exception as e:
        logger.warning(f"Yahoo Finance fetch failed {yf_ticker}: {e}")
        return []
    try:
        data      = json.loads(raw)
        result    = data['chart']['result'][0]
        timestamps = result['timestamp']
        closes    = result['indicators']['quote'][0]['close']
        cutoff_ts = (datetime.utcnow() - timedelta(days=days_back)).timestamp()
        rows = []
        for ts, c in zip(timestamps, closes):
            if c is None or ts < cutoff_ts:
                continue
            rows.append({'Date': datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d'),
                         'Close': str(c)})
        rows.sort(key=lambda r: r['Date'])
        return rows
    except Exception as e:
        logger.warning(f"Yahoo Finance parse error {yf_ticker}: {e}")
        return []

def _get_rows(stooq_ticker, days_back=35):
    """Try stooq first; fall back to Yahoo Finance."""
    rows = _stooq_rows(stooq_ticker, days_back)
    if rows:
        return rows
    yf_ticker = _YF_FALLBACK.get(stooq_ticker)
    if yf_ticker:
        logger.info(f"Stooq empty for {stooq_ticker} — trying Yahoo {yf_ticker}")
        rows = _yahoo_rows(yf_ticker, days_back)
    if not rows:
        logger.warning(f"No data for {stooq_ticker} from any source")
    return rows

def _close(rows, idx):
    try:
        v = rows[idx].get('Close', '').strip()
        return float(v) if v else None
    except (IndexError, ValueError):
        return None

def _summary_line(stooq_ticker, label, days_back=35):
    rows = _get_rows(stooq_ticker, days_back)
    cur  = _close(rows, -1)
    ref  = _close(rows, max(0, len(rows) - 21))   # ~4 trading weeks back
    if cur is None:
        return f"{label}: n/a", None, None, None
    if ref and ref != 0:
        chg   = (cur - ref) / ref * 100
        arrow = '↑' if chg >= 0 else '↓'
        line  = f"{label}: {cur:.2f}  ({arrow}{abs(chg):.1f}% vs 4W ago)"
        return line, cur, ref, chg
    return f"{label}: {cur:.2f}", cur, ref, None

def compile_quant_snapshot():
    """Fetch live market data. Returns a formatted text block for prompt injection
    plus a dict of raw values for ratio calculations."""
    lines = ["=== LIVE QUANT SNAPSHOT (treat as current ground truth) ==="]
    raw_vals = {}   # stooq_ticker → (current, 4W_ref, 4W_chg_pct)

    def add(stooq_ticker, label):
        line, cur, ref, chg = _summary_line(stooq_ticker, label)
        lines.append(line)
        raw_vals[stooq_ticker] = (cur, ref, chg)

    add("dxy.f",   "DXY Dollar Index")
    add("^vix",    "VIX")
    add("10us.b",  "US 10Y Yield (%)")
    add("2us.b",   "US 2Y Yield (%)")
    add("^spx",    "S&P 500")
    add("^rut",    "Russell 2000")
    add("^ndq",    "Nasdaq 100")
    add("cl.f",    "WTI Crude Oil")
    add("hg.f",    "Copper")
    add("xauusd",  "Gold")
    add("btcusd",  "Bitcoin")

    # ── Derived ratios ────────────────────────────────────────────────────────

    # 10Y-2Y yield curve spread
    c10, c2 = raw_vals.get("10us.b", (None,))[0], raw_vals.get("2us.b", (None,))[0]
    if c10 and c2:
        spread_bps = (c10 - c2) * 100
        lines.append(f"10Y-2Y Spread: {spread_bps:+.0f}bps  "
                      f"({'normal' if spread_bps > 0 else 'INVERTED'})")
        raw_vals['yield_spread_bps'] = spread_bps

    # Gold / Copper ratio  (risk appetite proxy — low = growth optimism, high = fear)
    gold, copper = raw_vals.get("xauusd", (None,))[0], raw_vals.get("hg.f", (None,))[0]
    if gold and copper and copper != 0:
        gc_ratio = gold / copper
        # historical context: ratio >500 typically fear, <400 growth
        sentiment = "FEAR-elevated" if gc_ratio > 500 else ("growth-neutral" if gc_ratio > 400 else "GROWTH-optimistic")
        lines.append(f"Gold/Copper Ratio: {gc_ratio:.0f}  ({sentiment})")
        raw_vals['gold_copper_ratio'] = gc_ratio

    # Russell / Nasdaq ratio  (breadth vs concentration signal)
    rut_c, rut_r = raw_vals.get("^rut", (None, None))[:2]
    ndq_c, ndq_r = raw_vals.get("^ndq", (None, None))[:2]
    if rut_c and ndq_c and ndq_c != 0 and rut_r and ndq_r and ndq_r != 0:
        cur_ratio = rut_c / ndq_c
        ref_ratio = rut_r / ndq_r
        ratio_chg = (cur_ratio - ref_ratio) / ref_ratio * 100
        arrow     = '↑' if ratio_chg >= 0 else '↓'
        desc      = 'small-caps outperforming (breadth expanding)' if ratio_chg > 0 else 'mega-cap dominance (narrow market)'
        lines.append(f"Russell/Nasdaq Ratio: {arrow}{abs(ratio_chg):.1f}% vs 4W ago  ({desc})")
        raw_vals['rut_ndq_ratio_chg'] = ratio_chg

    # Oil / Copper ratio  (supply shock vs demand — spike = supply fear, not demand)
    oil, cop = raw_vals.get("cl.f", (None,))[0], raw_vals.get("hg.f", (None,))[0]
    if oil and cop and cop != 0:
        oc_ratio = oil / cop
        lines.append(f"Oil/Copper Ratio: {oc_ratio:.2f}  "
                      f"(rising = supply shock narrative; falling = demand-led commodity move)")
        raw_vals['oil_copper_ratio'] = oc_ratio

    # Gold / Bitcoin ratio  (convergence/divergence signal)
    gold_c, gold_ref = raw_vals.get("xauusd", (None, None))[:2]
    btc_c,  btc_ref  = raw_vals.get("btcusd", (None, None))[:2]
    if gold_c and btc_c and btc_c != 0:
        gb_ratio = gold_c / btc_c
        lines.append(f"Gold/BTC Ratio: {gb_ratio:.4f}  (lower = BTC outperforming gold as macro hedge)")
        # 4W divergence
        if gold_ref and btc_ref and btc_ref != 0:
            gold_chg = (gold_c - gold_ref) / gold_ref * 100
            btc_chg  = (btc_c  - btc_ref)  / btc_ref  * 100
            diverge  = gold_chg - btc_chg
            lines.append(f"Gold vs BTC 4W divergence: {diverge:+.1f}pp  "
                          f"({'Gold outrunning BTC — watch for convergence' if diverge > 10 else 'BTC outrunning Gold' if diverge < -10 else 'moving in sync'})")
            raw_vals['gold_btc_divergence_4w'] = diverge

    # VIX context
    vix_c, _, vix_chg = raw_vals.get("^vix", (None, None, None))
    if vix_c:
        regime = ("FEAR / potential capitulation" if vix_c > 25
                  else "ELEVATED" if vix_c > 18
                  else "COMPLACENCY — low hedging demand")
        lines.append(f"VIX Regime: {regime}  (current {vix_c:.1f})")

    lines.append("=== END QUANT SNAPSHOT ===")
    block = "\n".join(lines)
    logger.info(f"Quant snapshot compiled:\n{block}")
    return block

# ── Source 4: Stocktwits (real financial social content, no auth for public stream) ──

def get_stocktwits_trending():
    """Fetch trending messages from Stocktwits. Filters to last 48 hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    results = []
    # Trending stocks stream
    for url in [
        "https://api.stocktwits.com/api/2/streams/trending.json?limit=30",
        "https://api.stocktwits.com/api/2/streams/suggested.json?limit=20",
    ]:
        raw = fetch_url(url)
        if not raw:
            continue
        try:
            data = json.loads(raw)
            for msg in data.get('messages', []):
                dt = parse_date(msg.get('created_at', ''))
                if dt and dt < cutoff:
                    continue
                body = msg.get('body', '').strip()
                if len(body) < 40:
                    continue
                syms = [s.get('symbol', '') for s in msg.get('symbols', []) if s.get('symbol')]
                tag  = f" [${', $'.join(syms)}]" if syms else ''
                results.append(f"{body}{tag}")
        except Exception as e:
            logger.warning(f"Stocktwits parse error {url}: {e}")
    logger.info(f"Stocktwits: {len(results)} fresh messages")
    return results

# ── Aggregate all signals ─────────────────────────────────────────────────────

def compile_signals():
    signals = {}
    mon_yr  = datetime.utcnow().strftime('%B %Y')   # e.g. "February 2026"

    # Social
    signals['twitter_trends']      = get_twitter_trends()
    signals['reddit_investing']    = get_reddit_posts('investing')
    signals['reddit_stocks']       = get_reddit_posts('stocks')
    signals['reddit_wsb']          = get_reddit_posts('wallstreetbets', limit=15)
    signals['reddit_worldnews']    = get_reddit_posts('worldnews', limit=20)
    signals['reddit_geopolitics']  = get_reddit_posts('geopolitics', limit=15)
    signals['reddit_economics']    = get_reddit_posts('economics', limit=15)
    signals['reddit_crypto']       = get_reddit_posts('CryptoCurrency', limit=15)

    # General finance & macro
    signals['yahoo_finance']       = get_rss_titles('https://finance.yahoo.com/rss/topstories')
    signals['google_markets']      = get_rss_titles(
        'https://news.google.com/rss/search?q=stock+market+investing+economy&hl=en-US&gl=US&ceid=US:en')
    signals['google_macro']        = get_rss_titles(
        'https://news.google.com/rss/search?q=central+bank+inflation+geopolitics+commodities&hl=en-US&gl=US&ceid=US:en')

    # ── Quant indicator news feeds (month-scoped so Google returns fresh data) ─
    signals['ism_pmi']             = get_rss_titles(
        f'https://news.google.com/rss/search?q=ISM+manufacturing+services+PMI+{mon_yr}&hl=en-US&gl=US&ceid=US:en',
        max_items=8)
    signals['fed_liquidity']       = get_rss_titles(
        f'https://news.google.com/rss/search?q=Fed+balance+sheet+bank+reserves+QT+{mon_yr}&hl=en-US&gl=US&ceid=US:en',
        max_items=8)
    signals['credit_spreads']      = get_rss_titles(
        f'https://news.google.com/rss/search?q=high+yield+credit+spreads+HYG+investment+grade+{mon_yr}&hl=en-US&gl=US&ceid=US:en',
        max_items=8)
    signals['rig_count']           = get_rss_titles(
        f'https://news.google.com/rss/search?q=Baker+Hughes+rig+count+oil+drilling+{mon_yr}&hl=en-US&gl=US&ceid=US:en',
        max_items=6)

    # ── Central bank feeds ────────────────────────────────────────────────────
    signals['cb_fed']              = get_rss_titles(
        'https://news.google.com/rss/search?q=Federal+Reserve+FOMC+interest+rate+decision&hl=en-US&gl=US&ceid=US:en',
        max_items=10)
    signals['cb_ecb']              = get_rss_titles(
        'https://news.google.com/rss/search?q=ECB+European+Central+Bank+interest+rate+eurozone&hl=en-US&gl=US&ceid=US:en',
        max_items=10)
    signals['cb_boj']              = get_rss_titles(
        'https://news.google.com/rss/search?q=Bank+of+Japan+BOJ+rate+hike+yen&hl=en-US&gl=US&ceid=US:en',
        max_items=10)
    signals['cb_rba']              = get_rss_titles(
        'https://news.google.com/rss/search?q=Reserve+Bank+Australia+RBA+interest+rate&hl=en-US&gl=US&ceid=US:en',
        max_items=10)
    signals['cb_nbp_poland']       = get_rss_titles(
        'https://news.google.com/rss/search?q=Poland+NBP+interest+rate+zloty+inflation&hl=en-US&gl=US&ceid=US:en',
        max_items=10)
    signals['cb_pboc_china']       = get_rss_titles(
        'https://news.google.com/rss/search?q=PBOC+China+rate+cut+stimulus+yuan+RRR&hl=en-US&gl=US&ceid=US:en',
        max_items=10)

    # Sector-specific
    signals['google_semis']        = get_rss_titles(
        'https://news.google.com/rss/search?q=semiconductor+NVIDIA+TSMC+ASML+AVGO+AI+chips&hl=en-US&gl=US&ceid=US:en',
        max_items=15)
    signals['google_energy']       = get_rss_titles(
        'https://news.google.com/rss/search?q=oil+energy+crude+OPEC+natural+gas+rig+count&hl=en-US&gl=US&ceid=US:en',
        max_items=12)
    signals['google_euauto']       = get_rss_titles(
        'https://news.google.com/rss/search?q=European+auto+BMW+Volkswagen+Stellantis+EV&hl=en-US&gl=US&ceid=US:en',
        max_items=10)

    # Flows & EM
    signals['google_flows']        = get_rss_titles(
        'https://news.google.com/rss/search?q=capital+flows+dollar+DXY+emerging+markets+liquidity&hl=en-US&gl=US&ceid=US:en',
        max_items=12)

    # Crypto
    signals['google_crypto']       = get_rss_titles(
        'https://news.google.com/rss/search?q=bitcoin+ethereum+crypto+defi+stablecoin&hl=en-US&gl=US&ceid=US:en',
        max_items=15)
    signals['coindesk']            = get_rss_titles(
        'https://www.coindesk.com/arc/outboundfeeds/rss/', max_items=15)

    signals['stocktwits']          = get_stocktwits_trending()

    total = sum(len(v) for v in signals.values())
    logger.info(f"Total signals compiled: {total} items across {len(signals)} sources")
    return signals

# ── Claude helpers ────────────────────────────────────────────────────────────

def fmt(label, items):
    if not items:
        return ""
    return f"\n### {label}\n" + "\n".join(f"- {i}" for i in items)

# DATA INTEGRITY: no invented numbers
DATA_INTEGRITY_RULE = """
⚠️  DATA INTEGRITY — NON-NEGOTIABLE:
You MUST NOT state specific numeric values (interest rates, GDP %, CPI, index levels, price targets)
UNLESS that exact figure appears in the signal feed above OR in the QUANT SNAPSHOT.
Your training-data knowledge of rates/data is STALE and WILL be wrong.
Use qualitative language for anything not sourced from the feed:
  ✓ "in an active easing cycle after recent cuts"     ✗ "at 4.0%"
  ✓ "inflation trending toward target"                ✗ "CPI at 2.3%"
EXCEPTION: QUANT SNAPSHOT values (DXY, VIX, yields, etc.) are live — use them freely.
If genuinely uncertain about a figure, write "[verify current figure]" or omit it.
"""

# FRESHNESS: never treat past events as future
FRESHNESS_RULE = """
📅  FRESHNESS — ABSOLUTE RULE — TODAY'S DATE IS IN THE PROMPT HEADER:
Every news headline in the feed has a [Mon DD] date tag.
• Events whose date tag is ≤ today HAVE ALREADY HAPPENED — describe them in PAST TENSE.
  ✓ "following last week's State of the Union"     ✗ "ahead of the State of the Union"
  ✓ "after the NBP held rates at its last meeting" ✗ "NBP is expected to lower rates"
  ✓ "following the RBA's recent cut"               ✗ "the RBA is set to cut"
• NEVER call any event "upcoming" or "anticipated" unless the signal feed contains a headline
  explicitly dated in the FUTURE confirming that it has not yet occurred.
• Do NOT rely on your training-data memory for event calendars — those dates may be months or years stale.
• QUANT SNAPSHOT data is live — treat those figures as current ground truth.
"""

BREVITY_RULE = """
📏  BREVITY — CRITICAL FOR OUTPUT LIMITS:
• Items with NOTHING NEW today: 2 sentences maximum. Do not pad.
• Items with something NEW or STRUCTURAL: up to 8 sentences — earn every word.
• Never repeat the same idea in different words to fill space.
Maximum information density. Readers are professionals — skip the obvious.
"""

DIRECTION_INTEGRITY_RULE = """
🧭  DIRECTION ACCURACY — THIS IS A HARD RULE — NO EXCEPTIONS:
The QUANT SNAPSHOT encodes live price direction with an arrow: ↑ = rising, ↓ = falling vs 4 weeks ago.
BEFORE writing ANY directional statement about an asset, check its QUANT SNAPSHOT arrow.

YIELDS: If QUANT SNAPSHOT shows "US 10Y Yield: X.XX  (↑Y.Y% vs 4W ago)" → yields are RISING / SURGING / CLIMBING.
  ✓ Write: "with yields surging" / "as the 10Y climbs" / "in a rising-rate environment"
  ✗ NEVER write: "yields are declining" / "falling rates" / "rate relief" — if the arrow says ↑
If QUANT SNAPSHOT shows ↓ for yields → they are falling. Write accordingly.

Same rule applies to EVERY asset: DXY, Gold, Oil, S&P, BTC, VIX — arrow = ground truth.
If you write a direction that contradicts the QUANT SNAPSHOT arrow, it is a factual error.
When in doubt: quote the snapshot line verbatim and let the number speak.
"""

def call_claude(prompt_text, max_tokens=16000):
    import time
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    for attempt in range(5):
        try:
            msg = client.beta.messages.create(
                model="claude-opus-4-6",
                max_tokens=max_tokens,
                betas=["output-128k-2025-02-19"],
                messages=[{"role": "user", "content": prompt_text}]
            )
            text = msg.content[0].text
            logger.info(f"Claude call done — {len(text)} chars, stop_reason={msg.stop_reason}")
            if msg.stop_reason == "max_tokens":
                logger.warning("Still truncated at max_tokens — increase if needed")
            return text
        except anthropic.RateLimitError as e:
            wait = 60 * (attempt + 1)  # 60s, 120s, 180s, 240s, 300s
            logger.warning(f"Rate limit hit (attempt {attempt+1}/5) — waiting {wait}s: {e}")
            if attempt == 4:
                raise
            time.sleep(wait)

# ── Part 1: Geography + Sectors + Underowned ──────────────────────────────────

def analyze_part1(signals, today_str, quant_snapshot):
    raw = (
        fmt("X/Twitter Trending (US)",         signals.get('twitter_trends', []))
        + fmt("Reddit r/investing",             signals.get('reddit_investing', []))
        + fmt("Reddit r/stocks",                signals.get('reddit_stocks', []))
        + fmt("Reddit r/wallstreetbets",        signals.get('reddit_wsb', []))
        + fmt("Reddit r/worldnews",             signals.get('reddit_worldnews', []))
        + fmt("Reddit r/geopolitics",           signals.get('reddit_geopolitics', []))
        + fmt("Reddit r/economics",             signals.get('reddit_economics', []))
        + fmt("Yahoo Finance",                  signals.get('yahoo_finance', []))
        + fmt("Google News — Markets",          signals.get('google_markets', []))
        + fmt("Google News — Macro",            signals.get('google_macro', []))
        + fmt("ISM / PMI News",                 signals.get('ism_pmi', []))
        + fmt("Fed Balance Sheet / Liquidity",  signals.get('fed_liquidity', []))
        + fmt("Credit Spreads",                 signals.get('credit_spreads', []))
        + fmt("Rig Count / Drilling",           signals.get('rig_count', []))
        + fmt("CB Feed — US Fed / FOMC",        signals.get('cb_fed', []))
        + fmt("CB Feed — ECB / Eurozone",       signals.get('cb_ecb', []))
        + fmt("CB Feed — Bank of Japan",        signals.get('cb_boj', []))
        + fmt("CB Feed — RBA / Australia",      signals.get('cb_rba', []))
        + fmt("CB Feed — NBP / Poland",         signals.get('cb_nbp_poland', []))
        + fmt("CB Feed — PBOC / China",         signals.get('cb_pboc_china', []))
        + fmt("Google News — Semis & AI Chips", signals.get('google_semis', []))
        + fmt("Google News — Energy & Oil",     signals.get('google_energy', []))
        + fmt("Google News — European Auto",    signals.get('google_euauto', []))
        + fmt("Google News — Flows & Dollar",   signals.get('google_flows', []))
    )

    prompt = f"""You are a senior portfolio manager at a global macro hedge fund. Today is {today_str}.
You are inspired by capitalflowresearch.com — you think in terms of global liquidity cycles, cross-border capital flows, and how money moves across asset classes.
Be willing to take non-consensus or controversial views. When something is structurally NEW, write 5-8 sentences on it.

{DATA_INTEGRITY_RULE}
{FRESHNESS_RULE}
{BREVITY_RULE}
{DIRECTION_INTEGRITY_RULE}

{quant_snapshot}

RAW SIGNAL FEED (all items are ≤{FRESHNESS_DAYS} days old, each tagged [Mon DD]):
{raw}

---
Produce a clean HTML fragment (NO <html>/<body> tags). Complete ALL THREE sections below fully.

<h2 style="color:#1a1a2e;border-bottom:2px solid #1a73e8;padding-bottom:6px">🌍 Geographic Macro Overview</h2>

Cover EXACTLY these geographies. Never skip any.
For EACH write FOUR explicit labelled parts:
• Macro Stance — monetary direction, fiscal stance, key signals (qualitative only — no invented rate numbers)
• New / Most Important — what has materially CHANGED per the signal feed this week (use past tense for completed events)
• Playbook ✓ — what is going exactly as the consensus script predicts
• ⚠️ Divergence — what BREAKS from the playbook. If structural, write 5-8 sentences on the mechanic.

Block per geography:
<div style="margin-bottom:24px;padding:16px;background:#f8f9ff;border-left:5px solid #1a73e8;border-radius:4px">
  <h3 style="margin:0 0 10px">[Flag] [Country] &nbsp;<span style="font-size:13px;font-weight:normal;color:[#2d7a2d/#c0392b/#b07d00]">[Bullish/Bearish/Mixed]</span> &nbsp;<span style="font-size:12px;background:#e8f0fe;padding:2px 8px;border-radius:10px;color:#1a73e8">[↑↓→ rate direction]</span></h3>
  <p><strong>Macro Stance:</strong> ...</p>
  <p><strong>New / Most Important:</strong> ...</p>
  <p><strong>Playbook ✓:</strong> ... &nbsp;|&nbsp; <strong>⚠️ Divergence:</strong> ...</p>
</div>

Required geographies: 🇺🇸 United States · 🇪🇺 European Union · 🇨🇳 China · 🇯🇵 Japan · 🇦🇺 Australia · 🇵🇱 Poland · 🌏 EM (1-2 most interesting only, skip if nothing new)

<hr style="border:none;border-top:2px solid #eee;margin:28px 0">

<h2 style="color:#1a1a2e;border-bottom:2px solid #34a853;padding-bottom:6px">📊 Sector Deep Dive</h2>

Cover ALL sectors below — never skip any. Brief if quiet, but always include.
Sectors: XLK · XLC · XLF · XLE · XLI · XLY · XLP · XLV · XLB · XLRE · XLU · European Auto (SXAP) · US/Asia Semis (SOXX/ASML/TSMC)

For EACH write THREE labelled parts:
• Narrative — current consensus and direction
• New Angle / Innovator — name the non-obvious company that is the new lens for this sector. Say WHY.
• ⚡ Breaking Convention — any signal going against the standard narrative. If real, 4-6 sentences. If none: "None today."

Block per sector:
<div style="margin-bottom:18px;padding:14px;background:#f9fff9;border-left:4px solid #34a853;border-radius:4px">
  <h3 style="margin:0 0 8px">[Emoji] [Sector / ETF] &nbsp;<span style="font-size:13px;font-weight:normal;color:[#2d7a2d/#c0392b/#b07d00]">[Bullish/Bearish/Mixed]</span></h3>
  <p><strong>Narrative:</strong> ...</p>
  <p><strong>New Angle / Innovator:</strong> ...</p>
  <p>⚡ <strong>Breaking Convention:</strong> ...</p>
</div>

<hr style="border:none;border-top:2px solid #eee;margin:28px 0">

<h2 style="color:#1a1a2e;border-bottom:2px solid #f4b400;padding-bottom:6px">🔍 Underowned Themes — Active on X, Underweight in Portfolios</h2>

3-5 themes showing disproportionate social activity vs. institutional ownership. Early-mover setups.

<div style="margin-bottom:16px;padding:14px;background:#fffdf0;border-left:4px solid #f4b400;border-radius:4px">
  <h4 style="margin:0 0 6px">🔍 [Theme]</h4>
  <p><strong>Why underowned institutionally:</strong> ...</p>
  <p><strong>X signal:</strong> [High/Medium — what specifically is being discussed]</p>
  <p><strong>Instrument:</strong> [specific ETF, stock, or pair trade]</p>
</div>

"""

    logger.info("Calling Claude — Part 1 (Geo + Sectors + Underowned)")
    return call_claude(prompt, max_tokens=16000)

# ── Part 2: Crypto + Flows + Anticipatory + Stocks ───────────────────────────

def analyze_part2(signals, today_str, quant_snapshot):
    raw = (
        fmt("X/Twitter Trending (US)",         signals.get('twitter_trends', []))
        + fmt("Reddit r/CryptoCurrency",        signals.get('reddit_crypto', []))
        + fmt("Reddit r/investing",             signals.get('reddit_investing', []))
        + fmt("Reddit r/worldnews",             signals.get('reddit_worldnews', []))
        + fmt("Reddit r/economics",             signals.get('reddit_economics', []))
        + fmt("Yahoo Finance",                  signals.get('yahoo_finance', []))
        + fmt("Google News — Markets",          signals.get('google_markets', []))
        + fmt("Google News — Macro",            signals.get('google_macro', []))
        + fmt("Google News — Crypto",           signals.get('google_crypto', []))
        + fmt("CoinDesk",                       signals.get('coindesk', []))
        + fmt("Google News — Flows & Dollar",   signals.get('google_flows', []))
        + fmt("Fed Balance Sheet / Liquidity",  signals.get('fed_liquidity', []))
        + fmt("Credit Spreads",                 signals.get('credit_spreads', []))
        + fmt("CB Feed — US Fed / FOMC",        signals.get('cb_fed', []))
        + fmt("CB Feed — ECB / Eurozone",       signals.get('cb_ecb', []))
        + fmt("CB Feed — Bank of Japan",        signals.get('cb_boj', []))
        + fmt("CB Feed — PBOC / China",         signals.get('cb_pboc_china', []))
        + fmt("Google News — Energy & Oil",     signals.get('google_energy', []))
        + fmt("Google News — Semis & AI Chips", signals.get('google_semis', []))
    )

    prompt = f"""You are a senior portfolio manager at a global macro hedge fund. Today is {today_str}.
You are inspired by capitalflowresearch.com — global liquidity cycles, cross-border flows, how money moves across asset classes.
Be specific, contrarian where warranted, and detailed on anything structurally new.

{DATA_INTEGRITY_RULE}
{FRESHNESS_RULE}
{BREVITY_RULE}
{DIRECTION_INTEGRITY_RULE}

{quant_snapshot}

RAW SIGNAL FEED (all items are ≤{FRESHNESS_DAYS} days old, each tagged [Mon DD]):
{raw}

---
Produce a clean HTML fragment (NO <html>/<body> tags). Complete ALL FOUR sections fully.

<h2 style="color:#1a1a2e;border-bottom:2px solid #9c27b0;padding-bottom:6px">₿ Crypto & Digital Assets</h2>

Focus on what is NEW or STRUCTURALLY CHANGING — not just price action. Cover:
• Narrative shifts — what is the market repricing (BTC as macro hedge vs risk asset, ETH yield, etc.)
• New protocol/regulatory/institutional change that challenges current thinking
• Cross-asset correlations: BTC vs Nasdaq, stablecoin supply as liquidity signal
• Contrarian or underowned crypto narratives gaining early X traction
If structurally interesting: 5-8 sentences on mechanic and portfolio implications.
If truly nothing new: say so in 2 sentences.

<div style="margin-bottom:20px;padding:16px;background:#f5f0ff;border-left:5px solid #9c27b0;border-radius:4px">
  <h3 style="margin:0 0 10px">₿ Crypto & Digital Assets</h3>
  [content]
</div>

<hr style="border:none;border-top:2px solid #eee;margin:28px 0">

<h2 style="color:#1a1a2e;border-bottom:2px solid #e91e8c;padding-bottom:6px">💰 Capital Flows & Liquidity Framework</h2>

Structure around four pillars. Use QUANT SNAPSHOT values where relevant:
1. GLOBAL LIQUIDITY — G4 CB balance sheets direction. Use fed_liquidity feed. Expanding or contracting? What does it mean for risk asset multiples? (Global M2 leads risk assets by 6-12 months)
2. CROSS-BORDER FLOWS — DXY as the organizing variable (use QUANT SNAPSHOT DXY level + 4W change). Strong USD = EM stress = commodity headwind. Weak USD = EM relief, commodity tailwind, international equity outperformance.
3. ROTATION — bonds and equities falling together (liquidity event) vs moving inversely (normal rotation)? Use S&P + VIX + yield data from QUANT SNAPSHOT.
4. CROWDED TRADE RISK — 1-2 consensus positions that look vulnerable to unwinding

Embed 2-3 liquidity and flow models using ACTUAL QUANT SNAPSHOT numbers. Be creative:
Think about: Dollar carry unwind signals, EM liquidity traps, stablecoin supply as on-chain M2, credit leading equity, repo stress.
Format: "MODEL NAME: [Condition A: actual value ✓/✗] AND [Condition B: actual value ✓/✗] → [RISK-ON / RISK-OFF / MIXED] — [what to buy/sell]"

Examples of creative models here:
"DOLLAR CARRY UNWIND: DXY 4W change < -2% ✓ AND VIX falling ✓ AND EM bond spreads tightening → RISK-ON for EM and carry trades — long EEM, BRL, IDR"
"CREDIT LEADS EQUITY REVERSAL: HY spreads 4W widening > 50bps ✗ AND S&P 500 near highs → equities have NOT priced in credit stress yet — sell SPY, 2-week lead"
"GLOBAL LIQUIDITY EXPANSION: G4 CB balance sheets net expanding per news feed AND Gold rising AND BTC rising simultaneously → early liquidity cycle — RISK-ON across the board"

<div style="margin-bottom:20px;padding:16px;background:#fff0f8;border-left:5px solid #e91e8c;border-radius:4px">
  <h3 style="margin:0 0 10px">💰 Capital Flows & Liquidity</h3>
  [content with embedded models using live numbers]
</div>

<hr style="border:none;border-top:2px solid #eee;margin:28px 0">

<h2 style="color:#1a1a2e;border-bottom:2px solid #00b894;padding-bottom:6px">🔮 Anticipatory Positioning — Markets Pricing In Future Events</h2>

2-4 assets/sectors/pairs moving NOW in anticipation of something NOT YET happened.
Only include genuine forward-pricing signals visible in today's feed — not stale expectations from memory.
Pattern: defense stocks → front-running NATO spending; small-caps breadth → front-running rate cut; gold → CB diversification.

<div style="margin-bottom:16px;padding:14px;background:#f0fff4;border-left:4px solid #00b894;border-radius:4px">
  <h4 style="margin:0 0 6px">🔮 [Asset / Sector / Pair]</h4>
  <p><strong>What the market is pricing in:</strong> ...</p>
  <p><strong>Evidence from today's signals:</strong> ...</p>
  <p><strong>Anticipated timing:</strong> ...</p>
  <p><strong>Risk if wrong:</strong> ...</p>
</div>

<hr style="border:none;border-top:2px solid #eee;margin:28px 0">

<h2 style="color:#1a1a2e;border-bottom:2px solid #e67e22;padding-bottom:6px">⚡ High-Conviction Stock Catalysts</h2>

4-8 stocks with heavy buzz AND a specific near-term catalyst for a large move. Only concrete stories:
• Something concrete ABOUT TO HAPPEN (earnings, product launch, regulatory decision, contract, index inclusion, short squeeze)
• Structural repricing being priced in early (business model pivot, supply/demand shock)
• Crowd ahead of the street — retail and fintwit moving before analysts update
No generic "AI tailwinds". Mechanism-level specificity only.

<div style="margin-bottom:22px;padding:16px;background:#fff8f0;border-left:4px solid #e67e22;border-radius:4px">
  <h3 style="margin:0 0 6px"><code style="background:#ffe0b2;padding:2px 6px;border-radius:3px">$TICKER</code> &nbsp;[Company] &nbsp;<span style="font-size:13px;color:[#2d7a2d/#c0392b]">[↑/↓]</span></h3>
  <p><strong>What is happening:</strong> [specific mechanism, not vibes]</p>
  <p><strong>Catalyst / timing:</strong> ...</p>
  <p><strong>Risk:</strong> ...</p>
</div>

<p style="color:#aaa;font-size:11px;margin-top:24px">Signals: X/Twitter · Reddit · Yahoo Finance · Google News · CoinDesk · CB feeds · stooq live market data. Framework: capitalflowresearch.com. Not financial advice.</p>"""

    logger.info("Calling Claude — Part 2 (Crypto + Flows + Anticipatory + Stocks)")
    return call_claude(prompt, max_tokens=16000)

# ── Part 3: What Retail Is Playing ───────────────────────────────────────────

def analyze_part3(signals, today_str, quant_snapshot):
    raw = (
        fmt("Stocktwits — Trending Messages",        signals.get('stocktwits', []))
        + fmt("Reddit r/wallstreetbets",             signals.get('reddit_wsb', []))
        + fmt("Reddit r/investing",                  signals.get('reddit_investing', []))
        + fmt("Reddit r/stocks",                     signals.get('reddit_stocks', []))
        + fmt("Reddit r/CryptoCurrency",             signals.get('reddit_crypto', []))
        + fmt("X/Twitter Trending Topics",           signals.get('twitter_trends', []))
        + fmt("Google News — Markets",               signals.get('google_markets', []))
        + fmt("Yahoo Finance",                       signals.get('yahoo_finance', []))
        + fmt("Google News — Semis & AI Chips",      signals.get('google_semis', []))
        + fmt("Google News — Energy & Oil",          signals.get('google_energy', []))
    )

    prompt = f"""You are a market analyst specialising in retail investor behaviour and crowd psychology. Today is {today_str}.

{DATA_INTEGRITY_RULE}
{FRESHNESS_RULE}
{DIRECTION_INTEGRITY_RULE}

{quant_snapshot}

RAW SIGNAL FEED (social media, news — ≤{FRESHNESS_DAYS} days old):
{raw}

---
TASK: Identify "What Retail Is Playing Right Now" — the dominant popular-narrative trade of this moment.

Historical examples of this phenomenon (use these as a reference for the TYPE of thing you are looking for):
• Rheinmetall / European defense stocks in 2025 — narrative: NATO rearmament supercycle, Europe defence budget explosion
• Gold in 2025 — narrative: dollar debasement, central-bank buying, de-dollarisation
• Nvidia in 2023–2024 — narrative: AI infrastructure arms race, every company needs GPUs
• Tesla in 2019–2021 — narrative: EV disruption, Elon as visionary, short-squeeze fuel
• GameStop in Jan 2021 — narrative: retail vs Wall St hedge funds, short squeeze as protest
• Bitcoin in 2020–2021 — narrative: digital gold, institutional adoption, inflation hedge

You are looking for ONE asset or theme that RIGHT NOW is:
1. Visibly surging in price (confirmed by QUANT SNAPSHOT or news in the feed)
2. Generating high retail social buzz (visible in Stocktwits, Reddit, Twitter in the feed)
3. Anchored to a simple, emotionally compelling popular narrative that retail investors are repeating

Only identify assets with ACTUAL evidence in the feed or QUANT SNAPSHOT — do not invent.

Produce a clean HTML fragment starting with:

<h2 style="color:#1a1a2e;border-bottom:2px solid #ff6b35;padding-bottom:6px">🔥 What Retail Is Playing</h2>
<p style="color:#666;font-size:13px;margin-bottom:20px">The dominant popular-narrative trade capturing retail attention right now — analogous to Rheinmetall 2025, Gold 2025, Nvidia 2023, Tesla 2019.</p>

Then ONE main block for the #1 retail trade:

<div style="margin-bottom:28px;padding:20px;background:#fff8f5;border-left:6px solid #ff6b35;border-radius:4px">
  <h3 style="margin:0 0 12px;font-size:20px">[Asset Name / Ticker] &nbsp;<span style="font-size:14px;font-weight:normal;color:#ff6b35">[The Popular Narrative in 5-8 words]</span></h3>
  <p><strong>Why retail is here:</strong> [The emotional/narrative hook — what story are retail investors telling themselves? Why does this feel obvious and unstoppable to them? What is the simple thesis?]</p>
  <p><strong>What's driving the surge:</strong> [Specific catalysts and price action — use the QUANT SNAPSHOT number and direction arrow for this asset if available, plus relevant news from the feed]</p>
  <p><strong>The social signal:</strong> [What are Reddit / Stocktwits / Twitter actually saying right now? Specific language, recurring themes, sentiment visible in the feed]</p>
  <p><strong>Historical analog:</strong> [Which past retail mania this most resembles — explain the mechanical similarity, not just surface vibes]</p>
  <p><strong>Smart money view:</strong> [What institutional / professional money thinks — is the move justified by fundamentals, is it a bubble forming, or a genuine structural trend that both sides agree on?]</p>
  <p><strong>When the narrative breaks:</strong> [The specific event, data point, or price level that would kill this trade and trigger a violent reversal — be concrete]</p>
</div>

Then 2–3 secondary themes also getting meaningful retail attention (smaller blocks):

<div style="margin-bottom:14px;padding:14px;background:#fff8f5;border-left:3px solid #ff9a70;border-radius:4px">
  <h4 style="margin:0 0 6px">[Asset / Theme] &nbsp;<span style="font-size:12px;font-weight:normal;color:#888">[Narrative tag]</span></h4>
  <p>[2–3 sentences: what retail is saying, the narrative hook, and the key risk to the trade]</p>
</div>

No other text outside the HTML blocks."""

    logger.info("Calling Claude — Part 3 (What Retail Is Playing)")
    return call_claude(prompt, max_tokens=6000)

# ── PDF (matplotlib PdfPages) ──────────────────────────────────────────────────

def _parse_html_paragraphs(full_html):
    """Strip HTML tags and return list of (style, text) tuples.
    Styles: 'title', 'h1', 'h2', 'body', 'hr'
    """
    clean = re.sub(r'<style[^>]*>.*?</style>', '', full_html, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<script[^>]*>.*?</script>', '', clean, flags=re.DOTALL | re.IGNORECASE)

    tag_re = re.compile(r'<(/?)(\w+)[^>]*>', re.IGNORECASE)
    buf, paragraphs, in_skip, tag_stack = [], [], 0, []
    BLOCK_TAGS = {'p', 'div', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'td', 'th', 'blockquote'}

    def flush(tag='body'):
        text = html_lib.unescape(''.join(buf)).strip()
        buf.clear()
        if not text:
            return
        style = 'h1' if tag == 'h1' else ('h2' if tag in ('h2', 'h3', 'h4', 'h5') else 'body')
        paragraphs.append((style, text))

    for token in re.split(r'(<[^>]+>)', clean):
        m = tag_re.match(token)
        if m:
            tag, closing = m.group(2).lower(), m.group(1) == '/'
            if tag in ('head', 'style', 'script'):
                in_skip += -1 if closing else 1
            elif in_skip > 0:
                pass
            elif not closing:
                tag_stack.append(tag)
                if tag == 'hr':
                    flush(); paragraphs.append(('hr', ''))
                elif tag == 'br':
                    buf.append('\n')
            else:
                if tag_stack and tag_stack[-1] == tag:
                    tag_stack.pop()
                if tag in BLOCK_TAGS:
                    flush(tag)
        elif in_skip == 0:
            buf.append(token)

    flush()
    return paragraphs


def _sanitize_for_mpl(text):
    """Escape matplotlib math-mode triggers and drop characters DejaVu Sans can't render."""
    # Strip supplementary-plane characters (emojis, etc. — codepoint > U+FFFF)
    text = ''.join(c if ord(c) <= 0xFFFF else '' for c in text)
    # Escape $ so matplotlib doesn't treat it as a math-mode delimiter
    text = text.replace('$', r'\$')
    return text


def _html_to_pdf_bytes(full_html, today_str):
    """Render the report HTML to PDF bytes using matplotlib PdfPages."""
    import textwrap
    from io import BytesIO
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib.backends.backend_pdf import PdfPages
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    # ── design tokens ────────────────────────────────────────────────────────
    C_BG     = '#0d1117'
    C_TITLE  = '#e6edf3'
    C_H1     = '#4fc3f7'
    C_H2     = '#81d4a0'
    C_BODY   = '#c9d1d9'
    C_MUTED  = '#8b949e'
    C_RULE   = '#30363d'
    C_ACCENT = '#1a73e8'

    PAGE_W, PAGE_H = 8.5, 11.0   # inches
    MX, MT, MB = 0.75, 0.70, 0.55
    TEXT_W_IN = PAGE_W - 2 * MX
    TEXT_H_IN = PAGE_H - MT - MB

    # ── font sizes → approximate line heights in axes-fraction coords ─────────
    # 1 inch = 72 pt; at PAGE_H inches tall, 1pt ≈ 1/(PAGE_H*72) figure-height
    # We express y in data-units 0..PAGE_H
    FS = {'title': 16, 'h1': 12, 'h2': 10, 'body': 8.5}
    LH = {'title': 0.26, 'h1': 0.22, 'h2': 0.19, 'body': 0.155}   # inches per line
    GAP = {'title': 0.20, 'h1': 0.18, 'h2': 0.10, 'body': 0.06, 'hr': 0.18}

    # Characters that fit across TEXT_W_IN at each font size
    # Empirical: DejaVu Sans ≈ 0.055 in/char at 9pt → scale proportionally
    def chars_per_line(style):
        base_pt = 9; base_cpl = 100
        return max(30, int(base_cpl * base_pt / FS.get(style, base_pt)))

    paragraphs = _parse_html_paragraphs(full_html)

    # ── helper: wrap a paragraph into lines, return list[str] ────────────────
    def wrap(text, style):
        lines = []
        for raw_line in text.split('\n'):
            stripped = raw_line.strip()
            if not stripped:
                lines.append('')
                continue
            lines.extend(textwrap.wrap(stripped, chars_per_line(style)) or [stripped])
        return lines or ['']

    # ── pre-compute line-sets per paragraph ──────────────────────────────────
    items = []   # list of (style, lines_list)
    for style, text in paragraphs:
        if style == 'hr':
            items.append(('hr', []))
        else:
            items.append((style, wrap(text, style)))

    # ── paginate ─────────────────────────────────────────────────────────────
    def paragraph_height(style, lines):
        if style == 'hr':
            return GAP['hr']
        return len(lines) * LH.get(style, LH['body']) + GAP.get(style, GAP['body'])

    pages = []   # list of list of (style, lines)
    cur_page, cur_y = [], TEXT_H_IN

    for style, lines in items:
        h = paragraph_height(style, lines)
        if h > TEXT_H_IN:
            # very long paragraph: split across pages
            if cur_page:
                pages.append(cur_page); cur_page = []; cur_y = TEXT_H_IN
            # chunk lines into pages
            if style != 'hr':
                chunk = []
                chunk_h = GAP.get(style, GAP['body'])
                for ln in lines:
                    lh = LH.get(style, LH['body'])
                    if chunk_h + lh > TEXT_H_IN and chunk:
                        pages.append([(style, chunk)])
                        chunk = []; chunk_h = GAP.get(style, GAP['body'])
                    chunk.append(ln); chunk_h += lh
                if chunk:
                    cur_page = [(style, chunk)]; cur_y = TEXT_H_IN - chunk_h
            continue

        if h > cur_y and cur_page:
            pages.append(cur_page); cur_page = []; cur_y = TEXT_H_IN

        cur_page.append((style, lines))
        cur_y -= h

    if cur_page:
        pages.append(cur_page)

    # ── render ────────────────────────────────────────────────────────────────
    buf = BytesIO()
    with PdfPages(buf) as pdf:
        total_pages = len(pages)
        for page_idx, page_items in enumerate(pages):
            fig = plt.figure(figsize=(PAGE_W, PAGE_H), facecolor=C_BG)
            ax  = fig.add_axes([0, 0, 1, 1], facecolor=C_BG)
            ax.set_xlim(0, PAGE_W); ax.set_ylim(0, PAGE_H); ax.axis('off')

            # ── top accent bar ────────────────────────────────────────────────
            ax.add_patch(mpatches.FancyBboxPatch(
                (0, PAGE_H - 0.06), PAGE_W, 0.06,
                boxstyle='square,pad=0', facecolor=C_ACCENT, linewidth=0))

            # ── header: title + date on page 1 ───────────────────────────────
            if page_idx == 0:
                ax.text(MX, PAGE_H - MT, 'Market Intelligence Briefing',
                        color=C_TITLE, fontsize=18, fontweight='bold',
                        va='top', ha='left', fontfamily='DejaVu Sans')
                ax.text(MX, PAGE_H - MT - 0.30, _sanitize_for_mpl(today_str) + '  ·  Macro  ·  Sectors  ·  Flows  ·  Crypto  ·  Quant',
                        color=C_MUTED, fontsize=8, va='top', ha='left', fontfamily='DejaVu Sans')
                # underline
                ax.plot([MX, PAGE_W - MX], [PAGE_H - MT - 0.52, PAGE_H - MT - 0.52],
                        color=C_ACCENT, linewidth=0.8)
                content_top = PAGE_H - MT - 0.65
            else:
                content_top = PAGE_H - MT + 0.05

            # ── body content ──────────────────────────────────────────────────
            y = content_top
            for style, lines in page_items:
                if style == 'hr':
                    mid = y - GAP['hr'] / 2
                    ax.plot([MX, PAGE_W - MX], [mid, mid], color=C_RULE, linewidth=0.4, alpha=0.7)
                    y -= GAP['hr']
                    continue

                # top gap before heading
                if style in ('h1', 'h2', 'title'):
                    y -= GAP.get(style, 0.10) * 0.5

                color = {'h1': C_H1, 'h2': C_H2, 'title': C_TITLE}.get(style, C_BODY)
                fs    = FS.get(style, FS['body'])
                bold  = style in ('h1', 'h2', 'title')
                lh    = LH.get(style, LH['body'])

                for ln in lines:
                    ax.text(MX, y, _sanitize_for_mpl(ln),
                            color=color, fontsize=fs,
                            fontweight='bold' if bold else 'normal',
                            va='top', ha='left', fontfamily='DejaVu Sans',
                            clip_on=True)
                    y -= lh

                y -= GAP.get(style, GAP['body'])

            # ── footer: page number ───────────────────────────────────────────
            ax.text(PAGE_W / 2, MB - 0.30, f'Page {page_idx + 1} / {total_pages}',
                    color=C_MUTED, fontsize=7, va='bottom', ha='center',
                    fontfamily='DejaVu Sans')
            ax.plot([MX, PAGE_W - MX], [MB - 0.15, MB - 0.15],
                    color=C_RULE, linewidth=0.3)

            pdf.savefig(fig, facecolor=C_BG, dpi=150)
            plt.close(fig)

    return buf.getvalue()


REPORTS_PREFIX = 'reports'

def save_html_to_s3(full_html):
    """Publish the report as a static HTML page to S3 (served via CloudFront) and
    rebuild the archive index. Non-fatal on failure."""
    try:
        s3 = boto3.client('s3', region_name=REGION)
        date_str = datetime.now().strftime('%Y-%m-%d')
        archive_key = f"{REPORTS_PREFIX}/archive/{date_str}.html"
        s3.put_object(Bucket=S3_BUCKET, Key=archive_key, Body=full_html.encode('utf-8'), ContentType='text/html')
        s3.put_object(Bucket=S3_BUCKET, Key=f"{REPORTS_PREFIX}/latest.html", Body=full_html.encode('utf-8'), ContentType='text/html')
        logger.info(f"HTML report saved → s3://{S3_BUCKET}/{archive_key}")

        keys = sorted({
            obj['Key'].rsplit('/', 1)[-1].replace('.html', '')
            for obj in s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=f"{REPORTS_PREFIX}/archive/").get('Contents', [])
        }, reverse=True)

        rows = '\n'.join(
            f'  <li><a href="archive/{d}.html">{d}</a></li>' for d in keys
        )
        index_html = f"""<html>
<head><meta charset="utf-8"><title>Market Intelligence Briefing — Archive</title></head>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:40px auto;color:#222">
  <h1 style="color:#1a1a2e">Market Intelligence Briefing</h1>
  <p><a href="latest.html">View latest report</a></p>
  <h2>Archive</h2>
  <ul style="line-height:1.8">
{rows}
  </ul>
</body>
</html>"""
        s3.put_object(Bucket=S3_BUCKET, Key=f"{REPORTS_PREFIX}/index.html", Body=index_html.encode('utf-8'), ContentType='text/html')
        logger.info(f"Archive index rebuilt — {len(keys)} reports")
    except Exception as e:
        logger.error(f"save_html_to_s3 failed (non-fatal): {e}", exc_info=True)


def save_pdf_to_s3(full_html, today_str):
    """Render report as a multi-page PDF via matplotlib PdfPages and upload to S3."""
    try:
        pdf_bytes = _html_to_pdf_bytes(full_html, today_str)
        key = f"Strategies/{datetime.now().strftime('%Y-%m-%d')}_Market_Intelligence.pdf"
        s3 = boto3.client('s3', region_name=REGION)
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=pdf_bytes, ContentType='application/pdf')
        logger.info(f"PDF saved → s3://{S3_BUCKET}/{key}  ({len(pdf_bytes):,} bytes)")
    except Exception as e:
        logger.error(f"save_pdf_to_s3 failed (non-fatal): {e}", exc_info=True)

    # Also save a machine-readable JSON version
    try:
        paragraphs = _parse_html_paragraphs(full_html)
        sections, current = [], None
        for style, text in paragraphs:
            if style == 'h1':
                current = {'heading': text, 'subheadings': [], 'body': []}
                sections.append(current)
            elif style == 'h2':
                if current is None:
                    current = {'heading': '', 'subheadings': [], 'body': []}
                    sections.append(current)
                current['subheadings'].append(text)
            elif style == 'body' and text:
                if current is None:
                    current = {'heading': '', 'subheadings': [], 'body': []}
                    sections.append(current)
                current['body'].append(text)
            # 'hr' ignored — just a visual separator

        payload = {
            'date': today_str,
            'generated_at': datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
            'sections': sections,
        }
        json_key = f"Strategies/json/{datetime.now().strftime('%Y-%m-%d')}_Market_Intelligence.json"
        s3 = boto3.client('s3', region_name=REGION)
        s3.put_object(
            Bucket=S3_BUCKET, Key=json_key,
            Body=json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8'),
            ContentType='application/json',
        )
        logger.info(f"JSON saved → s3://{S3_BUCKET}/{json_key}  ({len(sections)} sections)")
    except Exception as e:
        logger.error(f"save JSON to S3 failed (non-fatal): {e}", exc_info=True)


# ── Email ─────────────────────────────────────────────────────────────────────

RECIPIENT_EMAILS = [RECIPIENT_EMAIL, 'marcin.zieba4@gmail.com']

def send_email(html_part1, html_part2, html_part3):
    logger.info(f"Sending email — Source: {SENDER_EMAIL} | To: {RECIPIENT_EMAILS}")
    ses = boto3.client('ses', region_name=REGION)

    try:
        quota = ses.get_send_quota()
        logger.info(f"SES quota — Max24H: {quota.get('Max24HourSend')}, Sent: {quota.get('SentLast24Hours')}")
        attrs = ses.get_identity_verification_attributes(Identities=[SENDER_EMAIL] + RECIPIENT_EMAILS)
        for addr, info in attrs.get('VerificationAttributes', {}).items():
            logger.info(f"SES verification — {addr}: {info.get('VerificationStatus')}")
    except Exception as e:
        logger.warning(f"SES pre-check failed (non-fatal): {e}")

    today = datetime.now().strftime('%A, %B %d %Y')
    full_html = f"""<html>
<body style="font-family:Arial,sans-serif;max-width:820px;margin:auto;padding:24px;color:#222;line-height:1.6">
  <h1 style="color:#1a1a2e;margin-bottom:4px">Market Intelligence Briefing</h1>
  <p style="color:#888;margin-top:0">{today} &mdash; Macro · Sectors · Flows · Crypto</p>
  <hr style="border:none;border-top:3px solid #1a73e8;margin:16px 0 24px">
  {html_part1}
  <hr style="border:none;border-top:3px solid #9c27b0;margin:32px 0 24px">
  {html_part2}
  <hr style="border:none;border-top:3px solid #ff6b35;margin:32px 0 24px">
  {html_part3}
  <hr style="border:none;border-top:1px solid #ddd;margin:24px 0 12px">
  <p style="color:#aaa;font-size:11px">Powered by AWS Lambda + Claude Opus &mdash; for informational purposes only, not financial advice.</p>
</body>
</html>"""

    try:
        response = ses.send_email(
            Source=SENDER_EMAIL,
            Destination={'ToAddresses': RECIPIENT_EMAILS},
            Message={
                'Subject': {'Data': f'Market Intelligence — {today}'},
                'Body': {'Html': {'Data': full_html}, 'Text': {'Data': 'Open in HTML mode.'}}
            }
        )
        logger.info(f"SES send_email succeeded — MessageId: {response.get('MessageId')}")
    except ses.exceptions.MessageRejected as e:
        logger.error(f"SES MessageRejected: {e}")
        raise
    except ses.exceptions.MailFromDomainNotVerifiedException as e:
        logger.error(f"SES MailFromDomainNotVerified — check SENDER_EMAIL is verified: {e}")
        raise
    except Exception as e:
        logger.error(f"SES send_email failed — {type(e).__name__}: {e}")
        raise
    return full_html

# ── Telegram ──────────────────────────────────────────────────────────────────

def send_telegram(html_part1, html_part2, html_part3):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.info("Telegram not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing) — skipping")
        return

    today = datetime.now().strftime('%A, %B %d %Y')
    full_html = f"""<html>
<body style="font-family:Arial,sans-serif;max-width:820px;margin:auto;padding:24px;color:#222;line-height:1.6">
  <h1 style="color:#1a1a2e;margin-bottom:4px">Market Intelligence Briefing</h1>
  <p style="color:#888;margin-top:0">{today} &mdash; Macro &middot; Sectors &middot; Flows &middot; Crypto</p>
  <hr style="border:none;border-top:3px solid #1a73e8;margin:16px 0 24px">
  {html_part1}
  <hr style="border:none;border-top:3px solid #9c27b0;margin:32px 0 24px">
  {html_part2}
  <hr style="border:none;border-top:3px solid #ff6b35;margin:32px 0 24px">
  {html_part3}
  <hr style="border:none;border-top:1px solid #ddd;margin:24px 0 12px">
  <p style="color:#aaa;font-size:11px">Powered by AWS Lambda + Claude Opus &mdash; for informational purposes only, not financial advice.</p>
</body>
</html>"""

    base = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

    # 1 — brief intro message
    intro = (
        f"\U0001f4ca *Market Intelligence Briefing*\n"
        f"{today}\n\n"
        f"_Macro \u00b7 Sectors \u00b7 Flows \u00b7 Crypto_\n\n"
        f"Full report attached \U0001f447"
    )
    try:
        msg_body = json.dumps({'chat_id': TELEGRAM_CHAT_ID, 'text': intro, 'parse_mode': 'Markdown'}).encode()
        req = urllib.request.Request(
            f"{base}/sendMessage",
            data=msg_body,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        urllib.request.urlopen(req, timeout=15)
        logger.info("Telegram intro message sent")
    except Exception as e:
        logger.warning(f"Telegram sendMessage failed: {e}")

    # 2 — send the HTML report as a document
    filename = f"market_briefing_{datetime.now().strftime('%Y-%m-%d')}.html"
    html_bytes = full_html.encode('utf-8')
    boundary = b'TgBoundaryMarketDigest7890'

    def _field(name, value):
        return (
            b'--' + boundary + b'\r\n'
            b'Content-Disposition: form-data; name="' + name.encode() + b'"\r\n\r\n'
            + str(value).encode() + b'\r\n'
        )

    def _file_field(name, fname, content):
        return (
            b'--' + boundary + b'\r\n'
            b'Content-Disposition: form-data; name="' + name.encode() +
            b'"; filename="' + fname.encode() + b'"\r\n'
            b'Content-Type: text/html\r\n\r\n'
            + content + b'\r\n'
        )

    body = (
        _field('chat_id', TELEGRAM_CHAT_ID)
        + _field('caption', f"Market Briefing — {today}")
        + _file_field('document', filename, html_bytes)
        + b'--' + boundary + b'--\r\n'
    )

    try:
        req = urllib.request.Request(
            f"{base}/sendDocument",
            data=body,
            headers={'Content-Type': f'multipart/form-data; boundary={boundary.decode()}'},
            method='POST'
        )
        urllib.request.urlopen(req, timeout=60)
        logger.info("Telegram document sent successfully")
    except Exception as e:
        logger.error(f"Telegram sendDocument failed: {e}")

# ── Handler ───────────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    logger.info("Lambda started")
    try:
        signals        = compile_signals()
        quant_snapshot = compile_quant_snapshot()

        total = sum(len(v) for v in signals.values())
        if total == 0:
            logger.error("No signals collected — aborting")
            return {'statusCode': 500, 'body': 'No signals collected'}

        today_str  = datetime.now().strftime('%A, %B %d %Y')
        html_part1 = analyze_part1(signals, today_str, quant_snapshot)
        html_part2 = analyze_part2(signals, today_str, quant_snapshot)
        html_part3 = analyze_part3(signals, today_str, quant_snapshot)

        full_html = send_email(html_part1, html_part2, html_part3)
        save_pdf_to_s3(full_html, today_str)
        save_html_to_s3(full_html)
        send_telegram(html_part1, html_part2, html_part3)
        logger.info("All done successfully")
        return {'statusCode': 200, 'body': f'Sent digest with {total} raw signals'}
    except Exception as e:
        logger.exception(f"Unhandled error: {e}")
        raise
