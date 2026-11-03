from datetime import date,timedelta
import re

CATEGORIES={
 'results':(10,'Compare reported numbers and margins.'),
 'management_change':(9,'Inspect succession and verified experience.'),
 'M&A':(9,'Check consideration, funding and strategic fit.'),
 'litigation':(9,'Inspect quantified exposure; no inferred materiality.'),
 'fund_raise':(8,'Check dilution, funding cost and use of proceeds.'),
 'pledging':(8,'Watch changes in promoter collateral exposure.'),
 'credit_rating':(7,'Prioritise downgrades; collapse reaffirmations.'),
 'capex':(7,'Check capital commitment against cash generation.'),
 'insider_trading':(6,'Surface size and direction, without predicting returns.'),
 'dividend':(5,'Surface amount and record date.'),
 'bonus_split':(5,'Surface ratio and record date; no wealth creation claim.'),
 'press_release':(4,'Surface only the sourced operating development.'),
 'earnings_call':(3,'Link the transcript; notices remain routine.'),
 'investor_meetings':(1,'Collapse scheduling disclosures.'),
 'postal_ballot':(1,'Collapse routine voting notices.'),
 'agm_egm':(1,'Collapse meeting logistics.'),
 'unclassified':(2,'Keep visible in the routine archive; flag uncertain classification.')}
PATTERNS=[('management_change',r'\b(cfo|ceo|managing director|chief financial|resignation|appointment of.*director)\b'),('M&A',r'acqui[rs]|merger|joint venture|demerger'),('litigation',r'litigation|penalty|court|insolvency|regulatory order'),('fund_raise',r'fund.?rais|qip|rights issue|preferential|buyback'),('pledging',r'pledg'),('credit_rating',r'credit rating|rating reaffirm'),('capex',r'capex|capacity expansion|new plant'),('insider_trading',r'insider|promoter.*(purchase|sale)'),('bonus_split',r'bonus issue|stock split|sub.division'),('dividend',r'dividend'),('earnings_call',r'earnings call|conference call|concall|transcript'),('investor_meetings',r'investor meet|analyst meet'),('postal_ballot',r'postal ballot'),('agm_egm',r'annual general|extraordinary general|agm|egm'),('results',r'financial results|quarterly results|audited results'),('press_release',r'press release|order win|partnership')]
def classify(text):
    matches=[cat for cat,pat in PATTERNS if re.search(pat,text,re.I)]
    return {'category':matches[0] if matches else 'unclassified','confidence':'high' if len(matches)==1 else 'low','candidates':matches}

def rank(item,weight=5,subscriptions=()):
    base=CATEGORIES.get(item['category'],(2,''))[0]
    reaction=1+min(abs(item.get('price_change') or 0)/10,.5)+min(max((item.get('volume_ratio') or 1)-1,0)/5,.5)
    score=round(base*(1.3 if item['category'] in subscriptions else 1)*reaction*(.7+weight/10),1)
    tier='Needs attention' if score>=12 else 'Worth a look' if score>=5 else 'Routine'
    return dict(item,score=score,tier=tier,rank_reason=f"{item['category'].replace('_',' ')} · {weight:g}% position · {'subscribed' if item['category'] in subscriptions else 'not subscribed'} · "+(f"{reaction:.2f}× reaction" if item.get('price_change') is not None else 'reaction unavailable'))

def digest(items,as_of,days,weights,subscriptions,start=None):
    end=date.fromisoformat(as_of); begin=date.fromisoformat(start) if start else end-timedelta(days=days-1)
    return sorted([rank(i,weights.get(i['ticker'],5),subscriptions) for i in items if begin<=date.fromisoformat(i['date'])<=end],key=lambda i:i['score'],reverse=True)

def alert_events(prices,announcements,rules,as_of,days=30):
    end=date.fromisoformat(as_of); begin=end-timedelta(days=days-1); found=[]
    for row in prices:
        if not begin<=date.fromisoformat(row['date'])<=end: continue
        rule={**rules,**rules.get('overrides',{}).get(row['ticker'],{})}
        reasons=[]
        if row.get('volume_ratio') is not None and row['volume_ratio']>rule.get('volume',2): reasons.append(f"Volume {row['volume_ratio']:.2f}× > {rule.get('volume',2):g}×")
        if row.get('price_change') is not None and abs(row['price_change'])>rule.get('price',4): reasons.append(f"Move {row['price_change']:+.2f}% exceeds ±{rule.get('price',4):g}%")
        if reasons: found.append(dict(row,reasons=reasons,kind='market'))
    for row in announcements:
        if begin<=date.fromisoformat(row['date'])<=end and row['category'] in rules.get('categories',[]) and CATEGORIES.get(row['category'],(0,''))[0]>=5:
            found.append(dict(row,reasons=['Subscribed material announcement'],kind='filing'))
    return found
