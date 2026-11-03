import json,unittest
import tempfile
from unittest.mock import patch
from pathlib import Path
from .engine import classify

DATA=Path(__file__).resolve().parents[1]/'data'
class SliceOneTests(unittest.TestCase):
    def test_classifier_cases(self):
        for case in json.loads((DATA/'classification_cases.json').read_text())['cases']:
            with self.subTest(case=case): self.assertEqual(classify(case['text'])['category'],case['expected'])
    def test_ambiguous_is_not_confident(self):
        self.assertEqual(classify('Financial results and dividend')['confidence'],'low')
    def test_portfolio_weights_and_diversity(self):
        p=json.loads((DATA/'portfolio.json').read_text())
        self.assertEqual(sum(x['weight'] for x in p['portfolio']),100)
        self.assertTrue(15<=len(p['portfolio'])<=20)
        self.assertNotIn(p['held_out_ticker'],[x['ticker'] for x in p['portfolio']]+p['research_tickers'])
    def test_seed_provenance(self):
        seed=json.loads((DATA/'snapshot.json').read_text())
        for row in seed['announcements']:
            if seed['schema_version']==2:
                self.assertIn(row['source'],['bse','nse','screener'])
                self.assertTrue(row['pdf_url'] is None or row['pdf_url'].startswith(('https://','http://')))
                self.assertTrue(row['datetime'].endswith('+05:30'))
            else:
                self.assertTrue(row['source'].startswith('https://'))
                self.assertTrue(row['provenance'])
                self.assertFalse(row['simulated'])
    def test_missing_prices_not_invented(self):
        for row in json.loads((DATA/'snapshot.json').read_text())['prices']:
            self.assertFalse(row['simulated'])

class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try: import bs4,httpx
        except ImportError: raise unittest.SkipTest('Install backend requirements for adapter tests')
    def test_announcement_failure_returns_labelled_seed(self):
        from . import sources
        with tempfile.TemporaryDirectory() as tmp, patch.object(sources,'CACHE',Path(tmp)), patch.object(sources.BSEAdapter,'fetch',side_effect=RuntimeError('offline')):
            rows,mode=sources.announcements('INFY','2025-04-17','2025-04-17',code='500209')
            self.assertEqual(len(rows),2)
            self.assertIn('incomplete coverage',mode)
    def test_screener_failure_preserves_document_seed(self):
        from . import sources
        with tempfile.TemporaryDirectory() as tmp, patch.object(sources,'CACHE',Path(tmp)), patch.object(sources.CachedHTTP,'get',side_effect=RuntimeError('offline')):
            result=sources.ScreenerAdapter().fetch('INFY')
            self.assertEqual(result['mode'],'seed')
            self.assertGreaterEqual(len(result['documents']),2)
    def test_http_reuses_cache(self):
        from . import sources
        import httpx
        with tempfile.TemporaryDirectory() as tmp, patch.object(sources,'CACHE',Path(tmp)), patch.object(sources.time,'sleep'), patch.object(sources.httpx,'get',return_value=httpx.Response(200,content=b'checked',request=httpx.Request('GET','https://example.com'))) as get:
            self.assertEqual(sources.CachedHTTP().get('https://example.com')[1],'live')
            self.assertEqual(sources.CachedHTTP().get('https://example.com')[1],'cache')
            self.assertEqual(get.call_count,1)

if __name__=='__main__': unittest.main()
