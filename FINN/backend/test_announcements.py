import unittest
import json
from pathlib import Path
from .announcement_classifier import classify

class RealSubjects(unittest.TestCase):
 def test_real_subjects(self):
  cases=[
   ('HDFC Bank Limited has informed the Exchange regarding Allotment of 4675598 Shares.','fund_raise'),
   ('HDFC Bank Limited has informed the Exchange regarding Grant of 1302379 Options.','routine_compliance'),
   ('HDFC Bank Limited has informed the Exchange about Link of Recording','earnings_call'),
   ('HDFC Bank Limited has submitted to the Exchange, the financial results for the period ended September 30, 2026.','results'),
   ('HDFC Bank Limited has informed the Exchange about General Updates','unclassified')]
  for subject,expected in cases:
   with self.subTest(subject=subject): self.assertEqual(classify(subject)['category'],expected)
 def test_vague_disclosure_stays_uncertain(self):
  self.assertEqual(classify('Disclosure under Regulation 30')['confidence'],'low')

class SnapshotChecks(unittest.TestCase):
 def test_window_and_baselines(self):
  data=Path(__file__).resolve().parents[1]/'data'
  snapshot=json.loads((data/'snapshot.json').read_text())
  if snapshot['schema_version']!=2: self.skipTest('Current refresh not finished')
  rows=snapshot['announcements']; self.assertTrue(rows)
  self.assertEqual(len(rows),len({r['id'] for r in rows}))
  for r in rows:
   self.assertTrue('2026-09-15'<=r['datetime'][:10]<='2026-11-03')
   self.assertTrue(r['datetime'].endswith('+05:30'))
  self.assertLessEqual(sum(r['our_category']=='unclassified' for r in rows)/len(rows),.25)
  for h in json.loads((data/'portfolio.json').read_text())['portfolio']:
   prices=[r for r in snapshot['prices'] if r['ticker']==h['ticker']]
   self.assertEqual(len(prices),60)
   for r in prices:
    if r['date']>='2026-09-15': self.assertIsNotNone(r['volume_ratio'])
    self.assertLessEqual(r['date'],snapshot['as_of'])
  self.assertLess(sum(p.stat().st_size for p in data.glob('*.json')),5_000_000)

if __name__=='__main__': unittest.main()
