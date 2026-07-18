#!/usr/bin/env python3
"""
Shared utilities for the health-authority inspection scrapers.

Design principles:
- CHECK robots.txt before every host and obey it. If a path is disallowed,
  we skip it and tell you — do not work around this.
- Rate limit: minimum 3 seconds between requests to the same host.
- Cache every fetched page to data/cache/ so re-runs don't re-hit the site.
- Identify honestly via User-Agent with a contact address.

Standard library only (urllib), so it runs anywhere Python runs.
"""

import hashlib
import json
import re
import time
import urllib.request
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache"
DATA = ROOT / "data" / "facilities.json"

# Put a real contact email/URL here before running — it's basic scraping etiquette
# and gives site operators a way to reach you instead of blocking you.
USER_AGENT = "CareCheckBC-DataBot/0.1 (public child care data aggregation; contact: you@example.com)"

MIN_DELAY_SECONDS = 3.0
_last_request: dict = {}
_robots_cache: dict = {}


def robots_allows(url: str) -> bool:
    """Check robots.txt for the URL's host. Fail closed on parse errors? No —
    convention is fail-open if robots.txt is unreachable, but we log it."""
    host = urlparse(url).scheme + "://" + urlparse(url).netloc
    if host not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(host + "/robots.txt")
        try:
            rp.read()
            _robots_cache[host] = rp
        except Exception as e:
            print(f"  robots.txt unreachable for {host} ({e}); proceeding cautiously")
            _robots_cache[host] = None
    rp = _robots_cache[host]
    if rp is None:
        return True
    allowed = rp.can_fetch(USER_AGENT, url)
    if not allowed:
        print(f"  BLOCKED by robots.txt, skipping: {url}")
    return allowed


def fetch(url: str, *, use_cache: bool = True) -> str:
    """Polite fetch: robots-checked, rate-limited, cached. Returns '' on failure."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".html")
    if use_cache and cache_file.exists():
        return cache_file.read_text(encoding="utf-8", errors="replace")

    if not robots_allows(url):
        return ""

    host = urlparse(url).netloc
    elapsed = time.time() - _last_request.get(host, 0)
    if elapsed < MIN_DELAY_SECONDS:
        time.sleep(MIN_DELAY_SECONDS - elapsed)

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  fetch failed: {url} ({e})")
        return ""
    finally:
        _last_request[host] = time.time()

    cache_file.write_text(body, encoding="utf-8")
    return body


# ---------------------------------------------------------------- matching

def _norm_name(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\b(ltd|inc|society|the|a|an|of|and|&)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def attach_inspections(scraped: list, authority_name: str) -> None:
    """
    Merge scraped inspection records into data/facilities.json.

    `scraped` is a list of dicts:
      {
        "facility_name": str,        # name as it appears on the HA site
        "city": str,                 # optional, improves matching
        "inspections": [ {date, type, status, infractions, report_url} ]
      }

    Matching strategy: normalized-name exact match first, then
    normalized-name + city. Unmatched records are written to
    data/unmatched_<authority>.json for manual review — expect some; facility
    names on inspection sites don't always match the registry exactly.
    """
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    facilities = payload["facilities"]

    by_name = {}
    for f in facilities:
        by_name.setdefault(_norm_name(f["name"]), []).append(f)

    matched, unmatched = 0, []
    for rec in scraped:
        key = _norm_name(rec["facility_name"])
        candidates = by_name.get(key, [])
        if len(candidates) > 1 and rec.get("city"):
            candidates = [c for c in candidates
                          if c["city"].lower() == rec["city"].lower()] or candidates
        if candidates:
            fac = candidates[0]
            existing_dates = {(i.get("date"), i.get("type")) for i in fac["inspections"]}
            for ins in rec["inspections"]:
                if (ins.get("date"), ins.get("type")) not in existing_dates:
                    fac["inspections"].append(ins)
            matched += 1
        else:
            unmatched.append(rec)

    payload["meta"]["sample_data"] = False
    DATA.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    slug = re.sub(r"[^a-z0-9]+", "_", authority_name.lower()).strip("_")
    if unmatched:
        out = ROOT / "data" / f"unmatched_{slug}.json"
        out.write_text(json.dumps(unmatched, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{authority_name}: matched {matched}, unmatched {len(unmatched)} "
              f"(review {out.name})")
    else:
        print(f"{authority_name}: matched {matched}, no unmatched records")
