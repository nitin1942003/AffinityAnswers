import csv
import time
import re
from typing import List, Dict
from urllib.parse import urljoin, urlencode

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# ---------------------------
# Global Config
# ---------------------------
BASE_URL = "https://www.olx.in"
SEARCH_PATH = "/items/q-car-cover"
OUTPUT_CSV = "olx_car_cover_results.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}

MAX_PAGES = 5
DELAY_BETWEEN_REQUESTS = 2.0


# ---------------------------
# Helper Functions
# ---------------------------
def build_search_url(page: int = 1) -> str:
    params = {}
    if page > 1:
        params["page"] = page
    return BASE_URL + SEARCH_PATH + (f"?{urlencode(params)}" if params else "")


def extract_card_data(card) -> Dict:
    """
    Extract title, price, location, and link from a single search result card.
    """
    a = card.select_one('a[href^="/item/"], a[href^="https://www.olx.in/item/"]')
    if not a:
        return None

    link = urljoin(BASE_URL, a.get("href", "").strip())

    # Title
    title = None
    for sel in ["h6", "h5", "h4", "h3", '[role="heading"]', "p"]:
        el = a.select_one(sel)
        if el and el.get_text(strip=True):
            title = el.get_text(strip=True)
            break
    if not title:
        title = a.get_text(" ", strip=True)

    # Price
    full_text = card.get_text(" ", strip=True)
    price_match = re.search(r"₹\s?[\d,]+", full_text)
    price = price_match.group(0) if price_match else None

    # Location & Posted time
    location = None
    posted = None
    meta_candidates = card.select("span, p, div")
    meta_texts = [el.get_text(" ", strip=True) for el in meta_candidates if el.get_text(strip=True)]

    def looks_timey(s: str) -> bool:
        return any(w in s.lower() for w in ["ago", "today", "yesterday", "hour", "minute", "week", "day", "month"])

    for t in meta_texts:
        if (len(t) <= 40) and not t.startswith("₹") and not looks_timey(t) and re.search(r"[A-Za-z]", t):
            location = t
            break

    for t in meta_texts:
        # Accept things like "today", "yesterday", "2 days ago", ..., or date-like strings (e.g., "AUG 02", "JUN 15")
        t_stripped = t.strip()
        t_lower = t_stripped.lower()
        # Only extract the posted time, not the whole string
        # Try to match "today", "yesterday", "2 days ago", ..., or date-like strings
        if "today" in t_lower:
            posted = "today"
            break
        elif "yesterday" in t_lower:
            posted = "yesterday"
            break
        else:
            m = re.match(r"^(\d+)\s+days?\s+ago$", t_lower)
            if m and 2 <= int(m.group(1)) <= 6:
                posted = f"{m.group(1)} days ago"
                break
            # Match date-like strings (e.g., "AUG 02", "JUN 15")
            m2 = re.match(r"^(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d{1,2}$", t_stripped.upper())
            if m2:
                posted = t_stripped
                break

    ad_id = None
    m = re.search(r"(\d{6,})", link)
    if m:
        ad_id = m.group(1)

    return {
        "title": title,
        "price": price,
        "location": location,
        "posted": posted,
        "link": link,
        "ad_id": ad_id,
    }


def parse_search_page(html: str) -> List[Dict]:
    """
    Parse the HTML and return a list of results as dictionaries.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    item_links = soup.select('a[href^="/item/"], a[href^="https://www.olx.in/item/"]')
    seen_cards = set()

    for a in item_links:
        parent = a
        card = None
        for _ in range(4):
            parent = parent.parent
            if not parent:
                break
            if getattr(parent, "name", None) and len(parent.find_all(True, recursive=False)) >= 2:
                card = parent
                if str(hash(card)) in seen_cards:
                    card = None
                    break
                seen_cards.add(str(hash(card)))
                break
        if not card:
            card = a

        data = extract_card_data(card)
        if data and data["title"] and data["link"]:
            results.append(data)

    return list({r["link"]: r for r in results}.values())


def save_csv(rows: List[Dict], filepath: str = OUTPUT_CSV):
    """
    Save scraped data into a CSV file.
    """
    fieldnames = ["title", "price", "location", "posted", "link", "ad_id"]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})
    print(f"[done] Wrote {len(rows)} rows to {filepath}")


# ---------------------------
# Selenium Scraper
# ---------------------------
def scrape_olx_car_covers_selenium(max_pages: int = MAX_PAGES) -> List[Dict]:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument(f"user-agent={HEADERS['User-Agent']}")
    driver = webdriver.Chrome(options=options)

    all_rows: List[Dict] = []
    try:
        for page in range(1, max_pages + 1):
            url = build_search_url(page)
            print(f"[info] (Selenium) Fetching page {page}: {url}")
            driver.get(url)
            time.sleep(3.5)  # wait for JS to render

            html = driver.page_source
            rows = parse_search_page(html)
            print(f"[info] (Selenium) Found {len(rows)} items on page {page}.")
            if not rows:
                break
            all_rows.extend(rows)
            time.sleep(DELAY_BETWEEN_REQUESTS)
    finally:
        driver.quit()

    unique = {r["link"]: r for r in all_rows}
    return list(unique.values())


# ---------------------------
# Main Execution
# ---------------------------
if __name__ == "__main__":
    rows = scrape_olx_car_covers_selenium(MAX_PAGES)
    save_csv(rows, OUTPUT_CSV)
