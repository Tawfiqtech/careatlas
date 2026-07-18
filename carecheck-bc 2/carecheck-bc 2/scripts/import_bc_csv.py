#!/usr/bin/env python3
"""
Import the official BC Child Care Map CSV into data/facilities.json.

Written against the REAL schema of childcare_locations.csv (confirmed July 2026):
  FAC_PARTY_ID, SERVICE_TYPE_CD, NAME, ADDRESS_1, ADDRESS_2, CITY, POSTAL_CODE,
  LATITUDE, LONGITUDE, PHONE, WEBSITE, EMAIL, OP_*_YN, SRVC_*_YN, LANG_*_YN,
  PROVIDE_CD_MEALS, PROVIDE_CD_PICKUP, PRESCHOOL_*_YN, ABORIGINAL_PROGRAMMING_YN,
  ACCOMMODATE_SPECIAL_NEEDS, ECE_CERTIFICATION_YN, ELF_PROGRAMMING_YN,
  VACANCY_*, VACANCY_LAST_UPDATE, HA_FAC_INSPEC_RPTS, IS_INCOMPLETE_IND,
  IS_CCFRI_AUTH, IS_DUPLICATE

Note: this dataset has NO capacity column. It DOES have vacancy flags (updated
daily) and a per-facility link to its health authority inspection system.

STEP 1 — download the CSV:
  https://catalogue.data.gov.bc.ca/dataset/child-care-map-data
  (resource: childcare_locations, ~1.3 MB) into data/

STEP 2 — run:
  python3 scripts/import_bc_csv.py data/childcare_locations.csv

STEP 3 — rebuild:
  python3 scripts/build_site.py

Re-running preserves any inspection history already scraped (matched on
facility id, then name+postal), so imports never wipe scraper output.

Data licence: Open Government Licence – British Columbia. Attribution is a
condition of the licence and is rendered in the site footer by build_site.py.
"""

import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "facilities.json"

# Metro Vancouver MVP scope. Empty list = all of BC.
INCLUDE_CITIES = [
    "Vancouver", "Burnaby", "Surrey", "Richmond", "Coquitlam", "Port Coquitlam",
    "Port Moody", "North Vancouver", "West Vancouver", "New Westminster",
    "Delta", "Langley", "Maple Ridge", "Pitt Meadows", "White Rock", "Anmore",
    "Belcarra", "Bowen Island", "Lions Bay", "Tsawwassen",
]

# Services offered: CSV flag -> human label -> matching vacancy column
SERVICE_FLAGS = [
    ("SRVC_UNDER36_YN", "Infant & toddler (under 36 months)", "VACANCY_SRVC_UNDER36"),
    ("SRVC_30MOS_5YRS_YN", "30 months to school age", "VACANCY_SRVC_30MOS_5YRS"),
    ("SRVC_LICPRE_YN", "Licensed preschool", "VACANCY_SRVC_LICPRE"),
    ("SRVC_OOS_KINDER_YN", "Before & after school (kindergarten)", None),
    ("SRVC_OOS_GR1_AGE12_YN", "Before & after school (grades 1-7)", "VACANCY_SRVC_OOS_GR1_AGE12"),
]

LANGUAGE_FLAGS = [
    ("LANG_CANTONESE_YN", "Cantonese"),
    ("LANG_PUNJABI_YN", "Punjabi"),
    ("LANG_MANDARIN_YN", "Mandarin"),
    ("LANG_FRENCH_YN", "French"),
    ("LANG_SPANISH_YN", "Spanish"),
    ("LANG_OTHER_YN", "Other languages"),
]

FEATURE_FLAGS = [
    ("ACCOMMODATE_SPECIAL_NEEDS", "Accommodates special needs"),
    ("ECE_CERTIFICATION_YN", "ECE certified staff"),
    ("ABORIGINAL_PROGRAMMING_YN", "Indigenous programming"),
    ("ELF_PROGRAMMING_YN", "Early learning framework"),
    ("OP_WEEKEND_YN", "Open weekends"),
    ("OP_OVERNIGHT_YN", "Overnight care"),
    ("OP_EXT_WEEKDAY_BEFORE6AM_YN", "Opens before 6am"),
    ("OP_EXT_WEEKDAY_AFTER7PM_YN", "Open after 7pm"),
]

