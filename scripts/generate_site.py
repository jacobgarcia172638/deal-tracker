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
<header class="site-header">
  <div class="wrap header-inner">
    <a class="brand" href="index.html">
      <span class="brand-mark">&#128230;</span>
      <span class="brand-text">Deal Tracker</span>
    </a>
    <nav>
      <a href="index.html">Home</a>
      <a href="about.html">About</a>
    </nav>
  </div>
</header>
<main class="wrap">
"""

PAGE_FOOT = """
</main>
<footer class="site-footer">
  <div class="wrap">
    <p>As an Amazon Associate, this site may earn from qualifying purchases via links marked <em>(affiliate link)</em>.</p>
    <p class="muted">Page generated: {updated}</p>
  </div>
</footer>
</body>
</html>
"""

STYLE_CSS = """
:root {
  color-scheme: light;
  --bg: #f6f7fb;
  --bg-soft: #eef0f6;
  --card-bg: #ffffff;
  --text: #1c1f26;
  --muted: #6b7280;
  --border: #e7e9ee;
  --accent: #2563eb;
  --accent-dark: #1d4ed8;
  --green-bg: #e7f8ee; --green-text: #0f7a3d;
  --blue-bg: #e8f1ff; --blue-text: #1d4ed8;
  --amber-bg: #fff6e0; --amber-text: #92650a;
  --radius: 14px;
  --shadow: 0 1px 2px rgba(16, 24, 40, 0.04), 0 1px 3px rgba(16, 24, 40, 0.06);
  --shadow-hover: 0 8px 24px rgba(16, 24, 40, 0.10);
}

@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --bg: #0f1115;
    --bg-soft: #161922;
    --card-bg: #171a21;
    --text: #e7e9ee;
    --muted: #9aa1ae;
    --border: #262a35;
    --accent: #5b8def;
    --accent-dark: #7fa6f2;
    --green-bg: #103a24; --green-text: #4ade8a;
    --blue-bg: #12233f; --blue-text: #7fa6f2;
    --amber-bg: #3a2e0f; --amber-text: #f2c25b;
    --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 1px 3px rgba(0,0,0,0.35);
    --shadow-hover: 0 8px 24px rgba(0,0,0,0.45);
  }
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}

.wrap { max-width: 880px; margin: 0 auto; padding: 0 20px; }

/* Header */
.site-header {
  background: linear-gradient(135deg, #1d4ed8, #2563eb 55%, #3b82f6);
  color: #fff;
  padding: 18px 0;
  box-shadow: var(--shadow);
  position: sticky;
  top: 0;
  z-index: 10;
}
.header-inner { display: flex; align-items: center; justify-content: space-between; }
.brand { display: flex; align-items: center; gap: 10px; text-decoration: none; color: #fff; }
.brand-mark { font-size: 1.5rem; line-height: 1; }
.brand-text { font-size: 1.3rem; font-weight: 700; letter-spacing: -0.02em; }
.site-header nav a {
  color: #eaf0ff;
  text-decoration: none;
  margin-left: 18px;
  font-weight: 500;
  padding: 6px 12px;
  border-radius: 999px;
  transition: background 0.15s ease;
}
.site-header nav a:hover { background: rgba(255,255,255,0.15); }

/* Hero */
.hero { padding: 40px 0 8px; }
.hero h1 {
  font-size: clamp(1.6rem, 3vw, 2.1rem);
  margin: 0 0 8px;
  letter-spacing: -0.02em;
}
.hero p.tagline { color: var(--muted); margin: 0 0 22px; font-size: 1.02rem; }
.stat-row { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 8px; }
.stat-pill {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 8px 16px;
  font-size: 0.85rem;
  color: var(--muted);
  box-shadow: var(--shadow);
}
.stat-pill strong { color: var(--text); }

/* Layout */
main.wrap { padding-bottom: 48px; }
h2 {
  font-size: 1.25rem;
  margin: 40px 0 16px;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--border);
  letter-spacing: -0.01em;
}
h2:first-of-type { margin-top: 8px; }

/* Deal cards */
.updates { display: flex; flex-direction: column; gap: 12px; }
.deal-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 16px 18px;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  animation: fade-in-up 0.4s ease backwards;
}
.deal-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-hover); }
.deal-card-top { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.deal-title { font-weight: 600; text-decoration: none; color: var(--text); font-size: 1.02rem; }
.deal-title:hover { color: var(--accent-dark); text-decoration: underline; }
.deal-detail { color: var(--muted); font-size: 0.93rem; margin-top: 5px; }
.deal-detail strong { color: var(--text); }
.affiliate-note { color: var(--muted); font-size: 0.8rem; font-style: italic; margin-left: 4px; }

.tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-weight: 700;
  font-size: 0.72rem;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  padding: 4px 10px;
  border-radius: 999px;
  white-space: nowrap;
}
.tag.price_drop { background: var(--green-bg); color: var(--green-text); }
.tag.restock { background: var(--blue-bg); color: var(--blue-text); }
.tag.aggregator_deal { background: var(--amber-bg); color: var(--amber-text); }

