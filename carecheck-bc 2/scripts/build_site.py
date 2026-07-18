#!/usr/bin/env python3
"""
CareCheck BC — static site generator.

Reads data/facilities.json and generates the full site into dist/:
  /                       home: search + stats + city grid
  /city/<slug>/           all facilities in a city
  /facility/<slug>/       facility profile + inspection ledger (the SEO pages)
  /claim/                 provider claim-your-listing form (Netlify Forms)
  /about-the-data/        methodology + sources page
  /search-index.json      client-side search index
  sitemap.xml, robots.txt, styles.css, search.js

Run:  python3 scripts/build_site.py
Deps: Python 3.8+ standard library only (works on Netlify's build image).
"""

import json
import re
import shutil
from datetime import date
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "facilities.json"
STATIC = ROOT / "static"
DIST = ROOT / "dist"

SITE_NAME = "CareCheck BC"
SITE_TAGLINE = "Licensed child care in Metro Vancouver, with the inspection record attached."
# Set this to your real domain once connected on Netlify (no trailing slash).
BASE_URL = os.environ.get("URL", "https://careatlas.netlify.app").rstrip("/")


# ---------------------------------------------------------------- helpers

def slugify(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return text.strip("-")


def latest_inspection(fac: dict):
    ins = sorted(fac.get("inspections", []), key=lambda i: i.get("date", ""), reverse=True)
    return ins[0] if ins else None


def facility_stamp(fac: dict) -> str:
    """Status chip based on the most recent inspection."""
    latest = latest_inspection(fac)
    if latest is None:
        return '<span class="stamp stamp-none">No reports yet</span>'
    if latest.get("status") == "followup":
        return '<span class="stamp stamp-flag">Follow-up required</span>'
    return '<span class="stamp stamp-ok">Compliant</span>'


def fmt_date(iso: str) -> str:
    try:
        y, m, d = iso.split("-")
        months = ["", "January", "February", "March", "April", "May", "June", "July",
                  "August", "September", "October", "November", "December"]
        return f"{months[int(m)]} {int(d)}, {y}"
    except (ValueError, IndexError):
        return iso


# ---------------------------------------------------------------- layout

def page(title: str, body: str, *, description: str, canonical_path: str,
         sample_data: bool, extra_head: str = "") -> str:
    banner = (
        '<div class="sample-banner">You are viewing sample demonstration data. '
        'Real provincial data has not been imported yet.</div>'
        if sample_data else ""
    )
    year = date.today().year
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(description)}">
<link rel="canonical" href="{BASE_URL}{canonical_path}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@0,500;0,600;1,500&family=Public+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="stylesheet" href="/styles.css">
{extra_head}
</head>
<body>
{banner}
<header class="site-header">
  <div class="wrap">
    <a class="brand" href="/">Care<span class="brand-check">Check</span> BC</a>
    <nav class="site-nav">
      <a href="/about-the-data/">About the data</a>
      <a href="/claim/">For providers</a>
    </nav>
  </div>
</header>
{body}
<footer class="site-footer">
  <div class="wrap">
    <div class="foot-disclaimer">
      {SITE_NAME} republishes public licensing and inspection information for
      convenience. It is not affiliated with the Province of BC or any health
      authority. Always verify details with the facility and the
      <a href="https://www2.gov.bc.ca/gov/content/family-social-supports/caring-for-young-children">official provincial resources</a>
      before making care decisions.
    </div>
    <div>&copy; {year} {SITE_NAME} · <a href="/about-the-data/">Sources &amp; methodology</a></div>
  </div>
</footer>
</body>
</html>"""


# ---------------------------------------------------------------- pages

def build_home(facilities: list, cities: dict, meta: dict) -> str:
    total = len(facilities)
    total_spaces = sum(f.get("capacity") or 0 for f in facilities)
    inspected = sum(1 for f in facilities if f.get("inspections"))
    updated = fmt_date(meta.get("last_updated", ""))

    city_cards = "\n".join(
        f'<a class="city-card" href="/city/{slugify(c)}/">'
        f'<span class="city-name">{escape(c)}</span>'
        f'<span class="city-count">{len(fs)} facilities</span></a>'
        for c, fs in sorted(cities.items())
    )

    body = f"""
