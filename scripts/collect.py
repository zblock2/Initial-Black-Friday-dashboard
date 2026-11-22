#!/usr/bin/env python3
"""Conservative, product-level RSS discovery. Python stdlib, free GitHub Actions.

Only a confidently identified individual product becomes a product deal.
Article roundups and ambiguous offers are excluded rather than miscategorized.
"""
import datetime as dt
import email.utils
import hashlib
import html
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data' / 'deals.json'
FEEDS = {
    'DealNews': 'https://www.dealnews.com/?rss=1&sort=time',
    'DealNews Editors': 'https://www.dealnews.com/f1682/Staff-Pick/?rss=1',
    'Slickdeals': 'https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&rss=1',
}
# Categories are derived from the product title only, not the article body.
# Ordered specificity prevents "washer" matching "pressure washer", and "bed" matching "bedside".
PRODUCT_PATTERNS = [
    ('Baby & Kids', [r'\b(stroller|infant car seat|convertible car seat|crib|bassinet|diaper[s]?|baby monitor|baby carrier|baby bottle[s]?|breast pump|high chair|playpen|pack n play|toddler bed|lovevery|huggies|pampers|uppababy|nuna stroller)\b']),
    ('Appliances', [r'\b(refrigerator|fridge|dishwasher|washing machine|clothes washer|washer and dryer|washer/dryer|dryer|freezer|gas range|electric range|induction range|wall oven|microwave|air fryer|coffee maker|espresso machine)\b']),
    ('Furniture', [r'\b(murphy bed|sleeper sofa|sofa|couch|sectional|loveseat|mattress|bookshelf|bookcase|desk|dining table|bed frame|office chair|dresser|nightstand|cabinet)\b']),
    ('Home & Garden', [r'\b(robot vacuum|vacuum cleaner|stick vacuum|vacuum mop|floor mop|pressure washer|lawn mower|leaf blower|weed trimmer|power drill|cordless drill|tool kit|tool set|storage rack|shelving unit|pergola|snow blower|air purifier|dehumidifier)\b']),
    ('Electronics', [r'\b(laptop|macbook|iphone|ipad|tablet|monitor|headphones|earbuds|television|oled tv|qled tv|smart tv|gaming console|playstation|xbox|nintendo switch|ssd|graphics card|desktop pc|chromebook|smartwatch|apple watch)\b']),
    ('Clothing', [r'\b(sneakers|running shoes|boots|jacket|hoodie|sweater|jeans|leggings|t-shirt|polo shirt|winter coat)\b']),
]
# Article-level and promotional collections are not single-product offers.
ARTICLE_RE = re.compile(r'\b(best (black friday|cyber monday|holiday|deals?|discounts?|sales?|offers?)|top \d+|\d+ best|roundup|round-up|shopping guide|gift guide|our picks|everything (you need|on sale)|all the deals|deals (on|for|under|to shop)|how to|what to buy|live updates|black friday (deals|sales|offers)|cyber monday (deals|sales|offers)|shop (these|our|the) (deals|sales)|up to \d+% off|sitewide|storewide|entire site|buy one get one|bogo|coupon code|promo code)\b', re.I)
MULTI_RE = re.compile(r'\b(\d{2,}\+? (deals|products|items|picks)|dozens of|hundreds of|multiple products|various items|select (styles|items|products)|everything (at|from))\b', re.I)
PRICE_RE = re.compile(r'(?<![\w])\$\s?([\d,]+(?:\.\d{1,2})?)')
MODEL_RE = re.compile(r'\b(?=[A-Z0-9-]{6,}\b)(?=[A-Z0-9-]*[A-Z])(?=[A-Z0-9-]*\d)[A-Z0-9]+(?:-[A-Z0-9]+)*\b')
TAG_RE = re.compile(r'<[^>]*>')
RETAILERS = {'amazon': 'Amazon', 'best buy': 'Best Buy', 'walmart': 'Walmart', 'target': 'Target', 'home depot': 'Home Depot', "lowe's": "Lowe's", 'lowes': "Lowe's", 'costco': 'Costco', 'wayfair': 'Wayfair', 'macy': "Macy's", 'kohls': "Kohl's", 'kohl’s': "Kohl's", 'sams club': "Sam's Club", 'newegg': 'Newegg', 'ebay': 'eBay', 'ikea': 'IKEA', 'lenovo': 'Lenovo', 'dell': 'Dell', 'samsung': 'Samsung'}

