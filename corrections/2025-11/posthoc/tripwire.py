"""tripwire.py [dates] — hindsight tripwire for the November 2025 specs (kept OUT of the repo while writers work).

Each rule: (label, regex for outcome wording, first report date on which the outcome may appear). A hit on an earlier
report is a candidate leak (or a legitimate preview phrased like an outcome) — review it by hand against that date's feed."""
import json, re, sys, glob, os

C = '/home/user/DailyDigest_Markets/corrections/2025-11'
CITE = re.compile(r'\s*\[\[n\d{4}\]\]')
R = [
    ('Palantir Q3 results (Nov 3 after close)', r'Palantir.{0,140}(third-quarter|Q3|fiscal third).{0,140}(beat|topped|raised|revenue (rose|jumped|grew)|guidance)', '2025-11-04'),
    ('AMD Q3 results (Nov 4 after close)', r'\bAMD\b.{0,140}(third-quarter|Q3).{0,140}(beat|topped|raised|revenue (rose|jumped|grew)|guidance|forecast)', '2025-11-05'),
    ('Supreme Court tariff hearing (Nov 5)', r'(justices|Supreme Court).{0,120}(skeptic|sceptic|questioned|grilled|appeared)', '2025-11-06'),
    ('NBP cut to 4.00% (Nov 5)', r'(NBP|RPP|Polish central bank|National Bank of Poland|Council).{0,140}(cut|lower(ed)?|reduc(ed|tion)|trim(med)?)[^.]{0,80}(4[.,]00|4 ?%|4 per ?cent|4 proc)', '2025-11-06'),
    ('Musk pay package approved (Nov 6)', r'(Tesla|Musk).{0,140}(shareholders|investors|stockholders).{0,60}(approv)', '2025-11-07'),
    ('BoE 5-4 hold (Nov 6)', r'(Bank of England|BoE).{0,100}(5-4|five to four|narrowly)', '2025-11-07'),
    ('Challenger October layoffs (Nov 6)', r'Challenger.{0,100}(153|highest (October|since))', '2025-11-07'),
    ('China October exports -1.1% (Nov 7)', r'China.{0,100}(October|Oct\.?) exports.{0,80}(fell|declin|contract|drop)', '2025-11-10'),
    ('Takaichi Taiwan remarks (Nov 7)', r'Takaichi.{0,140}(Taiwan).{0,100}(remark|comment|said|warn)', '2025-11-10'),
    ('Pfizer wins Metsera (Nov 7)', r'Pfizer.{0,100}(wins|won|prevail|secur|clinch|beat Novo).{0,80}Metsera', '2025-11-10'),
    ('UMich sentiment prelim Nov (Nov 7)', r'(University of Michigan|Michigan).{0,100}(sentiment).{0,100}(November|Nov\.?).{0,60}(50\.3|near record|record low|second-lowest)', '2025-11-10'),
    ('Senate shutdown vote (Nov 9-10)', r'Senate.{0,100}(advanc|passed|cleared|voted).{0,100}(funding|spending|shutdown|stopgap)', '2025-11-11'),
    ('Shutdown ended / bill signed (Nov 12)', r'(shutdown (ended|is over|has ended)|signed (the|a) (funding|spending|stopgap)|end(ed|s)? the (longest )?shutdown|government reopen)', '2025-11-13'),
    ('SoftBank sold Nvidia stake (Nov 11)', r'SoftBank.{0,100}(sold|sale of|sells|dumped).{0,80}Nvidia', '2025-11-12'),
    ('Cisco Q1 FY26 results (Nov 12 after close)', r'Cisco.{0,140}(first-quarter|Q1|fiscal first).{0,140}(beat|topped|raised|record|guidance)', '2025-11-13'),
    ('Burry Scion deregistration (Nov 13)', r'(Scion).{0,100}(deregister|shut|closing|wind)', '2025-11-14'),
    ('Disney results (Nov 13)', r'Disney.{0,100}(fourth-quarter|Q4|fiscal fourth).{0,140}(beat|topped|missed|results|revenue)', '2025-11-14'),
    ('Berkshire Alphabet stake (Nov 14 13F)', r'Berkshire.{0,100}(Alphabet|Google)', '2025-11-17'),
    ('China October activity data (Nov 14)', r'China.{0,100}(October|Oct\.?).{0,80}(fixed.asset investment|industrial output|retail sales).{0,100}(fell|slow|weak|contract|miss|worst)', '2025-11-17'),
    ('Japan Q3 GDP contraction (Nov 16-17)', r'Japan.{0,100}(GDP|economy).{0,100}(shrank|contract|fell|declin).{0,60}(third quarter|Q3|July-September)', '2025-11-17'),
    ('China travel warning on Japan (Nov 14)', r'China.{0,100}(travel (advisory|warning)|advis(ed|es) (citizens|its citizens)).{0,100}Japan', '2025-11-17'),
    ('Thiel fund sold Nvidia (Nov 17)', r'Thiel.{0,100}(Nvidia)', '2025-11-18'),
    ('Home Depot Q3 results (Nov 18)', r'Home Depot.{0,140}(third-quarter|Q3).{0,140}(beat|missed|cut|lower|outlook|results)', '2025-11-19'),
    ('Gemini 3 launch (Nov 18)', r'Gemini 3', '2025-11-19'),
    ('Nvidia Q3 FY26 results (Nov 19 after close)', r'Nvidia.{0,160}(\$57|57\.0|\$65 billion|65 billion|third-quarter (results|revenue)|fiscal third).{0,120}(beat|topped|record|guid|forecast|revenue)', '2025-11-20'),
    ('FOMC October minutes (Nov 19)', r'(minutes).{0,100}(October).{0,100}(many|most|strong majority|several).{0,80}(participants|officials)', '2025-11-20'),
    ('Target / Lowe / TJX results (Nov 19)', r'(Target|Lowe.s|TJX).{0,120}(third-quarter|Q3).{0,140}(beat|missed|cut|raised|results|comparable)', '2025-11-20'),
    ('28-point Ukraine peace plan (Nov 19-20)', r'28.point', '2025-11-20'),
    ('Walmart Q3 results (Nov 20)', r'Walmart.{0,140}(third-quarter|Q3).{0,140}(beat|missed|raised|results|guidance)', '2025-11-21'),
    ('September jobs report (Nov 20)', r'(September|Sept\.?).{0,40}(jobs report|payrolls|employment report).{0,140}(119|4\.4)', '2025-11-21'),
    ('Williams room-to-cut remarks (Nov 21)', r'Williams.{0,140}(room|near term|near-term|adjust).{0,100}(rate|policy|cut)', '2025-11-24'),
    ('Bitcoin $80k low (Nov 21)', r'(bitcoin|BTC).{0,100}(\$80,?000|80k|\$81,?\d{3}|\$82,?\d{3})', '2025-11-24'),
    ('Japan stimulus approved (Nov 21)', r'(Takaichi|Japan).{0,100}(stimulus|economic package).{0,100}(approv|¥21|21\.3|trillion yen)', '2025-11-24'),
    ('Moodys Poland outlook (Nov 21)', r'Moody.s.{0,120}(Poland|Polish|Polska).{0,100}(outlook|rating)', '2025-11-24'),
    ('Geneva Ukraine talks (Nov 23)', r'Geneva.{0,100}(talks|meeting|delegation)', '2025-11-24'),
    ('Alphabet TPU / Meta report (Nov 24)', r'(Meta).{0,120}(TPU|Tensor Processing)', '2025-11-25'),
    ('Burry Substack (Nov 24)', r'Cassandra', '2025-11-25'),
    ('UK Autumn Budget outcome (Nov 26)', r'(Reeves).{0,120}(budget).{0,120}(raised|raising|tax rise|£26|£ ?2\d billion|freez)', '2025-11-27'),
    ('Alibaba results (Nov 25)', r'Alibaba.{0,120}(September.quarter|fiscal second|results).{0,120}(beat|missed|revenue|cloud)', '2025-11-26'),
    ('Dec FOMC outcome / December cut delivered', r'(Fed|FOMC).{0,100}(cut|lowered).{0,60}(December 10|Dec\.? 10)', '2025-12-31'),
]


def text_of(spec):
    out = []
    def walk(x):
        if isinstance(x, str): out.append(CITE.sub('', x))
        elif isinstance(x, list): [walk(y) for y in x]
        elif isinstance(x, dict): [walk(y) for y in x.values()]
    walk(spec)
    return out


def main():
    dates = sys.argv[1:] or [os.path.basename(f)[:-5] for f in sorted(glob.glob(f'{C}/specs/*.json'))]
    hits = 0
    for d in dates:
        spec = json.load(open(f'{C}/specs/{d}.json'))
        paras = text_of(spec)
        for label, rx, first in R:
            if d >= first: continue
            for t in paras:
                for m in re.finditer(rx, t, re.I | re.S):
                    hits += 1
                    s = max(0, m.start() - 60); e = min(len(t), m.end() + 60)
                    print(f'{d}  [{label} — first allowed {first}]  …{t[s:e]}…'.replace('\n', ' '))
    print(f'-- {hits} tripwire hits over {len(dates)} reports')


if __name__ == '__main__':
    main()