<section class="hero">
  <div class="wrap">
    <h1>Check any daycare's inspection record <em>before you visit.</em></h1>
    <p class="lede">Considering a specific daycare? Search its name to see its official
    health authority inspection history, licence details, and capacity — every licensed
    child care facility in Metro Vancouver, in one place.</p>
    <div class="search-box">
      <input id="search-input" type="search" placeholder="Type a daycare's name or your city&hellip;"
             aria-label="Search facilities" autocomplete="off">
      <div id="search-results" class="search-results" role="listbox"></div>
    </div>
    <div class="stats">
      <div class="stat"><div class="stat-num">{total:,}</div><div class="stat-label">Licensed facilities</div></div>
      <div class="stat"><div class="stat-num">{total_spaces:,}</div><div class="stat-label">Licensed spaces</div></div>
      <div class="stat"><div class="stat-num">{inspected:,}</div><div class="stat-label">With inspection reports</div></div>
      <div class="stat"><div class="stat-num">{escape(updated)}</div><div class="stat-label">Data updated</div></div>
    </div>
  </div>
</section>
<section class="section">
  <div class="wrap">
    <h2>Browse by city</h2>
    <p class="section-sub">Every facility listed is licensed under the Community Care and
    Assisted Living Act and inspected by its regional health authority.</p>
    <div class="city-grid">
{city_cards}
    </div>
  </div>
</section>
<script src="/search.js" defer></script>
"""
    return page(
        "Check a Daycare's Inspection Record — Metro Vancouver Child Care | CareCheck BC",
        body,
        description="Look up any licensed daycare in Metro Vancouver and read its official health authority inspection history before you tour. Free, covers every licensed facility.",
        canonical_path="/",
        sample_data=meta.get("sample_data", False),
    )


def build_city(city: str, facs: list, sample: bool) -> str:
    rows = "\n".join(
        f'<a class="facility-row" href="/facility/{f["slug"]}/">'
        f'<span class="f-name">{escape(f["name"])}</span>'
        f'{facility_stamp(f)}'
        f'<span class="f-meta">{escape(f.get("care_type", ""))} · {escape(f.get("address", ""))}'
        f' · Capacity {f.get("capacity") or "—"}</span>'
        f'</a>'
        for f in sorted(facs, key=lambda x: x["name"])
    )
    body = f"""
<div class="wrap">
  <nav class="crumbs"><a href="/">Home</a> / {escape(city)}</nav>
</div>
<section class="section">
  <div class="wrap">
    <h2>Licensed child care in {escape(city)}</h2>
    <p class="section-sub">{len(facs)} licensed facilities. The status chip reflects each
    facility's most recent health authority inspection.</p>
    <div class="facility-list">
{rows}
    </div>
  </div>