# Health authority inferred from the inspection-reports URL published per row.
HA_BY_URL = [
    ("inspections.vcha.ca", "Vancouver Coastal Health"),
    ("vch.ca", "Vancouver Coastal Health"),
    ("healthspace.ca/fha", "Fraser Health"),
    ("clients/viha", "Island Health"),
    ("clients/nha", "Northern Health"),
    ("northernhealth", "Northern Health"),
    ("interiorhealth", "Interior Health"),
]

# ~40% of rows ship with an EMPTY HA_FAC_INSPEC_RPTS. Health authority
# boundaries are geographic, so city is a reliable fallback within Metro Van.
CITY_TO_HA = {
    "vancouver": "Vancouver Coastal Health",
    "richmond": "Vancouver Coastal Health",
    "north vancouver": "Vancouver Coastal Health",
    "west vancouver": "Vancouver Coastal Health",
    "bowen island": "Vancouver Coastal Health",
    "lions bay": "Vancouver Coastal Health",
    "burnaby": "Fraser Health",
    "new westminster": "Fraser Health",
    "coquitlam": "Fraser Health",
    "port coquitlam": "Fraser Health",
    "port moody": "Fraser Health",
    "anmore": "Fraser Health",
    "belcarra": "Fraser Health",
    "surrey": "Fraser Health",
    "delta": "Fraser Health",
    "tsawwassen": "Fraser Health",
    "white rock": "Fraser Health",
    "langley": "Fraser Health",
    "maple ridge": "Fraser Health",
    "pitt meadows": "Fraser Health",
}

# Where to send someone when the province publishes no per-facility link.
HA_FALLBACK_URL = {
    "Vancouver Coastal Health": "https://inspections.vcha.ca/ChildCare/Table",
    "Fraser Health": "http://www.healthspace.ca/fha/childcare",
}


def yes(v: str) -> bool:
    return (v or "").strip().upper() == "Y"


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def norm(s: str) -> str:
    return re.sub(r"[\s_]+", "", (s or "").strip().lower())


def health_authority(url: str, city: str = "") -> str:
    u = (url or "").lower()
    for needle, name in HA_BY_URL:
        if needle in u:
            return name
    return CITY_TO_HA.get((city or "").strip().lower(), "")


def title_if_shouty(s: str) -> str:
    """Rows arrive inconsistently cased; normalize only all-caps / all-lower."""
    if not s:
        return s
    if s.isupper() or s.islower():
        return s.title()
    return s


