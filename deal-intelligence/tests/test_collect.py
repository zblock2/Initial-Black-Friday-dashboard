import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from collect import parse_feed, collect

RSS=b'''<rss><channel><item><title>Robot vacuum $249.99 at Example</title><link>https://example.org/deal/123</link><description>Robot vacuum</description><pubDate>Fri, 20 Nov 2026 16:00:00 GMT</pubDate></item></channel></rss>'''
class CollectorTests(unittest.TestCase):
    def test_parse_price_and_category(self):
        x=parse_feed(RSS,'Sample','2026-11-20T16:30:00+00:00')[0]
        self.assertEqual(x['price'],249.99)
        self.assertEqual(x['category'],'Home & Garden')
        self.assertTrue(x['url'].startswith('https://'))
    def test_feed_failures_preserve_other_sources(self):
        def fetch(url):
            if 'slickdeals' in url: raise TimeoutError('unavailable')
            return RSS
        r=collect(fetch=fetch,now='2026-11-20T17:00:00+00:00',prior=[])
        self.assertTrue(r['deals'])
        self.assertFalse(r['sources']['Slickdeals']['ok'])
    def test_history_retained(self):
        x=parse_feed(RSS,'DealNews','2026-11-20T16:30:00+00:00')[0]
        x['history']=[{'date':'2026-11-19T16:00:00+00:00','price':299.99,'retailer':'DealNews'}]
        r=collect(fetch=lambda url:RSS,now='2026-11-20T17:00:00+00:00',prior=[x])
        item=[d for d in r['deals'] if d['source']=='DealNews'][0]
        self.assertEqual(len(item['history']),2)
if __name__=='__main__':unittest.main()
