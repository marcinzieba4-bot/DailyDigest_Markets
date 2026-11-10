from pathlib import Path
root=Path('/workspace/work/april2024')
p=root/'tools/build_source_inventory.py';s=p.read_text()
s=s.replace("    'query_plan_sha256', 'physical_source_inventory_sha256')", "    'query_plan_sha256', 'physical_source_inventory_sha256', 'journaled_attempt_starts',\n    'journaled_interrupted_attempts', 'all_completed_attempts_accounted_for', 'planned_canonical_successes_complete')")
s=s.replace("    if set(startmap)!=set(ids):raise ValueError('Unfinished/unlogged physical starts remain')", """    interrupted=[row for row in starts if row['attempt_id']not in ids]
    limitation=json.loads(safe_path(CAPTURE_LIMITATION).read_bytes())
    if (limitation.get('unmatched_attempt_starts')!=interrupted
        or type(limitation.get('unmatched_attempt_start_count_at_review'))is not int
        or limitation['unmatched_attempt_start_count_at_review']!=len(interrupted)):
        raise ValueError('Journaled interrupted start set differs from explicit outage disclosure')
    if interrupted and limitation.get('status')!='explicit_environment_outage_capture_gap':
        raise ValueError('Actual journaled outage requires its explicit capture disclosure')""")
s=s.replace("    if {r['signature'] for r in planned}!=set(signatures):raise ValueError('Physical signature set differs from complete plan')", """    if {r['signature'] for r in planned}!=set(signatures):raise ValueError('Physical signature set differs from complete plan')
    for row in interrupted:
        if row['signature']not in signatures or not any(r.get('status')=='fetched'and r.get('request_url')==row.get('request_url')for r in signatures[row['signature']]):
            raise ValueError('Interrupted query has no retained exact-URL canonical success')""")
s=s.replace("        'missing_attempts':missing,'counts':{'physical_requests':len(rows),'physical_attempts':len(ledger),", "        'missing_attempts':missing,'interrupted_attempt_starts':interrupted,'counts':{'physical_requests':len(rows),'physical_attempts':len(ledger),")
s=s.replace("        'all_physical_network_attempts_complete':True,'attempt_starts_instrumentation_used':True,", "        'all_physical_network_attempts_complete':not bool(interrupted),'attempt_starts_instrumentation_used':True,\n        'journaled_attempt_starts':len(starts),'journaled_interrupted_attempts':len(interrupted),\n        'all_completed_attempts_accounted_for':True,'planned_canonical_successes_complete':True,")
s=s.replace("{'counts':result['counts'],'missing_attempts':result['missing_attempts']}", "{'counts':result['counts'],'missing_attempts':result['missing_attempts'],'interrupted_attempt_starts':result['interrupted_attempt_starts']}")
p.write_text(s)
p=root/'tools/build_artifacts.py';s=p.read_text();a=s.index("    capture_note = '",s.index('def methodology'));b=s.index("    return f'''",a)
s=s[:a]+"""    capture_note = 'The source audit separates journaled starts, completed physical attempts and retained response bodies.'
    if transport is not None:
        missing=transport.get('recorded_missing_response_bodies')
        interrupted=transport.get('journaled_interrupted_attempts')
        if (transport.get('status')!='physical_infrastructure_replay_passed' or transport.get('passed') is not True
            or type(missing) is not int or missing<0 or type(interrupted) is not int or interrupted<0
            or transport.get('unlogged_interrupted_attempts_actual_count')!=0
            or transport.get('all_physical_network_attempts_complete') is not (interrupted==0)
            or transport.get('all_completed_attempts_accounted_for') is not True
            or transport.get('planned_canonical_successes_complete') is not True):
            raise ValueError('Accepted actual journaled transport proof required for methodology')
        capture_note=(f'The request-start journal contains {interrupted} interrupted attempts without completion records after '
            'the managed environment outage; their HTTP outcomes and response bodies cannot be certified. '
            f'Among completed attempts, {missing} failed attempts lacked a response body. '
            'The exact affected starts and completed attempts remain disclosed without synthesized outcomes. '
            'Every planned canonical query eventually has an exact retained successful RSS response. '
            'See audit/independent_physical_source_review.json and audit_work/acquisition_capture_limitation.json in the frozen-source archive.')
"""+s[b:];p.write_text(s)
