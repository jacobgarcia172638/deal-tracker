"""
Checks every product in config/products.yaml for price changes and restocks.

Design notes (why it's built this way):
- Each product is checked inside its own try/except. If one product's page
  layout changes and breaks scraping, we log it and move on -- we never let
  one bad product take down the whole run.
- Only truly fatal problems (e.g. a broken products.yaml) are allowed to
  raise and fail the whole script, which is what triggers GitHub Actions'
  failure e-mail.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "products.yaml"
LAST_SEEN_PATH = ROOT / "data" / "last_seen.json"
UPDATES_PATH = ROOT / "data" / "updates.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

PRICE_PATTERN = re.compile(r"\$\s?[0-9]{1,4}(?:,[0-9]{3})*(?:\.[0-9]{2})?")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("scrape")


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_json(path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def extract_price(soup):
    # Try common Amazon-style price containers first, then fall back to
    # scanning the whole page for the first dollar amount.
    selectors = [
        "span.a-price span.a-offscreen",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
        "span#price_inside_buybox",
    ]
    for sel in selectors:
        tag = soup.select_one(sel)
        if tag:
            match = PRICE_PATTERN.search(tag.get_text())
            if match:
                return match.group(0)

    match = PRICE_PATTERN.search(soup.get_text(" "))
    return match.group(0) if match else None


def price_to_float(price_str):
    if not price_str:
        return None
    cleaned = price_str.replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def check_product(product):
    url = product["url"]
    in_stock_text = product.get("in_stock_text", "")

    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    page_text = soup.get_text(" ")
    in_stock = (in_stock_text.lower() in page_text.lower()) if in_stock_text else None

    price = price_to_float(extract_price(soup))

    return {
        "price": price,
        "in_stock": in_stock,
        "last_checked": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main():
    config = load_yaml(CONFIG_PATH)
    products = config.get("products", [])

    last_seen = load_json(LAST_SEEN_PATH, {})
    updates = load_json(UPDATES_PATH, [])

    if not products:
        log.warning("No products configured in %s -- nothing to check.", CONFIG_PATH)

    for product in products:
        name = product.get("name")
        url = product.get("url")
        if not name or not url:
            log.error("Skipping malformed product entry (missing name/url): %s", product)
            continue

        try:
            result = check_product(product)
        except Exception as exc:  # noqa: BLE001 -- one broken product must never kill the run
            log.error("Failed to check '%s' (%s): %s", name, url, exc)
            continue

        previous = last_seen.get(name)
        new_price = result["price"]
        new_stock = result["in_stock"]

        if previous:
            old_price = previous.get("price")
            old_stock = previous.get("in_stock")

            if new_price is not None and old_price is not None and new_price < old_price:
                updates.insert(0, {
                    "timestamp": result["last_checked"],
                    "product": name,
                    "type": "price_drop",
                    "old_price": old_price,
                    "new_price": new_price,
                    "affiliate_link": product.get("affiliate_link", url),
                })
                log.info("Price drop detected for '%s': %s -> %s", name, old_price, new_price)

            if old_stock is False and new_stock is True:
                updates.insert(0, {
                    "timestamp": result["last_checked"],
                    "product": name,
                    "type": "restock",
                    "new_price": new_price,
                    "affiliate_link": product.get("affiliate_link", url),
                })
                log.info("Restock detected for '%s'", name)
        else:
            log.info("First check for '%s' -- recording baseline, no alert generated.", name)

        last_seen[name] = {
            "url": url,
            "price": new_price,
            "in_stock": new_stock,
            "last_checked": result["last_checked"],
        }

    save_json(LAST_SEEN_PATH, last_seen)
    save_json(UPDATES_PATH, updates[:200])  # cap history so the file doesn't grow forever


if __name__ == "__main__":
    main()
