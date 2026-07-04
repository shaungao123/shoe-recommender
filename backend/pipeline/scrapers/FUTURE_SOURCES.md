# Future sources — evaluated, not yet built

Add each as `pipeline/scrapers/<source>.py` subclassing `BaseScraper`, then
register it in `pipeline/scrapers/__init__.py`.

## Next up (high value)

- **Manufacturer product pages** (Nike, adidas, Jordan, UA, Puma, New Balance,
  Anta, Li-Ning): primary specs, official images, colorways, MSRP, aesthetic
  descriptors — the best source for the aesthetic input. Heavily
  JS-rendered → will need Playwright. **Check robots.txt/ToS per brand before
  building; scraping retailer/manufacturer sites at scale needs sign-off.**

## Feed integrations (not scrapes)

- **Affiliate feeds** (Amazon PA-API / retailer networks): live price +
  `affiliate_url`. Both are deliberately left null in the canonical schema
  until this lands. Requires API keys / program approval.

## Stretch

- **RunRepeat official data export** (CSV/XLSX/JSON/SQL) — paid; see the note
  in `runrepeat.py`. Would replace that scraper's fetch step wholesale.
- **r/BBallShoes** via the official Reddit API — sentiment + fit chatter.
- **YouTube transcripts** via the official captions API — reviewer sentiment.
- **StockX / GOAT resale bands** — for the sneakerhead persona; check ToS,
  likely needs their partner APIs.
