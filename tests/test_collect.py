import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from collect import parse_feed, collect, extract_offer

RSS = b'''<rss><channel>
<item><title>iRobot Roomba Combo Robot Vacuum $249.99 at Amazon</title><link>https://example.org/deal/123</link><description>Shopping guide with mentions of laptops and refrigerators</description><pubDate>Fri, 20 Nov 2026 16:00:00 GMT</pubDate></item>
<item><title>Best Black Friday Deals on Refrigerators, TV and Sofas</title><link>https://example.org/article/456</link><description>Many things on sale</description></item>
<item><title>Samsung 55-inch OLED TV $799 at Best Buy</title><link>https://example.org/deal/789</link><description>TV and accessories</description></item>
</channel></rss>'''
class CollectorTests(unittest.TestCase):
    def test_extracts_individual_items_only(self):
        diag = {}
        items = parse_feed(RSS, 'Sample', '2026-11-20T16:30:00+00:00', diag)
        self.assertEqual(len(items), 2)
        self.assertEqual(diag['total'], 3)
        self.assertEqual(items[0]['category'], 'Home & Garden')
        self.assertEqual(items[0]['retailer'], 'Amazon')
        self.assertEqual(items[0]['price'], 249.99)
        self.assertEqual(items[1]['category'], 'Electronics')
        self.assertEqual(items[1]['retailer'], 'Best Buy')
        self.assertEqual(items[0]['linkType'], 'deal_article')
    def test_does_not_use_article_body_for_category(self):
        items = parse_feed(RSS, 'Sample', '2026-11-20T16:30:00+00:00')
        self.assertNotEqual(items[0]['category'], 'Appliances')
    def test_filters_roundups(self):
        self.assertIsNone(extract_offer('Best Black Friday Deals on 25 Appliances')[0])
        self.assertIsNone(extract_offer('Up to 50% Off All Refrigerators')[0])
        self.assertIsNone(extract_offer('Top 10 robot vacuums for 2026')[0])
    def test_price_ambiguity(self):
        self.assertIsNone(extract_offer('Samsung 55-inch OLED TV $899 or $799')[0])
    def test_feed_errors_preserve_other_sources(self):
        def fetch(url):
            if 'slickdeals' in url: raise TimeoutError('unavailable')
            return RSS
        res = collect(fetch=fetch, now='2026-11-20T17:00:00+00:00', prior=[])
        self.assertTrue(res['deals'])
        self.assertFalse(res['sources']['Slickdeals']['ok'])
    def test_history_and_old_articles(self):
        item = parse_feed(RSS, 'DealNews', '2026-11-20T16:30:00+00:00')[0]
        item['history'] = [{'date': '2026-11-19T16:00:00+00:00', 'price': 299.99, 'retailer': 'Amazon'}]
        legacy = {'id': 'bad', 'title': 'Best discounts', 'feed': True, 'category': 'Appliances'}
        res = collect(fetch=lambda _: RSS, now='2026-11-20T17:00:00+00:00', prior=[item, legacy])
        self.assertNotIn('bad', [d['id'] for d in res['deals']])
        matched = next(d for d in res['deals'] if d['id'] == item['id'])
        self.assertEqual(len(matched['history']), 2)

if __name__ == '__main__': unittest.main()
