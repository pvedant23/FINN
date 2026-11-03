import json,time
from datetime import datetime,timezone
from .sources import DATA,CACHE,ScreenerAdapter,YahooAdapter,announcements,ticker

def fetch_company(symbol,start,end):
    symbol=ticker(symbol); portfolio=json.loads((DATA/'portfolio.json').read_text())
    holding=next((x for x in portfolio['portfolio'] if x['ticker']==symbol),{})
    company=ScreenerAdapter().fetch(symbol)
    prices,price_mode=YahooAdapter().fetch(symbol,start,end)
    news,news_mode=announcements(symbol,start,end,exchange='bse' if holding.get('bse') else 'nse',code=holding.get('bse'))
    result=dict(ticker=symbol,fetched_at=datetime.now(timezone.utc).isoformat(),company=company,prices=prices,announcements=news,source_status={'screener':company['mode'],'prices':price_mode,'announcements':news_mode})
    CACHE.mkdir(exist_ok=True); (CACHE/f'company-{symbol}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result

def verify_portfolio():
    holdings=json.loads((DATA/'portfolio.json').read_text())['portfolio']; results=[]
    for h in holdings:
        symbol=h['ticker']; record={'ticker':symbol,'checked_at':datetime.now(timezone.utc).isoformat()}
        try:
            company=ScreenerAdapter().fetch(symbol)
            record.update(screener=bool(company['name']),screener_mode=company['mode'],name=company['name'],document_links=len(company['documents']))
        except Exception as exc: record.update(screener=False,screener_error=type(exc).__name__)
        try:
            prices,mode=YahooAdapter().fetch(symbol,'2025-03-01','2025-04-18')
            record.update(yfinance=bool(prices) and mode in ('live','cache'),price_mode=mode,price_rows=len(prices))
        except Exception as exc: record.update(yfinance=False,price_error=type(exc).__name__)
        results.append(record)
        (DATA/'verification.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        print(f"{symbol}: screener={record.get('screener')} yfinance={record.get('yfinance')}",flush=True)
        time.sleep(.6)
    return results
