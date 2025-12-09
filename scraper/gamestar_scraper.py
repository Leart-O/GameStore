# scraper/gamestar_scraper.py
"""
Robust scraper for gamestar-ks.com category pages with retries and backoff.

Features:
- session with HTTPAdapter + Retry (retries on connection/read errors)
- longer timeouts (connect, read)
- exponential backoff between attempts
- verbose retry/skip logs
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from requests.structures import CaseInsensitiveDict
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import argparse
import time
import re
import os
import json

BASE = "https://gamestar-ks.com"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.google.com/"
}

_BAD_TITLE_RE = re.compile(r"^\s*-\d+%$|^ska\s+n[eë]\s+stok\s*$", flags=re.IGNORECASE)


def make_session(retries=3, backoff_factor=0.5, pool_maxsize=10):
    s = requests.Session()
    s.headers.update(HEADERS)
    # Retry configuration: only idempotent methods by default. For GET we want retries.
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=pool_maxsize)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def parse_price(text):
    if not text:
        return None
    p = text.replace("€", "").replace("$", "").strip()
    p = p.replace(",", ".")
    num = "".join(ch for ch in p if (ch.isdigit() or ch == "." or ch == "-"))
    try:
        return float(num) if num else None
    except:
        return None


def fetch_product_detail(session, url, timeout):
    """Fetch product detail page and extract canonical product title."""
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        title_tag = (
            soup.select_one("h1.product_title")
            or soup.select_one("h1.entry-title")
            or soup.select_one("h1")
        )
        if title_tag:
            return title_tag.get_text(strip=True)
    except Exception:
        pass
    return None


def scrape_category(url: str, max_pages=1, verbose=False):
    # make a session with retries/backoff
    s = make_session(retries=4, backoff_factor=0.6)
    # visit homepage to acquire cookies
    try:
        s.get(BASE, timeout=(5, 10))
    except Exception:
        pass

    products = []

    # timeouts: (connect_timeout, read_timeout)
    timeout = (6, 30)  # connect in 6s, read up to 30s

    for page in range(1, max_pages + 1):
        page_url = url if page == 1 else f"{url.rstrip('/')}/page/{page}/"
        if verbose:
            print("Fetching:", page_url)

        # do a manual retry loop so we can show messages
        attempts = 0
        max_attempts = 3
        while attempts < max_attempts:
            attempts += 1
            try:
                r = s.get(page_url, timeout=timeout)
                r.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                if attempts < max_attempts:
                    wait = 1.0 * (2 ** (attempts - 1))
                    print(f"  Warning: request failed (attempt {attempts}/{max_attempts}): {e}. Retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                else:
                    print(f"  ERROR: failed to fetch {page_url} after {attempts} attempts: {e}. Skipping page.")
                    r = None
            # end try/except
        if r is None:
            continue

        soup = BeautifulSoup(r.text, "html.parser")

        items = soup.select("ul.products li.product")
        if verbose:
            print("  product items found:", len(items))

        for item in items:
            title_tag = (
                item.select_one("h2.woocommerce-loop-product__title")
                or item.select_one("a > h2")
                or item.select_one("h2")
                or item.select_one("h3")
                or item.select_one(".product-title")
                or item.select_one("a")
            )
            title = title_tag.get_text(strip=True) if title_tag else None

            price_tag = (
                item.select_one("span.woocommerce-Price-amount bdi")
                or item.select_one("span.woocommerce-Price-amount")
                or item.select_one(".price bdi")
                or item.select_one(".price")
                or item.select_one("bdi")
            )
            price = parse_price(price_tag.get_text()) if price_tag else None

            a = item.select_one("a.woocommerce-LoopProduct-link[href], a[href]")
            link = urljoin(BASE, a["href"]) if a and a.has_attr("href") else None

            status = None
            stock_tag = item.select_one(".stock, .outofstock, .availability")
            if stock_tag:
                st = stock_tag.get_text(strip=True).lower()
                if "out" in st or "ska" in st:
                    status = "out of stock"
                elif "in stock" in st or "available" in st:
                    status = "in stock"
                else:
                    status = stock_tag.get_text(strip=True)

            # fallback to detail page if title is missing or looks like a badge
            if not title or _BAD_TITLE_RE.match(title):
                if link:
                    dt = fetch_product_detail(s, link, timeout)
                    if dt:
                        title = dt

            if not title or _BAD_TITLE_RE.match(title):
                if verbose:
                    snippet = item.get_text(strip=True)[:120]
                    print("  Skipping bad item. snippet:", snippet)
                continue

            products.append({
                "name": title,
                "price": price,
                "brand": None,
                "status": status,
                "product_url": link
            })

        # polite delay between pages
        time.sleep(0.45)

    return products


def get_existing_names_from_api(base_url):
    try:
        r = requests.get(urljoin(base_url.rstrip('/') + '/', "products/"), timeout=(5, 15))
        r.raise_for_status()
        items = r.json()
        return {i.get("name") for i in items if i.get("name")}
    except Exception:
        return set()


def post_products_to_api(products, base_url, api_key, verbose=False):
    endpoint = urljoin(base_url.rstrip('/') + '/', "products/")
    api_key = (api_key or "").strip()

    headers = CaseInsensitiveDict()
    headers["api-key"] = api_key
    headers["content-type"] = "application/json"

    existing = get_existing_names_from_api(base_url)
    posted = 0
    skipped = 0

    s = make_session(retries=3, backoff_factor=0.4)
    timeout = (5, 15)

    for p in products:
        name = p.get("name")
        if name in existing:
            skipped += 1
            if verbose:
                print("  Skipping (exists):", name)
            continue

        payload = {
            "name": name,
            "brand": p.get("brand"),
            "status": p.get("status"),
            "price": p.get("price")
        }
        if verbose:
            print("  POST ->", name, payload)

        try:
            r = s.post(endpoint, json=payload, headers=headers, timeout=timeout)
            if r.status_code in (200, 201):
                posted += 1
                existing.add(name)
            else:
                print("  Failed POST:", r.status_code, r.text, name)
        except Exception as e:
            print("  Error posting:", e, name)

    print(f"\nPosted {posted}/{len(products)} (skipped {skipped})")
    return posted, skipped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", "-u", required=True)
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--mode", choices=("print", "post", "savejson"), default="print")
    parser.add_argument("--base-url", default=os.getenv("BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--api-key", default=os.getenv("API_KEYS"))
    parser.add_argument("--out", default="products.json")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    products = scrape_category(args.url, max_pages=args.pages, verbose=args.verbose)
    print(f"\n🔍 Found {len(products)} valid products\n")

    if args.mode == "print":
        print(json.dumps(products, indent=2, ensure_ascii=False))
    elif args.mode == "savejson":
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(products, f, indent=2, ensure_ascii=False)
        print("Saved:", args.out)
    elif args.mode == "post":
        if not args.api_key:
            print("Missing --api-key")
            return
        post_products_to_api(products, args.base_url, args.api_key, verbose=args.verbose)


if __name__ == "__main__":
    main()
