#!/usr/bin/env python3
"""Collect public RSS deal summaries. No secrets, external Python packages or HTML scraping."""
import datetime as dt
import email.utils
import hashlib
import html
import json
import os
import re
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
CATEGORIES = {
 'Appliances': ['refrigerator','dishwasher','washer','dryer','freezer','range','oven','fridge','appliance','microwave'],
 'Furniture': ['sofa','couch','murphy bed','mattress','desk','chair','furniture','bookshelf','bed frame','cabinet'],
 'Home & Garden': ['robot vacuum','vacuum','mop','lawn','garden','tool','drill','storage','pergola','home improvement','pressure washer'],
 'Baby & Kids': ['baby','stroller','crib','diaper','car seat','nursery','toddler','lovevery','bottle','pampers','huggies'],
 'Electronics': ['laptop','macbook','iphone','ipad','tablet','monitor','headphone','earbud','tv ','television','gaming','computer','ssd'],
 'Clothing': ['shoes','jacket','shirt','pants','sneakers','apparel','clothing'],
}
DOLLAR = re.compile(r'(?<!\w)\$\s?([\d,]+(?:\.\d{1,2})?)')
TAG = re.compile(r'<[^>]*>')

def plain(s):
    return re.sub(r'\s+', ' ', html.unescape(TAG.sub(' ',s or ''))).strip()[:800]

def node_text(item, name):
    n=item.find(name)
    return ''.join(n.itertext()).strip() if n is not None else ''

def categorize(s):
    s=s.lower()
    for cat, words in CATEGORIES.items():
        if any(word in s for word in words): return cat
    return 'Other'

def parse_feed(xmlbytes, source, collected):
    root = ET.fromstring(xmlbytes)
    found=[]
    entries=root.findall('./channel/item')
    if not entries:
        entries=root.findall('{http://www.w3.org/2005/Atom}entry')
    for item in entries:
        title=plain(node_text(item,'title') or node_text(item,'{http://www.w3.org/2005/Atom}title'))
        link=node_text(item,'link')
        if not link:
            a=item.find('{http://www.w3.org/2005/Atom}link'); link=a.attrib.get('href','') if a is not None else ''
        if not title or not link.startswith('https://'): continue
        description=plain(node_text(item,'description') or node_text(item,'{http://www.w3.org/2005/Atom}summary'))
        raw_price=DOLLAR.search(title)
        price=float(raw_price.group(1).replace(',','')) if raw_price else None
        published=node_text(item,'pubDate')
        try: posted=email.utils.parsedate_to_datetime(published).astimezone(dt.timezone.utc).isoformat() if published else collected
        except Exception: posted=collected
        uid=hashlib.sha256((source+'|'+link.split('?')[0]).encode()).hexdigest()[:20]
        found.append(dict(id=uid,title=title,url=link,source=source,category=categorize(title+' '+description),
                          price=price,description=description[:350],published=posted,firstSeen=collected,updated=collected,
                          history=[],retailer='',feed=True))
    return found

def collect(fetch=None, now=None, prior=None):
    fetch=fetch or (lambda url: urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'DealIntelligencePersonalRSS/1.0 (+RSS reader)'}), timeout=18).read())
    now=now or dt.datetime.now(dt.timezone.utc).isoformat()
    if prior is None:
        try: prior=json.loads(OUTPUT.read_text(encoding='utf-8')).get('deals',[])
        except (FileNotFoundError, ValueError): prior=[]
    merged={d['id']:d for d in prior if 'id' in d}
    status={}
    for source,url in FEEDS.items():
        try:
            items=parse_feed(fetch(url),source,now)
            for item in items:
                old=merged.get(item['id'])
                if old:
                    item['firstSeen']=old.get('firstSeen',now)
                    history=old.get('history',[])
                    if item.get('price') is not None and (not history or history[-1].get('price') != item['price']):
                        history.append({'date':now,'price':item['price'],'retailer':source})
                    item['history']=history[-365:]
                elif item.get('price') is not None:
                    item['history']=[{'date':now,'price':item['price'],'retailer':source}]
                merged[item['id']]=item
            status[source]={'ok':True,'count':len(items),'checked':now}
        except Exception as exc:
            status[source]={'ok':False,'error':str(exc)[:180],'checked':now}
    # Keep feed-derived items for 45 days; important: age is informational, not an expiry claim.
    cutoff=dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=45)
    kept=[]
    for d in merged.values():
        try:
            timestamp=dt.datetime.fromisoformat(d.get('firstSeen',now).replace('Z','+00:00'))
            if timestamp >= cutoff: kept.append(d)
        except Exception: kept.append(d)
    kept.sort(key=lambda d:d.get('published',''),reverse=True)
    return {'generatedAt':now,'deals':kept[:1800],'sources':status,'disclaimer':'Prices extracted from deal headlines only; validate at merchant checkout. Prices and expiration may change.'}

if __name__=='__main__':
    result=collect()
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Saved',len(result['deals']),'deals:',result['sources'])
