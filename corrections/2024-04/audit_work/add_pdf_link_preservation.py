from pathlib import Path
root=Path('/workspace/work/april2024')
p=root/'tools/build_artifacts.py';s=p.read_text();mark='def accepted_components(dates):'
new='''def check_pdf_links(date,pdf,evidence):
    """Retain clickable absolute source and timing-evidence URLs in the PDF."""
    actual=set()
    for page in pdf.pages:
        for ref in page.get('/Annots',[]):
            annotation=ref.get_object();action=annotation.get('/A')
            if action is not None:
                action=action.get_object() if hasattr(action,'get_object') else action
                if action.get('/URI') is not None:actual.add(str(action['/URI']))
    expected={item['url'] for item in evidence.values()}
    expected.update(item['availability_review']['evidence_url'] for item in evidence.values() if item.get('availability_review'))
    if not expected or not expected<=actual:
        missing=[key for key,item in evidence.items() if item['url']not in actual]
        raise ValueError(date+' PDF lost source/timing links: '+repr(missing))
    return {'unique_source_and_timing_URLs':len(expected),'all_source_links_clickable':True}

'''
assert mark in s;s=s.replace(mark,new+mark)
s=s.replace("            pdf_preservation=check_pdf_prose(date,pdf,payload['spec'],payload['evidence'])", "            pdf_preservation=check_pdf_prose(date,pdf,payload['spec'],payload['evidence'])\n            pdf_links=check_pdf_links(date,pdf,payload['evidence'])")
s=s.replace("'pdf_preservation':pdf_preservation,'files':", "'pdf_preservation':pdf_preservation,'pdf_links':pdf_links,'files':")
p.write_text(s)
p=root/'audit_work/review_final_artifacts.py';s=p.read_text();mark='def source_archive_review(manifest,inventory):'
new='''def pdf_link_preservation(pdf,evidence,date):
    # Inspect actual PDF annotations independently of HTML labels and prose.
    urls=set()
    for page in pdf.pages:
        for ref in page.get('/Annots',[]):
            obj=ref.get_object();action=obj.get('/A')
            if action is None:continue
            if hasattr(action,'get_object'):action=action.get_object()
            if action.get('/URI') is not None:urls.add(str(action.get('/URI')))
    expected=set()
    for key,item in evidence.items():
        check(item['url']in urls,date+' missing clickable PDF source link '+key)
        expected.add(item['url'])
        if item.get('availability_review'):
            url=item['availability_review']['evidence_url'];check(url in urls,date+' missing timing URL '+key);expected.add(url)
    return {'unique_source_and_timing_URLs':len(expected),'all_source_links_clickable':True}

'''
assert mark in s;s=s.replace(mark,new+mark)
s=s.replace("        pdf_count=pdf_preservation(date,text,spec,evidence)", "        pdf_count=pdf_preservation(date,text,spec,evidence)\n        pdf_links=pdf_link_preservation(pdf,evidence,date)")
s=s.replace("'ledger_records':len(evidence),'prose_ledger_and_citations_preserved':True", "'ledger_records':len(evidence),'pdf_links':pdf_links,'prose_ledger_and_citations_preserved':True")
p.write_text(s)
