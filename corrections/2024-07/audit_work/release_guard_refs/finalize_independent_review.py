"""Bind the completed, fixed-scope release-guard review to locked owner bytes."""
from pathlib import Path
import datetime as dt,hashlib,json
from zoneinfo import ZoneInfo
R=Path(__file__).resolve().parents[2]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text())
lock=load(R/'audit_work/news_policy_lock.json')
tests=load(Path(__file__).with_name('independent_guard_cases.json'))
expected={
 'release_schedule_sha256':('audit_work/july_release_schedule.json','ec0affb8cf6d2e518d655e9fafd76c6d5b7ac56db1548962b1d6e95be7f2ec7d'),
 'screening_tool_sha256':('tools/ready_feeds.py','17ba7efe7b6bf89d67899b605f5507d3cfebc21227473103b29b33600ff8a5e4'),
 'named_exclusions_sha256':('audit_work/july_named_source_exclusions.json','06aba4eb3f84a714a7d429cf46641cd01c4b2b6245ec39a5a8010e87f9de6888')}
for field,(name,value)in expected.items():
 assert sha(R/name)==value==tests[field]==lock['files'][name],field
assert tests['passed']is True and not tests['failures']
refs_path=Path(__file__).with_name('official_timing_excerpts.json')
scan_path=Path(__file__).with_name('focused_staged_headline_scan.json');scan=load(scan_path)
recommendation_path=Path(__file__).with_name('named_omission_recommendations.json')
source_refs=load(refs_path)['references']
clock=[]
for label,local,zone,cutoff,strict in [
 ('Tankan','2024-07-01T08:50:00','Asia/Tokyo','2024-07-01T00:00:00+00:00',False),
 ('Japan final manufacturing PMI','2024-07-01T09:30:00','Asia/Tokyo','2024-07-01T00:00:00+00:00',False),
 ('Japan May preliminary wages','2024-07-08T08:30:00','Asia/Tokyo','2024-07-08T00:00:00+00:00',False),
 ('SK hynix press-release strict upper bound','2024-07-25T09:00:00','Asia/Seoul','2024-07-25T00:00:00+00:00',True),
 ('UK exit-poll publication','2024-07-04T22:00:00','Europe/London','2024-07-05T00:00:00+00:00',False)]:
 utc=dt.datetime.fromisoformat(local).replace(tzinfo=ZoneInfo(zone)).astimezone(dt.timezone.utc)
 clock.append({'event':label,'local':local,'timezone':zone,'utc':utc.isoformat(),'edition_cutoff_utc':cutoff,'release_is_strictly_before_this_upper_bound':strict,'relation_to_cutoff':'strict upper bound equals cutoff, so an on-schedule release is earlier'if strict else'before'if utc<dt.datetime.fromisoformat(cutoff)else'after'})
