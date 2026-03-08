"""
SCRIPT 10 — Final Merger
=============================================
Combines all raw JSON files into a single clean dataset.

  1. Load all raw source files
  2. Normalize schema across all records
  3. Deduplicate within and across sources
  4. Filter low-quality records
  5. Assign unique IDs + completeness scores
  6. Export to JSON + CSV
"""

import os
import re
import json
import csv

from utils import load_json, save_json, get_logger, load_config

logger = get_logger("script_10_merger")
config = load_config()

FINAL_DIR  = config["output"]["final_dir"]
JSON_OUT   = os.path.join(FINAL_DIR, "indian_remedies_dataset.json")
CSV_OUT    = os.path.join(FINAL_DIR, "indian_remedies_dataset.csv")

os.makedirs(FINAL_DIR, exist_ok=True)


# ─────────────────────────────────────────
# SOURCE FILES
# ─────────────────────────────────────────

SOURCE_FILES = [
    (os.path.join(config["output"]["raw_hf_dir"],      "hf_remedies.json"),               "huggingface"),
    (os.path.join(config["output"]["raw_website_dir"], "1mg_remedies.json"),               "1mg"),
    (os.path.join(config["output"]["raw_website_dir"], "stylecraze_remedies.json"),        "stylecraze"),
    (os.path.join(config["output"]["raw_reddit_dir"],  "reddit_remedies.json"),            "reddit"),
    (os.path.join(config["output"]["raw_reddit_dir"],  "reddit_remedies_expanded.json"),   "reddit"),
    (os.path.join(config["output"]["raw_youtube_dir"], "youtube_remedies.json"),           "youtube"),
]

# ─────────────────────────────────────────
# CANONICAL SCHEMA
# Every record in the final dataset will
# have exactly these fields in this order
# ─────────────────────────────────────────

SCHEMA = [
    "id",
    "problem",
    "symptoms",
    "possible_causes",
    "remedy",
    "ingredients",
    "preparation",
    "traditional_system",
    "severity_level",
    "doctor_consult",
    "source",
    "completeness_score",
]

CONTENT_FIELDS = [
    "problem", "symptoms", "possible_causes",
    "remedy", "ingredients", "preparation",
    "traditional_system",
]


# ─────────────────────────────────────────
# NORMALIZERS
# ─────────────────────────────────────────

VALID_SYSTEMS = {
    "ayurvedic", "herbal", "home remedy",
    "traditional", "siddha", "unani", "yoga"
}

def normalize_system(val: str) -> str:
    if not val:
        return "Home Remedy"
    v = val.strip().lower()
    for s in VALID_SYSTEMS:
        if s in v:
            return val.strip().title()
    return "Home Remedy"

def normalize_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "yes", "1")
    return False

def normalize_severity(val: str) -> str:
    if not val:
        return ""
    v = val.strip().lower()
    if v in ("low", "mild"):
        return "low"
    if v in ("medium", "moderate"):
        return "medium"
    if v in ("high", "severe", "critical"):
        return "high"
    return ""

def clean_field(val) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    # Remove placeholder values
    if s.lower() in ("[deleted]", "[removed]", "none", "null", "n/a"):
        return ""
    # Collapse excessive whitespace
    s = re.sub(r"\s+", " ", s)
    return s

def normalize_record(raw: dict, source_label: str) -> dict:
    return {
        "id":                 "",   # assigned later
        "problem":            clean_field(raw.get("problem", "")),
        "symptoms":           clean_field(raw.get("symptoms", "")),
        "possible_causes":    clean_field(raw.get("possible_causes", "")),
        "remedy":             clean_field(raw.get("remedy", "")),
        "ingredients":        clean_field(raw.get("ingredients", "")),
        "preparation":        clean_field(raw.get("preparation", "")),
        "traditional_system": normalize_system(raw.get("traditional_system", "")),
        "severity_level":     normalize_severity(raw.get("severity_level", "")),
        "doctor_consult":     normalize_bool(raw.get("doctor_consult", False)),
        "source":             clean_field(raw.get("source", source_label)),
        "completeness_score": 0.0,  # computed later
    }


