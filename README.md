# Deal Tracker

A fully automated deal-tracking website. It checks a list of products you
configure, detects price drops and restocks, and publishes updates to a free
GitHub Pages site — on a schedule, with no manual work after setup.

This README is split into three parts:

- **Part A** — one-time setup you do once, right now.
- **Part B** — the *only* ongoing manual action you'll ever take (optional, only when you want to add/remove a product, or add your affiliate tag).
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

The first `git push` will open a browser window asking you to sign in to
GitHub and authorize your Mac — just follow the prompts. After that, your
Mac remembers your login and you won't be asked again for this project.

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

Nothing to configure here — the workflow file
(`.github/workflows/update.yml`) is already in the repo and will start
running automatically every 4 hours as soon as it's pushed to GitHub. You can
confirm it's active by clicking the **Actions** tab on your repo — you should
see "Update Deal Tracker" listed as a workflow.

*Optional check:* click into the **Actions** tab → **Update Deal Tracker** →
**Run workflow** to trigger one run immediately, just to see it work. You
never have to do this again — it's just for peace of mind.

### A5. Turn on failure e-mail notifications (so you're only ever alerted when something breaks)

1. Click your profile picture (top-right on GitHub) → **Settings**.
2. In the left sidebar, click **Notifications**.
3. Find the **Actions** section.
4. Make sure **"Send notifications for failed workflows only"** is selected,
   with email as a delivery method.
5. Save if prompted.

This is a one-time, account-wide setting — GitHub will now email you only if
a scheduled run actually fails (e.g. all products broke, or the config file
has a typo). Silence means everything is working.

**Setup is now complete.** Your site is live, updating itself every 4 hours,
and will email you only if something breaks.

---

## Part B — The only file you ever edit: `config/products.yaml`

This is the **one and only** file you should ever touch by hand, and only
when you want to add or remove a tracked product, or add your real Amazon
affiliate tag. No coding required — it's a plain text list.

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
- Checking every product in `config/products.yaml` for price drops and restocks, every 4 hours.
- Detecting changes and adding new "newest first" entries to the site.
- Rebuilding the entire static site (`docs/index.html`, `about.html`) every run.
- Committing and pushing the updated data/site back to GitHub automatically.
- Publishing to your live GitHub Pages URL — no manual deploy, ever.
- Skipping gracefully and logging a warning if one product's page breaks scraping, without stopping the other products or crashing the run.
- Emailing you **only if a run genuinely fails** (per the Part A5 setting).

**The only things that ever need you, and only if you want them:**
- Editing `config/products.yaml` to add/remove a product or add your real affiliate tag (Part B). Optional, occasional, no coding.
- The one-time setup in Part A (create repo, enable Pages, enable email alerts) — done once, never again.

If you never touch `config/products.yaml` again, the site keeps running and
updating on the two sample/example entries already seeded in it. Nothing
else will ever require your attention unless GitHub emails you about a
failed run.

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

## Project structure

```
deal-tracker/
├── config/products.yaml      # <- the only file you ever edit
├── data/last_seen.json       # last known price/stock per product (auto-updated)
├── data/updates.json         # history of detected price drops/restocks (auto-updated)
├── docs/                     # the generated static site (GitHub Pages serves this)
├── scripts/scrape.py         # checks each product, updates data/
├── scripts/generate_site.py  # rebuilds docs/ from data/
├── .github/workflows/update.yml  # the schedule that runs everything
└── requirements.txt
```