def plain(s):
    return re.sub(r'\s+', ' ', html.unescape(TAG_RE.sub(' ', s or ''))).strip()[:1000]

def node_text(item, name):
    n = item.find(name)
    return ''.join(n.itertext()).strip() if n is not None else ''

def normalize_title(title):
    s = plain(title)
    s = re.sub(r'^\s*(?:deal alert|deal of the day|hot deal|frontpage deal)\s*[:\-]\s*', '', s, flags=re.I)
    s = re.sub(r'\s+(?:at|from|via|on)\s+(?:amazon|best buy|walmart|target|home depot|lowe\'?s|costco|wayfair|newegg|ebay)\s*$', '', s, flags=re.I)
    s = re.sub(r'\s*(?:\([^)]*\b(?:save|off|coupon)\b[^)]*\)|\[coupon[^]]*\])', '', s, flags=re.I)
    s = re.sub(r'\s*[:\-|–—]\s*(?:now|only|as low as|just)\s*\$[\d,.]+.*$', '', s, flags=re.I)
    s = PRICE_RE.sub('', s)
    s = re.sub(r'\b(?:free shipping|shipped|with coupon|after coupon|prime members only|today only|reg(?:ularly)?\.?)\b.*$', '', s, flags=re.I)
    return re.sub(r'\s+', ' ', s).strip(' -:|–—,$')[:180]

def category_for_product(title):
    for category, patterns in PRODUCT_PATTERNS:
        if any(re.search(p, title, flags=re.I) for p in patterns):
            return category
    return 'Other'

def retailer_for(title, description=''):
    # Avoid inferring seller from arbitrary article description mentioning another store.
    lower = title.lower()
    for token, retailer in RETAILERS.items():
        if re.search(r'\b(?:at|from|via|on)\s+' + re.escape(token) + r'\b', lower) or re.search(r'\b' + re.escape(token) + r'\s*[:|–—-]', lower):
            return retailer
    return ''

def extract_offer(title, description=''):
    """Returns product fields if title plausibly describes one item, else (None, reason)."""
    title = plain(title)
    if ARTICLE_RE.search(title) or MULTI_RE.search(title):
        return None, 'article_or_roundup'
    # A headline describing a product with a fixed price is stronger evidence than a general promotion.
    product = normalize_title(title)
    category = category_for_product(product)
    if category == 'Other':
        return None, 'unrecognized_product'
    if len(product) < 7 or len(product.split()) < 2:
        return None, 'vague_product'
    # If multiple separately priced items are described, no reliable price assignment is possible.
    prices = PRICE_RE.findall(title)
    if len(prices) > 1:
        return None, 'multiple_prices'
    price = float(prices[0].replace(',', '')) if prices else None
    # Cheap generic offers (e.g. "Robot vacuum sale") cannot be treated as a specific SKU.
    model_match = next((m for m in MODEL_RE.finditer(product.upper()) if not re.fullmatch(r'\d+(?:INCH|GB|TB|OZ|LB|WATT|HZ|IN|FT|PACK)', m.group(0))), None)
    has_specific = bool(model_match or len(product.split()) >= 4)
    if not has_specific and price is None:
        return None, 'insufficient_product_detail'
    if re.search(r'\b(?:deals|sale|clearance|discounts|collection|assorted|select models)\b', product, re.I):
        return None, 'general_promotion'
    confidence = 'medium' if has_specific and price is not None else 'low'
    return {
        'productTitle': product, 'category': category,
        'price': price, 'retailer': retailer_for(title, description),
        'matchConfidence': confidence,
        # Only explicit models yield a reliable cross-offer grouping key.
        'model': model_match.group(0) if model_match else '',
    }, None