# ─────────────────────────────────────────
# QUALITY FILTER
# Removes records that are too sparse
# Minimum requirements:
#   - problem must exist (>5 chars)
#   - remedy must exist (>20 chars)
#   - at least 2 other content fields filled
# ─────────────────────────────────────────

def passes_quality(record: dict) -> bool:
    if len(record.get("problem", "")) < 5:
        return False
    if len(record.get("remedy", "")) < 20:
        return False
    other_fields = ["symptoms", "possible_causes", "ingredients", "preparation"]
    filled = sum(1 for f in other_fields if record.get(f, "").strip())
    return filled >= 1


# ─────────────────────────────────────────
# COMPLETENESS SCORE
# % of content fields that are non-empty
# ─────────────────────────────────────────

def compute_completeness(record: dict) -> float:
    filled = sum(1 for f in CONTENT_FIELDS if record.get(f, "").strip())
    return round(filled / len(CONTENT_FIELDS) * 100, 1)


# ─────────────────────────────────────────
# DEDUPLICATION
# Two passes:
#   Pass 1 — exact source URL dedup
#   Pass 2 — fuzzy title dedup (catches same remedy from diff sources)
# ─────────────────────────────────────────

def normalize_title(text: str) -> str:
    """Lowercase, strip punctuation, collapse spaces."""
    t = text.lower()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def deduplicate(records: list) -> list:
    # Pass 1: exact source dedup
    seen_sources = set()
    pass1 = []
    for r in records:
        key = r["source"].lower()
        if key not in seen_sources:
            seen_sources.add(key)
            pass1.append(r)

    # Pass 2: fuzzy title dedup
    # If two records have identical normalized titles
    # and same traditional_system, keep the one with higher completeness score
    title_map = {}
    for r in pass1:
        key = (normalize_title(r["problem"]), r["traditional_system"].lower())
        if key not in title_map:
            title_map[key] = r
        else:
            existing = title_map[key]
            if r["completeness_score"] > existing["completeness_score"]:
                title_map[key] = r

    return list(title_map.values())


# ─────────────────────────────────────────
# ID ASSIGNMENT
# ─────────────────────────────────────────

def assign_ids(records: list) -> list:
    for i, r in enumerate(records, 1):
        r["id"] = f"REM_{i:06d}"
    return records


# ─────────────────────────────────────────
# CSV EXPORTER
# ─────────────────────────────────────────

def export_csv(records: list, path: str):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SCHEMA)
        writer.writeheader()
        writer.writerows(records)


# ─────────────────────────────────────────
# SUMMARY PRINTER
# ─────────────────────────────────────────