def parse_vacancy_date(raw: str) -> str:
    """'2026/07/14' -> '2026-07-14'."""
    m = re.match(r"(\d{4})[/-](\d{2})[/-](\d{2})", (raw or "").strip())
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python3 scripts/import_bc_csv.py data/childcare_locations.csv")
    src = Path(sys.argv[1])
    if not src.exists():
        sys.exit(f"CSV not found: {src}")

    # Preserve scraped inspection history across re-imports
    prev_by_id, prev_by_np = {}, {}
    if OUT.exists():
        old = json.loads(OUT.read_text(encoding="utf-8"))
        for f in old.get("facilities", []):
            if f.get("inspections"):
                if f.get("fac_party_id"):
                    prev_by_id[f["fac_party_id"]] = f["inspections"]
                prev_by_np[(norm(f.get("name", "")), norm(f.get("postal", "")))] = f["inspections"]

    include = {c.lower() for c in INCLUDE_CITIES}
    facilities = []
    skipped_city = skipped_dupe = 0
    seen_slugs = set()

    with open(src, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        if "NAME" not in header or "CITY" not in header:
            sys.exit(f"FATAL: unexpected CSV header — no NAME/CITY column.\nGot: {header}")

        for row in reader:
            if yes(row.get("IS_DUPLICATE")):
                skipped_dupe += 1
                continue

            city = (row.get("CITY") or "").strip()
            if include and city.lower() not in include:
                skipped_city += 1
                continue

            name = title_if_shouty((row.get("NAME") or "").strip())
            if not name:
                continue

            services, vacancies = [], []
            for flag, label, vac_col in SERVICE_FLAGS:
                if yes(row.get(flag)):
                    services.append(label)
                    if vac_col and yes(row.get(vac_col)):
                        vacancies.append(label)

            languages = [label for flag, label in LANGUAGE_FLAGS if yes(row.get(flag))]
            features = [label for flag, label in FEATURE_FLAGS if yes(row.get(flag))]

            address = " ".join(
                p for p in [(row.get("ADDRESS_1") or "").strip(),
                            (row.get("ADDRESS_2") or "").strip()] if p
            )
            postal = (row.get("POSTAL_CODE") or "").strip()
            fac_id = (row.get("FAC_PARTY_ID") or "").strip()
            inspect_url = (row.get("HA_FAC_INSPEC_RPTS") or "").strip()
            ha = health_authority(inspect_url, city)
            if not inspect_url:
                inspect_url = HA_FALLBACK_URL.get(ha, "")

            slug = slugify(f"{name}-{city}")
            base, n = slug, 2
            while slug in seen_slugs:
                slug = f"{base}-{n}"
                n += 1
            seen_slugs.add(slug)

            facilities.append({
                "id": f"bc-{fac_id}",
                "fac_party_id": fac_id,
                "slug": slug,
                "name": name,
                "care_type": (row.get("SERVICE_TYPE_CD") or "").strip(),
                "address": address,
                "city": title_if_shouty(city),
                "postal": postal,
                "lat": to_float(row.get("LATITUDE")),
                "lng": to_float(row.get("LONGITUDE")),
                "phone": (row.get("PHONE") or "").strip(),
                "website": (row.get("WEBSITE") or "").strip(),
                "email": (row.get("EMAIL") or "").strip(),
                "health_authority": ha,
                "inspection_url": inspect_url,
                "services": services,
                "ages": "; ".join(services),
                "vacancies": vacancies,
                "vacancy_updated": parse_vacancy_date(row.get("VACANCY_LAST_UPDATE")),
                "languages": languages,
                "features": features,
                "meals": (row.get("PROVIDE_CD_MEALS") or "").strip(),
                "ccfri": yes(row.get("IS_CCFRI_AUTH")),
                "incomplete": yes(row.get("IS_INCOMPLETE_IND")),
                "capacity": None,  # not published in this dataset
                "inspections": prev_by_id.get(fac_id)
                               or prev_by_np.get((norm(name), norm(postal)), []),
            })

    payload = {
        "meta": {
            "sample_data": False,
            "last_updated": date.today().isoformat(),
            "sources": [
                "BC Data Catalogue — Child Care Map Data (childcare_locations.csv), "
                "Open Government Licence – British Columbia",
                "Vancouver Coastal Health — Child Care Facility Inspection Reports",
                "Fraser Health — Child Care Facility Inspection Reports",
            ],
        },
        "facilities": facilities,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    with_vac = sum(1 for f in facilities if f["vacancies"])
    with_ins = sum(1 for f in facilities if f["inspections"])
    ha_counts = {}
    for f in facilities:
        k = f["health_authority"] or "(unknown)"
        ha_counts[k] = ha_counts.get(k, 0) + 1

    print(f"Imported {len(facilities)} facilities")
    print(f"  skipped: {skipped_city} outside included cities, {skipped_dupe} flagged duplicates")
    print(f"  reporting a vacancy: {with_vac}")
    print(f"  with inspection history preserved: {with_ins}")
    for ha, c in sorted(ha_counts.items(), key=lambda x: -x[1]):
        print(f"  {ha}: {c}")
    print("Next: python3 scripts/build_site.py")


if __name__ == "__main__":
    main()
