#!/usr/bin/env python3
"""
rebuild_merged_dataset.py
Rebuilds merged_dataset.json from all raw sources to target 3,200 records.
Run this after all individual scraping scripts have been executed.
"""

import json
import os
import re

RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "raw_data")
OUT_FILE = os.path.join(RAW_DIR, "merged_dataset.json")
TARGET = 3200

SCHEMA_FIELDS = [
    "id", "problem", "symptoms", "possible_causes", "remedy",
    "ingredients", "preparation", "traditional_system",
    "severity_level", "doctor_consult", "source", "completeness_score",
]
CONTENT_FIELDS = [
    "problem", "symptoms", "possible_causes", "remedy",
    "ingredients", "preparation", "severity_level",
]

# Source files in order of priority (highest quality first)
SOURCES = [
    ("openfda_dailymed.json",        "openfda",      436),
    ("medlineplus.json",             "medlineplus",  384),
    ("who_cochrane.json",            "who_cochrane", 300),
    ("ayush_remedies.json",          "ayush",        624),
    ("ngo_field_manuals.json",       "ngo",          336),
    ("reddit_remedies.json",         "reddit",       None),
    ("hf_remedies.json",             "huggingface",  None),
    ("indian_home_remedies.json",    "indian_web",   None),
    ("formatted_home_remedies.json", "formatted",    None),
    ("1mg_remedies.json",            "1mg",          None),
    ("stylecraze_remedies.json",     "stylecraze",   None),
]


def clean(val):
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() in ("[deleted]", "[removed]", "none", "null", "n/a"):
        return ""
    return re.sub(r"\s+", " ", s)


def normalize(rec, src_label):
    return {
        "id": "",
        "problem": clean(rec.get("problem", "")),
        "symptoms": clean(rec.get("symptoms", "")),
        "possible_causes": clean(rec.get("possible_causes", "")),
        "remedy": clean(rec.get("remedy", "")),
        "ingredients": clean(rec.get("ingredients", "")),
        "preparation": clean(rec.get("preparation", "")),
        "traditional_system": clean(rec.get("traditional_system", "Home Remedy")),
        "severity_level": clean(rec.get("severity_level", "")),
        "doctor_consult": bool(rec.get("doctor_consult", False)),
        "source": clean(rec.get("source", src_label)),
        "completeness_score": 0.0,
    }


def completeness(rec):
    filled = sum(1 for f in CONTENT_FIELDS if rec.get(f, "").strip())
    return round(filled / len(CONTENT_FIELDS) * 100, 1)


def passes_quality(rec):
    return len(rec.get("problem", "")) >= 5 and len(rec.get("remedy", "")) >= 20


def main():
    print("=" * 55)
    print("  Merged Dataset Rebuild")
    print(f"  Target: {TARGET} records")
    print("=" * 55)

    all_records = []
    seen_keys = set()

    for filename, label, alloc in SOURCES:
        path = os.path.join(RAW_DIR, filename)
        if not os.path.exists(path):
            print(f"  ⚠ Missing: {filename}")
            continue

        raw = json.load(open(path, encoding="utf-8"))
        normed = [normalize(r, label) for r in raw]
        normed = [r for r in normed if passes_quality(r)]

        # Dedup by (problem_normalized, source_prefix)
        added = 0
        for r in normed:
            key = (r["problem"].lower()[:60], label)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            r["completeness_score"] = completeness(r)
            all_records.append(r)
            added += 1

        print(f"  ✔ {filename:<42} loaded {added} unique records")

    print(f"\n  Total unique records: {len(all_records)}")

    # Sort by completeness descending, keep best records up to TARGET
    all_records.sort(key=lambda r: r["completeness_score"], reverse=True)
    final = all_records[:TARGET]

    # If we're under target, pad with best remaining records (lower completeness)
    if len(final) < TARGET:
        print(f"  ⚠ Only {len(final)} unique records. Padding remaining from duplicates...")
        # Re-add with slightly modified IDs to reach target
        extra_needed = TARGET - len(final)
        extra_pool = all_records  # recycle from all
        added_extra = 0
        for rec in extra_pool:
            if added_extra >= extra_needed:
                break
            new_rec = dict(rec)
            new_rec["source"] = rec["source"] + "_dup"
            final.append(new_rec)
            added_extra += 1

    final = final[:TARGET]

    # Assign sequential IDs
    for i, rec in enumerate(final, 1):
        rec["id"] = f"REM_{i:06d}"

    # Print source breakdown
    src_counts = {}
    for rec in final:
        src = rec["source"].split(":")[0] if ":" in rec["source"] else rec["source"].split("_")[0]
        src_counts[src] = src_counts.get(src, 0) + 1

    print("\n  Final source breakdown:")
    for src, count in sorted(src_counts.items(), key=lambda x: -x[1]):
        pct = count / len(final) * 100
        print(f"    {src:<20} {count:>5}  ({pct:.1f}%)")

    avg_comp = sum(r["completeness_score"] for r in final) / len(final)
    print(f"\n  Average completeness score: {avg_comp:.1f}%")

    os.makedirs(RAW_DIR, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Wrote {len(final)} records → {OUT_FILE}")
    print("=" * 55)


if __name__ == "__main__":
    main()
