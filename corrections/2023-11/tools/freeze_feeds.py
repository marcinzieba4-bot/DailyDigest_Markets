"""freeze_feeds.py — build, screen and freeze the 22 November 2023 own-date author feeds.

Inputs: the complete acquisition plan (audit/news_query_plan.json) whose status must be
all_requests_acquired_caps_resolved. For each report date the own-cutoff merge (fetch_news.collect_feed)
uses only requests ending by that cutoff; ready_feeds.screen applies the release-clock guards and named
exclusions. Outputs (authors read only feeds/ and cards/):
  feeds/DATE.json.gz             frozen author feed (headline records, ids nNNNN)
  exclusions/DATE.json           editorial exclusions bound to the frozen feed hash (initially empty)
  audit/news_ready_DATE.json     screen receipt with every excluded record and its guard
  audit/news_frozen_DATE.json    hash bindings (raw, ready, provenance)
  audit/news_provenance/DATE.json.gz  qualifying physical request signatures per record
A frozen feed is never rewritten with different bytes (fetch_news.atomic_json enforces this)."""
from __future__ import annotations
import hashlib, json, sys
from fetch_news import ROOT, atomic_json, build_feed, json_bytes
from expand_capped_news import DATES, load_harvest, read, PLAN, COVERAGE, sha
from ready_feeds import screen

def main():
    plan = read(PLAN); coverage = read(COVERAGE)
    assert plan['status'] == 'all_requests_acquired_caps_resolved' and coverage['failed_requests'] == 0
    batches = load_harvest(plan)
    only = set(sys.argv[1:])
    for d in DATES:
        stamp = d.isoformat()
        if only and stamp not in only: continue
        raw = build_feed(d, batches, persist=False)
        payload, ledger = raw.pop('_payload'), raw.pop('_ledger')
        ready = screen(d, raw=payload, persist=False)
        feed = ready.pop('_payload')
        feed_path = ROOT / 'feeds' / (stamp + '.json.gz')
        atomic_json(ROOT / 'work' / 'unreviewed_feeds' / (stamp + '.json.gz'), payload, True)
        atomic_json(ROOT / 'audit' / 'news_provenance' / (stamp + '.json.gz'), ledger, True)
        atomic_json(feed_path, feed, True)
        feed_sha = hashlib.sha256(feed_path.read_bytes()).hexdigest()
        assert feed_sha == ready['ready_sha256']
        atomic_json(ROOT / 'audit' / ('news_ready_' + stamp + '.json'), ready)
        frozen = dict(date=stamp, feed_sha256=feed_sha, raw_sha256=raw['feed_sha256'], provenance_sha256=raw['provenance_sha256'],
                      ready_receipt_sha256=hashlib.sha256(json_bytes(ready)).hexdigest(), query_plan_sha256=sha(PLAN),
                      ready_items=ready['ready_items'], excluded_items=ready['excluded_items'], status='frozen_complete_own_date',
                      rule='Own-cutoff prefix queries and refinements only; descendants of later-cutoff refinement roots excluded.')
        atomic_json(ROOT / 'audit' / ('news_frozen_' + stamp + '.json'), frozen)
        ex_path = ROOT / 'exclusions' / (stamp + '.json')
        if not ex_path.exists():
            ex_path.parent.mkdir(exist_ok=True)
            ex_path.write_text(json.dumps({'date': stamp, 'feed_sha256': feed_sha, 'exclusions': [],
                'scope': 'Editorial exclusions found after the freeze (misdated, post-cutoff or ambiguous records); the frozen feed is never mutated.'}, indent=1))
        print(stamp, 'raw', raw['items'], 'ready', ready['ready_items'], 'excluded', ready['excluded_items'], dict(ready['excluded_by_guard']) if len(ready['excluded_by_guard']) < 6 else len(ready['excluded_by_guard']), flush=True)

if __name__ == '__main__':
    main()
