"""
Regenerates the static site shell in docs/ -- index.html, about.html,
style.css. Runs every time so the site never needs a manual rebuild.

Unlike the earlier version of this script, deal content is NOT baked into
the HTML anymore. Only a static "shell" (header, hero, About page, login
form) is generated here. The actual deals and tracked-product data are
fetched live, client-side, straight from Supabase -- and Postgres Row
Level Security (see supabase/schema.sql) decides whether the visitor is
entitled to see them (active trial or active subscription). That's what
makes the paywall real instead of cosmetic: the gate is enforced by the
database, not by this script or by JavaScript in the page.

Requires SUPABASE_URL, SUPABASE_ANON_KEY, STRIPE_PAYMENT_LINK as
environment variables. The anon key is safe to embed in public HTML by
design -- Supabase's security model relies on RLS policies, not on keeping
the anon key secret.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
STRIPE_PAYMENT_LINK = os.environ.get("STRIPE_PAYMENT_LINK", "")

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
.empty-state.gate { border-style: solid; text-align: left; }
.empty-state.gate h3 { margin: 0 0 8px; color: var(--text); }

/* Login / upgrade */
.login-form { display: flex; gap: 8px; flex-wrap: wrap; margin: 14px 0 6px; }
.login-form input {
  flex: 1;
  min-width: 200px;
  padding: 10px 14px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  font-size: 0.95rem;
}
.login-form button, .upgrade-btn {
  padding: 10px 18px;
  border-radius: 999px;
  border: none;
  background: var(--accent);
  color: #fff;
  font-weight: 600;
  font-size: 0.95rem;
  cursor: pointer;
  text-decoration: none;
  display: inline-block;
  transition: background 0.15s ease;
}
.login-form button:hover, .upgrade-btn:hover { background: var(--accent-dark); }

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

# Vanilla JS, no build step. Loaded only on index.html. Handles: email login
# (magic link, no password), checking trial/subscription entitlement, and
# rendering deals -- all fetched live from Supabase, gated by that project's
# Row Level Security policies (see supabase/schema.sql). If a visitor isn't
# entitled, the "deals" query below simply comes back empty -- there is no
# code path in this file that can show gated content to the wrong person,
# because the enforcement lives in Postgres, not here.
APP_SCRIPT = """
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
<script>
(function () {
  var SUPABASE_URL = "%(supabase_url)s";
  var SUPABASE_ANON_KEY = "%(supabase_anon_key)s";
  var STRIPE_PAYMENT_LINK = "%(stripe_payment_link)s";
  var TRIAL_MS = 24 * 60 * 60 * 1000;

  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    document.getElementById('app').innerHTML =
      '<div class="empty-state">Site is not yet configured (missing Supabase settings).</div>';
    return;
  }

  var sb = supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
  var appEl = document.getElementById('app');

  function escapeHtml(str) {
    return String(str == null ? '' : str).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function formatPrice(v) {
    return (typeof v === 'number') ? ('$' + v.toFixed(2)) : '—';
  }

  function renderSignedOut() {
    appEl.innerHTML =
      '<div class="empty-state gate">' +
      '<h3>Start your free day</h3>' +
      '<p>Enter your email for a one-click login link. Browse free for 24 hours, no card required.</p>' +
      '<form id="login-form" class="login-form">' +
      '<input type="email" id="login-email" placeholder="you@example.com" required>' +
      '<button type="submit">Send my login link</button>' +
      '</form>' +
      '<p id="login-status" class="muted"></p>' +
      '</div>';

    document.getElementById('login-form').addEventListener('submit', function (e) {
      e.preventDefault();
      var email = document.getElementById('login-email').value.trim();
      var statusEl = document.getElementById('login-status');
      statusEl.textContent = 'Sending...';
      sb.auth.signInWithOtp({
        email: email,
        options: { emailRedirectTo: window.location.href }
      }).then(function (res) {
        statusEl.textContent = res.error
          ? ('Error: ' + res.error.message)
          : 'Check your email for a login link.';
      });
    });
  }

  function renderLocked(userId, email) {
    var url;
    try { url = new URL(STRIPE_PAYMENT_LINK); } catch (e) { url = null; }
    if (url) {
      if (userId) url.searchParams.set('client_reference_id', userId);
      if (email) url.searchParams.set('prefilled_email', email);
    }
    var href = url ? url.toString() : '#';
    appEl.innerHTML =
      '<div class="empty-state gate">' +
      '<h3>Your free day is up</h3>' +
      '<p>Subscribe for $4/month to keep seeing new deals as they\\'re found.</p>' +
      '<a class="upgrade-btn" href="' + href + '">Subscribe — $4/mo</a>' +
      '</div>';
  }

  function dealCardHtml(u, index) {
    var icons = { price_drop: '&#128181;', restock: '&#9989;', aggregator_deal: '&#128293;' };
    var label, link, detail, note, rel;
    if (u.type === 'price_drop') {
      label = 'Price Drop';
      link = u.affiliate_link || '#';
      detail = formatPrice(u.old_price) + ' → <strong>' + formatPrice(u.new_price) + '</strong>';
      note = '<span class="affiliate-note">(affiliate link)</span>';
      rel = 'nofollow sponsored noopener';
    } else if (u.type === 'restock') {
      label = 'Restock';
      link = u.affiliate_link || '#';
      detail = 'Now in stock — <strong>' + formatPrice(u.new_price) + '</strong>';
      note = '<span class="affiliate-note">(affiliate link)</span>';
      rel = 'nofollow sponsored noopener';
    } else {
      label = u.source || 'Deal';
      link = u.link || '#';
      detail = u.snippet || '';
      note = '';
      rel = 'nofollow noopener';
    }
    var icon = icons[u.type] || '';
    var delay = Math.min(index * 0.03, 0.3).toFixed(2);
    return (
      '<div class="deal-card" style="animation-delay:' + delay + 's">' +
      '<div class="deal-card-top">' +
      '<span class="tag ' + u.type + '">' + icon + ' ' + escapeHtml(label) + '</span>' +
      '<span class="timestamp">' + escapeHtml(u.created_at || '') + '</span>' +
      '</div>' +
      '<a class="deal-title" href="' + link + '" target="_blank" rel="' + rel + '">' + escapeHtml(u.product) + '</a>' +
      note +
      (detail ? '<div class="deal-detail">' + detail + '</div>' : '') +
      '</div>'
    );
  }

  function renderEntitled(deals, products) {
    var html = '';
    html += '<div class="stat-row" style="margin-bottom:28px;">';
    html += '<span class="stat-pill"><strong>' + deals.length + '</strong> deals logged</span>';
    html += '<span class="stat-pill"><strong>' + products.length + '</strong> products watched closely</span>';
    html += '</div>';

    html += '<h2>Latest Updates</h2>';
    if (deals.length) {
      html += '<div class="updates">' + deals.map(dealCardHtml).join('') + '</div>';
    } else {
      html += '<div class="empty-state">No deals recorded yet. Check back soon.</div>';
    }

    html += '<h2>Currently Tracked Products</h2>';
    if (products.length) {
      html += '<div class="table-card"><table class="status">';
      html += '<tr><th>Product</th><th>Price</th><th>In Stock</th><th>Last Checked</th></tr>';
      products.forEach(function (p) {
        var stockLabel = p.in_stock === true ? '<span class="stock-yes">Yes</span>'
          : p.in_stock === false ? '<span class="stock-no">No</span>'
          : '<span class="stock-unknown">Unknown</span>';
        html += '<tr><td>' + escapeHtml(p.name) + '</td><td>' + formatPrice(p.price) + '</td>' +
          '<td>' + stockLabel + '</td><td>' + escapeHtml(p.last_checked || '—') + '</td></tr>';
      });
      html += '</table></div>';
    } else {
      html += '<div class="empty-state">No products configured yet — add some in <code>config/products.yaml</code>.</div>';
    }

    appEl.innerHTML = html;
  }

  function main() {
    sb.auth.getSession().then(function (res) {
      var session = res.data.session;
      if (!session) { renderSignedOut(); return; }

      var userId = session.user.id;
      var email = session.user.email;

      Promise.all([
        sb.from('profiles').select('trial_started_at').eq('id', userId).maybeSingle(),
        sb.from('subscriptions').select('status').eq('user_id', userId).maybeSingle()
      ]).then(function (results) {
        var profile = results[0].data;
        var subscription = results[1].data;

        var trialActive = false;
        if (profile && profile.trial_started_at) {
          var started = new Date(profile.trial_started_at).getTime();
          trialActive = (Date.now() - started) < TRIAL_MS;
        }
        var subscribed = subscription && subscription.status === 'active';

        if (!trialActive && !subscribed) { renderLocked(userId, email); return; }

        Promise.all([
          sb.from('deals').select('*').order('created_at', { ascending: false }).limit(50),
          sb.from('tracked_products').select('*')
        ]).then(function (dealsResults) {
          renderEntitled(dealsResults[0].data || [], dealsResults[1].data || []);
        });
      });
    });
  }

  sb.auth.onAuthStateChange(function () { main(); });
  main();
})();
</script>
"""


def render_index():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    html = [PAGE_HEAD.format(title="Deal Tracker — Latest Price Drops & Restocks")]

    html.append('<section class="hero">')
    html.append("<h1>Deals, tracked automatically.</h1>")
    html.append(
        '<p class="tagline">Price drops, restocks, and fresh finds from across the web '
        "— updated every few hours, no one behind the wheel.</p>"
    )
    html.append("</section>")

    html.append('<div id="app"><div class="empty-state">Loading…</div></div>')

    html.append(PAGE_FOOT.format(updated=now))
    html.append(
        APP_SCRIPT
        % {
            "supabase_url": SUPABASE_URL,
            "supabase_anon_key": SUPABASE_ANON_KEY,
            "stripe_payment_link": STRIPE_PAYMENT_LINK,
        }
    )
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

<p>New visitors get a free 24-hour trial (just an email address, no card
required); after that, continued access is $4/month.</p>
</div>
""")
    html.append(PAGE_FOOT.format(updated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")))
    return "".join(html)


def main():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    (DOCS_DIR / "index.html").write_text(render_index(), encoding="utf-8")
    (DOCS_DIR / "about.html").write_text(render_about(), encoding="utf-8")
    (DOCS_DIR / "style.css").write_text(STYLE_CSS, encoding="utf-8")


if __name__ == "__main__":
    main()
