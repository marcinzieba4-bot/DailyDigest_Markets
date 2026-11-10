"""Retained finite April safety-policy code snapshot for independent projection replay.
This is an explicit implementation snapshot of reviewed policy, not independent
article research. The reviewer implements its own item merge and projection.
"""
from pathlib import Path
import datetime as dt,gzip,hashlib,json,re
from collections import Counter
ROOT=Path(__file__).resolve().parent.parent
WIN={'news':7,'result':14,'monthly':35}
UTC=dt.timezone.utc
PREVIEW = re.compile(r'\b(?:preview|previews|ahead of|week ahead|to report|will report|set to report|what to expect|earnings calendar)\b', re.I)
def read_json(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)

DATES = [dt.date(2024, 4, n) for n in range(1, 31) if dt.date(2024, 4, n).weekday() < 5]

FORWARD = re.compile(
    r"(?:\bexpect(?:ed|s)?\b|\bforecasts?\b|\bforecasting\b|\bwill\b|\bwould\b|\bcould\b|\bmight\b|"
    r"\bset to\b|\bdue\b|\bpoised\b|\blikely\b|\bseen\b|\bconsensus\b|\bestimates?\b|\bpreview\b|\bahead\b|"
    r"\bawait\w*\b|\bto (?:unveil|announce|impose|set|sign|cut|raise|hold|keep|release|publish|report|decide|"
    r"review|meet|be|discuss|consider|weigh)\b|\bplans? to\b|\bweighs?\b|\bcalendar\b|\bthis week\b|\bnext week\b|"
    r"\bon (?:monday|tuesday|wednesday|thursday|friday)\b|\bdue (?:on|out)\b|\bprognoz|\boczekuj|\boczekiw|"
    r"\bspodziew|\bzapowied|\bszacuj)",
    re.I,
)

NEUTRALISE = re.compile(
    r"\b(?:better|worse|more|less|higher|lower|stronger|weaker|faster|slower|above|below|in line)\s+than\s+"
    r"(?:expected|forecast|estimates?|predicted|anticipated)\b|\bas\s+(?:expected|forecast|anticipated)\b",
    re.I,
)

SCHEDULE_PATH=ROOT/'audit_work/april_release_schedule.json'

SCHEDULE=read_json(SCHEDULE_PATH)

RELEASE_GUARDS=[(x['label'],x['eligible_edition'],x['earliest_pub_date'],x['pattern'])for x in SCHEDULE['guards']]

GUARD_META={x['label']:x for x in SCHEDULE['guards']}

NAMED_PATH=ROOT/'audit_work/april_named_source_exclusions.json'

NAMED=read_json(NAMED_PATH)['exclusions']

OBSERVED_COMPANY_PREVIEWS=frozenset()

DISPOSITIONS_PATH=ROOT/'audit_work/april_observed_semantic_dispositions.json'

DISPOSITIONS=read_json(DISPOSITIONS_PATH)['dispositions']

DISPOSITION_BY_EVENT={(x['title'],x['guard']):x for x in DISPOSITIONS}

assert len(DISPOSITION_BY_EVENT)==len(DISPOSITIONS),'Duplicate observed event disposition'

OBSERVED_PREVIEW_TITLES=frozenset(x['title']for x in DISPOSITIONS if x['disposition']=='preview')

GUARD_VERSION='apr-2024-release-guards-v1'

SEMANTIC_GUARDS=[('rolling or live market page',re.compile(r'\b(?:live updates|live blog|live coverage|stock market (?:news )?today|markets today|stock market live|as it happened)\b|^LIVE:',re.I)),('advertisement or coupon page',re.compile(r'^Advertisement\b|sponsored content|advertorial|promo code|discount code|coupon code',re.I))]

