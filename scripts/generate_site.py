"""
Reads data/last_seen.json and data/updates.json and (re)writes the static
site in docs/ -- index.html, about.html, style.css. Runs every time so the
site never needs a manual rebuild.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "products.yaml"
LAST_SEEN_PATH = ROOT / "data" / "last_seen.json"
UPDATES_PATH = ROOT / "data" / "updates.json"
DOCS_DIR = ROOT / "docs"

PAGE_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header>
  <h1><a href="index.html">Deal Tracker</a></h1>
  <nav>
    <a href="index.html">Home</a>
    <a href="about.html">About</a>
  </nav>
</header>
<main>
"""

PAGE_FOOT = """
</main>
<footer>
  <p>As an Amazon Associate, this site may earn from qualifying purchases via links marked "(affiliate link)".</p>
  <p>Page generated: {updated}</p>
</footer>
</body>
</html>
"""

STYLE_CSS = """
body { font-family: -apple-system, Helvetica, Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; color: #222; line-height: 1.5; }
header { border-bottom: 2px solid #eee; margin-bottom: 20px; padding-bottom: 10px; }
header h1 { margin: 0 0 8px 0; }
header h1 a { text-decoration: none; color: #b12704; }
nav a { margin-right: 15px; color: #007185; text-decoration: none; }
nav a:hover { text-decoration: underline; }
ul.updates { list-style: none; padding: 0; }
ul.updates li { padding: 10px 0; border-bottom: 1px solid #eee; }
.tag { font-weight: bold; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; margin-right: 8px; }
.tag.price_drop { background: #d4edda; color: #155724; }
.tag.restock { background: #cce5ff; color: #004085; }
.timestamp { color: #888; font-size: 0.85em; float: right; }
table.status { border-collapse: collapse; width: 100%; margin-top: 10px; }
table.status th, table.status td { border: 1px solid #ddd; padding: 8px; text-align: left; }
table.status th { background: #fafafa; }
footer { margin-top: 30px; padding-top: 10px; border-top: 1px solid #eee; color: #666; font-size: 0.85em; }
"""


def load_yaml(path):
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_json(path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_price(value):
    return f"${value:,.2f}" if isinstance(value, (int, float)) else "—"


def render_index(last_seen, updates):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    html = [PAGE_HEAD.format(title="Deal Tracker — Latest Price Drops & Restocks")]
    html.append("<h2>Latest Updates</h2>")

    if updates:
        html.append('<ul class="updates">')
        for u in updates[:50]:
            label = "Price Drop" if u["type"] == "price_drop" else "Restock"
            link = u.get("affiliate_link", "#")
            if u["type"] == "price_drop":
                detail = f'{format_price(u.get("old_price"))} → <strong>{format_price(u.get("new_price"))}</strong>'
            else:
                detail = f'Now in stock — {format_price(u.get("new_price"))}'
            html.append(
                f'<li><span class="tag {u["type"]}">{label}</span> '
                f'<a href="{link}" target="_blank" rel="nofollow sponsored noopener">{u["product"]}</a> '
                f'<em>(affiliate link)</em> — {detail} '
                f'<span class="timestamp">{u["timestamp"]}</span></li>'
            )
        html.append("</ul>")
    else:
        html.append("<p>No price drops or restocks recorded yet. Check back soon.</p>")

    html.append("<h2>Currently Tracked Products</h2>")
    if last_seen:
        html.append(
            '<table class="status"><tr><th>Product</th><th>Price</th>'
            '<th>In Stock</th><th>Last Checked</th></tr>'
        )
        for name, info in last_seen.items():
            stock = info.get("in_stock")
            stock_label = "Yes" if stock else ("No" if stock is False else "Unknown")
            html.append(
                f"<tr><td>{name}</td><td>{format_price(info.get('price'))}</td>"
                f"<td>{stock_label}</td><td>{info.get('last_checked', '—')}</td></tr>"
            )
        html.append("</table>")
    else:
        html.append("<p>No products configured yet — add some in <code>config/products.yaml</code>.</p>")

    html.append(PAGE_FOOT.format(updated=now))
    return "".join(html)


def render_about():
    html = [PAGE_HEAD.format(title="About — Deal Tracker")]
    html.append("""
<h2>About This Site</h2>
<p>Deal Tracker automatically monitors a small list of products for price drops
and restocks, and publishes updates here as soon as they're detected. Checks run
automatically every few hours &mdash; nothing on this site is posted or edited by hand.</p>

<p>Some links on this site are Amazon affiliate links, clearly marked
"(affiliate link)". As an Amazon Associate, this site may earn from qualifying
purchases at no extra cost to you.</p>

<p>This is a personal hobby project built to keep an eye on prices for a
small, hand-picked list of products.</p>
""")
    html.append(PAGE_FOOT.format(updated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")))
    return "".join(html)


def main():
    last_seen = load_json(LAST_SEEN_PATH, {})
    updates = load_json(UPDATES_PATH, [])

    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    (DOCS_DIR / "index.html").write_text(render_index(last_seen, updates), encoding="utf-8")
    (DOCS_DIR / "about.html").write_text(render_about(), encoding="utf-8")
    (DOCS_DIR / "style.css").write_text(STYLE_CSS, encoding="utf-8")


if __name__ == "__main__":
    main()
