"""
Pulls already-vetted deals from public RSS feeds of established deal
aggregator sites (Slickdeals, DealNews, etc.) and adds any new ones to
data/updates.json. This is how the site covers "many different websites"
without needing a specific product URL configured for each one.

Complements scrape.py, which instead tracks a hand-picked list of specific
products from config/products.yaml for price drops/restocks.

Design notes:
- Each feed is fetched inside its own try/except -- if one feed goes down
  or changes format, it's logged and skipped, same self-healing approach
  as scrape.py.
- data/seen_aggregator_links.json remembers which deal links have already
  been published, so re-running every 4 hours doesn't re-add duplicates.
- These are NOT affiliate links -- they point at the original deal page
  from the aggregator site, so they are intentionally NOT labeled
  "(affiliate link)" on the site.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "products.yaml"
UPDATES_PATH = ROOT / "data" / "updates.json"
SEEN_PATH = ROOT / "data" / "seen_aggregator_links.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

TAG_STRIP = re.compile(r"<[^>]+>")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("aggregate")


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


def clean_snippet(text, limit=200):
    if not text:
        return ""
    text = TAG_STRIP.sub("", text)
    text = " ".join(text.split())
    return text[:limit] + ("…" if len(text) > limit else "")


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
            "source": name,
            "title": title,
            "link": link,
            "snippet": clean_snippet(description),
        })
    return items


def main():
    config = load_yaml(CONFIG_PATH)
    sources = config.get("deal_sources", [])

    updates = load_json(UPDATES_PATH, [])
    seen_links = set(load_json(SEEN_PATH, []))

    if not sources:
        log.warning("No deal_sources configured in %s -- nothing to aggregate.", CONFIG_PATH)

    new_count = 0

    for source in sources:
        name = source.get("name")
        rss_url = source.get("rss_url")
        if not name or not rss_url:
            log.error("Skipping malformed deal source (missing name/rss_url): %s", source)
            continue

        try:
            items = fetch_feed(name, rss_url)
        except Exception as exc:  # noqa: BLE001 -- one broken feed must never kill the run
            log.error("Failed to fetch feed '%s' (%s): %s", name, rss_url, exc)
            continue

        added_this_source = 0
        for entry in items:
            if entry["link"] in seen_links:
                continue
            updates.insert(0, {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "type": "aggregator_deal",
                "product": entry["title"],
                "source": entry["source"],
                "link": entry["link"],
                "snippet": entry["snippet"],
            })
            seen_links.add(entry["link"])
            new_count += 1
            added_this_source += 1

        log.info("Fetched %d items from '%s', %d new.", len(items), name, added_this_source)

    save_json(UPDATES_PATH, updates[:300])
    save_json(SEEN_PATH, list(seen_links)[-5000:])  # cap so the file doesn't grow forever

    log.info("Added %d new aggregator deals this run.", new_count)


if __name__ == "__main__":
    main()