.timestamp { color: var(--muted); font-size: 0.78rem; white-space: nowrap; }

.empty-state {
  background: var(--card-bg);
  border: 1px dashed var(--border);
  border-radius: var(--radius);
  padding: 28px;
  color: var(--muted);
  text-align: center;
}

/* Status table */
.table-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
}
table.status { border-collapse: collapse; width: 100%; }
table.status th, table.status td { padding: 12px 16px; text-align: left; }
table.status th {
  background: var(--bg-soft);
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--muted);
  border-bottom: 1px solid var(--border);
}
table.status tr:not(:last-child) td { border-bottom: 1px solid var(--border); }
table.status tr:hover td { background: var(--bg-soft); }
.stock-yes { color: var(--green-text); font-weight: 600; }
.stock-no { color: #e5484d; font-weight: 600; }
.stock-unknown { color: var(--muted); }

/* About page */
.about-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 26px 30px;
  margin-top: 24px;
}
.about-card ul { padding-left: 20px; }
.about-card li { margin-bottom: 6px; }

/* Footer */
.site-footer {
  border-top: 1px solid var(--border);
  padding: 24px 0 40px;
  color: var(--muted);
  font-size: 0.85rem;
}
.site-footer p { margin: 4px 0; }
.muted { color: var(--muted); }
code {
  background: var(--bg-soft);
  padding: 2px 6px;
  border-radius: 6px;
  font-size: 0.9em;
}

@keyframes fade-in-up {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 560px) {
  .header-inner { flex-direction: column; align-items: flex-start; gap: 10px; }
  .deal-card-top { flex-direction: column; align-items: flex-start; gap: 4px; }
  table.status th:nth-child(3), table.status td:nth-child(3) { display: none; }
  .hero { padding-top: 28px; }
}