</section>
"""
    return page(
        f"Daycares in {city} with Inspection Records — All {len(facs)} Licensed Facilities",
        body,
        description=f"Every licensed daycare and child care facility in {city}, BC with its health authority inspection status. Check a facility's record before you tour.",
        canonical_path=f"/city/{slugify(city)}/",
        sample_data=sample,
    )


def build_facility(f: dict, sample: bool) -> str:
    inspections = sorted(f.get("inspections", []), key=lambda i: i.get("date", ""), reverse=True)

    entries = []
    for ins in inspections:
        flagged = ins.get("status") == "followup"
        infractions = ins.get("infractions", [])
        if infractions:
            inf_html = '<div class="infraction-list">' + "".join(
                f'<div class="infraction"><span class="inf-cat">{escape(i.get("category", "Requirement"))}</span>'
                f'{escape(i.get("note", ""))}</div>'
                for i in infractions
            ) + "</div>"
        else:
            inf_html = '<p class="le-clear">No infractions recorded.</p>'
        report = (
            f'<a class="le-report-link" href="{escape(ins["report_url"])}" rel="nofollow">'
            f'View official report</a>'
            if ins.get("report_url") else ""
        )
        stamp = ('<span class="stamp stamp-flag">Follow-up required</span>' if flagged
                 else '<span class="stamp stamp-ok">Compliant</span>')
        entries.append(f"""
      <div class="ledger-entry{' flagged' if flagged else ''}">
        <div class="le-head">
          <span class="le-date">{escape(fmt_date(ins.get("date", "")))}</span>
          <span class="le-type">{escape(ins.get("type", "Inspection"))} inspection</span>
          {stamp}
        </div>
        {inf_html}
        {report}
      </div>""")

    ledger = (
        f'<div class="ledger-entries">{"".join(entries)}</div>'
        if entries else
        '<p class="le-clear">No inspection reports on file yet for this facility.</p>'
    )

    body = f"""
<div class="wrap">
  <nav class="crumbs"><a href="/">Home</a> /
    <a href="/city/{slugify(f["city"])}/">{escape(f["city"])}</a> / {escape(f["name"])}</nav>
</div>
<section class="facility-head">
  <div class="wrap">
    <h1>{escape(f["name"])}</h1>
    <p class="f-sub">{escape(f.get("care_type", ""))} · {escape(f.get("address", ""))},
      {escape(f["city"])} {escape(f.get("postal", ""))}</p>
    <div class="licence-strip">
      <div class="licence-cell"><div class="lc-label">Licence status</div><div class="lc-value">Licensed</div></div>
      <div class="licence-cell"><div class="lc-label">Care type</div><div class="lc-value">{escape(f.get("care_type", "—"))}</div></div>
      <div class="licence-cell"><div class="lc-label">Capacity</div><div class="lc-value">{f.get("capacity") or "—"} children</div></div>
      <div class="licence-cell"><div class="lc-label">Ages</div><div class="lc-value">{escape(f.get("ages") or "—")}</div></div>
      <div class="licence-cell"><div class="lc-label">Health authority</div><div class="lc-value">{escape(f.get("health_authority", "—"))}</div></div>
    </div>
  </div>
</section>
<section class="wrap ledger">
  <h2>Inspection ledger</h2>
  <p class="ledger-sub">Routine and follow-up inspections conducted by
  {escape(f.get("health_authority", "the regional health authority"))}, most recent first.</p>
  {ledger}
  <div class="claim-cta">
    <p><strong>Run this facility?</strong> Claim your free listing to add your phone number,
    website, program details, and current openings.</p>
    <a class="btn" href="/claim/?facility={escape(f["slug"])}">Claim this listing</a>
  </div>
</section>
"""
    latest = latest_inspection(f)
    desc = (
        f"Before you tour {f['name']} in {f['city']}, read its official health authority "
        f"inspection history. Licensed {f.get('care_type', 'child care')}, capacity "
        f"{f.get('capacity') or '—'}. "
        + (f"Most recent inspection: {fmt_date(latest['date'])}." if latest else "Licence details on record.")
    )
    schema = {
        "@context": "https://schema.org",
        "@type": "ChildCare",
        "name": f["name"],
        "address": {
            "@type": "PostalAddress",
            "streetAddress": f.get("address", ""),
            "addressLocality": f["city"],
            "addressRegion": "BC",
            "postalCode": f.get("postal", ""),
            "addressCountry": "CA",
        },
        "url": f"{BASE_URL}/facility/{f['slug']}/",
    }
    extra_head = ('<script type="application/ld+json">'
                  + json.dumps(schema, ensure_ascii=False)
                  + "</script>")
    return page(
        f"{f['name']} ({f['city']}) — Inspection History & Licence Record",
        body,
        description=desc,
        canonical_path=f"/facility/{f['slug']}/",
        sample_data=sample,
        extra_head=extra_head,
    )


def build_claim(sample: bool) -> str:
    body = f"""
