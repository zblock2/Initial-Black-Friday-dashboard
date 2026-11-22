# Deal Intelligence — $0 personal Black Friday dashboard

A static browser dashboard plus a conservative **product-level candidate extractor** that runs for free through GitHub Actions. This v2 filters generic roundup articles and categorizes from recognized product names instead of article descriptions.

## What works

- **Automatic discovery:** DealNews and Slickdeals RSS; only headlines plausibly describing a *single recognized product* are admitted. Roundups, broad promotions, ambiguous multiple-price offers and unknown products are excluded. Category comes from product title alone, never from article description. The collector reports how many feed entries it rejects and why. No paid APIs or retailer checkout scraping.
- **Personalized ranking:** category + keyword matches, price availability, locally observed markdown evidence, watchlist boost. The 0–100 number is **personal match**, not proof of an exceptional discount.
- **Search/filter/sort:** category, source, product name/model/merchant text, price availability, match score, newest, lowest price, observed savings. Long article descriptions do not contaminate product search results.
- **Watchlists and target prices:** local-browser storage; target achieved badge. Targets are checked when viewing the dashboard, **not push notifications**.
- **History charts:** compare data collected from RSS headline prices over time, or your imported observations. Empty or incomplete history is clearly labeled. The collector records a new snapshot when a parsed headline price changes, not at every poll.
- **Cross-retailer comparison:** manually add listings using the same exact product model; automatic groups are populated only where a plausible model token appears. Listings with similar names are **not automatically verified identical**.
- **Research links:** Google Shopping and CamelCamelCamel search shortcuts.
- **Import/export:** CSV offers import, CSV export, JSON local backup/restore, local browser persistence.

## Start using it locally

1. Extract the ZIP.
2. Install Python 3 if not already installed.
3. Open a terminal in the extracted `deal-intelligence` folder.
4. Run `python scripts/collect.py` (Windows may use `py scripts/collect.py`).
5. Run `python -m http.server 8000` (or `py -m http.server 8000`).
6. Open **http://localhost:8000/** in Chrome or Edge.

You can also double-click `index.html` to open the interface, but some browsers prevent local `fetch()` from loading `data/deals.json`; the local web server is recommended.

## Publish a continuously updated dashboard at $0 using GitHub Pages

1. Create a **public** repository on GitHub (for example `deal-intelligence`). Public repository code and public deal-feed data will be visible to everyone. Your saved watchlist remains local to your browser.
2. Upload the **contents** of `deal-intelligence` to the repository root, including `.github/workflows/update-deals.yml` (use GitHub Desktop to preserve the hidden `.github` folder). The repository root must contain `index.html`, not an enclosing `deal-intelligence` folder.
3. Go to **Settings → Pages → Build and deployment → Source** and select **GitHub Actions**. Do *not* choose "Deploy from a branch"; the workflow explicitly publishes the updated site each run.
4. Go to **Actions → Refresh deals and publish dashboard → Run workflow**, choosing `main`. If GitHub requires approval to run workflows, approve it.
5. After both `refresh` and `deploy` succeed, visit `https://YOUR_GITHUB_USERNAME.github.io/YOUR_REPOSITORY/`, and use **Reload feed**.
6. The workflow collects and publishes approximately every three hours. GitHub may delay or skip scheduled jobs.

If the `Save refreshed dataset` step reports a permissions error, review **Settings → Actions → General → Workflow permissions**. For the workflow's built-in `GITHUB_TOKEN` to commit fresh deal data, select **Read and write permissions** if available. The YAML also requests `contents: write`.

The first live run needs internet access to the public RSS feeds. Feeds can fail or reject automated retrieval; the source-health status will identify such failures. Neither the app nor the collector can guarantee new deals from each provider.

GitHub Pages and standard Actions on public repositories have free allowances, subject to GitHub's usage policies. No purchased domain, secret, paid API, or hosted database is required.

### Privacy and data portability

Saved personal data is stored only in the localStorage of the browser and site origin where you use the app. Using a different computer, browser, HTTP port, or switching from local to GitHub Pages will not sync it. Use **Backup JSON** and **Restore JSON** to move your settings. Never commit exported backups to the public GitHub repository.

## CSV format

```csv
title,price,retailer,url,category,group,date,target
"Example refrigerator",1899.99,"Store A",https://example.com/offer,Appliances,MODEL123,2026-11-20,1700
"Example refrigerator",1799.99,"Store B",https://example.com/other,Appliances,MODEL123,2026-11-20,1700
```

Date and target are optional. Importing the same title + retailer again will add a new price observation. `group` is how separate store offers are compared. Use exact model identifiers for real comparisons.

## Data limitations

- RSS content is a **deal discovery feed**, not a live retail product API. Headline prices can be absent, ambiguous, out of date, coupon-dependent, or for different product variants. Always verify at checkout. In particular, headlines with multiple dollar amounts are now excluded rather than assigning the wrong price.
- Automatic price history begins only when the collector first sees a given deal URL, and only changes captured in feed headline prices are tracked. It does not backfill 12 months of history.
- Automated cross-retailer matching is approximate by exact normalized title. Use manual model grouping for reliable comparisons.
- The dashboard does not independently check stock, expiration, shipping, taxes, checkout totals, or verified manufacturer SKUs.
- The collector retains the last 45 days of feed entries and caps published data at 1800 entries. Feed content is attributed to its source, linking users to the original source article without rewriting referral links.
- It is not a replacement for a licensed retailer price feed or Keepa's historical data service.

## Architecture

- `index.html`, `styles.css`, `app.js`: static interface, no JavaScript dependencies.
- `scripts/collect.py`: resilient RSS ingest + preservation of history + source statuses.
- `data/deals.json`: public deal-feed dataset consumed by the browser.
- `.github/workflows/update-deals.yml`: scheduled and manual collector runs, commits data updates.
- `tests/`: unit tests that run without external dependencies.

## Running tests

```sh
python -m unittest discover -s tests -v
```

## Sources

- DealNews official feed page: https://www.dealnews.com/pages/rss.html
- Slickdeals feed: https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&rss=1
- GitHub Pages: https://docs.github.com/en/pages
- GitHub Actions: https://docs.github.com/en/actions

## Version 2: Product-level discovery behavior

The collector now treats a deal article as a **lead**, not automatically as an individual product. It extracts a normalized product title when a recognized product type exists, rejects known roundup or article patterns, does not search article descriptions to decide categories, and records `isProduct`, `productTitle`, `articleTitle`, `matchConfidence`, `model`, `retailer`, and `linkType`. The original source article URL remains available, but is **not** mislabeled as a merchant listing. Old unclassified feed items are dropped on the first v2 refresh.

**Important limitation:** This improves product precision but still does not guarantee a canonical SKU, direct merchant product URL, verified price or complete catalog. Those require a permitted retailer-level product data source/API or structured product metadata. When an item lacks a clear seller or model, the app explicitly says so. A strict filter may lead to fewer discovered products; the collector displays per-source rejected-entry diagnostics in `data/deals.json`.

### Upgrade your existing GitHub repository

Download the v2 ZIP and copy **its contents, not the enclosing folder**, over your repository root. Commit and push the changed files. Go to Actions → Refresh deals and publish dashboard → Run workflow. GitHub Pages will republish the updated site. Local watchlists remain untouched because they are stored in your browser.
