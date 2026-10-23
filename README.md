# SF Apartment Hunter

Scans furnished-rental sources every 30 minutes (7am to midnight Pacific) for 1–2BR apartments (furnished or unfurnished) with in-unit W/D at $3–5k in Nob Hill, North Beach, Russian Hill, Cow Hollow/Marina, Pacific Heights, Hayes Valley, Castro, Mission Dolores, Noe Valley, and West/Central/East SoMa and Mission Bay. The Market St corridor between 5th and 8th (Market to Howard) is excluded. It pushes new matches to your phone (ntfy), emails a digest (Gmail) and publishes a dashboard (GitHub Pages).

- **confirmed**: every requirement confirmed. Sends a push and an email.
- **needs a check**: nothing rules it out, but the listing doesn't confirm one detail: *W/D not confirmed*, *Location not confirmed* or *Price/beds missing*. Email only, grouped by what's missing.
- **Furnishing** is a label, not a filter: emails group listings as Furnished / Unfurnished / Not stated, and the dashboard has a furnishing filter. Set `furnishing.require_furnished: true` in `criteria.yaml` to go back to furnished-only.
- Pushes are capped at 8 per run (deals and cheapest first), plus one summary push when there are more.
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
Sites that block scrapers can still email you. Create a saved search with alerts on each site below, filtered to San Francisco, $3,000–5,000, 1–2 beds and in-unit laundry where the site offers that filter. Leave furnishing open unless you only want furnished. Send the alerts to the `GMAIL_USER` inbox. Each run reads the last 3 days of alerts (read-only), runs them through the same filters, and alerts you once per listing.

- **Furnished Finder:** furnishedfinder.com, saved search with email alerts
- **Zillow:** Rentals, More → Furnished and In-unit laundry, Save search
- **HotPads:** same filters, Save search
- **Apartments.com:** Furnished and Washer/Dryer - In Unit filters, Save search
- **Redfin:** Rentals, Save search
- **MLSListings:** create a free account, search Rent → San Francisco, Save search with email alerts

`sources.yaml` → `Alert emails` → `assume` records what each saved search already guarantees. If you leave a filter off a site's search, remove its flag there.

## Notes
- **Craigslist may block GitHub's servers.** If the Craigslist count on the dashboard's "Sources & health" stays at 0, or you get a "source stopped working" email, run Craigslist from your Mac instead: schedule `python -m scraper.run --source craigslist` with launchd/cron, then `git pull --rebase && git push`.
- **Sites that can't be scraped** (bot protection or login) are listed on the dashboard. Furnished Finder is the one worth a saved-search alert.
- **Weekly cleanup:** every Sunday (~3am Pacific) the `prune` workflow re-opens every kept listing and deletes the ones taken down (Craigslist, Blueground, AppFolio, RentSFNow, Zumper). Their ids go into `data/removed.json` for 90 days so they can't come back. Reddit and alert-email listings can't be checked and are left alone. Try it locally with `python -m scraper.prune --dry-run`.
- **Adding a landlord on AppFolio:** if a landlord's "Available rentals" page is `<name>.appfolio.com/listings`, add `<name>` to `subdomains` in `sources.yaml`.
- **Adding a landlord on Buildium:** same idea for `<name>.managebuilding.com/Resident/public/rentals`: add `<name>` under `Buildium landlords`.
- **Local agencies:** J. Wavro and Rentals Inc. are scraped from their own sites. Other agencies checked (Brick & Mortar, Anchor Realty, Kenney & Everest / Everest Mwamba, Brick+Timber's RentCafe portal) either load listings with JavaScript or are already covered through Zumper.
- **Blueground prices** depend on stay length. The price shown is the lowest rent for the minimum stay.
