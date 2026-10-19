import sys,re,html
def totext(t):
    t=re.sub(r'<style.*?</style>','',t,flags=re.S)
    t=re.sub(r'</(p|div|li|h[1-6]|tr|br)>','\n',t)
    t=re.sub(r'<[^>]+>',' ',t); t=html.unescape(t)
    t=re.sub(r'[ \t\xa0]+',' ',t); t=re.sub(r'\n\s*\n+','\n',t)
    return t
if __name__=='__main__':
    print(totext(open(sys.argv[1],encoding='utf-8').read()))
