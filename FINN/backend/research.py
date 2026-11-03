"""Cached deterministic Screener tables; no inferred missing cells."""
import json,re,time,urllib.request,urllib.error
from pathlib import Path
from bs4 import BeautifulSoup
DATA=Path(__file__).resolve().parents[1]/'data'
def fetch(ticker):
 ticker=ticker.upper()
 if not re.fullmatch(r'[A-Z0-9&-]+',ticker):raise ValueError('Invalid NSE ticker')
 out=dict(ticker=ticker,source='Screener (company-reported)',tables={},about='',status='failed')
 for basis,suffix in [('consolidated','consolidated/'),('standalone','')]:
  url=f'https://www.screener.in/company/{ticker}/{suffix}';cache=DATA/'cache'/f'research-{ticker}-{basis}.html';cache.parent.mkdir(exist_ok=True)
  try:
   if cache.exists():html=cache.read_text(encoding='utf-8')
   else:
    time.sleep(3)
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.screener.in/','Accept':'text/html'})
    html=urllib.request.urlopen(req,timeout=40).read().decode();cache.write_text(html,encoding='utf-8')
   soup=BeautifulSoup(html,'html.parser')
   if not soup.select_one('#profit-loss table'):continue
   out.update(url=url,basis=basis)
   about=soup.select_one('.company-profile .sub') or soup.select_one('.company-profile')
   out['about']=about.get_text(' ',strip=True) if about else ''
   for section in ['profit-loss','balance-sheet','cash-flow','ratios','quarters']:
    table=soup.select_one(f'#{section} table');rows=[]
    if table:
     periods=[x.get_text(' ',strip=True) for x in table.select('thead th')][1:]
     for tr in table.select('tbody tr'):
      cells=tr.select('td')
      if not cells:continue
      label=cells[0].get_text(' ',strip=True);unit='%' if '%' in label else 'Rs' if 'EPS' in label else 'days' if 'Days' in label or 'Cycle' in label else 'Rs crore'
      if section=='ratios' and unit=='Rs crore':unit='ratio'
      metrics=[]
      for period,cell in zip(periods,cells[1:]):
       raw=cell.get_text(' ',strip=True);num=raw.replace(',','').replace('%','').strip()
       try:value=float(num)
       except ValueError:value=None
       metrics.append(dict(period=period,value=value,raw=raw or 'not available',unit=unit,source=out['source'],url=url))
      rows.append(dict(label=label,metrics=metrics[-12:] if section=='quarters' else metrics))
    out['tables'][section]=rows
   out['status']='fully' if all(out['tables'].values()) and out['about'] else 'partly';break
  except Exception as exc:out['error']=str(exc)
 (DATA/'research').mkdir(exist_ok=True);(DATA/'research'/f'{ticker}.json').write_text(json.dumps(out,separators=(',',':')),encoding='utf-8');return out
if __name__=='__main__':
 holdings=json.loads((DATA/'portfolio.json').read_text())['portfolio'];results=[fetch(s) for s in [h['ticker'] for h in holdings]+['HCLTECH','TITAN','DRREDDY','CAMS']]
 Path('docs/research-coverage.md').write_text('# Research coverage\n\nMissing rows/cells are not available; no estimates. Fully = all five tables and About parsed.\n\n| Ticker | Status |\n|---|---|\n'+'\n'.join(f"| {r['ticker']} | {r['status']} |" for r in results))
 print([(r['ticker'],r['status']) for r in results])
