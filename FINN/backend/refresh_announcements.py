"""Bounded public-source refresh. No LLMs, no PDF parsing."""
import json,hashlib,time,re
from datetime import datetime,timedelta,timezone
from collections import Counter
from urllib.parse import urlencode,urljoin
from pathlib import Path
import httpx
from bs4 import BeautifulSoup
from .sources import DATA,YahooAdapter
from .announcement_classifier import classify

IST=timezone(timedelta(hours=5,minutes=30))
HEADERS={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36','Referer':'https://www.bseindia.com/','Origin':'https://www.bseindia.com','Accept':'application/json,text/html,application/pdf,*/*'}
RAW=DATA/'cache'/'current-feed'
class Fetcher:
 def __init__(self): self.client=httpx.Client(headers=HEADERS,timeout=25,follow_redirects=True); self.last=0
 def get(self,url):
  RAW.mkdir(parents=True,exist_ok=True); key=hashlib.sha256(url.encode()).hexdigest(); f=RAW/(key+'.raw')
  if f.exists(): return f.read_bytes()
  meta=RAW/(key+'.meta.json')
  if meta.exists() and json.loads(meta.read_text())['status']>=400: raise ValueError('Cached HTTP '+str(json.loads(meta.read_text())['status'])+' (attempt budget exhausted)')
  for attempt in range(3):
   time.sleep(max(0,1.05-(time.monotonic()-self.last))+2**attempt-1); self.last=time.monotonic()
   try:
    print('Fetching',url,flush=True)
    began=time.monotonic(); chunks=[]; size=0
    with self.client.stream('GET',url) as r:
     (RAW/(key+'.meta.json')).write_text(json.dumps({'url':url,'status':r.status_code,'fetched_at':datetime.now(IST).isoformat()}))
     r.raise_for_status()
     for chunk in r.iter_bytes():
      size+=len(chunk); chunks.append(chunk)
      if time.monotonic()-began>40 or size>30_000_000: raise ValueError('Download exceeded 40 seconds or 30 MB; not retried')
    body=b''.join(chunks); f.write_bytes(body); return body
   except httpx.HTTPError:
    if attempt==2: raise

def normalize(symbol,stamp,subject,category,pdf,source):
 if not pdf or not pdf.startswith(('https://','http://')): pdf=None
 dt=datetime.fromisoformat(stamp)
 if dt.tzinfo is None: dt=dt.replace(tzinfo=IST)
 dt=dt.astimezone(IST); result=classify(subject)
 return dict(id=hashlib.sha256(f'{symbol}|{dt.isoformat()}|{pdf}|{subject}'.encode()).hexdigest()[:24],ticker=symbol,datetime=dt.isoformat(),subject=subject,exchange_category=category,our_category=result['category'],confidence=result['confidence'],pdf_url=pdf,source=source,fetched_at=datetime.now(IST).isoformat())

def price_history(fetcher,symbol):
 start=int(datetime(2026,6,1,tzinfo=IST).timestamp()); end=int(datetime(2026,11,4,tzinfo=IST).timestamp())
 body=json.loads(fetcher.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS?period1={start}&period2={end}&interval=1d'))
 result=body['chart']['result'][0]; quotes=result['indicators']['quote'][0]; rows=[]
 for i,stamp in enumerate(result['timestamp']):
  close=quotes['close'][i]; volume=quotes['volume'][i]
  if close is None or volume is None: continue
  previous=rows[-1]['close'] if rows else None; baseline=sum(r['volume'] for r in rows[-20:])/20 if len(rows)>=20 else None
  rows.append(dict(ticker=symbol,date=datetime.fromtimestamp(stamp,IST).date().isoformat(),close=round(close,4),volume=volume,price_change=round((close/previous-1)*100,3) if previous else None,volume_ratio=round(volume/baseline,3) if baseline else None,source='Yahoo Finance chart API',simulated=False))
 return rows,'live or raw cache (Yahoo chart)'

def refresh():
 f=Fetcher(); portfolio=json.loads((DATA/'portfolio.json').read_text())['portfolio']; allrows=[]; coverage=[]; prices=[]; failures=[]; results=[]
 for h in portfolio:
  symbol=h['ticker']; soup=BeautifulSoup(f.get(f'https://www.screener.in/company/{symbol}/consolidated/'),'html.parser')
  labels=[a.get_text(' ',strip=True) for a in soup.select('a')]; bse=next((re.search(r'BSE:\s*(\d+)',x).group(1) for x in labels if re.search(r'BSE:\s*(\d+)',x)),None)
  nse=next((re.search(r'NSE:\s*(\S+)',x).group(1) for x in labels if re.search(r'NSE:\s*(\S+)',x)),None)
  rows=[]; errors=[]
  try:
   if not bse: raise ValueError('No BSE code in Screener header')
   for page in range(1,51):
    query=urlencode(dict(pageno=page,strCat=-1,strPrevDate='20260915',strScrip=bse,strSearch='P',strToDate='20261103',strType='C'))
    raw=json.loads(f.get('https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w?'+query))
    if not isinstance(raw,dict): raise ValueError(str(raw))
    batch=raw.get('Table',[])
    if not batch: break
    for r in batch: rows.append(normalize(symbol,r['NEWS_DT'],r['NEWSSUB'],r.get('CATEGORYNAME'),urljoin('https://www.bseindia.com/xml-data/corpfiling/AttachLive/',r['ATTACHMENTNAME']),'bse'))
   else: raise ValueError('pagination cap; incomplete')
   if not rows: raise ValueError('Empty BSE window')
  except Exception as e: errors.append('BSE: '+str(e)); rows=[]
  if not rows:
   try:
    f.get('https://www.nseindia.com/')
    query=urlencode(dict(index='equities',symbol=symbol,from_date='15-09-2026',to_date='03-11-2026'))
    raw=json.loads(f.get('https://www.nseindia.com/api/corporate-announcements?'+query))
    if not isinstance(raw,list): raise ValueError('Non-list response')
    for r in raw: rows.append(normalize(symbol,r['sort_date'],r.get('attchmntText') or r['desc'],r.get('desc'),r.get('attchmntFile'),'nse'))
    if not rows: raise ValueError('Empty NSE window')
   except Exception as e: errors.append('NSE: '+str(e)); rows=[]
  if not rows:
   for li in soup.select('#company-announcements-tab li'):
    a=li.find('a'); t=li.find('time')
    if a and t: rows.append(normalize(symbol,t['datetime'],' '.join(a.find_all(string=True,recursive=False)).strip(),None,a['href'],'screener'))
   if not rows:
    failures.append(dict(ticker=symbol,errors=errors+['Screener: no dated public announcements']))
    (DATA/'refresh-failures.json').write_text(json.dumps(failures,indent=2)); raise RuntimeError('All three sources failed: '+symbol+' '+str(failures))
   errors.append('Screener recent list only; search requires login; window incomplete')
  rows=list({r['id']:r for r in rows if '2026-09-15'<=r['datetime'][:10]<='2026-11-03'}.values())
  candidates=[r for r in rows if re.search(r'financial results|financial result',r['subject'],re.I) and re.search(r'sep|30.09.2026|q2',r['subject'],re.I) and not re.search(r'will be|to consider|intimation|scheduled|newspaper|transcript|recording|call with|earnings call',r['subject'],re.I)]
  downloaded=False
  for r in candidates:
   try: blob=f.get(r['pdf_url']); ok=blob.lstrip().startswith(b'%PDF-'); error=None if ok else 'Response is not PDF bytes'
   except Exception as e: ok=False; error=str(e)
   results.append(dict(ticker=symbol,subject=r['subject'],pdf_url=r['pdf_url'],downloaded=ok,error=error)); downloaded|=ok
  series,mode=price_history(f,symbol)
  # Today is incomplete before 15:30 IST; never seed an intraday bar as EOD.
  now=datetime.now(IST); cutoff='2026-11-03' if (now.hour,now.minute)>=(16,0) else '2026-11-02'
  series=[r for r in series if r['date']<=cutoff][-60:]; prices.extend(series)
  allrows.extend(rows); coverage.append(dict(ticker=symbol,bse=bse,nse=nse,announcement_count=len(rows),results_found=bool(candidates),pdf_downloaded=downloaded,price_sessions=len(series),price_mode=mode,source=rows[0]['source'] if rows else None,errors=errors))
  print(symbol,len(rows),'results',len(candidates),'prices',len(series),flush=True)
  (DATA/'refresh-report.json').write_text(json.dumps(dict(coverage=coverage,results=results,distribution=dict(Counter(r['our_category'] for r in allrows))),indent=2))
  (RAW/'normalized-progress.json').write_text(json.dumps(allrows))
 fixture=DATA/'infosys-april-2025-fixture.json'
 if not fixture.exists(): fixture.write_bytes((DATA/'snapshot.json').read_bytes())
 snapshot=dict(schema_version=2,as_of=max(r['date'] for r in prices),mode='historical real-source snapshot',coverage=coverage,prices=prices,documents=[],announcements=allrows)
 (DATA/'snapshot.json').write_text(json.dumps(snapshot,separators=(',',':')),encoding='utf-8')
 print('distribution',dict(Counter(r['our_category'] for r in allrows)),flush=True)
if __name__=='__main__': refresh()
