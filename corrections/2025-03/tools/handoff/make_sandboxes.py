"""Create one isolated sandbox per March 2025 weekday edition.

Each sandbox holds only: BRIEF.md, reference/, tools/, its own feed and card, and empty specs/ notes/ folders.
Writers and editors therefore cannot read any other date's feed, card, spec or notes.
"""
import datetime as dt, shutil, sys
from pathlib import Path

REPO = Path('/home/user/DailyDigest_Markets/corrections/2025-03')
ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / 'sandboxes'
DATES = [dt.date(2025, 3, n).isoformat() for n in range(1, 32) if dt.date(2025, 3, n).weekday() < 5]

for d in DATES:
    box = ROOT / d
    if box.exists():
        shutil.rmtree(box)
    (box / 'feeds').mkdir(parents=True); (box / 'cards').mkdir(); (box / 'specs').mkdir(); (box / 'notes').mkdir()
    shutil.copytree(REPO / 'tools', box / 'tools', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(REPO / 'reference', box / 'reference')
    shutil.copy(REPO / 'BRIEF.md', box / 'BRIEF.md')
    shutil.copy(REPO / 'feeds' / f'{d}.json.gz', box / 'feeds' / f'{d}.json.gz')
    shutil.copy(REPO / 'cards' / f'{d}.json', box / 'cards' / f'{d}.json')
print('sandboxes:', len(DATES), 'under', ROOT)
