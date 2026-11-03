"""Live → disk cache → committed seed. Failures remain visible."""
import hashlib,json,time,re
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urljoin,urlparse
import httpx
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; CACHE=DATA/'cache'
def ticker(value):
    value=value.upper().removesuffix('.NS')
    if not re.fullmatch(r'[A-Z0-9&-]{1,24}',value): raise ValueError('Invalid NSE symbol')
    return value

class CachedHTTP:
    def get(self,url,ttl=86400):
        CACHE.mkdir(exist_ok=True); key=hashlib.sha256(url.encode()).hexdigest(); file=CACHE/(key+'.bin')
        if file.exists() and time.time()-file.stat().st_mtime<ttl: return file.read_bytes(),'cache'
        error=None
        for attempt in range(3):
            try:
                time.sleep(.5*(attempt+1))
                r=httpx.get(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json,text/html,application/pdf','Referer':'https://www.bseindia.com/'},timeout=25,follow_redirects=True)
                r.raise_for_status(); file.write_bytes(r.content); return r.content,'live'
            except (httpx.HTTPError,OSError) as exc: error=exc
        if file.exists(): return file.read_bytes(),'stale cache'
        raise RuntimeError(f'Source unavailable: {type(error).__name__}')

class ScreenerAdapter:
    def fetch(self,symbol):
        symbol=ticker(symbol); url=f'https://www.screener.in/company/{symbol}/consolidated/'
        saved=CACHE/f'screener-{symbol}.json'
        try: body,mode=CachedHTTP().get(url)
        except RuntimeError:
            if saved.exists(): return dict(json.loads(saved.read_text(encoding='utf-8')),mode='stale cache')
            discovery=DATA/'screener-seed.json'
            if discovery.exists():
                known=json.loads(discovery.read_text(encoding='utf-8'))['companies'].get(symbol)
                if known: return dict(known,mode='seed',warning='Discovery snapshot fetched 2026-11-03; not point-in-time research evidence')
            seed=load_seed(); docs=[d for d in seed['documents'] if d['ticker']==symbol]
            return dict(ticker=symbol,name=None,url=url,documents=docs,tables={},mode='seed',warning='Live page unavailable; seed coverage only')
        soup=BeautifulSoup(body,'html.parser')
        name=soup.find('h1')
        if not name: raise ValueError('No company page found')
        docs=[]
        for a in soup.select('#documents a[href]'):
            href=urljoin(url,a['href']); label=a.get_text(' ',strip=True)
            if label and any(k in (label+' '+href).lower() for k in ('transcript','annual','concall','report','results')):
                docs.append({'url':href,'label':label})
        tables={s.get('id'):s.get_text(' ',strip=True) for s in soup.select('section[id]') if s.get('id') in ['quarters','profit-loss','balance-sheet','cash-flow','ratios']}
        result=dict(ticker=symbol,name=name.get_text(strip=True),url=url,documents=docs,tables=tables,mode=mode)
        saved.write_text(json.dumps(result,indent=2),encoding='utf-8'); return result

class YahooAdapter:
    def fetch(self,symbol,start,end):
        import yfinance as yf
        symbol=ticker(symbol); file=CACHE/f'prices-{symbol}-{start}-{end}.json'; CACHE.mkdir(exist_ok=True)
        if file.exists() and time.time()-file.stat().st_mtime<86400: return json.loads(file.read_text()),'cache'
        try:
            yf.set_tz_cache_location(str(CACHE/'yfinance'))
            frame=yf.Ticker(symbol+'.NS').history(start=start,end=end,auto_adjust=False,actions=False,timeout=12)
            if frame.empty: raise ValueError('No prices returned')
            rows=[]
            for i,(day,row) in enumerate(frame.iterrows()):
                previous=frame.iloc[i-1]['Close'] if i else None
                # Exactly 20 prior sessions; exclude the trigger day.
                average=float(frame.iloc[i-20:i]['Volume'].mean()) if i>=20 else None
                rows.append(dict(ticker=symbol,date=day.strftime('%Y-%m-%d'),close=float(row['Close']),volume=int(row['Volume']),price_change=round((float(row['Close'])/previous-1)*100,3) if previous else None,volume_ratio=round(float(row['Volume'])/average,3) if average else None,source='Yahoo Finance via yfinance',simulated=False))
            file.write_text(json.dumps(rows)); return rows,'live'
        except Exception:
            if file.exists(): return json.loads(file.read_text()),'cache'
            seed=json.loads((DATA/'snapshot.json').read_text(encoding='utf-8'))
            return [r for r in seed['prices'] if r['ticker']==symbol and start<=r['date']<end],'seed (live unavailable)'

class BSEAdapter:
    def fetch(self,code,start,end):
        if not re.fullmatch(r'\d{6}',str(code)): raise ValueError('BSE code must have six digits')
        rows=[]
        for page in range(1,51):
            url=f'https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w?pageno={page}&strCat=-1&strPrevDate={start.replace("-","")}&strScrip={code}&strSearch=P&strToDate={end.replace("-","")}&strType=C'
            body,mode=CachedHTTP().get(url,ttl=3600); payload=json.loads(body)
            if isinstance(payload,str):
                try: payload=json.loads(payload)
                except json.JSONDecodeError: raise ValueError('Exchange returned a string instead of announcement data')
            if not isinstance(payload,dict) or 'Table' not in payload: raise ValueError('Unrecognised exchange response')
            batch=payload['Table'] or []
            if not batch: break
            rows.extend(batch)
        else: raise RuntimeError('Pagination cap reached: do not claim complete coverage')
        return rows

class NSEAdapter:
    def fetch(self,symbol,start,end):
        symbol=ticker(symbol); CACHE.mkdir(exist_ok=True); saved=CACHE/f'nse-{symbol}-{start}-{end}.json'
        if saved.exists() and time.time()-saved.stat().st_mtime<3600: return json.loads(saved.read_text())
        # Cookie bootstrap is kept within one session. Never bypass access controls.
        with httpx.Client(headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'},timeout=25) as client:
            client.get('https://www.nseindia.com/').raise_for_status()
            r=client.get('https://www.nseindia.com/api/corporate-announcements',params={'index':'equities','symbol':symbol,'from_date':datetime.fromisoformat(start).strftime('%d-%m-%Y'),'to_date':datetime.fromisoformat(end).strftime('%d-%m-%Y')}); r.raise_for_status(); rows=r.json(); saved.write_text(json.dumps(rows)); return rows

def load_seed():
    return json.loads((DATA/'snapshot.json').read_text(encoding='utf-8'))

def announcements(symbol,start,end,exchange='bse',code=None):
    from .announcement_classifier import classify
    symbol=ticker(symbol); CACHE.mkdir(exist_ok=True); saved=CACHE/f'announcements-{exchange}-{symbol}-{start}-{end}.json'
    if saved.exists() and time.time()-saved.stat().st_mtime<3600: return json.loads(saved.read_text()),'cache'
    try:
        raw=BSEAdapter().fetch(code,start,end) if exchange=='bse' else NSEAdapter().fetch(symbol,start,end)
        rows=[]
        for item in raw:
            headline=item.get('NEWSSUB') or item.get('desc') or item.get('subject') or ''
            stamp=item.get('NEWS_DT') or item.get('an_dt') or item.get('sort_date') or ''
            try:
                stamp=datetime.fromisoformat(stamp[:19]).date().isoformat()
            except ValueError:
                try: stamp=datetime.strptime(stamp[:11],'%d-%b-%Y').date().isoformat()
                except ValueError: raise ValueError('Unrecognised announcement date; refusing incomplete feed')
            attachment=item.get('ATTACHMENTNAME') or item.get('attchmntFile')
            source=(urljoin('https://www.bseindia.com/xml-data/corpfiling/AttachLive/',attachment) if exchange=='bse' else attachment) if attachment else None
            rows.append(dict(id=str(item.get('NEWSID') or item.get('seq_id') or hashlib.sha256(json.dumps(item,sort_keys=True).encode()).hexdigest()[:16]),ticker=symbol,date=stamp,headline=headline,source=source,exchange=exchange,simulated=False,**classify(headline)))
        saved.write_text(json.dumps(rows,indent=2),encoding='utf-8'); return rows,'live'
    except Exception as exc:
        if saved.exists(): return json.loads(saved.read_text()),f'stale cache ({type(exc).__name__})'
        seed=load_seed()
        fixture=DATA/'infosys-april-2025-fixture.json'
        if end<'2026-01-01' and fixture.exists(): seed=json.loads(fixture.read_text())
        return [r for r in seed['announcements'] if r['ticker']==symbol and start<=r.get('date',r.get('datetime','')[:10])<=end],f'seed ({type(exc).__name__}; incomplete coverage)'
