#!/usr/bin/env python3
"""
Scrape child care inspection reports — Fraser Health.

Fraser Health publishes routine + follow-up inspection reports through a searchable
database ("Inspection Reports website") covering 
Burnaby, Surrey, Coquitlam, Delta, Langley, and the rest of the Fraser region. Start here:
  https://www.fraserhealth.ca/health-topics-a-to-z/school-health/kindergarten-readiness/child-care

HOW TO USE THIS SCRIPT (honest version):
This is a working framework, not a finished scraper. I could not inspect the
live Fraser Health site while writing it, so the two things marked ADJUST below need
one pass of confirmation against the real pages:

  ADJUST 1 — LISTING_URLS: the actual URL(s) of the inspection report
             listing/search results. Open the Fraser Health inspection database in your
             browser, note the URL pattern (many HA report systems expose a
             plain paginated list or accept a query string), and paste it in.
  ADJUST 2 — the regexes in parse_listing() and parse_report(): open one
             listing page and one report page, View Source, and align the
             patterns with the real markup. The fastest way: paste the page
             source into Claude and ask for the corrected regexes.

If the report system turns out to be a JavaScript app with a JSON backend
(common), even better — open DevTools > Network, find the API call, and
point fetch() at that JSON endpoint instead; parsing gets trivial.

The polite-scraping layer (robots.txt, 3s rate limit, caching) is handled by
scrape_common.py and needs no changes.

Run:  python3 scripts/scrape_fraser.py
Then: python3 scripts/build_site.py
"""

import re

from scrape_common import fetch, attach_inspections

# ADJUST 1: real listing/search-results URL(s) for the Fraser Health inspection database.
LISTING_URLS = [
    # CONFIRMED via HA_FAC_INSPEC_RPTS column in the provincial CSV:
    "http://www.healthspace.ca/fha/childcare",
    # "https://inspections.vch.ca/ChildCare/Table?page=1",   # example shape only
]


def parse_listing(html: str) -> list:
    """
    Extract (facility_name, report_url) pairs from a listing page.
    ADJUST 2: align this regex with the real markup.
    """
    pattern = re.compile(
        r'<a[^>]+href="(?P<url>[^"]*(?:report|inspection)[^"]*)"[^>]*>(?P<name>[^<]{3,120})</a>',
        re.IGNORECASE,
    )
    out = []
    for m in pattern.finditer(html):
        out.append({"name": m.group("name").strip(), "url": m.group("url")})
    return out


def parse_report(html: str, report_url: str) -> dict:
    """
    Extract one inspection record from a report page.
    ADJUST 2: align these regexes with the real markup.
    """
    def grab(pat, default=""):
        m = re.search(pat, html, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else default

    date_raw = grab(r"inspection\s*date[:\s<>/a-z\"=]*(\d{4}-\d{2}-\d{2}|\w+ \d{1,2},? \d{4})")
    ins_type = grab(r"inspection\s*type[:\s<>/a-z\"=]*([A-Za-z\- ]{4,30})", "Routine")

    infractions = []
    for m in re.finditer(
        r'<td[^>]*>(?P<cat>[A-Za-z &/]+)</td>\s*<td[^>]*>(?P<note>[^<]{5,400})</td>',
        html,
    ):
        infractions.append({
            "category": m.group("cat").strip(),
            "note": m.group("note").strip(),
        })

    return {
        "date": normalize_date(date_raw),
        "type": ins_type.title(),
        "status": "followup" if infractions else "compliant",
        "infractions": infractions,
        "report_url": report_url,
    }


def normalize_date(raw: str) -> str:
    """Accepts '2026-03-11' or 'March 11, 2026' -> ISO."""
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    m = re.match(r"(\w+) (\d{1,2}),? (\d{4})", raw)
    if m:
        months = {mn.lower(): i for i, mn in enumerate(
            ["January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"], 1)}
        mon = months.get(m.group(1).lower())
        if mon:
            return f"{m.group(3)}-{mon:02d}-{int(m.group(2)):02d}"
    return raw


def main():
    if not LISTING_URLS:
        print("No LISTING_URLS configured yet.")
        print("Open the Fraser Health inspection database, find the listing URL pattern,")
        print("and add it to LISTING_URLS at the top of this script.")
        print("Start here: https://www.fraserhealth.ca/health-topics-a-to-z/school-health/kindergarten-readiness/child-care")
        return

    scraped = []
    for listing_url in LISTING_URLS:
        html = fetch(listing_url)
        if not html:
            continue
        entries = parse_listing(html)
        print(f"{listing_url}: {len(entries)} report links found")
        for entry in entries:
            report_html = fetch(entry["url"])
            if not report_html:
                continue
            record = parse_report(report_html, entry["url"])
            scraped.append({
                "facility_name": entry["name"],
                "city": "",
                "inspections": [record],
            })

    if scraped:
        attach_inspections(scraped, "Fraser Health")
    else:
        print("Nothing scraped — check LISTING_URLS and the parse patterns.")


if __name__ == "__main__":
    main()