@media (prefers-reduced-motion: reduce) {
  .deal-card { animation: none; }
  .deal-card, .deal-card:hover { transition: none; transform: none; }
}
"""

TAG_ICONS = {
    "price_drop": "&#128181;",     # money with wings-ish / drop
    "restock": "&#9989;",          # check mark
    "aggregator_deal": "&#128293;",  # fire
}


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


def render_deal_card(u, index):
    utype = u["type"]
    if utype == "price_drop":
        label = "Price Drop"
        link = u.get("affiliate_link", "#")
        detail = f'{format_price(u.get("old_price"))} → <strong>{format_price(u.get("new_price"))}</strong>'
        affiliate_note = '<span class="affiliate-note">(affiliate link)</span>'
        rel = "nofollow sponsored noopener"
    elif utype == "restock":
        label = "Restock"
        link = u.get("affiliate_link", "#")
        detail = f'Now in stock — <strong>{format_price(u.get("new_price"))}</strong>'
        affiliate_note = '<span class="affiliate-note">(affiliate link)</span>'
        rel = "nofollow sponsored noopener"
    else:  # aggregator_deal -- from an external deal site, not our affiliate link
        label = u.get("source", "Deal")
        link = u.get("link", "#")
        detail = u.get("snippet", "")
        affiliate_note = ""
        rel = "nofollow noopener"

    icon = TAG_ICONS.get(utype, "")
    detail_html = f'<div class="deal-detail">{detail}</div>' if detail else ""
    delay = min(index * 0.03, 0.3)

    return (
        f'<div class="deal-card" style="animation-delay:{delay:.2f}s">'
        f'<div class="deal-card-top">'
        f'<span class="tag {utype}">{icon} {label}</span>'
        f'<span class="timestamp">{u["timestamp"]}</span>'
        f'</div>'
        f'<a class="deal-title" href="{link}" target="_blank" rel="{rel}">{u["product"]}</a>'
        f'{affiliate_note}'
        f'{detail_html}'
        '</div>'
    )


def render_index(last_seen, updates):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    sources = {u.get("source") for u in updates if u["type"] == "aggregator_deal"}
    sources.discard(None)

    html = [PAGE_HEAD.format(title="Deal Tracker — Latest Price Drops & Restocks")]

    html.append('<section class="hero">')
    html.append("<h1>Deals, tracked automatically.</h1>")
    html.append('<p class="tagline">Price drops, restocks, and fresh finds from across the web — updated every few hours, no one behind the wheel.</p>')
    html.append('<div class="stat-row">')
    html.append(f'<span class="stat-pill"><strong>{len(updates)}</strong> deals logged</span>')
    html.append(f'<span class="stat-pill"><strong>{len(last_seen)}</strong> products watched closely</span>')
    if sources:
        html.append(f'<span class="stat-pill"><strong>{len(sources)}</strong> aggregator sources</span>')
    html.append('</div>')
    html.append('</section>')

    html.append("<h2>Latest Updates</h2>")
    if updates:
        html.append('<div class="updates">')
        for i, u in enumerate(updates[:50]):
            html.append(render_deal_card(u, i))
        html.append("</div>")
    else:
        html.append('<div class="empty-state">No deals recorded yet. Check back soon.</div>')

    html.append("<h2>Currently Tracked Products</h2>")
    if last_seen:
        html.append('<div class="table-card"><table class="status">')
        html.append("<tr><th>Product</th><th>Price</th><th>In Stock</th><th>Last Checked</th></tr>")
        for name, info in last_seen.items():
            stock = info.get("in_stock")
            if stock is True:
                stock_label = '<span class="stock-yes">Yes</span>'
            elif stock is False:
                stock_label = '<span class="stock-no">No</span>'
            else:
                stock_label = '<span class="stock-unknown">Unknown</span>'
            html.append(
                f"<tr><td>{name}</td><td>{format_price(info.get('price'))}</td>"
                f"<td>{stock_label}</td><td>{info.get('last_checked', '—')}</td></tr>"
            )
        html.append("</table></div>")
    else:
        html.append(
            '<div class="empty-state">No products configured yet — '
            'add some in <code>config/products.yaml</code>.</div>'
        )

    html.append(PAGE_FOOT.format(updated=now))
    return "".join(html)


def render_about():
    html = [PAGE_HEAD.format(title="About — Deal Tracker")]
    html.append("""
<section class="hero" style="padding-top:16px;">
<h1>About This Site</h1>
</section>
<div class="about-card">
<p>Deal Tracker automatically publishes deal updates from two sources, and checks
run every few hours &mdash; nothing on this site is posted or edited by hand:</p>
<ul>
<li>Broad deal coverage pulled from established deal-aggregator sites (Slickdeals,
DealNews) spanning many retailers.</li>
<li>A hand-picked list of specific products watched closely for price drops and
restocks.</li>
</ul>

<p>Some links on this site are Amazon affiliate links, clearly marked
"(affiliate link)" &mdash; as an Amazon Associate, this site may earn from
qualifying purchases on those at no extra cost to you. Deals sourced from
aggregator sites link directly to the original deal post and are not
affiliate links.</p>

<p>This is a personal hobby project built to keep an eye on good deals
across the web.</p>
</div>
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