def parse_feed(xmlbytes, source, collected, diagnostics=None):
    root = ET.fromstring(xmlbytes)
    found = []
    entries = root.findall('./channel/item') or root.findall('{http://www.w3.org/2005/Atom}entry')
    skipped = {}
    for item in entries:
        title = plain(node_text(item, 'title') or node_text(item, '{http://www.w3.org/2005/Atom}title'))
        link = node_text(item, 'link')
        if not link:
            a = item.find('{http://www.w3.org/2005/Atom}link')
            link = a.attrib.get('href', '') if a is not None else ''
        if not title or not link.startswith('https://'):
            skipped['invalid_entry'] = skipped.get('invalid_entry', 0) + 1
            continue
        description = plain(node_text(item, 'description') or node_text(item, '{http://www.w3.org/2005/Atom}summary'))
        product, reason = extract_offer(title, description)
        if not product:
            skipped[reason] = skipped.get(reason, 0) + 1
            continue
        published = node_text(item, 'pubDate')
        try:
            posted = email.utils.parsedate_to_datetime(published).astimezone(dt.timezone.utc).isoformat() if published else collected
        except (ValueError, TypeError, IndexError):
            posted = collected
        uid = hashlib.sha256((source + '|' + link.split('?')[0]).encode()).hexdigest()[:20]
        found.append({
            'id': uid, 'title': product['productTitle'], 'productTitle': product['productTitle'],
            'articleTitle': title, 'url': link, 'source': source, 'category': product['category'],
            'price': product['price'], 'description': description[:350], 'published': posted,
            'firstSeen': collected, 'updated': collected, 'history': [],
            'retailer': product['retailer'], 'feed': True, 'isProduct': True,
            'matchConfidence': product['matchConfidence'], 'model': product['model'],
            'group': product['model'], 'linkType': 'deal_article',
        })
    if diagnostics is not None:
        diagnostics['total'] = len(entries)
        diagnostics['skipped'] = skipped
    return found

def collect(fetch=None, now=None, prior=None):
    fetch = fetch or (lambda url: urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'DealIntelligencePersonalRSS/2.0 (+RSS reader)'}), timeout=18).read())
    now = now or dt.datetime.now(dt.timezone.utc).isoformat()
    if prior is None:
        try:
            prior = json.loads(OUTPUT.read_text(encoding='utf-8')).get('deals', [])
        except (FileNotFoundError, ValueError):
            prior = []
    # Drop ambiguous legacy feed articles: only the new product-level feed records are retained.
    merged = {d['id']: d for d in prior if 'id' in d and (not d.get('feed') or d.get('isProduct') is True)}
    status = {}
    for source, url in FEEDS.items():
        try:
            metrics = {}
            items = parse_feed(fetch(url), source, now, diagnostics=metrics)
            for item in items:
                old = merged.get(item['id'])
                if old:
                    item['firstSeen'] = old.get('firstSeen', now)
                    history = old.get('history', [])
                    if item['price'] is not None and (not history or history[-1].get('price') != item['price']):
                        history.append({'date': now, 'price': item['price'], 'retailer': item['retailer'] or source})
                    item['history'] = history[-365:]
                elif item['price'] is not None:
                    item['history'] = [{'date': now, 'price': item['price'], 'retailer': item['retailer'] or source}]
                merged[item['id']] = item
            status[source] = {'ok': True, 'count': len(items), 'checked': now, **metrics}
        except Exception as exc:
            status[source] = {'ok': False, 'error': str(exc)[:180], 'checked': now}
    cutoff = dt.datetime.fromisoformat(now.replace('Z', '+00:00')) - dt.timedelta(days=45)
    kept = []
    for d in merged.values():
        try:
            timestamp = dt.datetime.fromisoformat(d.get('firstSeen', now).replace('Z', '+00:00'))
            if timestamp >= cutoff:
                kept.append(d)
        except (ValueError, TypeError):
            kept.append(d)
    kept.sort(key=lambda d: d.get('published', ''), reverse=True)
    return {
        'generatedAt': now, 'deals': kept[:1800], 'sources': status,
        'disclaimer': 'Single-product candidates extracted from deal headlines; ambiguous articles are excluded. Merchant prices and exact models require checkout verification. Links may lead to deal articles, not product pages.',
    }

if __name__ == '__main__':
    result = collect()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Saved', len(result['deals']), 'product candidates:', result['sources'])
