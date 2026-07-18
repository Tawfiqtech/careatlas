#!/usr/bin/env python3
"""
Import the official BC Child Care Map CSV into data/facilities.json.

STEP 1 — download the CSV (free, no account needed):
  BC Data Catalogue dataset: "Child Care Map Data"
  https://catalogue.data.gov.bc.ca/dataset/child-care-map-data
  Download childcare_locations.csv into the data/ folder.

STEP 2 — run:
  python3 scripts/import_bc_csv.py data/childcare_locations.csv

STEP 3 — rebuild the site:
  python3 scripts/build_site.py

Notes:
- This script REPLACES data/facilities.json but PRESERVES any inspections
  already attached to a facility (matched by name+postal), so re-running the
  import after scraping does not wipe inspection history.
- Column names in government CSVs occasionally change. The COLUMN_ALIASES
  map below tries several known variants for each field; if the script
  reports missing columns, open the CSV, check its header row, and add the
  actual column name to the right alias list.
"""

import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "facilities.json"

# Cities to include (Metro Vancouver MVP). Comparison is case-insensitive.
# Empty list = include everything in the CSV (all of BC).
INCLUDE_CITIES = [
    "Vancouver", "Burnaby", "Surrey", "Richmond", "Coquitlam", "Port Coquitlam",
    "Port Moody", "North Vancouver", "West Vancouver", "New Westminster",
    "Delta", "Langley", "Maple Ridge", "Pitt Meadows", "White Rock", "Anmore",
    "Belcarra", "Bowen Island", "Lions Bay", "Tsawwassen",
]

# For each field we need, a list of column-name candidates (checked
# case-insensitively, ignoring spaces/underscores).
COLUMN_ALIASES = {
    "name": ["NAME", "FACILITY_NAME", "SERVICE_NAME", "CHILD_CARE_NAME"],
    "address": ["ADDRESS_1", "ADDRESS", "STREET_ADDRESS", "PHYSICAL_ADDRESS"],
    "city": ["CITY", "MUNICIPALITY", "COMMUNITY"],
    "postal": ["POSTAL_CODE", "POSTAL", "ZIP"],
    "care_type": ["SERVICE_TYPE_CD", "SERVICE_TYPE", "FACILITY_TYPE", "TYPE_OF_CARE", "CARE_TYPE"],
    "capacity": ["OP_TOTAL_CAPACITY", "CAPACITY", "TOTAL_CAPACITY", "MAX_CAPACITY", "LICENSED_CAPACITY"],
    "phone": ["PHONE", "PHONE_NUMBER", "CONTACT_PHONE"],
    "website": ["WEBSITE", "WEB_SITE", "URL"],
    "health_authority": ["HA_NAME", "HEALTH_AUTHORITY", "REGIONAL_HEALTH_AUTHORITY", "HLTH_AUTH"],
    "ages": ["AGE_GROUP", "AGES", "AGE_RANGE"],
}


def norm(s: str) -> str:
    return re.sub(r"[\s_]+", "", (s or "").strip().lower())


def build_column_map(header: list) -> dict:
    lookup = {norm(h): h for h in header}
    colmap, missing = {}, []
    for field, candidates in COLUMN_ALIASES.items():
        for cand in candidates:
            if norm(cand) in lookup:
                colmap[field] = lookup[norm(cand)]
                break
        else:
            missing.append(field)
    if missing:
        print(f"NOTE: no column found for: {', '.join(missing)}")
        print("Open the CSV, check the header row, and add the real column name")
        print("to COLUMN_ALIASES in this script if the field matters to you.")
        print(f"CSV header was: {header}\n")
    required = {"name", "city"}
    if not required.issubset(colmap):
        sys.exit("FATAL: could not locate the facility name and/or city columns. "
                 "Fix COLUMN_ALIASES and re-run.")
    return colmap


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python3 scripts/import_bc_csv.py data/childcare_locations.csv")
    src = Path(sys.argv[1])
    if not src.exists():
        sys.exit(f"CSV not found: {src}")

    # Preserve inspections already scraped, keyed by (name, postal)
    existing_inspections = {}
    if OUT.exists():
        old = json.loads(OUT.read_text(encoding="utf-8"))
        for f in old.get("facilities", []):
            key = (norm(f.get("name", "")), norm(f.get("postal", "")))
            if f.get("inspections"):
                existing_inspections[key] = f["inspections"]

    include = {c.lower() for c in INCLUDE_CITIES}
    facilities, skipped = [], 0

    with open(src, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        colmap = build_column_map(reader.fieldnames or [])

        def get(row, field, default=""):
            col = colmap.get(field)
            return (row.get(col) or default).strip() if col else default

        for i, row in enumerate(reader):
            city = get(row, "city")
            if include and city.lower() not in include:
                skipped += 1
                continue
            name = get(row, "name")
            if not name:
                continue
            postal = get(row, "postal")
            cap_raw = get(row, "capacity")
            try:
                capacity = int(float(cap_raw)) if cap_raw else None
            except ValueError:
                capacity = None

            key = (norm(name), norm(postal))
            facilities.append({
                "id": f"bc-{i:05d}",
                "slug": slugify(f"{name}-{city}"),
                "name": name,
                "care_type": get(row, "care_type"),
                "address": get(row, "address"),
                "city": city.title() if city.isupper() else city,
                "postal": postal,
                "health_authority": get(row, "health_authority"),
                "capacity": capacity,
                "ages": get(row, "ages"),
                "phone": get(row, "phone"),
                "website": get(row, "website"),
                "inspections": existing_inspections.get(key, []),
            })

    payload = {
        "meta": {
            "sample_data": False,
            "last_updated": date.today().isoformat(),
            "sources": [
                "BC Data Catalogue — Child Care Map Data (childcare_locations.csv)",
                "Vancouver Coastal Health — Child Care Facility Inspection Reports",
                "Fraser Health — Child Care Facility Inspection Reports",
            ],
        },
        "facilities": facilities,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    kept_ins = sum(1 for f in facilities if f["inspections"])
    print(f"Imported {len(facilities)} facilities ({skipped} outside included cities skipped).")
    print(f"Preserved existing inspection history on {kept_ins} facilities.")
    print("Next: python3 scripts/build_site.py")


if __name__ == "__main__":
    main()
