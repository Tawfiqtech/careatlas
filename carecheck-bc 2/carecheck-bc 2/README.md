# CareCheck BC

Every licensed child care facility in Metro Vancouver, with health authority
inspection history attached — searchable in one place. A static, SEO-first
directory built to rank for "child care [city]" and "[facility name] inspection"
searches, with a free claim-your-listing flow for providers.

**Stack:** Python (std-lib only) static site generator → Netlify. No frameworks,
no build dependencies, no database. Data lives in `data/facilities.json` in the repo.

---

## Repo layout

```
data/facilities.json        All facility + inspection data (currently SAMPLE data)
scripts/build_site.py       Generates the whole site into dist/
scripts/import_bc_csv.py    Imports the official BC childcare_locations.csv
scripts/scrape_common.py    Polite-scraping layer: robots.txt, rate limit, cache
scripts/scrape_vch.py       VCH inspection scraper (needs one config pass — see below)
scripts/scrape_fraser.py    Fraser Health inspection scraper (same)
static/                     styles.css + search.js, copied into dist/
netlify.toml                Build config (python3 scripts/build_site.py → dist/)
.github/workflows/          Weekly automated data refresh
```

---

## Launch runbook (in order)

### Step 0 — Deploy the sample site (10 minutes, today)

**Fastest path (zero terminal):** the project download includes a pre-built
`dist/` folder (gitignored — Netlify rebuilds it on every deploy in the Git
flow). Go to https://app.netlify.com/drop and drag the `dist` folder in —
live in under a minute. Use this to see it running, then switch to the Git
flow below so deploys are automatic.

**Proper path (Git-connected):**
1. Push this repo to GitHub.
2. In Netlify: **Add new site → Import from Git**, pick the repo. Build settings
   are read from `netlify.toml` automatically. Deploy.
3. The site goes live with the 12 sample facilities and a visible
   "sample data" banner. This lets you see and share the product immediately.
4. Canonical URLs and the sitemap configure themselves: `build_site.py` reads
   Netlify's `URL` environment variable at build time, and Netlify updates that
   automatically when you attach a custom domain (Porkbun, same flow as Green
   Haven). No code change needed when the domain changes.
   The fallback in `BASE_URL` is only used for local/manual builds.

**If your repo has everything nested inside a subfolder** (e.g. `carecheck-bc/`),
set Netlify → Site configuration → Build & deploy → **Base directory** to that
folder name, and leave build command and publish directory blank — `netlify.toml`
inside the folder handles the rest.

### Step 1 — Import the real provincial registry (30–60 minutes)

1. Download the official CSV (free, no account):
   **BC Data Catalogue → "Child Care Map Data" → childcare_locations.csv**
   https://catalogue.data.gov.bc.ca/dataset/child-care-map-data
2. Put it in `data/` and run:
   ```
   python3 scripts/import_bc_csv.py data/childcare_locations.csv
   python3 scripts/build_site.py
   ```
   No terminal? This repo includes a `.devcontainer/` config: on the GitHub repo
   page, click **Code → Codespaces → Create codespace** and you get a full
   browser-based terminal with Python ready (free tier is plenty). Upload the
   CSV to `data/` there and run the commands above. Alternatively, attach the
   CSV in a Claude conversation and have it produce the updated
   `facilities.json` for you to commit through the GitHub web editor.
3. The import filters to Metro Vancouver by default (edit `INCLUDE_CITIES` in
   the script to change scope). If the government renamed CSV columns, the script
   tells you exactly which field it couldn't find; add the real column name to
   `COLUMN_ALIASES`.
4. Commit + push. The sample banner disappears automatically
   (`meta.sample_data` flips to `false`). You now have thousands of real,
   indexable facility pages.

### Step 2 — Wire up inspection scrapers (the real work: one focused session)

The scrapers in `scripts/scrape_vch.py` and `scripts/scrape_fraser.py` handle
robots.txt compliance, rate limiting (3s/request), and caching already. What
they need from you is one pass against the live sites:

1. Open each health authority's inspection report database in your browser:
   - VCH: https://www.vch.ca/en/child-care-facility-inspections
   - Fraser: https://www.fraserhealth.ca/health-topics-a-to-z/school-health/kindergarten-readiness/child-care
