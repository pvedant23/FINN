"""Deterministic, conservative filing parser. Ambiguity produces link-only output."""
import json,re,hashlib
from pathlib import Path
from .finance import crore,change,ebitda
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'
PERIODS=['2026-09-30','2026-06-30','2025-09-30']
def headers(text):
 # CDSL's embedded text maps the printed J to ')'; verified against page 10.
 text=text.replace(')un30,','Jun30,')
 lines=text.splitlines(); dates=[]
 for i,line in enumerate(lines[:24]):
  found=re.findall(r'(30)[./](09|06)[./](2026|2025)',line)
  if len(found)>=3: dates=[f'{y}-{m}-{d}' for d,m,y in found];break
  found=re.findall(r'(Sep(?:tember)?|Jun(?:e)?|Mar(?:ch)?)\s*30,?\s*(202[56])',line,re.I)
  if len(found)>=3: dates=[f'{y}-{("09" if m.lower().startswith("sep") else "06")}-30' for m,y in found];break
  months=re.findall(r'(September|June|March)\s+(?:30|31)',line,re.I)
  if len(months)>=3 and i+1<len(lines):
   years=re.findall(r'202[56]',lines[i+1]);
   if len(years)>=3: dates=[f'{y}-{dict(september="09",june="06",march="03")[m.lower()]}-30' for m,y in zip(months,years)];break
 if not all(d in dates[:3] for d in PERIODS): raise ValueError('Quarter column headers ambiguous or incomplete')
 return [dates[:3].index(d) for d in PERIODS]
NUM=r'(?:\(?-?(?:\d{1,3}(?:,\d{3})+|\d{1,3}(?:,\d{2})*,\d{3}|\d+)(?:\.\d+)?\)?|-)'
def numeric_rows(text):
 out=[]; prefix=''
 for line in text.splitlines():
  m=re.search(r'\s('+NUM+r'(?:\s+'+NUM+r'){5})\s*$',line)
  if m:
   tokens=m[1].split(); values=[0. if t=='-' else float(t.replace(',','').replace('(','-').replace(')','')) for t in tokens]
   name=(prefix+' '+line[:m.start()]).strip(); out.append((re.sub(r'[^a-z]','',name.lower()),values,line));prefix=''
  else: prefix=(prefix+' '+line)[-230:]
 return out
def parse_page(text,page,bank=False):
 idx=headers(text); unit='lakh' if re.search('lakh',text,re.I) else 'million' if re.search('million',text,re.I) else 'crore' if re.search('crore',text,re.I) else None
 if not unit: raise ValueError('Unit not reliably identified')
 raw=numeric_rows(text); rows={}
 def take(key,pattern,required=True):
  matches=[r for r in raw if re.search(pattern,r[0])]
  if len(matches)!=1:
   if required: raise ValueError(f'{key}: missing or ambiguous row')
   return None
  values=[round(crore(matches[0][1][j],unit),5) for j in idx];rows[key]={'values':values,'page':page};return values
 def add(key,a,b): rows[key]={'values':[round(x+y,5) for x,y in zip(a,b)],'page':page,'derived':True};return rows[key]['values']
 if bank:
  take('interest_earned',r'interestearned');take('interest_expended',r'interestexpended');take('other_income',r'otherincome[a-z]*$');take('operating_expenses',r'^.*operatingexpenses[a-z]*$');take('ppop',r'operatingprofitbeforeprovisions')
  add('nii',rows['interest_earned']['values'],[-v for v in rows['interest_expended']['values']]);take('pbt',r'profitfromordinaryactivitiesbeforetax');take('tax',r'taxexpense[a-z]*$');take('pat',r'netprofitfortheperiodbeforeminority');take('provisions',r'provisionsotherthantax')
 else:
  rev=take('revenue',r'(?:total)?revenuefromoperations$',False)
  if rev is None: add('revenue',take('sales_products',r'saleofproductsandservices$'),take('other_operating_revenue',r'otheroperatingrevenue$'))
  take('other_income',r'otherincome(?:net|refernote)?$');take('finance_cost',r'financecosts?$');take('da',r'depreciationandamortisationexpenses?$');take('pbt',r'profitbeforetax$');take('pat',r'(?:netprofitaftertax|profitfortheperiod|profitaftertax)$');take('total_income',r'totalincome[a-z]*$');take('expenses',r'totalexpenses[a-z]*$')
  tax=take('tax',r'totaltax(?:expenses?)?$',False)
  if tax is None:add('tax',take('current_tax',r'currenttax$'),take('deferred_tax',r'deferredtax$'))
  for k,pat in [('associate',r'shareofprofitlossofassociate$'),('restructuring',r'restructuringexpenses$'),('labour',r'statutoryimpactofnewlabourcodes$'),('settlement',r'settlementoflegalclaim$')]:take(k,pat,False)
 tolerance=max(.03,3*crore(1,unit))
 for j in range(3):
  v=lambda k:rows[k]['values'][j] if k in rows else 0
  if abs(v('pbt')-v('tax')-v('pat'))>tolerance:raise ValueError('PBT minus tax does not reconcile to PAT')
  expected=v('ppop')-v('provisions') if bank else v('total_income')-v('expenses')+v('associate')-v('restructuring')-v('labour')-v('settlement')
  if abs(expected-v('pbt'))>tolerance:raise ValueError('Income/expense components do not reconcile to PBT')
  if bank and abs(v('nii')+v('other_income')-v('operating_expenses')-v('ppop'))>tolerance:raise ValueError('Bank operating components do not reconcile to PPOP')
  if not bank and abs(v('revenue')+v('other_income')-v('total_income'))>tolerance:raise ValueError('Revenue and other income do not reconcile')
 if not bank:rows['ebitda']={'values':[round(ebitda({k:rows[k]['values'][j] for k in ['pbt','finance_cost','da','other_income']}),5) for j in range(3)],'page':page,'derived':True}
 for key,row in rows.items():
  a,b,c=row['values'];row.update(qoq=change(a,b),yoy=change(a,c))
  row['margins']=[round(v/den*100,2) if den>0 else None for v,den in zip(row['values'],rows['interest_earned' if bank else 'revenue']['values'])]
 return rows
