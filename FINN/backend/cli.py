"""Run from repository root: python -m backend.cli demo | fetch | verify."""
import argparse,json
from pathlib import Path
from .announcement_classifier import classify

DATA=Path(__file__).resolve().parents[1]/'data'
def demo():
    seed=json.loads((DATA/'snapshot.json').read_text(encoding='utf-8'))
    portfolio=json.loads((DATA/'portfolio.json').read_text(encoding='utf-8'))
    print(json.dumps({'as_of':seed['as_of'],'mode':seed['mode'],'coverage':seed['coverage'],'portfolio_count':len(portfolio['portfolio']),'price_rows':len(seed['prices']),'documents':len(seed['documents']),'announcements':[dict(i,classification=classify(i.get('subject',i.get('headline','')))) for i in seed['announcements']]},indent=2))

def main():
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['demo','fetch','verify','refresh','research']); p.add_argument('symbol',nargs='?'); p.add_argument('--ticker',default='INFY'); p.add_argument('--start',default='2026-09-15'); p.add_argument('--end',default='2026-11-03'); args=p.parse_args()
    if args.command=='research':
        from .research import fetch
        return print(json.dumps(fetch(args.symbol or args.ticker)))
    if args.command=='demo': return demo()
    if args.command=='refresh':
        from .refresh_announcements import refresh
        return refresh()
    from .ingest import fetch_company,verify_portfolio
    result=verify_portfolio() if args.command=='verify' else fetch_company(args.ticker,args.start,args.end)
    print(json.dumps(result,indent=2))
if __name__=='__main__': main()
