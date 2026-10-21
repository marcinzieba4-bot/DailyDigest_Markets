import sys, json, types, importlib.util, os
for v in ('ANTHROPIC_API_KEY', 'SENDER_EMAIL', 'RECIPIENT_EMAIL'): os.environ.setdefault(v, 'x')
sys.modules.setdefault('anthropic', types.ModuleType('anthropic'))
spec = importlib.util.spec_from_file_location('lf', '/home/user/DailyDigest_Markets/lambda_function.py')
lf = importlib.util.module_from_spec(spec); spec.loader.exec_module(lf)
h, j = sys.argv[1], json.load(open(sys.argv[2]))['sections'][0]
P = lf._parse_html_paragraphs(open(h, encoding='utf-8').read())
subs = [t for s, t in P if s == 'h2']; body = [t for s, t in P if s == 'body']; h1 = [t for s, t in P if s == 'h1']
print('h1', h1 == [j['heading']], '| subheadings', subs == j['subheadings'], len(subs), '| body', body == j['body'], len(body))
for a, b in zip(body, j['body']):
    if a != b: print('DIFF\n  got:', repr(a[:200]), '\n  exp:', repr(b[:200])); break
