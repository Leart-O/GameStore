# scraper/gamestar_scraper.py
"""
Scraper using requests + BeautifulSoup to extract product data from gamestar-ks.com.
It extracts: name, price, brand, status.

IMPORTANT:
- You must inspect the actual HTML of the target category/product pages at gamestar-ks.com and
  adapt the CSS selectors below if needed (site HTML may change).
- This script is a starter that looks for common patterns; adjust selectors/class names to be correct.

Usage:
python scraper/gamestar_scraper.py --url "https://gamestar-ks.com/product-category/your-category/" --mode print
or use --mode post to send to API: require --api-key and --base-url
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import argparse
import os
import json

BASE = "https://gamestar-ks.com"

def parse_price(text):
    if not text:
        return None
    p = text.replace("€","").replace("$","").replace(",","").strip()
    num = ''.join(ch for ch in p if (ch.isdigit() or ch == "." or ch == "-"))
    try:
        return float(num) if num else None
    except:
        return None

def scrape_category(url: str, max_pages=1):
    """
    Scrape products from a category or listing page.
    Returns list of dicts: {'name','price','brand','status','product_url'}
    NOTE: You must edit CSS selectors below to match actual page markup.
    """
    products = []
    session = requests.Session()
    for page in range(1, max_pages+1):
        page_url = url
        # if site uses paged URLs, adapt here (example: ?paged=2 or /page/2)
        if page > 1:
            if "?" in url:
                page_url = f"{url}&paged={page}"
            else:
                page_url = f"{url.rstrip('/')}/page/{page}/"
        headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                }
        resp = session.get(page_url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # ADAPT selectors: common patterns for WooCommerce sites:
        # product_items = soup.select("ul.products li.product")
        product_items = soup.select("li.product, div.product, article.product")
        if not product_items:
            # fallback: any link with 'product' in its class
            product_items = soup.find_all("a", class_=lambda v: v and "product" in v)

        for item in product_items:
            # product URL
            link = None
            a = item.find("a", href=True)
            if a:
                link = urljoin(BASE, a["href"])

            # name/title
            title = None
            t = item.select_one(".woocommerce-loop-product__title") or item.select_one(".product-title") or item.select_one("h2") or item.select_one("h3")
            if t:
                title = t.get_text(strip=True)
            else:
                # fallback to link text
                if a and a.get_text(strip=True):
                    title = a.get_text(strip=True)

            # price
            price = None
            # common WooCommerce selectors for price
            price_tag = item.select_one(".price") or item.select_one(".amount") or item.find("span", class_=lambda v: v and "price" in v)
            if price_tag:
                price = parse_price(price_tag.get_text())

            # brand - many stores include brand in meta or within a span
            brand = None
            brand_tag = item.select_one(".brand") or item.select_one(".product-brand") or item.find("span", class_=lambda v: v and "brand" in v)
            if brand_tag:
                brand = brand_tag.get_text(strip=True)

            # status - try to find 'out of stock' markers
            status = None
            stock_tag = item.select_one(".outofstock, .stock, .availability")
            if stock_tag:
                status_text = stock_tag.get_text(strip=True).lower()
                if "out of stock" in status_text or "unavailable" in status_text:
                    status = "out of stock"
                elif "in stock" in status_text or "available" in status_text:
                    status = "in stock"
                else:
                    status = stock_tag.get_text(strip=True)

            # clean/title required
            if title:
                products.append({
                    "name": title,
                    "price": price,
                    "brand": brand,
                    "status": status,
                    "product_url": link
                })
        time.sleep(0.5)
    return products

def post_products_to_api(products, base_url, api_key):
    import requests
    endpoint = urljoin(base_url, "products/")
    headers = {"Content-Type":"application/json", "api-key": api_key}
    count = 0
    for p in products:
        payload = {
            "name": p.get("name"),
            "brand": p.get("brand"),
            "status": p.get("status"),
            "price": p.get("price")
        }
        try:
            r = requests.post(endpoint, json=payload, headers=headers, timeout=10)
            if r.status_code in (200,201):
                count += 1
            else:
                print("Failed to POST:", r.status_code, r.text, payload)
        except Exception as e:
            print("Error posting:", e, payload)
    print(f"Posted {count}/{len(products)} products to API.")
    return count

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", "-u", required=True, help="Category or listing URL to scrape")
    parser.add_argument("--pages", type=int, default=1, help="How many pages to scrape")
    parser.add_argument("--mode", choices=("print","post","savejson"), default="print")
    parser.add_argument("--base-url", default=os.getenv("BASE_URL","http://127.0.0.1:8000"))
    parser.add_argument("--api-key", default=os.getenv("API_KEYS"))
    parser.add_argument("--out", default="products.json")
    args = parser.parse_args()

    products = scrape_category(args.url, max_pages=args.pages)
    print(f"Found {len(products)} products")

    if args.mode == "print":
        print(json.dumps(products, indent=2, ensure_ascii=False))
    elif args.mode == "savejson":
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(products, fh, ensure_ascii=False, indent=2)
        print("Saved to", args.out)
    elif args.mode == "post":
        if not args.api_key:
            print("API key required to post to API.")
            return
        post_products_to_api(products, args.base_url, args.api_key)

if __name__ == "__main__":
    main()
