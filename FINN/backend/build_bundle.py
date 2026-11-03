"""Static Push preparation. No PDF processing or model calls."""
import json,re
from pathlib import Path
from datetime import datetime,timedelta
from collections import Counter,defaultdict
from .finance import fiscal_period

ROOT=Path(__file__).resolve().parents[1]
WEIGHTS={'results':10,'management_change':9,'M&A':9,'litigation':9,'fund_raise':8,'pledging':8,'order_win':7,'credit_rating':7,'capex':7,'insider_trading':6,'dividend':5,'bonus_split':5,'product_or_partnership':4,'clarification':4,'earnings_call':3,'unclassified':2,'routine':1}
DEFAULT=['results','management_change','M&A','litigation','fund_raise','order_win']

def results_period(subject,stamp):
 # Prefer the reporting period, not a date elsewhere in exchange boilerplate.
 text=re.split(r'\b(?:ended|ending)\b',subject,flags=re.I)[-1]
 months={'march':3,'mar':3,'june':6,'jun':6,'september':9,'sep':9,'december':12,'dec':12}
 names='|'.join(months)
 m=re.search(rf'(?:(?:30|31)(?:st|th)?\s+({names})|({names})\s+(?:30|31)(?:st|th)?)[,\s]*(20\d{{2}})?',text,re.I)
 if m:
  month=months[(m[1] or m[2]).lower()];year=int(m[3] or stamp[:4])
  if not m[3] and month>int(stamp[5:7]):year-=1
  return fiscal_period(f'{year}-{month:02d}-01')
 # Results published in a quarter normally concern the last completed quarter.
 d=datetime.fromisoformat(stamp);first=((d.month-1)//3)*3+1
 return fiscal_period((d.replace(month=first,day=1)-timedelta(days=1)).date().isoformat())

def headline(row,c):
 ticker=row['ticker'];subject=row['subject']
 if c=='results':return f'{ticker} {results_period(subject,row["datetime"])} results'
 fallback=f'{ticker} '+{'unclassified':'Regulatory update','M&A':'Acquisition update','routine':'Routine filing'}.get(c,c.replace('_',' ').capitalize())
 text=re.sub(r'^.*?has (?:informed|submitted to) the Exchange(?:\s+(?:regarding|about|that))?[,\s]*','',subject,flags=re.I)
 title=re.search(r'\btitled\s+["\s]*(.+)',text,re.I)
 if title:text=title[1]
 if re.match(r'In continuation|Pursuant to',text,re.I):
  pieces=re.split(r'we (?:wish to )?inform|please find (?:enclosed|attached)|regarding|about',text,maxsplit=1,flags=re.I)
  if len(pieces)<2:return fallback
  text=pieces[1]
 text=re.sub(r'^(?:we (?:wish to )?inform )?you that\s+','',text,flags=re.I)
 text=re.sub(r'^press release\s*[-:]\s*','',text,flags=re.I)
 if re.match(r'(?:the )?board (?:of directors of the company,? )?(?:at|has at)',text,re.I):return fallback
 # Known routine subjects get complete noun phrases, not legal fragments.
 for pattern,caption in [(r'newspaper','Newspaper notice'),(r'schedule.*meet|investors?.*meeting','Investor meeting schedule'),(r'trading window','Trading window notice'),(r'certificate under|regulation 74','Depository compliance certificate'),(r'link.*recording|audio recording','Earnings call recording')]:
  if re.search(pattern,text,re.I):return f'{ticker} {caption}'
 if re.search(r'^(?:disclosure|intimation).*regulation|^announcement under',text,re.I):return fallback
 text=re.sub(r'^(?:(?:the|a|an|regarding|about|please note that)\s+)+','',text.strip(' \"\'.,'),flags=re.I)
 text=re.sub(r'\s+',' ',text).strip(' \"\'.,')
 text=re.split(r'(?<=[.!?])\s+(?=[A-Z])',text)[0]
 words=text.split()[:12]
 dangling={'for','the','a','an','of','to','and','or','in','on','at','by','with','under','from','its','our','their','that','as','financial','unaudited','standalone','consolidated','fy','major'}
 while words and words[-1].lower().strip('.,;:') in dangling:words.pop()
 if len(words)<3:return fallback
 clean=' '.join(words).strip(' ,;:.-\"\'');return clean[:1].upper()+clean[1:].lower()
def category(row):
 s=row['subject'].lower(); c=row['our_category']
 if re.search('newspaper|analyst.*meet|investor.*meet|schedule.*meet|trading window',s): return 'routine'
 if c in ['routine_compliance','investor_meetings','agm_egm','postal_ballot']: return 'routine'
 if c=='press_release':
  if re.search('order.*(win|award)|wins?.*order|contract.*award',s): return 'order_win'
  if re.search('clarif|rumour|rumor',s): return 'clarification'
  if re.search('product|launch|partner|collaborat|innovation|modernization|transformation',s): return 'product_or_partnership'
  return 'routine'
 return c
def reaction(stamp,prices):
 dt=datetime.fromisoformat(stamp); day=dt.date().isoformat()
 eligible=[p for p in prices if p['date']>day or (p['date']==day and (dt.hour,dt.minute)<(15,30))]
 if not eligible: return dict(session=None,price_pct=None,volume_ratio=None,label='Next reaction session unavailable')
 p=min(eligible,key=lambda p:p['date'])
 return dict(session=p['date'],price_pct=p['price_change'],volume_ratio=p['volume_ratio'],label='EOD market reaction; not attribution')
def topic(row):
 s=row['subject'].lower()
 if re.search('financial result|quarter.*result|earnings|transcript|presentation|newspaper|audio.*record|recording',s): return 'results'
 return row['category']
def score(item,asof,subs=DEFAULT):
 r=item['reaction']; available=r['session'] and r['session']<=asof
 reaction_factor=1+min(abs(r['price_pct'] or 0)/10,.5)+min(max((r['volume_ratio'] or 1)-1,0)/5,.5) if available else 1
 return round(WEIGHTS.get(item['category'],2)*(1.3 if item['category'] in subs else 1)*reaction_factor*(.7+item['weight']/10),3)
def cluster(items):
 groups=defaultdict(list)
 for i in items: groups[(i['ticker'],i['datetime'][:10],i['topic'])].append(i)
 out=[]
 for group in groups.values():
  ordered=sorted(group,key=lambda i:(-WEIGHTS.get(i['category'],2),i['datetime'],i['id']))
  out.append(dict(ordered[0],attachments=ordered[1:]))
 return out
def counts(items,asof,days,thresholds):
 start=(datetime.fromisoformat(asof)-timedelta(days=days-1)).date().isoformat(); c=Counter()
 for i in cluster([i for i in items if start<=i['datetime'][:10]<=asof]):
  s=score(i,asof); tier='routine' if i['category']=='routine' else 'attention' if s>=thresholds[0] else 'look' if s>=thresholds[1] else 'routine'; c[tier]+=1
 return {k:c[k] for k in ['attention','look','routine']}
def build():
 seed=json.loads((ROOT/'data/snapshot.json').read_text()); holdings=json.loads((ROOT/'data/portfolio.json').read_text())['portfolio']; by={h['ticker']:h for h in holdings}; items=[]
 for row in seed['announcements']:
  c=category(row)
  item=dict(row,category=c,headline=headline(row,c),weight=by[row['ticker']]['weight'],reaction=reaction(row['datetime'],[p for p in seed['prices'] if p['ticker']==row['ticker']]))
  item['topic']=topic(item); items.append(item)
 # Fit fixed thresholds on 30d only; small windows are reported, not forced into quotas.
 asof=seed['as_of']; best=None
 for a in range(100,261):
  for l in range(30,a,5):
   thresholds=[a/10,l/10]; c=counts(items,asof,30,thresholds); n=sum(c.values()) or 1
   loss=abs(c['attention']/n-.075)+abs(c['look']/n-.175)
   if best is None or loss<best[0]: best=(loss,thresholds)
 thresholds=best[1]
 bundle=dict(version=1,as_of=asof,announcements_through=seed['announcements_through'],holdings=holdings,prices=seed['prices'],announcements=items,sessions=sorted({p['date'] for p in seed['prices']}),weights=WEIGHTS,default_categories=DEFAULT,thresholds=thresholds,calibration={str(d):counts(items,asof,d,thresholds) for d in [1,7,30]},coverage_note='NSE filings: 15 Sep–3 Nov 2026. Earlier replay dates have prices only. Mock portfolio weights.')
 bundle['research']={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in (ROOT/'data/research').glob('*.json')}
 # Compact repeated provenance in the browser bundle; full metric provenance stays in research/*.json.
 for research in bundle['research'].values():
  research['metric_provenance']='Every metric inherits this company source and URL; originals retain explicit provenance.'
  for table in research.get('tables',{}).values():
   for row in table:
    for metric in row['metrics']:
     for key in ['source','url','raw']:metric.pop(key,None)
 for name,key in [('promise-vs-delivered','curated'),('management-enrichment','management')]:
  path=ROOT/'data'/f'{name}.json'
  if path.exists():bundle[key]=json.loads(path.read_text(encoding='utf-8-sig'))
 results=ROOT/'data/parsed-results.json'
 bundle['results']=json.loads(results.read_text(encoding='utf-8')) if results.exists() else {}
 assert len(json.dumps(bundle).encode())<2000000, 'Bundle exceeds 2 MB'
 (ROOT/'data/bundle.json').write_text(json.dumps(bundle,separators=(',',':')),encoding='utf-8'); print(json.dumps({'thresholds':thresholds,'counts':bundle['calibration']})); return bundle
if __name__=='__main__': build()