def crosscheck(symbol,rows):
 seed=json.loads((DATA/'screener-seed.json').read_text());text=seed['companies'].get(symbol,{}).get('tables',{}).get('quarters','');periods=re.findall(r'(?:Mar|Jun|Sep|Dec) 20\d\d',text)
 checked=0
 for key,label in [('revenue','Sales'),('pat','Net Profit')]:
  if key not in rows:continue
  m=re.search(label+r'\s*\+?\s*((?:-?[\d,]+(?:\.\d+)?\s+)+)',text)
  if not m:continue
  values=[float(x.replace(',','')) for x in m[1].split()]
  for j,p in enumerate(['Sep 2026','Jun 2026','Sep 2025']):
   if p in periods and periods.index(p)<len(values):
    expected=values[periods.index(p)]; actual=rows[key]['values'][j]
    if abs(expected-actual)>max(abs(expected)*.01,.005):raise ValueError(f'Screener {key} disagreement for {p}')
    checked+=1
 return 'From filing, cross-checked' if checked==6 else 'From filing'
def build():
 import pdfplumber
 records=json.loads((DATA/'refresh-report.json').read_text())['results'];output={};audit=[]
 for r in records:
  if r['document_role']!='results_filing':continue
  symbol=r['ticker'];f=DATA/'cache/current-feed'/(hashlib.sha256(r['pdf_url'].encode()).hexdigest()+'.raw'); errors=[];result=None
  if f.exists():
   digest=hashlib.sha256(f.read_bytes()).hexdigest(); cache=DATA/'cache'/f'{digest}.text.json'
   if cache.exists():pages=json.loads(cache.read_text(encoding='utf-8'))
   else:
    with pdfplumber.open(f) as pdf:pages=[(i+1,p.extract_text() or '') for i,p in enumerate(pdf.pages)]
    cache.write_text(json.dumps(pages),encoding='utf-8')
   candidates=[(i,t) for i,t in pages if 'consolidated' in t[:1500].lower() and re.search(r'total\s*income',t,re.I)]
   basis='consolidated'
   if not candidates:
    candidates=[(i,t) for i,t in pages if 'standalone' in t[:1500].lower() and re.search(r'total\s*income',t,re.I)];basis='standalone'
   for page,text in candidates:
    try:
     rows=parse_page(text,page,symbol in ['HDFCBANK','ICICIBANK','BAJFINANCE']);badge=crosscheck(symbol,rows) if basis=='consolidated' else 'From filing'
     result=dict(available=True,rows=rows,badge=badge,basis=basis,crosscheck='via Screener (company-reported)' if 'cross-checked' in badge else 'not cross-checked');break
    except ValueError as exc:errors.append(f'Page {page}: {exc}')
  if result is None:result=dict(available=False,rows={},badge='Low confidence: '+('; '.join(errors) or 'Readable consolidated table unavailable'),crosscheck='not cross-checked',basis='unknown')
  result.update(ticker=symbol,pdf_url=r['pdf_url'],periods=PERIODS,bank=symbol in ['HDFCBANK','ICICIBANK','BAJFINANCE'],document_sha256=digest if f.exists() else None);audit.append(result)
  if symbol not in output or result['available']:output[symbol]=result
 for symbol in ['HINDUNILVR','SHARDAMOTR']:
  matches=[r for r in json.loads((DATA/'snapshot.json').read_text())['announcements'] if r['ticker']==symbol and re.search('financial results|outcome of board meeting',r['subject'],re.I)]
  output[symbol]=dict(available=False,rows={},badge='Low confidence: '+('Only newspaper publication found' if matches else 'No results filing in snapshot'),pdf_url=matches[0]['pdf_url'] if matches else None,ticker=symbol,bank=False,periods=PERIODS)
 (DATA/'parsed-results.json').write_text(json.dumps(output,separators=(',',':')),encoding='utf-8');(DATA/'results-parse-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
 print([(k,v['available'],v['badge']) for k,v in output.items()])
if __name__=='__main__':build()