COMPLETED = re.compile(r"\b(?:announced|unveiled|approved|confirmed|unchanged|reach|reaches|hit|hits|shrink|shrinks|contract|contracts|rebound|rebounds|rise|fall|surge|slump|jump|gain|gains|grow|grows|cool|cools|ease|eases|moderate|moderates|contraction|expansion|rattles?|rattled|dominates?|dominated|spars?|sparred|clash(?:es)?|clashed|defeats?|vows?|vowed|pledges?|pledged|urges?|urged|promises?|promised|won|elected|president-elect|conceded|defeated|shows|showed|wins|sweeps|swept|secures|secured|closes|closed|ends|ended|lowered|held|kept|reported|surged|accelerated|slowed|beats|beat|misses|missed|tops|topped|rises|rose|falls|fell|jumps|jumped|slumps|slumped|raises|raised|cuts|cut|lowers|holds|keeps|expands|expanded|declines|declined|accelerates|slows|increases|increased|decreases|decreased|drops|dropped)\b|"
                       r"(?:Trump|Harris|Fed|FOMC|Federal Reserve|BOE|Bank of England|RBA|Reserve Bank of Australia|RBNZ|Bank of Canada|ECB|BOJ|NBP|RPP|China|Nvidia)"
                       r".{0,35}\b(?:wins|cuts|cut|lowers|holds|keeps|expands|expanded|declines|declined|accelerates|slows|increases|increased|decreases|decreased|drops|dropped|leaves|reports|beats|beat|misses|missed|unveils|approves|announces)\b",re.I)

EXPLICIT_PREVIEW = re.compile(r"\b(?:preview|ahead of|what to expect|set to report|earnings calendar)\b|"
                              r"\b(?:expected|forecast|likely|seen|set|poised|due) to (?:win|cut|hold|keep|report|beat|announce|unveil|release)\b|"
                              r"\b(?:will|could|would|might) (?:win|cut|hold|keep|report|beat|announce|unveil|release)\b",re.I)

FORWARD_ACTION = re.compile(
    r"\b(?:(?:will|could|would|may|might|should)(?:\s+(?:also|still|soon|now|again|further))?|"
    r"(?:expected|forecast|likely|seen|set|poised|due)\s+to|plans?\s+to|to)\s+"
    r"(?:win|cut|hold|keep|report|beat|miss|top|rise|fall|jump|surge|slump|raise|lower|announce|unveil|"
    r"approve|expand|decline|accelerate|slow|increase|decrease|drop|gain|grow|cool|ease|moderate|reach|hit|shrink|contract|rebound|rattle|dominate|spar|clash|defeat|vow|pledge|urge|promise|release|publish|decide|leave|end|secure|sweep|close|show|trade|exchange|attack|accuse)\b",re.I)

FINANCIAL_OUTCOME=re.compile(r"\b(?:beats?|miss(?:es|ed)?|tops?|reports?|reported|posts?|posted|cuts?|raises?|lowers?)\b.{0,35}\b(?:earnings|revenue|sales|profit|EPS|guidance|forecasts?|bookings|deliveries|estimates|results)\b|\b(?:earnings|revenue|sales|profit|EPS|guidance|forecasts?|bookings|deliveries|results)\b.{0,35}\b(?:beats?|miss(?:es|ed)?|tops?|rose|fell|rises?|falls?|grows?|grew|surges?|jumps?|slumps?|drops?|declines?|doubles?|triples?|soars?|disappoints?|disappointed|record)\b",re.I)

MARKET_CLAUSE=re.compile(r"\b(?:stocks?|shares?|equities|bonds?|bond yields?|dollar|yen|yuan|gold|oil|markets?)\b[^,;.!?]{0,45}\b(?:rose|fell|rises?|falls?|gains?|jumps?|surges?|slumps?|drops?|declines?)\b",re.I)

POLICY_OUTCOME=re.compile(r"\b(?:Fed|FOMC|Federal Reserve|ECB|Lagarde|BOJ|Bank of Japan|Ueda|RBA|RBNZ|Bank of Canada|PBOC|NBP|RPP|Glapi\w*)\b.{0,45}\b(?:cuts?|hikes?|lifts?|lifted|raises?|holds?|held|keeps?|kept|leaves?|left|lowers?|lowered|unchanged|decides?|agrees?|agreed|announces?|announced)\b|\b(?:rates?|policy|bond.buying)\b.{0,30}\b(?:cut|held|unchanged|raised|hiked|reduced|kept|left)\b",re.I)

ADDITIONAL_FORWARD=re.compile(r'\b(?:before (?:the )?(?:earnings|results|report|decision)|earnings expectations|earnings estimates|looms?|considers?|mulls?|weighs?|could|would|might)\b',re.I)

FUTURE_RATE_NOUN=re.compile(r'\b(?:(?:likelihood|chances?|prospect|probability|odds|hopes|expectations|bets) of (?:a |another |the )?|(?:a|an|another|next|possible|potential|expected) )(?:Fed )?(?:rate )?(?:cut|hike)\b',re.I)

SETTLED_UK=re.compile(r'\b(?:is named|was named|has been named|named prime minister|sworn in|has conceded|concedes (?:defeat|the election)|conceded (?:defeat|the election)|appointed prime minister|becomes? (?:Britain[’\']s |the )?prime minister|enters? Downing Street|takes office|takes power)\b',re.I)

