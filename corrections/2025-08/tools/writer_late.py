"""Own-date writing aid. Loads exactly one report's card and frozen evidence."""
from pathlib import Path
import collections, gzip, json, re, sys

ROOT=Path(__file__).resolve().parent.parent

class Writer:
    def __init__(self,date):
        self.date=date
        self.card=json.loads((ROOT/'cards'/f'{date}.json').read_text())
        self.items={i['id']:i for i in json.loads(gzip.decompress((ROOT/'feeds'/f'{date}.json.gz').read_bytes()))['items']}
        self.usage=collections.Counter()
    def q(self,identifier,text):
        assert identifier in self.items,identifier
        self.usage[identifier]+=1
        return text+' [['+identifier+']]'
    def price(self,ticker,periods=(1,5,20)):
        m=self.card['markets'][ticker]
        name=m['name'].split(' (')[0]
        text=f"{name} closed at {m['close']}"
        if not ticker.startswith('^') and not ticker.endswith('=X'):
            text+=' '+m['currency']
        changes=[]
        for n in periods:
            v=m[f'chg_{n}s_pct']
            if v is None:continue
            changes.append(f"{'up' if v>=0 else 'down'} {abs(v):.2f}% "+{1:'in the prior session',5:'over five sessions',20:'over 20 sessions'}[n])
        if changes:text+=', '+', '.join(changes)
        desc='prior completed daily close' if m['tz']=='UTC' and ticker.endswith('-USD') else 'prior close'
        return text+f". (Yahoo Finance, {desc} {m['session']})"
    def treasury(self):
        t=self.card['treasury']
        y=t['prior_close_pct'];c=t['chg_20obs_bps']
        return (f"The US Treasury par curve put the 2Y at {y['2y']} and the 10Y at {y['10y']}, with a 10Y–2Y spread of {t['spread_10y_2y_bps']:+d} bps. "
                f"Over 20 Treasury observations the 2Y moved {c['2y']:+d} bps, the 10Y {c['10y']:+d} bps and the spread {c['spread']:+d} bps. "
                f"The curve is {t['curve_shape']}; its move was {t['curve_move_20obs']}. (US Treasury, prior close {t['prior_close_date']})")
    def save(self,spec):
        assert spec['date']==self.date
        (ROOT/'specs').mkdir(exist_ok=True)
        (ROOT/'specs'/f'{self.date}.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
        print('saved',self.date,'citation uses',sum(self.usage.values()),'distinct',len(self.usage))

def B(title,parts,**kw):return {'title':title,'parts':parts,**kw}
def G(key,stance,label,parts):return {'key':key,'stance':stance,'label':label,'parts':parts}

