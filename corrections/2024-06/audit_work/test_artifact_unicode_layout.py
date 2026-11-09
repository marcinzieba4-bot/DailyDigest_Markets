"""Synthetic browser/PDF preservation self-QA; never read or build a report.

The standalone fixture uses generic prose only and lives in a temporary work
directory. Its receipt is engineering evidence, not independent acceptance.
"""
from pathlib import Path
import datetime as dt
import hashlib
import importlib.util
import json
import tempfile

from bs4 import BeautifulSoup
from pypdf import PdfReader
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def module(name, path):
    info = importlib.util.spec_from_file_location('synthetic_' + name, path)
    value = importlib.util.module_from_spec(info)
    info.loader.exec_module(value)
    return value


def main():
    render = module('render', ROOT / 'tools/render.py')
    builder = module('builder', ROOT / 'tools/build_artifacts.py')
    reviewer = module('reviewer', ROOT / 'audit_work/review_final_artifacts.py')
    labels = ['Playbook ✓', '⚡ Breaking Convention', 'When the Narrative Breaks']
    literal = ('Synthetic Łódź risk [100] keeps −3.2% and now here as separate words; '
               'non\u2011breaking, non\u2010breaking and non-breaking remain distinct. '
               'The fixture timestamp is 2000-01-01T07:00:00+00:00. [[n0001]]')
    spec = {'geo': [], 'sectors': [], 'earnings_pattern': {'parts': []}, 'underowned': [],
            'crypto': {'parts': []}, 'flows': {'parts': []}, 'anticipatory': [], 'catalysts': [],
            'retail_intro': 'Synthetic introduction with literal [100] and Łódź. [[n0001]]', 'retail': []}
    for i in range(24):
        spec['earnings_pattern']['parts'].append([labels[i % len(labels)], f'Fixture occurrence {i}. ' + literal])
    evidence = {'n0001': {'id': 'n0001', 'title': 'Synthetic non\u2011breaking source [100] — Łódź',
                          'src': 'Synthetic Outlet', 'published_at': '2000-01-01T07:00:00+00:00',
                          'url': 'https://example.org/synthetic-only',
                          'availability_review': {'reason': 'Synthetic availability explanation only',
                                                  'known_before_utc': '2000-01-01T08:00:00+00:00',
                                                  'evidence_url': 'https://example.org/synthetic-timing'}}}
    doc = render.Doc(evidence)
    parts = doc.parts(spec['earnings_pattern']['parts'])
    parts.append('<p class="retail-intro">' + doc.text(spec['retail_intro']) + '</p>')
    item = evidence['n0001']
    ledger = ('<details class="ledger" open><summary>Dated evidence · 1 sources</summary><ol>'
              '<li data-source-id="n0001"><a href="' + item['url'] + '">' + render.esc(item['title'])
              + '</a> — ' + render.esc(item['src']) + ' · ' + render.esc(item['published_at'])
              + '<br><span>Timing: ' + render.esc(item['availability_review']['reason'])
              + ' Verified available before ' + render.esc(item['availability_review']['known_before_utc'])
              + '. <a href="' + item['availability_review']['evidence_url'] + '">Timing evidence</a>.</span></li></ol></details>')
    html = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width,initial-scale=1"><style>' + render.CSS
            + '</style></head><body style="' + render.BODY + '"><h1>Generic synthetic fixture</h1>'
            '<div class="report-block retail-lead">' + ''.join(parts) + '</div>' + ledger + '</body></html>')
    expected = reviewer.html_preservation(BeautifulSoup(html, 'html.parser'), spec, evidence, 'synthetic')
    layouts = []
    with tempfile.TemporaryDirectory(prefix='artifact_unicode_synthetic_', dir=ROOT / 'work') as temporary:
        path = Path(temporary) / 'synthetic-only.pdf'
        with sync_playwright() as engine:
            browser = engine.chromium.launch(headless=True, executable_path='/usr/bin/chromium', args=['--no-sandbox'])
            page = browser.new_page()
            for width, height in [(1440, 1000), (390, 844)]:
                page.set_viewport_size({'width': width, 'height': height})
                page.set_content(html, wait_until='load')
                row = page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})')
                assert row['scroll'] <= width, row
                layouts.append(row)
            page.set_viewport_size({'width': 1440, 'height': 1000})
            page.pdf(path=str(path), format='A4', print_background=True,
                     margin={'top': '14mm', 'bottom': '16mm', 'left': '14mm', 'right': '14mm'})
            browser.close()
        pdf = PdfReader(path)
        text = '\n'.join(page.extract_text() or '' for page in pdf.pages)
        assert builder.check_pdf_prose('synthetic', pdf, spec, evidence)['paragraphs_preserved'] == expected
        assert reviewer.pdf_preservation('synthetic', text, spec, evidence) == expected
        try:
            reviewer.pdf_preservation('synthetic', text.replace('\u2011', '\u2010'), spec, evidence)
        except ValueError:
            pass
        else:
            raise AssertionError('Literal U+2011 to U+2010 mutation was accepted')
        for key in ['reason', 'known_before_utc']:
            corrupted = text.replace(item['availability_review'][key], 'CORRUPTED')
            try:
                reviewer.pdf_preservation('synthetic', corrupted, spec, evidence)
            except ValueError:
                pass
            else:
                raise AssertionError('Timing exception text mutation was accepted: ' + key)
        pdf_pages = len(pdf.pages)
    files = ['tools/render.py', 'tools/build_artifacts.py', 'audit_work/review_final_artifacts.py',
             'audit_work/test_artifact_unicode_layout.py']
    receipt = {'status': 'synthetic_checks_passed', 'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
               'scope': 'Engineering self-QA of generic browser/PDF fixture only; no report facts read or report artifacts built.',
               'runtime_report_artifacts_reviewed': False, 'synthetic_paragraphs_preserved': expected,
               'synthetic_pdf_pages': pdf_pages, 'literal_U2011_mutation_rejected': True, 'layouts': layouts,
               'tool_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files}}
    (ROOT / 'checks/artifact_unicode_layout_synthetic.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
