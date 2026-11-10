from pathlib import Path
root=Path('/workspace/work/april2024')
p=root/'tools/build_artifacts.py';s=p.read_text().replace("manifest['artifact_targets']!=65 or manifest['report_zip_members']!=63", "manifest['artifact_targets']!=len(DATES)*3+5 or manifest['report_zip_members']!=len(DATES)*3+3")
a=s.index('    capture_note = (',s.index('def methodology'));b=s.index("    return f'''",a)
s=s[:a]+'''    capture_note = 'The source audit separately records every physical request attempt and its retained response body.'
    if transport is not None:
        missing=transport.get('recorded_missing_response_bodies')
        interrupted=transport.get('unlogged_interrupted_attempts_actual_count')
        if (transport.get('status')!='physical_infrastructure_replay_passed' or transport.get('passed') is not True
            or type(missing) is not int or missing<0 or interrupted!=0
            or transport.get('all_physical_network_attempts_complete') is not True):
            raise ValueError('Accepted complete modern transport proof required for methodology')
        capture_note=(f'All physical request starts and completions are retained. {missing} failed attempts lacked a response body; '
            'the exact affected attempts and transport reasons are recorded separately. Every successful canonical RSS response '
            'for the complete query plan is retained. See audit/independent_physical_source_review.json in the frozen-source archive.')
''' + s[b:]
s=s.replace("    private=set(public['commitments'])\n    if not private<=members:raise ValueError('Private research original missing before public projection')\n    paths={path for path in paths if path.relative_to(ROOT).as_posix() not in private}\n", "    # Original research responses are outside ROOT. Only explicit commitments are public.\n    private=set(public['commitments'])\n    if any((ROOT/name).is_file() for name in private):raise ValueError('External private original was copied into the public root')\n")
s=s.replace("for relative in (replay_tool.PUBLIC_RESEARCH_MANIFEST,", "for relative in (replay_tool.PRIVATE_MANIFEST,replay_tool.PUBLIC_RESEARCH_MANIFEST,")
p.write_text(s)
p=root/'tools/publish.py';s=p.read_text().replace('April 2024 — 20 weekday','April 2024 — 22 weekday')
s=s.replace("for month, last in [(7, 31), (8, 31), (9, 30), (10, 31), (11, 30)]:", "for month, last in [(6, 30), (7, 31), (8, 31), (9, 30), (10, 31), (11, 30)]:")
s=s.replace("if len(targets) != 71 or len({x['key'] for x in targets}) != 71:", "if len(targets) != len(DATES)*3+5 or len({x['key'] for x in targets}) != len(DATES)*3+5:")
p.write_text(s)
p=root/'tools/verify_delivery.py';s=p.read_text().replace("len(receipt.get('targets',[]))!=65", "len(receipt.get('targets',[]))!=len(dates)*3+5").replace('65 expected April','71 expected April').replace("len(archive.namelist())!=63", "len(archive.namelist())!=len(dates)*3+3").replace('exactly 63 expected','exactly 69 expected').replace("len(members)==60", "len(members)==len(dates)*3").replace('All 40 PDF/JSON','All 44 PDF/JSON').replace('All 65 scoped','All 71 scoped').replace('20 daily HTML','22 daily HTML').replace('all 60 HTML/PDF/JSON','all 66 HTML/PDF/JSON').replace('including 40 native','including 44 native').replace('Latest, July/August','Latest, June/July/August')
p.write_text(s)
