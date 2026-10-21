"""fetch_earnings.py <dates> — harvest date-bounded earnings headlines (7-day window, items dated strictly before the
report date) into ../feeds_earn/<date>.json, for the earnings-first Sector Deep Dive. Same harvester as fetch_feeds.py."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_feeds as ff
W = 7
ff.OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'feeds_earn')
ff.TOPICS = {
    'earn_reported': [('earnings beat estimates', W), ('earnings miss estimates', W), ('raises guidance', W),
                      ('cuts guidance', W), ('quarterly results shares', W), ('beats expectations shares', W),
                      ('profit warning', W)],
    'earn_outlook':  [('earnings preview', W), ('analysts raise estimates', W), ('earnings estimates revised', W),
                      ('price target raised earnings', W), ('earnings season outlook', W)],
    'earn_sector':   [('tech earnings', W), ('chipmaker earnings', W), ('software earnings', W), ('bank earnings', W),
                      ('oil company earnings', W), ('retailer earnings', W), ('pharma earnings', W),
                      ('medtech earnings', W), ('industrial earnings', W), ('airline earnings', W),
                      ('utility earnings', W), ('homebuilder earnings', W), ('automaker earnings', W),
                      ('media earnings', W), ('REIT earnings', W), ('chemical earnings', W), ('miner earnings', W),
                      ('food company earnings', W), ('consumer staples earnings', W), ('restaurant earnings', W)],
}
if __name__ == '__main__':
    os.makedirs(ff.OUT, exist_ok=True)
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(3) as ex:
        for d, msg in ex.map(ff.one, sys.argv[1:]):
            print(d, msg, flush=True)
