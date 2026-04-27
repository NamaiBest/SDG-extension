#!/usr/bin/env python3
"""
Stage 2a: OpenFDA / DailyMed Drug Label Extraction
Pulls 436 drug label records from the OpenFDA Drug Label API.
Conforms to the 12-field schema.
"""

import json
import os
import time
import requests

RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "raw_data")
OUT_FILE = os.path.join(RAW_DIR, "openfda_dailymed.json")

API = "https://api.fda.gov/drug/label.json"
TARGET = 436
PER_PAGE = 100  # max allowed by API

# Common OTC drug searches for home-remedy-relevant conditions
SEARCHES = [
    'indications_and_usage:"cough"',
    'indications_and_usage:"cold"',
    'indications_and_usage:"headache"',
    'indications_and_usage:"pain"',
    'indications_and_usage:"fever"',
    'indications_and_usage:"allergy"',
    'indications_and_usage:"digestive"',
    'indications_and_usage:"skin"',
    'indications_and_usage:"sleep"',
    'indications_and_usage:"nausea"',
    'indications_and_usage:"diarrhea"',
    'indications_and_usage:"constipation"',
    'indications_and_usage:"inflammation"',
    'indications_and_usage:"burn"',
    'indications_and_usage:"wound"',
    'indications_and_usage:"sore throat"',
    'indications_and_usage:"acne"',
    'indications_and_usage:"muscle"',
]


def clean_text(val):
    """Extract text from FDA's array-of-strings format."""
    if isinstance(val, list):
        return " ".join(val).strip()
    if isinstance(val, str):
        return val.strip()
    return ""


def make_record(item, idx):
    """Map an OpenFDA drug label to the 12-field schema."""
    indication = clean_text(item.get("indications_and_usage", ""))
    warnings = clean_text(item.get("warnings", ""))
    dosage = clean_text(item.get("dosage_and_administration", ""))
    active = clean_text(item.get("active_ingredient", ""))
    purpose = clean_text(item.get("purpose", ""))

    # Map fields
    brand = ""
    openfda = item.get("openfda", {})
    if openfda.get("brand_name"):
        brand = openfda["brand_name"][0]

    problem = indication[:500] if indication else purpose[:500]
    remedy_text = dosage[:500] if dosage else indication[:500]

    # Determine if doctor_consult should be flagged
    consult = any(
        kw in (warnings + indication).lower()
        for kw in ["consult a doctor", "seek medical", "call poison", "emergency"]
    )

    # Severity from warnings
    severity = "mild"
    if any(kw in warnings.lower() for kw in ["serious", "fatal", "emergency", "poison"]):
        severity = "severe"
    elif any(kw in warnings.lower() for kw in ["persistent", "chronic"]):
        severity = "moderate"

    return {
        "id": f"FDA_{idx:06d}",
        "problem": problem,
        "symptoms": indication[:300],
        "possible_causes": "",
        "remedy": f"{brand}: {remedy_text}" if brand else remedy_text,
        "ingredients": active[:300],
        "preparation": dosage[:300],
        "traditional_system": "Western/Pharmacological",
        "severity_level": severity,
        "doctor_consult": consult,
        "source": "openfda:drug_label",
        "completeness_score": 0.0,  # will be recomputed by merger
    }


def fetch_records():
    """Fetch drug labels from OpenFDA API."""
    records = []
    seen_ids = set()

    for search_q in SEARCHES:
        if len(records) >= TARGET:
            break
        skip = 0
        while len(records) < TARGET and skip < 500:
            params = {
                "search": search_q,
                "limit": PER_PAGE,
                "skip": skip,
            }
            try:
                resp = requests.get(API, params=params, timeout=15)
                if resp.status_code == 404:
                    break
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])
                if not results:
                    break

                for item in results:
                    item_id = item.get("id", str(len(records)))
                    if item_id in seen_ids:
                        continue
                    seen_ids.add(item_id)
                    rec = make_record(item, len(records) + 1)
                    if rec["problem"] and len(rec["problem"]) > 20:
                        records.append(rec)
                    if len(records) >= TARGET:
                        break

                skip += PER_PAGE
                time.sleep(0.3)  # rate limit: 240/min
            except requests.exceptions.RequestException as e:
                print(f"  ⚠ API error for '{search_q}': {e}")
                break

        print(f"  [{len(records)}/{TARGET}] after query: {search_q[:50]}")

    return records[:TARGET]


def main():
    print("🔬 Stage 2a: OpenFDA / DailyMed extraction")
    print(f"   Target: {TARGET} records")

    records = fetch_records()

    # Compute completeness scores
    fields = ["problem", "symptoms", "possible_causes", "remedy",
              "ingredients", "preparation", "severity_level"]
    for rec in records:
        filled = sum(1 for f in fields if rec.get(f))
        rec["completeness_score"] = round(filled / len(fields) * 100, 1)

    os.makedirs(RAW_DIR, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"✅ Wrote {len(records)} records to {OUT_FILE}")
    return records


if __name__ == "__main__":
    main()
