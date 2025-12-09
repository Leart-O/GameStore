# scraper/debug_fetch.py
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

URL = "https://gamestar-ks.com/product-category/aksion-zbritje/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/"
}

def run():
    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        # First visit the homepage to get cookies
        s.get("https://gamestar-ks.com", timeout=15)
    except Exception as e:
        print("Warning: homepage visit failed:", e)
    try:
        r = s.get(URL, timeout=20)
    except Exception as e:
        print("ERROR fetching category page:", e)
        return

    text = r.text or ""
    print("HTTP status:", r.status_code)
    print("Response length:", len(text))
    print("Contains 'cloudflare'?:", "cloudflare" in text.lower())
    print("Contains 'captcha'?:", "captcha" in text.lower())
    print("Contains 'checking your browser'?:", "checking your browser" in text.lower())
    print("Contains 'attention required'?:", "attention required" in text.lower())
    # Print first 1200 characters so we can see the page head
    print("\n--- snippet (first 1200 chars) ---\n")
    print(text[:1200])
    # Save full HTML for manual inspection
    out = "scraper/debug_gamestar.html"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"\nSaved full HTML to: {out}")

    # quick try selectors
    soup = BeautifulSoup(text, "html.parser")
    selectors = [
        "div.products div.product",
        "ul.products li.product",
        "article.product",
        "div.product",
        "li.product",
        "div[class*=product]",
    ]
    for sel in selectors:
        found = soup.select(sel)
        print(f"Selector '{sel}' -> {len(found)} found")

if __name__ == "__main__":
    run()