findings=[
 {'id':'RG01','area':'UK projection versus completed acts','finding':'An exit-poll phrase previously allowed named/sworn-in PM and concession claims, including an intervening country adjective or Downing Street entry, to escape the settled-result guard.','disposition':'Owner added focused actual-clause controls. All six reproduced mixed-status negatives reject; a pure eligible July 4 exit-poll projection remains permitted in the July 5 edition. The arbitrary settled-result 09:00 UTC minute was replaced by an explicit conservative day-only bound.','evidence_keys':['uk_exit_poll_preview'],'resolved':True},
 {'id':'RG02','area':'Company-result trigger and mixed clauses','finding':'The narrow third trigger lookahead missed top-estimates, profit-soars/doubles, Q4-disappoints, earnings-surprise and better-than-expected-comparison forms.','disposition':'The reproduced actual-result forms now reject before their release eligibility. Explicit previews remain eligible and an actual first clause is not cleared by a later forecast clause. The complete owner regression set was replayed against the locked bytes.','resolved':True},
 {'id':'RG03','area':'TSMC separate disclosures','finding':'The July 10 monthly revenue disclosure and revenue-only quarter aggregate are not the July 18 EPS/profit/outlook release.','disposition':'Separate conservative day-only guards allow eligible revenue-only reporting from July 11 and full earnings/profit/outlook from July 19. The observed profit-seen-jumping preview remains a preview.','evidence_keys':['tsmc_revenue_operation','tsmc_full_result'],'resolved':True},
 {'id':'RG04','area':'Early-local Japan and Korea','finding':'A single local-calendar-day rule cannot distinguish Japan 08:30/08:50 releases from Japan 09:30 PMI releases, or a Korean press release explicitly scheduled before 09:00 Seoul.','disposition':'Primary Tankan and PMI embargo headers and the dated MHLW wage schedule support the listed UTC conversions. SK hynix has a strict-before-midnight bound and July 25 eligibility; its July 24 synthetic actual rejects. No July 25 cash-session reaction is inferred from the earlier earnings clock.','evidence_keys':['japan_tankan','japan_manufacturing_pmi','japan_services_pmi','japan_flash_pmi','japan_may_wages','skhynix_early_local'],'resolved':True},
 {'id':'RG05','area':'GUS dates and clock precision','finding':'June wages/employment and industrial-output/producer-price releases are dated July 18, retail July 22, and official registered unemployment July 23. A current-page 2026 release-hour banner is not 2024 evidence.','disposition':'The four guards use conservative next-cutoff eligibility July 19, July 23 and July 24, with release_utc null and no invented exact hour. Earlier ministry estimates must remain distinct from the later GUS release.','evidence_keys':['gus_wages_employment','gus_industry','gus_retail','gus_unemployment'],'resolved':True},
 {'id':'RG06','area':'Samsung clock uncertainty','finding':'A July 31 Korean local date alone does not prove whether the full result preceded UTC midnight. The preliminary July 5 article has a separate original-version uncertainty.','disposition':'Samsung full results have their own explicitly uncertain conservative August 1 bound rather than the claim that every Korean morning release follows midnight. Only the exact doubtful July 5 Reuters record is removed by the named policy; other eligible company news and later own-date evidence remain available.','evidence_keys':['samsung_full_uncertain_clock'],'resolved':True},
 {'id':'RG07','area':'Exact publisher-version uncertainties','finding':'The current Reuters retrieval dates for July 5 n1053 and July 31 n1915 are after their respective cutoffs, while RSS dates are earlier. The displayed retrieval Date is not certified as first publication.','disposition':'Both exact own-date records, including their raw IDs, titles, RSS URLs/pubDates and current raw-source identities, are bound in the recommendation artifact. Current screening removes both through the owner-controlled named table. Release-event timing is not substituted for article-vintage evidence.','resolved':True},
 {'id':'RG08','area':'Observed eligible previews','finding':'The bounded actual-headline scan found three genuine pending Microsoft/multi-company previews conservatively excluded: Await Earnings for Clarity, report will offer a new gauge, and biggest test yet: earnings from the named companies.','disposition':'Only those three observed titles received focused positive controls. They are reclassified as company news with a seven-day age limit; stale instances are removed rather than promoted by a broad monthly category. All three fresh observed controls and the existing TSMC preview control pass.','resolved':True}
]
limits=[
 'This is a fixed-scope independent AI release-guard review, not authoring acceptance, source freeze, human review, original article-body-vintage verification or a certification of every exact minute in the 90-entry table.',
 'Regex coverage is not complete natural-language understanding. A finite known-schedule screen cannot prove every retained headline contemporaneous, relevant, correctly attributed or semantically safe.',
 'Every later authored concrete claim still requires independent review against its own date headline/card, including actual versus preview, period and company role, market-session versus after-hours reaction, instrument, horizon, unit and split context.',
 'The single bounded actual scan read 82 distinct matching June/July headlines across 23 provisional staged candidates. Those provisional files were not final locked-source acceptance. The source owner must restage all 69 current candidates, and recover_context must replay the locked inputs separately.',
 'Twenty selected historical timing references are retained as connected-web excerpts and URLs. Original full publisher/PDF bytes were not retrieved; direct urllib requests received tunnel403. Later sidebars and irrelevant search results were not used as evidence.',
 'National/Tokyo CPI timing has dated secondary-calendar corroboration in this review, with explicit primary-header and mutable-URL limits. The Japan household-spending exact clock was not independently certified here; no applicable actual headline appeared before its release in the bounded July 5 scan. Omit a doubtful actual rather than infer a clock from memory.',
 'An eligible early-local earnings release does not make a later local cash-session reaction available. A US after-close result can be known at the following midnight while that day’s regular-session close still precedes the result.',
 'The displayed current Reuters dates are not asserted to be original publication dates; conservative exact-record omissions resolve their uncertainty without a guessed original vintage.'
]
review={'review_type':'independent_fixed_scope_release_guard_review','reviewer':'/root/writer_late','reviewed_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'passed_fixed_scope_with_named_conservative_omissions','passed':True,'authoring_acceptance':False,'fatal_or_major_remaining':0,'errors':[],
        **{field:value for field,(_,value)in expected.items()},'bound_schedule_guard_count':len(load(R/'audit_work/july_release_schedule.json')['guards']),
        'owner_policy_lock_sha256':sha(R/'audit_work/news_policy_lock.json'),
        'timing_reference_path':str(refs_path.relative_to(R)),'timing_reference_sha256':sha(refs_path),'timing_reference_count':len(source_refs),
        'named_omission_recommendations_path':str(recommendation_path.relative_to(R)),'named_omission_recommendations_sha256':sha(recommendation_path),
        'independent_tests_path':str(Path(__file__).with_name('independent_guard_cases.json').relative_to(R)),'independent_tests_sha256':sha(Path(__file__).with_name('independent_guard_cases.json')),
        'checks':{'independently_designed_synthetic_cases':tests['case_count'],'exact_named_omission_records':len(tests['named_record_checks']),'observed_preview_positive_controls':len(tests['observed_preview_controls']),'owner_regressions_independently_replayed':tests['owner_regression_replay']['case_count'],'all_passed':True},
        'bounded_actual_headline_scan':{'path':str(scan_path.relative_to(R)),'sha256':sha(scan_path),'distinct_headlines_read':scan['distinct_headlines'],'provisional_candidate_count':len(scan['input_candidates']),'finding':'No additional pre-release actual admission identified in this fixed focused set. Three observed preview overblocks were corrected; two exact version uncertainties are conservatively removed. Tax-election and commercial-store PMI lexical matches were not treated as economic or political release evidence.'},
        'clock_conversions':clock,'findings_and_dispositions':findings,
        'supported_and_uncertain_timing_decisions':[{key:row[key]for key in ['key','url','document_date','timing_decision','precision','limits']}for row in source_refs],
        'named_record_checks':tests['named_record_checks'],'observed_preview_controls':tests['observed_preview_controls'],
        'remaining_uncertain_versions':[{'date':x['date'],'id':x['id'],'disposition':'exact record omitted, uncertainty not guessed','basis':x['evidence']}for x in load(recommendation_path)['exclusions']],
        'review_limits':limits,'source_ownership':'No source-owned guard code, feed, schedule, named exclusion table or author report was edited by this reviewer.'}
for field,(name,value)in expected.items():assert sha(R/name)==value
out=R/'audit/independent_release_guard_review.json';tmp=out.with_suffix('.json.tmp');tmp.write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n');tmp.replace(out)
print(json.dumps({'path':str(out.relative_to(R)),'sha256':sha(out),'passed':review['passed'],'fatal_or_major_remaining':0,'checks':review['checks'],'release_schedule_sha256':review['release_schedule_sha256'],'screening_tool_sha256':review['screening_tool_sha256'],'named_exclusions_sha256':review['named_exclusions_sha256']},indent=2))
