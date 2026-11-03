import unittest
from .build_bundle import reaction,category,cluster,headline,results_period
class Pipeline(unittest.TestCase):
 def test_results_headlines_from_real_subjects(self):
  subjects=['the financial results for the period ended September 30, 2026',"In continuation of our letter of today's date on the Unaudited Financial",'the consolidated and standalone un-audited financial results of the Company for the','Unaudited Financial Results for the quarter and half year ended 30 September']
  for subject in subjects:
   self.assertEqual(headline(dict(ticker='INFY',subject=subject,datetime='2026-10-23T16:00:00+05:30'),'results'),'INFY Q2 FY27 results')
  self.assertEqual(results_period('Results for the quarter ended June 30, 2026','2026-10-23'),'Q1 FY27')
  self.assertEqual(results_period('Financial results','2025-04-17'),'Q4 FY25')
 def test_headline_boilerplate_and_dangling_words(self):
  row=dict(ticker='INFY',datetime='2026-10-23')
  self.assertEqual(headline(dict(row,subject='Pursuant to Regulation 30 of SEBI'),'unclassified'),'INFY Regulatory update')
  self.assertEqual(headline(dict(row,subject='In continuation of our letter'),'routine'),'INFY Routine filing')
  text=headline(dict(row,subject='Company announces a new strategic collaboration expanding technology services across India for the'),'product_or_partnership')
  self.assertLessEqual(len(text.split()),12);self.assertFalse(text.endswith('for the'));self.assertFalse(text.endswith('for'))
 def test_session_cutoff(self):
  prices=[dict(date=d,price_change=2,volume_ratio=1.2) for d in ['2026-10-30','2026-11-02']]
  self.assertEqual(reaction('2026-10-30T15:29:00+05:30',prices)['session'],'2026-10-30')
  self.assertEqual(reaction('2026-10-30T15:30:00+05:30',prices)['session'],'2026-11-02')
  self.assertEqual(reaction('2026-10-31T10:00:00+05:30',prices)['session'],'2026-11-02')
  self.assertIsNone(reaction('2026-11-02T18:00:00+05:30',prices)['price_pct'])
 def test_real_subjects(self):
  cases=[('Announcement under Regulation 30 (LODR)-Newspaper Publication','routine'),('Infosys and ABN Amro Extend Strategic Collaboration to Simplify IT Landscape','product_or_partnership')]
  for subject,expected in cases: self.assertEqual(category(dict(subject=subject,our_category='press_release')),expected)
 def test_cluster_keeps_all_attachments(self):
  rows=[dict(id=str(i),ticker='INFY',datetime='2026-10-23T16:00:00+05:30',topic='results',category=c) for i,c in enumerate(['routine','results','earnings_call'])]
  grouped=cluster(rows); self.assertEqual(len(grouped),1); self.assertEqual(grouped[0]['category'],'results'); self.assertEqual(len(grouped[0]['attachments']),2)
if __name__=='__main__': unittest.main()
