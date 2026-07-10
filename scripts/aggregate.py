"""
Pulls already-vetted deals from public RSS feeds of established deal
aggregator sites (Slickdeals, DealNews, etc.) and writes any new ones to
Supabase (see supabase_client.py). This is how the site covers "many
different websites" without needing a specific product URL configured for
each one.

Complements scrape.py, which instead tracks a hand-picked list of specific
products from config/products.yaml for price drops/restocks.

Design notes:
- Each feed is fetched inside its own try/except -- if one feed goes down
  or changes format, it's logged and skipped, same self-healing approach
  as scrape.py.
- Duplicate deals (same 'link') are skipped automatically by a unique
  index in Supabase (see supabase/schema.sql) -- no local "seen" file
  needed anymore.
- These are NOT affiliate links -- they point at the original deal page
  from the aggregator site, so they are intentionally NOT labeled
  "(affiliate link)" on the site.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
import yaml

from supabase_client import insert_deals, require_config

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "products.yaml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

TAG_STRIP = re.compile(r"<[^>]+>")
CONTENT_ENCODED_TAG = "{http://purl.org/rss/1.0/modules/content/}encoded"
STORE_SLUG_PATTERN = re.compile(r'data-store-slug="([^"]+)"')
BUY_NOW_AT_PATTERN = re.compile(r"(?:Buy Now|Shop Now) at ([^<]+?)</p>")

# Slickdeals' store slugs don't always title-case into the name a store
# actually uses -- a few common ones are worth correcting by hand.
STORE_NAME_FIXES = {
    "Lowes": "Lowe's",
    "Best Buy": "Best Buy",
    "Home Depot": "Home Depot",
}

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("aggregate")


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def clean_snippet(text, limit=200):
    if not text:
        return ""
    text = TAG_STRIP.sub("", text)
    text = " ".join(text.split())
    return text[:limit] + ("…" if len(text) > limit else "")


def humanize_slug(slug):
    name = " ".join(word.capitalize() for word in slug.replace("-", " ").split())
    return STORE_NAME_FIXES.get(name, name)


def extract_store(item, description):
    """
    Figures out which retailer a deal is actually from, so the site can
    filter by store. Slickdeals embeds a structured "data-store-slug" in
    its content:encoded block; DealNews instead ends its description with
    plain text like "Buy Now at Amazon". Falls back to None (shown as
    "Other" on the site) if neither pattern matches.
    """
    content = item.findtext(CONTENT_ENCODED_TAG) or ""
    match = STORE_SLUG_PATTERN.search(content)
    if match:
        return humanize_slug(match.group(1))

    match = BUY_NOW_AT_PATTERN.search(description)
    if match:
        return match.group(1).strip()

    return None


def fetch_feed(name, rss_url):
    resp = requests.get(rss_url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    items = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = item.findtext("description") or ""
        if not title or not link:
            continue
        items.append({
            "type": "aggregator_deal",
            "product": title,
            "source": name,
            "store": extract_store(item, description),
            "link": link,
            "snippet": clean_snippet(description),
        })
    return items


def main():
    # Fail fast and loudly if Supabase isn't configured at all -- this must
    # NOT be swallowed as a per-feed failure below, or a total
    # misconfiguration would silently never trigger the failure email.
    require_config()

    config = load_yaml(CONFIG_PATH)
    sources = config.get("deal_sources", [])

    if not sources:
        log.warning("No deal_sources configured in %s -- nothing to aggregate.", CONFIG_PATH)
        return

    total_new = 0

    for source in sources:
        name = source.get("name")
        rss_url = source.get("rss_url")
        if not name or not rss_url:
            log.error("Skipping malformed deal source (missing name/rss_url): %s", source)
            continue

        try:
            items = fetch_feed(name, rss_url)
            inserted = insert_deals(items)
        except Exception as exc:  # noqa: BLE001 -- one broken feed must never kill the run
            log.error("Failed to process feed '%s' (%s): %s", name, rss_url, exc)
            continue

        log.info("Fetched %d items from '%s', %d new.", len(items), name, len(inserted))
        total_new += len(inserted)

    log.info("Added %d new aggregator deals this run.", total_new)


if __name__ == "__main__":
    main()