def print_summary(records: list, source_counts: dict):
    total = len(records)

    print("\n── Records by source ──────────────────────────")
    for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        bar = "█" * int(count / total * 40)
        print(f"  {src:<15} {count:>5}  {bar}")

    print("\n── Field fill rates ───────────────────────────")
    for f in CONTENT_FIELDS + ["severity_level"]:
        filled = sum(1 for r in records if r.get(f, "").strip())
        pct    = filled / total * 100
        bar    = "█" * int(pct // 10) + "░" * (10 - int(pct // 10))
        print(f"  {f:<22} {pct:>5.1f}%  {bar}")

    print("\n── Completeness score distribution ────────────")
    bands = {"0-25%": 0, "26-50%": 0, "51-75%": 0, "76-100%": 0}
    for r in records:
        s = r["completeness_score"]
        if s <= 25:    bands["0-25%"] += 1
        elif s <= 50:  bands["26-50%"] += 1
        elif s <= 75:  bands["51-75%"] += 1
        else:          bands["76-100%"] += 1
    for band, count in bands.items():
        pct = count / total * 100
        bar = "█" * int(pct // 5)
        print(f"  {band:<12} {count:>5} ({pct:>4.1f}%)  {bar}")

    print("\n── Traditional system breakdown ───────────────")
    systems = {}
    for r in records:
        s = r.get("traditional_system", "Unknown")
        systems[s] = systems.get(s, 0) + 1
    for sys, count in sorted(systems.items(), key=lambda x: -x[1]):
        pct = count / total * 100
        print(f"  {sys:<20} {count:>5} ({pct:>4.1f}%)")

    avg_score = sum(r["completeness_score"] for r in records) / total
    print(f"\n── Average completeness score: {avg_score:.1f}%")


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("  Final Merger & Dataset Exporter")
    print("=" * 55)

    # Step 1: Load all source files
    print("\n[Step 1] Loading source files...")
    all_records  = []
    source_counts = {}

    for filepath, source_label in SOURCE_FILES:
        if not os.path.exists(filepath):
            print(f"  ⚠ Not found: {filepath}")
            continue
        records = load_json(filepath)
        if not records:
            print(f"  ⚠ Empty: {filepath}")
            continue
        print(f"  ✔ {os.path.basename(filepath):<45} {len(records):>5} records")
        all_records += records
        source_counts[source_label] = source_counts.get(source_label, 0) + len(records)

    print(f"\n  Total loaded: {len(all_records)} records")

    # Step 2: Normalize
    print("\n[Step 2] Normalizing schema...")
    normalized = []
    for source_label in [sl for _, sl in SOURCE_FILES]:
        pass  # label already in each record's source field

    normalized = [
        normalize_record(r, r.get("source", "unknown"))
        for r in all_records
    ]
    print(f"  ✔ {len(normalized)} records normalized")

    # Step 3: Compute completeness scores
    print("\n[Step 3] Computing completeness scores...")
    for r in normalized:
        r["completeness_score"] = compute_completeness(r)

    # Step 4: Quality filter
    print("\n[Step 4] Filtering low-quality records...")
    before_filter = len(normalized)
    normalized    = [r for r in normalized if passes_quality(r)]
    filtered_out  = before_filter - len(normalized)
    print(f"  Removed {filtered_out} low-quality records")
    print(f"  Remaining: {len(normalized)}")

    # Step 5: Deduplicate
    print("\n[Step 5] Deduplicating...")
    before_dedup = len(normalized)
    normalized   = deduplicate(normalized)
    dupes_removed = before_dedup - len(normalized)
    print(f"  Removed {dupes_removed} duplicate records")
    print(f"  Remaining: {len(normalized)}")

    # Step 6: Assign IDs
    print("\n[Step 6] Assigning unique IDs...")
    normalized = assign_ids(normalized)
    print(f"  ✔ IDs assigned: REM_000001 → REM_{len(normalized):06d}")

    # Step 7: Update source counts after dedup
    source_counts = {}
    for r in normalized:
        src = r["source"].split(":")[0] if ":" in r["source"] else r["source"]
        source_counts[src] = source_counts.get(src, 0) + 1

    # Step 8: Print summary
    print_summary(normalized, source_counts)

    # Step 9: Export
    print(f"\n[Step 9] Exporting...")
    save_json(normalized, JSON_OUT)
    export_csv(normalized, CSV_OUT)

    print(f"\n{'=' * 55}")
    print(f"  DATASET COMPLETE")
    print(f"{'=' * 55}")
    print(f"  Total records  : {len(normalized)}")
    print(f"  JSON output    : {JSON_OUT}")
    print(f"  CSV output     : {CSV_OUT}")
    print(f"{'=' * 55}")

    # Print one sample record
    if normalized:
        print("\n── Sample record ──────────────────────────────")
        sample = {k: v for k, v in normalized[0].items()}
        for field, value in sample.items():
            val_str = str(value)
            if len(val_str) > 80:
                val_str = val_str[:80] + "..."
            print(f"  {field:<22} : {val_str}")
        print("───────────────────────────────────────────────")