2. **Check their robots.txt and terms of use first.** The scraper checks
   robots.txt automatically and refuses disallowed paths, but read the site
   terms yourself too. If scraping is prohibited, don't — fall back to the
   manual path in Step 2b.
3. Find the listing URL pattern (or, better, a JSON API in DevTools → Network)
   and fill in `LISTING_URLS`.
4. View-source one listing page and one report page, paste the HTML into
   Claude, and ask it to fix the regexes in `parse_listing()` / `parse_report()`.
5. Run each scraper, then rebuild:
   ```
   python3 scripts/scrape_vch.py
   python3 scripts/scrape_fraser.py
   python3 scripts/build_site.py
   ```
6. Review `data/unmatched_*.json` — facilities whose inspection-site name didn't
   match the registry name. Fix the important ones by hand in `facilities.json`.

**Step 2b — manual fallback (if scraping is disallowed):** start with just the
facilities people actually search for. Each week, look up the ~20 most-viewed
facilities on the HA sites and paste the reports into a Claude chat to convert
into the JSON inspection format. Slower, but 100% compliant and still more
useful than anything else online.

### Step 3 — Turn on the weekly auto-refresh

`.github/workflows/refresh-data.yml` runs every Monday: scrapes new reports,
verifies the build, commits, and your Netlify deploy fires automatically. It's
inert until the scrapers are configured, so it's safe to leave enabled from day one.

### Step 4 — SEO launch checklist

- [ ] Set final domain in `BASE_URL` (build_site.py) — sitemap + canonicals depend on it
- [ ] Google Search Console: verify the domain, submit `/sitemap.xml`
- [ ] Bing Webmaster Tools: same (it's 2 minutes and nobody bothers)
- [ ] Confirm the claim form works: submit a test on `/claim/`, check
      Netlify → Forms. Wire notifications to Make/Gmail exactly like the
      Green Haven lead flow.
- [ ] Post the site in 2–3 Metro Vancouver parenting Facebook groups, framed as
      a free tool, not a business ("I built a free site that puts all the
      daycare inspection reports in one place"). That plus SEO is the entire
      launch plan.

### Step 5 — Monetization (only after traffic exists)

Do nothing paid until Search Console shows real impressions for facility-name
queries. Then, in order of least-effort:
1. Featured placement for claimed listings (providers pay to rank first in
   their city — Stripe payment link, no calls).
2. "Openings available" badge as part of the paid tier — the thing parents
   actually filter for.
3. Only much later: parent-side premium reports. Don't start here; supply-side
   money is simpler and doesn't paywall safety data (which would poison the
   SEO + trust flywheel).

---

## Everyday commands

```
python3 scripts/build_site.py                                # rebuild site → dist/
python3 scripts/import_bc_csv.py data/childcare_locations.csv # refresh registry
python3 scripts/scrape_vch.py && python3 scripts/scrape_fraser.py
```

Local preview: `cd dist && python3 -m http.server 8000` → http://localhost:8000

## Data model

`data/facilities.json`:
```json
{
  "meta": { "sample_data": false, "last_updated": "YYYY-MM-DD", "sources": [] },
  "facilities": [{
    "id": "…", "slug": "…", "name": "…", "care_type": "…",
    "address": "…", "city": "…", "postal": "…",
    "health_authority": "…", "capacity": 7, "ages": "…",
    "phone": "", "website": "",
    "inspections": [{
      "date": "YYYY-MM-DD", "type": "Routine|Follow-up",
      "status": "compliant|followup",
      "infractions": [{ "category": "…", "note": "…" }],
      "report_url": ""
    }]
  }]
}
```

## Legal & ethics notes (read once, seriously)

- Licensing and inspection data is public information published by government
  bodies; republishing facts is fine. Still: keep the disclaimer footer, never
  editorialize a facility as "unsafe," and present infractions verbatim-factual.
- The scraper obeys robots.txt and rate-limits itself. Don't remove that.
- The site deliberately does NOT rank or score facilities — the province
  explicitly doesn't, and inventing a score creates both liability and
  unfairness. Chips only reflect what the latest report literally says.
- Honor takedown/correction requests from providers fast (the claim form is
  the channel). Accuracy complaints are also your best data-quality signal.