MODAL_SUBJECT_ACTION=re.compile(r'\b(?:will|could|would|can|might|may|should)\s+(?:the\s+)?(?:Fed|FOMC|ECB|BOJ|RBA|PBOC|it|they|he|she)\s+(?:rate\s+)?(?:cuts?|hikes?|raises?|holds?|keeps?|reports?|beats?|misses?|tops?|grows?)\b',re.I)

PENDING_POLICY_ACTION=re.compile(r'\b(?:to weigh|to debate|to discuss|to consider|weighs?|considers?|debates?|discusses?|mulls?)\s+(?:(?:an?|the|another)\s+)?(?:rate\s+)?(?:hike|cut|increase|reduction)\b|\b(?:possible|potential|expected|likely|prospective|anticipated)\s+(?:(?:Fed|BOJ|ECB|PBOC)\s+)?(?:rate\s+)?(?:hike|cut|increase|reduction)\b|\b(?:opens?|opening|opened)\s+(?:the\s+)?door\s+to\s+(?:rate\s+)?cuts?\b',re.I)

PENDING_FINANCIAL_CLAUSE=re.compile(r'\b(?:set for|poised for|on track for)\b[^,;.!?]{0,100}\b(?:decline|rise|fall|growth|increase|decrease)\b',re.I)

FINANCIAL_COMPLETION_HINT=re.compile(r'\b(?:earnings|results|revenue|sales|profits?|EPS)\b.{0,30}\b(?:were|was|came in|surprise|surprises|surprised|beat|beats|miss|misses|rose|fell|soars?|doubles?|disappoints?)\b',re.I)

