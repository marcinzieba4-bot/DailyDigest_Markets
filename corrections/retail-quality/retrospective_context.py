"""Read-only editorial memory for retrospective writing; no live-handler changes."""
import re
import html as html_lib
from datetime import datetime, timedelta
REPORTS_PREFIX = "reports"
S3_BUCKET = "s3bucketmz"
RETROSPECTIVE_SELECTION_RULE = 'For a retrospective report, select from its own eligible dated evidence and earlier editorial history only. A persistent theme may remain when its catalyst, reaction or attention meaningfully changes. A new price or subtitle alone does not justify another full essay. Shorten unchanged carryovers. Do not impose ticker quotas or infer a measured retail ranking from price/news. Compare prior selections chronologically before publication; never use later-month popularity or performance to select an earlier report.'

def _load_recent_retail_history(today_str, s3=None, max_reports=5, lookback_days=14):
    """Read prior retail selections as editorial memory, never future facts.

    Uses existing archive objects, no writes or downstream report invocation.
    A genuine archive-read failure is surfaced rather than silently dropping
    the cross-day context. Missing dates (weekends/first run) are ordinary.
    """
    report_date = None
    for pattern in ('%A, %B %d %Y', '%A, %B %d, %Y', '%Y-%m-%d'):
        try:
            report_date = datetime.strptime(today_str, pattern).date()
            break
        except ValueError:
            pass
    if report_date is None:
        raise ValueError('Retail history requires an unambiguous report date')
    if s3 is None:
        raise ValueError('Pass the explicitly configured read-only archive client')
    history = []
    for offset in range(1, lookback_days + 1):
        day = report_date - timedelta(days=offset)
        key = f"{REPORTS_PREFIX}/archive/{day.isoformat()}.html"
        try:
            response = s3.get_object(Bucket=S3_BUCKET, Key=key)
            try:
                previous = response['Body'].read().decode('utf-8')
            finally:
                response['Body'].close()
        except Exception as error:
            code = getattr(error, 'response', {}).get('Error', {}).get('Code')
            if code in ('404', 'NoSuchKey', 'NotFound'):
                continue
            raise RuntimeError('Cannot read prior retail selection history') from error
        start = re.search(r'<h2\b[^>]*>[^<]*What Retail Is Playing.*?</h2>', previous, flags=re.I | re.S)
        if not start:
            continue
        section = previous[start.end():]
        end = re.search(r'<h2\b|<footer\b|<details\b', section, flags=re.I)
        if end:
            section = section[:end.start()]
        text = html_lib.unescape(re.sub(r'<[^>]+>', ' ', section))
        text = re.sub(r'\s+', ' ', text).strip()
        history.append({'report_date': day.isoformat(), 'retail_excerpt': text[:7000]})
        if len(history) >= max_reports:
            break
    return list(reversed(history))
