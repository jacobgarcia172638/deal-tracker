# Deal Tracker

A fully automated deal-tracking website with two sources of deals, gated
behind a $4/month subscription with a free 24-hour trial (just an email
address, no card required to try it):

1. **Broad deal coverage** across many retailers, pulled automatically from
   established deal-aggregator sites (Slickdeals, DealNews) via their public
   RSS feeds. No configuration needed per product — this just runs.
2. **Specific products you pick**, watched closely for price drops and
   restocks using your own Amazon affiliate link.

Note the important difference between the two: aggregator deals (#1) link to
the original deal post and are **not** affiliate links. Only products you
explicitly configure yourself (#2) use your affiliate link, clearly labeled
"(affiliate link)".

Every deal is tagged with the retailer it's actually from (Amazon, Lowe's,
Best Buy, Walmart, Home Depot, whichever stores currently have deals in the
feeds), and the site shows a row of filter pills so visitors can narrow the
list down to one store at a time.

**If you already ran `supabase/schema.sql` once before this store-filter
feature existed**, re-run the whole file again in Supabase's SQL Editor — it's
safe to run repeatedly and will just add the missing `store` column.

**How the paywall actually works:** it's enforced by the database (Postgres
Row Level Security in Supabase), not by the website's JavaScript. A visitor
without an active trial or subscription genuinely cannot retrieve deal data
— it isn't just hidden on the page. See `supabase/schema.sql` if you want to
read the actual rules.

This README is split into three parts:

- **Part A** — one-time setup you do once, right now (GitHub *and* the
  paywall infrastructure — Supabase, Resend, Stripe).
- **Part B** — the *only* ongoing manual action you'll ever take (optional,
  only when you want to add/remove a product, or add your affiliate tag).
- **Part C** — a plain confirmation of what runs itself forever, untouched.

---

## Part A — One-time setup (do this once)

You'll need a free [GitHub.com](https://github.com) account. If you don't have
one, create it first at github.com/signup.

### A1. Create the GitHub repository

