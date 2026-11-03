import unittest,json
from pathlib import Path
from .finance import fiscal_period,previous_period,crore,change,ebitda,compare
from .results_parser import headers,parse_page
class FinanceTests(unittest.TestCase):
 def test_real_filing_tables(self):
  fixtures=json.loads((Path(__file__).resolve().parents[1]/'data/results-table-fixtures.json').read_text())
  expected={'TCS':(73188,13934),'KPRMILL':(1939.74,345),'CDSL':(394.48,173.30)}
  for symbol,f in fixtures.items():
   with self.subTest(symbol=symbol):
    rows=parse_page(f['text'],f['page'])
    self.assertEqual(rows['revenue']['values'][0],expected[symbol][0]);self.assertEqual(rows['pat']['values'][0],expected[symbol][1])
    self.assertTrue(all(r['page']==f['page'] for r in rows.values()))
    self.assertTrue(rows['ebitda']['derived'])
 def test_reconciliation_failure_refuses_numbers(self):
  f=json.loads((Path(__file__).resolve().parents[1]/'data/results-table-fixtures.json').read_text())['TCS']
  with self.assertRaisesRegex(ValueError,'reconcile'):
   parse_page(f['text'].replace('13,934','15,934'),f['page'])
 def test_periods(self):
  self.assertEqual(fiscal_period('2026-04-01'),'Q1 FY27');self.assertEqual(fiscal_period('2026-06-30'),'Q1 FY27');self.assertEqual(fiscal_period('2026-09-30'),'Q2 FY27');self.assertEqual(previous_period('Q1 FY27'),'Q4 FY26');self.assertEqual(previous_period('Q2 FY27',4),'Q2 FY26')
 def test_units(self):
  self.assertEqual(crore(100,'lakh'),1);self.assertEqual(crore(10,'million'),1);self.assertEqual(crore(10000000,'rupees'),1)
 def test_known_infosys_april(self):
  # Official Q4 FY25 consolidated filing p12, linked by the retained April fixture.
  fixture=json.loads((Path(__file__).resolve().parents[1]/'data/infosys-april-2025-fixture.json').read_text())
  self.assertTrue(any(x['ticker']=='INFY' for x in fixture['announcements']))
  row=dict(pbt=9663,finance_cost=102,da=1299,other_income=1190)
  self.assertEqual(ebitda(row),9874);self.assertIsNone(ebitda(row,'bank'));self.assertIsNone(ebitda(row,'nbfc'))
  self.assertAlmostEqual(change(40925,41764),-2.01,places=2)
 def test_growth_bases(self):
  self.assertIsNone(change(10,0));self.assertIsNone(change(10,-2))
 def test_compare_matches_exact_period_and_basis(self):
  rows=[dict(period=p,basis=b,revenue=v) for p,b,v in [('Q2 FY27','consolidated',120),('Q1 FY27','consolidated',100),('Q2 FY26','consolidated',80),('Q1 FY27','standalone',999)]]
  revenue=compare(rows,'Q2 FY27')[0]
  self.assertEqual((revenue['qoq'],revenue['yoy']),(20,50))
 def test_headers_not_positions(self):
  self.assertEqual(headers('Quarter ended\n30.06.2026 30.09.2025 30.09.2026'),[2,0,1])
  with self.assertRaises(ValueError):headers('Quarter ended September 2026')
if __name__=='__main__':unittest.main()
