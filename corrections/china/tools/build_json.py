"""build_json.py <dates> — rebuild corrections/2026-10-19/json/<date>_Market_Intelligence.json from the edited HTML with the
Lambda's own paragraph parser, keeping the original date and generated_at (same procedure as poland/tools/finalize.py)."""
import sys, os, json, types, importlib.util
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import C, REPORTS
ROOT = os.path.dirname(os.path.dirname(C))
for v in ('ANTHROPIC_API_KEY', 'SENDER_EMAIL', 'RECIPIENT_EMAIL'): os.environ.setdefault(v, 'x')
sys.modules.setdefault('anthropic', types.ModuleType('anthropic'))
spec = importlib.util.spec_from_file_location('lf', os.path.join(ROOT, 'lambda_function.py'))
lf = importlib.util.module_from_spec(spec); spec.loader.exec_module(lf)
JD = os.path.join(os.path.dirname(REPORTS), 'json')
for d in sys.argv[1:]:
    jp = os.path.join(JD, f'{d}_Market_Intelligence.json'); oj = json.load(open(jp))
    sections, cur = [], None
    for style, text in lf._parse_html_paragraphs(open(os.path.join(REPORTS, f'{d}.html'), encoding='utf-8').read()):
        if style == 'h1': cur = {'heading': text, 'subheadings': [], 'body': []}; sections.append(cur)
        elif style == 'h2':
            if cur is None: cur = {'heading': '', 'subheadings': [], 'body': []}; sections.append(cur)
            cur['subheadings'].append(text)
        elif style == 'body' and text:
            if cur is None: cur = {'heading': '', 'subheadings': [], 'body': []}; sections.append(cur)
            cur['body'].append(text)
    json.dump({'date': oj['date'], 'generated_at': oj['generated_at'], 'sections': sections}, open(jp, 'w'), ensure_ascii=False, indent=2)
    print(d, 'json', sum(len(s['body']) for s in sections), 'paragraphs')