1. Go to [github.com/new](https://github.com/new).
2. **Repository name**: `deal-tracker` (or any name you like).
3. Set it to **Public** (GitHub Pages' free tier requires a public repo,
   unless you're on a paid plan).
4. Do **not** check "Add a README" — you already have one.
5. Click **Create repository**. Leave the empty-repo instructions page open.

### A2. Push this project to your new repository

Open **Terminal** on your Mac, then run these commands one at a time. Replace
`YOUR-USERNAME` with your actual GitHub username (shown in the URL of the
empty-repo page from step A1).

```bash
cd "/Users/johngaffoglio/Library/Mobile Documents/com~apple~CloudDocs/Downloads/deal-tracker"
git remote add origin https://github.com/YOUR-USERNAME/deal-tracker.git
git branch -M main
git push -u origin main
```

The first `git push` will ask you to sign in to GitHub and authorize your
Mac — just follow the prompts. After that, your Mac remembers your login and
you won't be asked again for this project.

> The project is already saved as a local git commit — the commands above
> only need to connect it to GitHub and upload it.

### A3. Turn on GitHub Pages (this makes the site live)

1. On your repository's GitHub page, click **Settings** (top tab).
2. In the left sidebar, click **Pages**.
3. Under "Build and deployment" → **Source**, choose **Deploy from a branch**.
4. Under **Branch**, choose **main** and **/docs**, then click **Save**.
5. Wait 1–2 minutes. Refresh the page — GitHub will show your live URL, e.g.:
   `https://YOUR-USERNAME.github.io/deal-tracker/`

That URL is your public site. Bookmark it.

### A4. Turn on the automatic schedule (GitHub Actions)

Nothing to configure here yet — the workflow file
(`.github/workflows/update.yml`) is already in the repo. It won't run
successfully until the secrets from A9–A11 below are in place, but there's
nothing you need to click to "turn it on."

### A5. Turn on failure e-mail notifications (so you're only ever alerted when something breaks)

1. Click your profile picture (top-right on GitHub) → **Settings**.
2. In the left sidebar, click **Notifications**.
3. Find the **Actions** section.
4. Make sure **"Send notifications for failed workflows only"** is selected,
   with email as a delivery method.
5. Save if prompted.

This is a one-time, account-wide setting — GitHub will now email you only if
a scheduled run actually fails. Silence means everything is working.

---

The remaining steps (A6–A11) set up the paywall itself: a free database +
login system (Supabase), a way to actually send login emails (Resend), and
payment processing (Stripe). None of these are things I can create on your
behalf — they're your accounts.

### A6. Create a free Supabase project (the database + login system)

1. Go to [supabase.com](https://supabase.com), sign up free, click **New
   project**. Pick any name, generate/save a database password somewhere
   safe, pick a region near you, click **Create new project**. Wait ~2
   minutes for it to provision.
2. In the left sidebar, click the **SQL Editor** icon → **New query**.
3. Open [`supabase/schema.sql`](supabase/schema.sql) from this repo, copy
   its entire contents, paste into the SQL Editor, click **Run**. This
   creates every table and the paywall rule itself — nothing else to
   configure here.
4. In the left sidebar, click the gear icon (**Project Settings**) → **Data
   API**. Copy the **Project URL** and the **anon public** key — you'll need
   both in step A11. On the same page, also copy the **service_role** key
   (click "reveal" — it's marked secret). Treat the service_role key like a
   password: it's the one truly sensitive value in this whole setup.

### A7. Create a free Resend account (so login emails actually get sent)

Supabase's own free email sender only allows 2 emails per hour total —
too few for real signups. Resend's free tier fixes that.

1. Go to [resend.com](https://resend.com), sign up free.
2. Dashboard → **API Keys** → **Create API Key**. Copy it.
3. Back in your Supabase project: **Authentication** (left sidebar) →
   **Sign In / Providers** or **Emails** → find **SMTP Settings** → enable
   **Custom SMTP** and fill in:
   - Host: `smtp.resend.com`
   - Port: `587`
   - Username: `resend`
   - Password: the API key you just copied
   - Sender email: `onboarding@resend.dev` (Resend's shared test sender —
     works immediately, no domain verification needed to get started)
4. Save.

### A8. Create your Stripe account and the $4/month price

1. Go to [stripe.com](https://stripe.com) and sign up. You can explore
   everything below in **Test mode** (the default) before ever entering
   real bank details — recommended until you've confirmed the whole flow
   works end to end.
2. Dashboard → **Product catalog** → **Add product**. Name it (e.g. "Deal
   Tracker Subscription"), set pricing to **Recurring**, **$4.00**,
   **Monthly**. Save.
3. On that product's page, click **Create payment link**. Leave the
   defaults, create it, then copy the resulting URL (looks like
   `https://buy.stripe.com/xxxxxxxxx`). This is the link visitors click to
   subscribe.

### A9. Deploy the webhook (the one piece of backend code in this project)

This is the only custom server code anywhere in this setup — everything
else is configuration. In Terminal:

```bash
cd "/Users/johngaffoglio/Library/Mobile Documents/com~apple~CloudDocs/Downloads/deal-tracker"
npx supabase login
npx supabase link --project-ref YOUR-PROJECT-REF
npx supabase secrets set STRIPE_API_KEY=sk_test_your_key_here STRIPE_WEBHOOK_SIGNING_SECRET=placeholder
npx supabase functions deploy stripe-webhook
```

- `YOUR-PROJECT-REF` is in your Supabase project's URL/settings (a short
  string of letters and numbers).
- `sk_test_...` is your Stripe **Secret key** (Stripe Dashboard → Developers
  → API keys). Use the test-mode key while testing.
- The webhook signing secret is set to a placeholder for now — you'll
  replace it with the real one in the next step.
- `npx` downloads the Supabase CLI on the fly using the Node.js already on
  this Mac — no separate install needed.

### A10. Point Stripe at the webhook

1. Stripe Dashboard → **Developers** → **Webhooks** → **Add endpoint**.
2. Endpoint URL: `https://YOUR-PROJECT-REF.supabase.co/functions/v1/stripe-webhook`
3. Select these events: `checkout.session.completed`,
   `customer.subscription.updated`, `customer.subscription.deleted`,
   `invoice.payment_failed`.
4. Save, then click **Reveal** next to "Signing secret" (starts with
   `whsec_...`), copy it.
5. Back in Terminal, replace the placeholder from A9:
   ```bash
   npx supabase secrets set STRIPE_WEBHOOK_SIGNING_SECRET=whsec_the_real_value
   ```

### A11. Add everything as GitHub secrets

Repo → **Settings** → **Secrets and variables** → **Actions** → **New
repository secret**. Add each of these (values collected in A6 and A8):

| Secret name | Value |
|---|---|
| `SUPABASE_URL` | Project URL from A6 |
| `SUPABASE_SERVICE_ROLE_KEY` | service_role key from A6 (the sensitive one) |
| `SUPABASE_ANON_KEY` | anon public key from A6 |
| `STRIPE_PAYMENT_LINK` | Payment Link URL from A8 |

### A12. Test it, then go live

1. Actions tab → **Update Deal Tracker** → **Run workflow**. Wait ~1 minute,
   then refresh your live site.
2. Try the "Start your free day" flow yourself with your own email — check
   your inbox for the login link.
3. Once the trial expires (or to test immediately, edit your test row's
   `trial_started_at` in Supabase's Table Editor), confirm the "Subscribe"
   button appears and completes checkout using Stripe's test card
   `4242 4242 4242 4242`, any future date, any CVC.
4. When you're satisfied it all works, switch Stripe to **Live mode**
   (toggle in the Stripe Dashboard), create a live-mode Payment Link and
   API key, and update the `STRIPE_PAYMENT_LINK` GitHub secret and the
   `STRIPE_API_KEY` Supabase secret (`npx supabase secrets set
   STRIPE_API_KEY=sk_live_...`) to the live-mode values. You'll also need a
   second live-mode webhook endpoint (repeat A10) since test and live mode
   are separate in Stripe.

**Setup is now complete.** Your site is live, updating itself every 4 hours,
gated by a real paywall, and will email you only if something breaks.

---

## Part B — The only file you ever edit: `config/products.yaml`

This is the **one and only** file you should ever touch by hand, and only
when you want to add or remove a tracked product, add another deal-aggregator
RSS feed, or add your real Amazon affiliate tag. No coding required — it's a
plain text list with two sections.

### Section 1: `deal_sources` (broad coverage — rarely needs editing)

Already configured with Slickdeals and DealNews. You don't need to touch
this section at all unless you find another aggregator site with a public
RSS feed you'd like added — just copy the pattern:

```yaml
  - name: "Another Aggregator"
    rss_url: "https://example.com/deals/rss"
```

### Section 2: `products` (your hand-picked, closely-watched items)

Open [`config/products.yaml`](config/products.yaml). Each product looks like
this:

```yaml
  - name: "Example Wireless Mouse"
    url: "https://www.amazon.com/dp/B0EXAMPLE1"
    affiliate_link: "https://www.amazon.com/dp/B0EXAMPLE1?tag=YOURTAG-20"
    in_stock_text: "In Stock"
```

- **To add a product**: copy one of these blocks, paste it under the last
  one, and edit the four values.
- **To remove a product**: delete its block.
- **To add your real Amazon affiliate tag once approved**: this is the exact
  line to change, once per product —

  ```yaml
    affiliate_link: "https://www.amazon.com/dp/B0EXAMPLE1?tag=YOURTAG-20"
  ```

  Replace `YOURTAG-20` with the real tag Amazon gives you (it looks like
  `yourname-20`). That's the only field that needs your affiliate tag.

**How to save your edit** — easiest way, directly on GitHub.com, no Terminal
needed:

1. Go to your repo on GitHub → open `config/products.yaml`.
2. Click the pencil (✏️) icon to edit.
3. Make your change, scroll down, click **Commit changes**.

That's it. The next scheduled run (within 4 hours) automatically reads your
updated file, checks the new/changed products, and rebuilds the site. You
never need to rebuild, redeploy, or write any code.

---

## Part C — What runs itself vs. what needs you

**Runs completely on its own, forever, with zero input from you:**
- Pulling fresh deals from Slickdeals and DealNews's public feeds, every 4 hours.
- Checking every product in `config/products.yaml` for price drops and restocks, every 4 hours.
- Writing results to Supabase and rebuilding the static site shell every run.
- Enforcing the paywall itself (trial expiry, active subscriptions) via the database — no per-run action needed.
- Keeping subscriptions in sync automatically whenever Stripe sends a billing event (renewal, cancellation, failed payment) to the webhook.
- Publishing to your live GitHub Pages URL — no manual deploy, ever.
- Skipping gracefully and logging a warning if one product, or one aggregator feed, breaks — without stopping anything else or crashing the run.
- Emailing you **only if a run genuinely fails** (per the Part A5 setting).

**The only things that ever need you, and only if you want them:**
- Editing `config/products.yaml` to add/remove a product, add an aggregator feed, or add your real affiliate tag (Part B). Optional, occasional, no coding.
- The one-time setup in Part A (GitHub, Supabase, Resend, Stripe) — done once, never again.
- Ordinary business upkeep that comes with charging real money: refunds, cancellations, customer questions, and any sales-tax obligations in your area. That's on you, not on any script here.

---

## A note on reliability (read once)

Amazon and other large retailers actively try to block automated scraping
(CAPTCHAs, bot detection, layout changes). This project is built to degrade
gracefully — a broken product just gets skipped and logged — but you may
occasionally see a product go quiet if its page changes shape or blocks the
request outright. If that happens, no email is sent (it's not treated as a
failure) since it's isolated to that one product; check the Actions tab logs
if you want to see why. Sites with simpler, less bot-protected pages tend to
scrape most reliably.

## A note on the trial (read once)

The 1-day trial is tracked per email address in the database, not by a
browser cookie — clearing cookies or using a private window won't reset it.
Someone determined could still get another free day with a new email
address; this is a reasonable tradeoff for a hobby-scale project, not a
fraud-proof system.

## Project structure

```
deal-tracker/
├── config/products.yaml              # <- the only file you ever edit
├── docs/                             # the generated static site shell (GitHub Pages serves this)
├── scripts/scrape.py                 # checks hand-picked products, writes to Supabase
├── scripts/aggregate.py              # pulls deals from Slickdeals/DealNews RSS feeds, writes to Supabase
├── scripts/supabase_client.py        # shared helper for writing to Supabase via REST
├── scripts/generate_site.py          # rebuilds the static site shell in docs/
├── supabase/schema.sql               # tables + the actual paywall rules (Row Level Security)
├── supabase/functions/stripe-webhook # the one piece of backend code; keeps subscriptions in sync
├── .github/workflows/update.yml      # the schedule that runs everything
└── requirements.txt
```