<section class="section">
  <div class="wrap">
    <h2>Claim your facility listing</h2>
    <p class="section-sub">Free for licensed providers. Once verified, you can add your
    contact details, website, program description, and current openings to your listing.</p>
    <div class="form-card">
      <form name="claim-listing" method="POST" data-netlify="true" netlify-honeypot="bot-field" action="/claim/thanks/">
        <input type="hidden" name="form-name" value="claim-listing">
        <p style="display:none"><label>Leave this empty: <input name="bot-field"></label></p>
        <div class="form-field">
          <label for="facility">Facility name</label>
          <input id="facility" name="facility" type="text" required>
        </div>
        <div class="form-field">
          <label for="name">Your name</label>
          <input id="name" name="name" type="text" required>
        </div>
        <div class="form-field">
          <label for="email">Email</label>
          <input id="email" name="email" type="email" required>
        </div>
        <div class="form-field">
          <label for="phone">Phone (optional)</label>
          <input id="phone" name="phone" type="tel">
        </div>
        <div class="form-field">
          <label for="message">Anything you'd like updated on your listing?</label>
          <textarea id="message" name="message" rows="4"></textarea>
        </div>
        <button class="btn" type="submit">Submit claim</button>
        <p class="form-note">We verify claims against the licence record before making
        changes, usually within 2 business days.</p>
      </form>
    </div>
  </div>
</section>
<script>
  // Pre-fill facility name from ?facility= slug
  (function () {{
    var p = new URLSearchParams(window.location.search).get("facility");
    if (p) document.getElementById("facility").value = p.replace(/-/g, " ");
  }})();
</script>
"""
    return page(
        f"Claim your listing — {SITE_NAME}",
        body,
        description="Licensed child care providers: claim your free CareCheck BC listing to add contact details, program information, and current openings.",
        canonical_path="/claim/",
        sample_data=sample,
    )


def build_claim_thanks(sample: bool) -> str:
    body = """
<section class="section">
  <div class="wrap prose">
    <h2>Claim received</h2>
    <p>Thanks — we've got your claim. We verify every claim against the provincial licence
    record before making changes, usually within 2 business days. We'll email you once
    your listing is updated.</p>
    <p><a href="/">Back to search</a></p>
  </div>
</section>
"""
    return page(
        f"Claim received — {SITE_NAME}",
        body,
        description="Your listing claim has been received.",
        canonical_path="/claim/thanks/",
        sample_data=sample,
    )


def build_about(meta: dict) -> str:
    sources = "".join(f"<p>&bull; {escape(s)}</p>" for s in meta.get("sources", []))
    body = f"""
<section class="section">
  <div class="wrap prose">
    <h2>About the data</h2>
    <p>{SITE_NAME} combines two kinds of public information: the provincial registry of
    licensed child care locations, and routine inspection reports published by regional
    health authorities. Neither is hard to find on its own — but they live on separate
    government websites, in different formats, and no official tool joins them together.
    That's the whole point of this site.</p>
    <h2>Sources</h2>
    {sources}
    <h2>What "Compliant" and "Follow-up required" mean</h2>
    <p>Health authorities inspect every licensed facility at least once a year. When an
    inspection finds a requirement not being met, the licensing officer records it and
    schedules a follow-up. A "Follow-up required" chip on this site means the most recent
    inspection on file recorded one or more infractions; it does not mean a facility is
    unsafe, and facilities are not ranked or rated by the province. Read the specific
    infractions — context matters far more than the chip.</p>
    <h2>What this site is not</h2>
    <p>This is an independent convenience tool, not a government service. Records here can
    lag the official sources, and inspection reports summarized here omit detail contained
    in the originals. Always confirm licence status and inspection history with the
    facility's health authority before making a care decision.</p>
    <h2>Corrections</h2>
    <p>Run a facility and see something wrong? <a href="/claim/">Claim your listing</a>
    and tell us — corrections are prioritized.</p>
  </div>
