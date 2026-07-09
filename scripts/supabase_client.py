"""
Minimal REST helper for writing to Supabase (PostgREST) using the
service-role key. Used by scrape.py and aggregate.py, which write their
results here now instead of committing local JSON files -- anything
committed to this public repo would be readable by anyone and would defeat
the paywall entirely (see supabase/schema.sql for the actual gate, which
lives in Postgres Row Level Security, not in these scripts).

Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY as environment
variables (set as GitHub Actions secrets in CI, or in your own shell when
testing locally). The service-role key bypasses Row Level Security, which
is expected here -- these scripts are the trusted data source, not a
visitor's browser.
"""

import os

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")


def _headers(extra=None):
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def require_config():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set as environment "
            "variables (GitHub Actions repo secrets) for this script to run."
        )


def get_all_tracked_products():
    """Returns {product_name: row_dict} for every hand-picked product's current snapshot."""
    require_config()
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/tracked_products",
        headers=_headers(),
        params={"select": "*"},
        timeout=20,
    )
    resp.raise_for_status()
    return {row["name"]: row for row in resp.json()}


def upsert_tracked_product(row):
    """Insert or update the current price/stock snapshot for one product."""
    require_config()
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/tracked_products",
        headers=_headers({"Prefer": "resolution=merge-duplicates,return=minimal"}),
        params={"on_conflict": "name"},
        json=row,
        timeout=20,
    )
    resp.raise_for_status()


def insert_deals(rows):
    """
    Bulk-insert deal rows. Rows whose 'link' already exists are silently
    skipped (see the unique index in schema.sql) -- this is what stops the
    aggregator from re-adding the same RSS item every run. Rows with no
    'link' (hand-picked price drops/restocks) are never treated as
    duplicates. Returns only the rows that were newly inserted.
    """
    if not rows:
        return []
    require_config()
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/deals",
        headers=_headers({"Prefer": "resolution=ignore-duplicates,return=representation"}),
        params={"on_conflict": "link"},
        json=rows,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
