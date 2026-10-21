"""fetch_earn_prev.py <dates> — for report date D, harvest the PREVIOUS earnings week (D-14 … D-8) into
../feeds_earn_prev/<D>.json, for dates whose D-7 earnings feed was never harvested (before 2026-06-25).
Implemented by running fetch_earnings' harvester for date D-7 and renaming the result."""
import os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_earnings  # noqa: F401  (sets fetch_feeds.TOPICS to the earnings topics)
import fetch_feeds as ff
ff.OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'feeds_earn_prev')
if __name__ == '__main__':
    os.makedirs(ff.OUT, exist_ok=True)
    for d in sys.argv[1:]:
        p = (dt.date.fromisoformat(d) - dt.timedelta(days=7)).isoformat()
        dst = os.path.join(ff.OUT, f'{d}.json')
        if os.path.exists(dst): print(d, 'cached'); continue
        _, msg = ff.one(p)
        os.replace(os.path.join(ff.OUT, f'{p}.json'), dst)
        print(d, '(prev week of', p + ')', msg, flush=True)
