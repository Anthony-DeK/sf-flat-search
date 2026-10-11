# SF Apartment Hunter

Scans furnished-rental sources every 30 minutes (7am to midnight Pacific) for furnished 1–2BR apartments with in-unit W/D at $3–5k in Nob Hill, North Beach, Russian Hill, Cow Hollow/Marina, Pacific Heights, Hayes Valley, Castro, Mission Dolores, Noe Valley, and West/Central/East SoMa and Mission Bay. The Market St corridor between 5th and 8th (Market to Howard) is excluded. It pushes new matches to your phone (ntfy), emails a digest (Gmail) and publishes a dashboard (GitHub Pages).

- **match**: every requirement confirmed. Sends a push and an email.
- **maybe**: nothing disqualifies it, but furnished, W/D or the exact neighborhood is unconfirmed. Email only.
- **🔥 deal**: in the cheapest quarter of $/bedroom for its neighborhood, once 6 or more comparable listings have been seen.

Edit `criteria.yaml` (price, beds, neighborhood boxes, keyword rules) and `sources.yaml` (sources, AppFolio landlords) to change the search.

## One-time setup
1. **Repo**: create a **public** repo on GitHub and push this folder.
   Public repos get free Pages and unlimited Actions minutes. A private repo would exceed the 2,000 free minutes a month and needs a paid plan for Pages. No secrets live in the repo.
   ```sh
   cd ~/sf-apartment-hunter && git init && git add . && git commit -m "init"
   git remote add origin https://github.com/<you>/sf-apartment-hunter.git && git push -u origin main
   ```
2. **ntfy**: install the ntfy app (iOS/Android) and subscribe to a hard-to-guess topic, e.g. `sfapt-` plus some random characters. Anyone who knows the topic can read it.
3. **Gmail app password**: turn on 2-Step Verification, then create one at https://myaccount.google.com/apppasswords.
4. **Secrets**: in the repo, go to Settings → Secrets and variables → Actions → New repository secret, and add:
   `NTFY_TOPIC`, `GMAIL_USER` (your Gmail address), `GMAIL_APP_PASSWORD`, `ALERT_TO` (where the digest goes).
5. **Pages**: Settings → Pages → Deploy from branch → `main` / `/docs`.
6. **First run**: Actions → scan → Run workflow. You should get a push for each current match and one digest email.

## Local
```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
.venv/bin/python -m scraper.run --dry-run           # prints alerts, saves nothing
.venv/bin/python -m scraper.run --dry-run --source blueground
.venv/bin/python -m pytest tests
```

## Alert-email import
Sites that block scrapers can still email you. Create a saved search with alerts on each site below, filtered to San Francisco, $3,000–5,000, 1–2 beds, furnished and in-unit laundry where the site offers those filters. Send the alerts to the `GMAIL_USER` inbox. Each run reads the last 3 days of alerts (read-only), runs them through the same filters, and alerts you once per listing.

- **Furnished Finder:** furnishedfinder.com, saved search with email alerts
- **Zillow:** Rentals, More → Furnished and In-unit laundry, Save search
- **HotPads:** same filters, Save search
- **Apartments.com:** Furnished and Washer/Dryer - In Unit filters, Save search
- **Redfin:** Rentals, Save search

`sources.yaml` → `Alert emails` → `assume` records what each saved search already guarantees. If you leave a filter off a site's search, remove its flag there.

## Notes
- **Craigslist may block GitHub's servers.** If the Craigslist count on the dashboard's "Sources & health" stays at 0, or you get a "source stopped working" email, run Craigslist from your Mac instead: schedule `python -m scraper.run --source craigslist` with launchd/cron, then `git pull --rebase && git push`.
- **Sites that can't be scraped** (bot protection or login) are listed on the dashboard. Furnished Finder is the one worth a saved-search alert.
- **Adding a landlord on AppFolio:** if a landlord's "Available rentals" page is `<name>.appfolio.com/listings`, add `<name>` to `subdomains` in `sources.yaml`.
- **Blueground prices** depend on stay length. The price shown is the lowest rent for the minimum stay.