</section>
"""
    return page(
        f"About the data — {SITE_NAME}",
        body,
        description="Where CareCheck BC's licensing and inspection data comes from, how often it updates, and what its limitations are.",
        canonical_path="/about-the-data/",
        sample_data=meta.get("sample_data", False),
    )


def build_404(sample: bool) -> str:
    body = """
<section class="section">
  <div class="wrap prose">
    <h2>Page not found</h2>
    <p>That listing may have moved or the facility may no longer be licensed.</p>
    <p><a href="/">Search all facilities</a></p>
  </div>
</section>
"""
    return page(
        f"Page not found — {SITE_NAME}",
        body,
        description="Page not found.",
        canonical_path="/404.html",
        sample_data=sample,
    )


# ---------------------------------------------------------------- main

def main():
    with open(DATA, encoding="utf-8") as fh:
        payload = json.load(fh)

    meta = payload.get("meta", {})
    facilities = payload["facilities"]
    sample = meta.get("sample_data", False)

    # Ensure slugs exist and are unique
    seen = set()
    for f in facilities:
        if not f.get("slug"):
            f["slug"] = slugify(f"{f['name']}-{f['city']}")
        base = f["slug"]
        n = 2
        while f["slug"] in seen:
            f["slug"] = f"{base}-{n}"
            n += 1
        seen.add(f["slug"])

    cities = {}
    for f in facilities:
        cities.setdefault(f["city"], []).append(f)

    # Fresh dist/
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    # Static assets
    shutil.copy(STATIC / "styles.css", DIST / "styles.css")
    shutil.copy(STATIC / "search.js", DIST / "search.js")
    shutil.copy(STATIC / "favicon.svg", DIST / "favicon.svg")

    # Pages
    (DIST / "index.html").write_text(build_home(facilities, cities, meta), encoding="utf-8")

    for city, facs in cities.items():
        d = DIST / "city" / slugify(city)
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(build_city(city, facs, sample), encoding="utf-8")

    for f in facilities:
        d = DIST / "facility" / f["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(build_facility(f, sample), encoding="utf-8")

    d = DIST / "claim"
    d.mkdir(parents=True)
    (d / "index.html").write_text(build_claim(sample), encoding="utf-8")
    (d / "thanks").mkdir()
    (d / "thanks" / "index.html").write_text(build_claim_thanks(sample), encoding="utf-8")

    d = DIST / "about-the-data"
    d.mkdir(parents=True)
    (d / "index.html").write_text(build_about(meta), encoding="utf-8")

    (DIST / "404.html").write_text(build_404(sample), encoding="utf-8")

    # Search index (compact keys: n=name, c=city, t=type, s=slug, h=haystack)
    search_index = [
        {
            "n": f["name"],
            "c": f["city"],
            "t": f.get("care_type", ""),
            "s": f["slug"],
            "h": f"{f['name']} {f['city']} {f.get('care_type', '')} {f.get('address', '')}".lower(),
        }
        for f in facilities
    ]
    (DIST / "search-index.json").write_text(
        json.dumps(search_index, ensure_ascii=False), encoding="utf-8"
    )

    # Sitemap + robots
    urls = ["/", "/about-the-data/", "/claim/"]
    urls += [f"/city/{slugify(c)}/" for c in cities]
    urls += [f"/facility/{f['slug']}/" for f in facilities]
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(f"  <url><loc>{BASE_URL}{u}</loc></url>" for u in urls)
        + "\n</urlset>\n"
    )
    (DIST / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    (DIST / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n", encoding="utf-8"
    )

    print(f"Built {len(facilities)} facility pages, {len(cities)} city pages -> {DIST}")


if __name__ == "__main__":
    main()
