from pathlib import Path
import json
R=Path(__file__).resolve().parents[1];d='2025-08-18'
s=json.loads((R/'specs'/f'{d}.json').read_text());c=json.loads((R/'cards'/f'{d}.json').read_text())
def price(t):
 m=c['markets'][t];v=m['chg_20s_pct'];return f"{t} closed at {m['close']}, {'up' if v>=0 else 'down'} {abs(v):.2f}% over 20 sessions. (Yahoo Finance, prior close {m['session']}) "
x={'title':'$AMAT — China access changes the equipment outlook','stance':'Bearish','parts':[
['Catalyst & Thesis',"Reuters reports that Applied Materials' forecast was hit by a China pause and export-license problems, with the shares down 13%. [[n1381]] That is a specific revenue-access and customer-timing problem rather than a reason to declare that all semiconductor demand has collapsed. The investment needs a route from equipment demand to permitted, profitable delivery."],
['Price Hurdle & Risk',price('AMAT')+"A weaker share price can compensate for uncertainty only when the earnings range can be assessed. China permissions and the timing of customer spending may change the near-term revenue path even while the longer-term equipment opportunity survives. Avoid valuing uncertain access as guaranteed sales."],
['Trade Expression',"Avoid adding long exposure until the company can establish a more dependable delivery and earnings bridge. The positive trigger would be clearer access or customer demand that replaces the affected opportunity; another expansion in the broad AI narrative alone would not resolve the forecast constraint. Reuters' account identifies the policy and timing risks behind that caution. [[n1381]]"]]}
s['catalysts']=[x if b['title'].startswith('$HOOD') else b for b in s['catalysts']]
for b in s['catalysts']:
 if b['title'].startswith('$LLY'):
  b['parts'][0][1]="Yahoo Finance reports BofA's analyst raising questions about US pricing after Lilly increased GLP-1 prices abroad. [[n5140]] The commercial catalyst is the relationship between demand, realised pricing and access. Investors need to distinguish a larger market opportunity from the amount the producer can earn after distribution, reimbursement and supply commitments."
  b['parts'][1][1]=price('LLY')+"Pricing is not the only risk: Reuters reports a Texas lawsuit alleging that Lilly bribed providers to prescribe its medicines. [[n5806]] An allegation is not a finding, but the legal process belongs in the risk assessment alongside commercial demand and the valuation."
(R/'specs'/f'{d}.json').write_text(json.dumps(s,ensure_ascii=False,indent=2))