def guard_hit(title,published,stamp):
    """Reject a premature outcome without making a later-clause modal an escape."""
    if title in OBSERVED_COMPANY_PREVIEWS:return None
    normalised=NEUTRALISE.sub('',title)
    for label,eligible,start,pattern in RELEASE_GUARDS:
        if not(stamp<eligible and start<=published<stamp and re.search(pattern,title,re.I)):continue
        kind=GUARD_META[label]['kind']
        observed=DISPOSITION_BY_EVENT.get((title,label))
        if observed and observed.get('applies_from_edition','0000-00-00')>stamp:observed=None
        if observed:
            assert observed['disposition']in{'not_this_event','preview'}and observed['reason']
            continue
        if kind in {'split_distribution','split_trading'}:
            stage_text=re.sub(r'\b(?:split.adjusted|post.split)\s+trading\s+(?:will|is expected to|is set to|is scheduled to|to)\s+(?:begin|start|commence)\b', '',normalised,flags=re.I)
            stage_text=FORWARD_ACTION.sub('',stage_text)
            stage_text=re.sub(r'\b(?:will|could|would|may|might|expected to|scheduled to|set to|plans? to|to)\s+(?:be\s+)?(?:split|distribute|distribute[ds]|complete|completed|become effective|effective|begin|start|commence|trade)\b[^,;.!?]{0,45}', '',stage_text,flags=re.I)
            if kind=='split_trading':
                actual=re.search(r'split.adjusted.{0,35}(?:trading|trade)|(?:begins?|began|starts?|started|commences?|commenced).{0,35}(?:trading|trade).{0,25}split|(?:first|debut).{0,20}(?:day|session).{0,25}(?:after|following).{0,20}split',stage_text,re.I)
            else:
                actual=re.search(r'(?:has|have|had|was|were).{0,12}(?:split|distributed)|split.{0,25}(?:completed|effective|took effect)|(?:completed|completes|distributed|distributes).{0,30}(?:split|shares)|split.adjusted',stage_text,re.I)
            if actual:return label
            continue
        if kind=='staged_event':
            # Announcing a schedule is a real earlier event, not the keynote or
            # debate itself. Finished clauses cannot hide behind later forecasts.
            stage_text=FORWARD_ACTION.sub('',normalised)
            historical=bool(re.search(r'debates? in history|presidential debate history|six decades of|facts about presidential|questions about presidential|presidential debates.{0,20}healthy democracy|most memorable.{0,25}debate history|which presidential debates drew',normalised,re.I))
            pending=re.search(r'how to watch|what time|what to (?:watch|know)|watching for|what.{0,3}at stake|faces? pressure to|to face off|faces? (?:Trump|Biden) in (?:the )?first.{0,20}debate|preview|what to expect|ahead of|set to|scheduled|plans? to|will|could|would|may|might|to (?:host|hold|begin|unveil|announce)|announces?.{0,30}(?:date|schedule)',normalised,re.I)
            outcome=re.search(r'\b(?:trade insults|exchange accusations|attack(?:s|ed)?|accus(?:es|ed)|approved|approves?|authorized|authorizes?|voted|votes?|unveils?|unveiled|introduced|introduces|announced|revealed|reveals|launches?|launched|debuts?|debuted|clash(?:es|ed)?|spar(?:s|red)?|stumbles?|stumbled|rattles?|rattled|dominates?|dominated|wins?|won|loses?|lost|performance|takeaways|highlights|recap|what.{0,10}learned|fact.check)\b',stage_text,re.I)
            directly_pending=re.search(r'(?:will|could|would|may|might|expected to|set to|to)\s+(?:unveil|introduce|announce|reveal|launch|debut|clash|spar|stumble|rattle|dominate|win|lose)\b',normalised,re.I)
            if outcome:return label
            if historical or pending:continue
            return label
        # Mask only directly governed future actions. Do not erase a completed
        # first clause because another clause forecasts something else.
        policy_pending=re.sub(r'\b(?:is|are)\s+(?:set|expected|likely|poised)\s+to\s+(?:begin|start|commence)\s+(?:rate\s+)?(?:cuts|hikes)\b','',normalised,flags=re.I)
        policy_pending=re.sub(r'\b(?:expected to|forecast to|likely to|seen to|set to|will|could|would|may|might)\s+(?:keep|hold|leave)\b[^,;.!?]{0,50}\b(?:unchanged|steady|on hold)\b','',policy_pending,flags=re.I)
        outcome_text=FUTURE_RATE_NOUN.sub('',PENDING_FINANCIAL_CLAUSE.sub('',PENDING_POLICY_ACTION.sub('',MODAL_SUBJECT_ACTION.sub('',FORWARD_ACTION.sub('',policy_pending)))))
        direct_forward=outcome_text!=normalised
        if re.match(r'^\s*(?:what\s+)?if\b',normalised,re.I):
            first=re.split(r'[?;.!]',normalised,maxsplit=1)[0]
            outcome_text=outcome_text.replace(first,'',1)
            direct_forward=True
        calendar_notice=bool(re.search(r'announc\w*.*(?:webcast|conference call|date|schedule)|sets? (?:the )?date|date for .*results',normalised,re.I))
        clear_preview=bool(re.search(r'(?:five|six|ten|key|big) questions for',normalised,re.I) or direct_forward or calendar_notice or EXPLICIT_PREVIEW.search(normalised) or PREVIEW.search(normalised) or ADDITIONAL_FORWARD.search(normalised) or re.search(r'Outlook for|optimism about|before (?:Q[1-4] |quarterly )?(?:earnings|results)|nears? (?:the )?earnings|earnings to (?:reflect|show|test|reveal|shed)|here.s what you need to know|meeting started|(?:earnings|profits?|revenue|sales) (?:seen|expected|forecast) [a-z]+',normalised,re.I))
        if kind in{'company_result','company_operation'}:
            # A stock move before earnings is eligible news; it does not report
            # the financial outcome. Actual cuts/beats in another clause fail.
            # Preserve observed separate disclosures/issuer roles, not a future
            # parent-company result: Westlife franchisee, industry EV sales and
            # litigation about streaming-revenue taxation are different events.
            if FINANCIAL_COMPLETION_HINT.search(MARKET_CLAUSE.sub('',outcome_text))or FINANCIAL_OUTCOME.search(MARKET_CLAUSE.sub('',outcome_text)):return label
            if re.search(r'court|lawsuit|appeal|tax',title,re.I)and not re.search(r'earnings|results|profits?|EPS|quarter',title,re.I):continue
            if clear_preview:continue
            return label
        if kind=='policy':
            if POLICY_OUTCOME.search(outcome_text):return label
            if clear_preview or FORWARD.search(normalised):continue
            return label
        if COMPLETED.search(MARKET_CLAUSE.sub('',outcome_text)):return label
        if clear_preview or FORWARD.search(normalised):continue
        return label
    return None
CANONICAL_SCREENING='Canonical publisher vintages not generally resolved. Author news input uses exact RSS headlines/pubDate with finite April release guards and observed event dispositions. Separate clock review may inspect publisher pages for identity/vintage/time only; no article-body facts enter the feed.'
