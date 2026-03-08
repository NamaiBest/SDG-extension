"""
SCRIPT 09b — Pre-Merger Field Enrichment
==========================================
Populates two fields that are 0% across Reddit data:
  - possible_causes : extracted from remedy/symptoms text
                      using cause-pattern sentences +
                      problem-based lookup table
  - preparation     : extracted from remedy text using
                      action-word sentences (boil, mix,
                      teaspoon, daily, etc.)

Runs on ALL raw JSON files before the merger so the
final dataset has maximum field coverage.

Input files modified in-place (backups created):
  - data/raw/reddit/reddit_remedies.json
  - data/raw/reddit/reddit_remedies_expanded.json
  - data/raw/huggingface/hf_remedies.json
  - data/raw/websites/1mg_remedies.json
  - data/raw/websites/stylecraze_remedies.json
"""

import os
import re
import json
import shutil

from utils import save_json, load_json, get_logger, load_config

logger = get_logger("script_09b_enrich")
config = load_config()

RAW_DIR = "data/raw"

FILES_TO_ENRICH = [
    os.path.join(config["output"]["raw_reddit_dir"],   "reddit_remedies.json"),
    os.path.join(config["output"]["raw_reddit_dir"],   "reddit_remedies_expanded.json"),
    os.path.join(config["output"]["raw_hf_dir"],       "hf_remedies.json"),
    os.path.join(config["output"]["raw_website_dir"],  "1mg_remedies.json"),
    os.path.join(config["output"]["raw_website_dir"],  "stylecraze_remedies.json"),
]


# ─────────────────────────────────────────
# PREPARATION EXTRACTOR
# Scans remedy/symptoms text for sentences
# containing action words and measurements
# ─────────────────────────────────────────

PREP_TRIGGERS = [
    "boil", "mix", "add", "take", "apply", "drink", "consume",
    "prepare", "heat", "grind", "crush", "blend", "soak", "steep",
    "strain", "simmer", "stir", "dilute", "massage", "inhale",
    "teaspoon", "tablespoon", "cup", "glass", "drops", "ml", "gram",
    "twice a day", "once a day", "twice daily", "daily",
    "every morning", "every night", "every day",
    "on an empty stomach", "before bed", "before sleep",
    "after meal", "after food", "with warm water", "with honey",
    "with milk", "with water", "for 7 days", "for a week",
    "for 30 days", "for a month", "continue for",
    "how to make", "how to use", "how to prepare",
    "method:", "recipe:", "procedure:"
]

def extract_preparation(text: str) -> str:
    if not text:
        return ""
    sentences = re.split(r"[.!?\n|]", text)
    found = []
    for s in sentences:
        s = s.strip()
        if len(s) > 15 and any(kw in s.lower() for kw in PREP_TRIGGERS):
            found.append(s)
    return " | ".join(found[:6])


# ─────────────────────────────────────────
# CAUSE EXTRACTOR
# Two strategies:
#   1. Pattern extraction from text — looks
#      for sentences with causal language
#   2. Problem lookup table — maps known
#      conditions to their common causes
# ─────────────────────────────────────────

CAUSE_PATTERNS = [
    r"caused by\s+([^.!?\n]{5,80})",
    r"due to\s+([^.!?\n]{5,80})",
    r"because of\s+([^.!?\n]{5,80})",
    r"results? from\s+([^.!?\n]{5,80})",
    r"triggered by\s+([^.!?\n]{5,80})",
    r"leads? to\s+([^.!?\n]{5,80})",
    r"result(?:s|ing)? (?:in|from)\s+([^.!?\n]{5,80})",
    r"(?:main |common )?cause[sd]?\s+(?:of|is|are|include)\s+([^.!?\n]{5,80})",
    r"reason[sd]?\s+(?:for|is|are|include)\s+([^.!?\n]{5,80})",
    r"factors?\s+(?:include|that cause|responsible)\s+([^.!?\n]{5,80})",
]

def extract_causes_from_text(text: str) -> str:
    if not text:
        return ""
    found = []
    tl = text.lower()
    for pattern in CAUSE_PATTERNS:
        matches = re.findall(pattern, tl)
        for m in matches:
            m = m.strip().rstrip(".,;")
            if 5 < len(m) < 120 and m not in found:
                found.append(m)
    return " | ".join(found[:3])

# ── Problem-based cause lookup ────────────
# Common causes for frequently occurring
# conditions in Indian home remedy datasets
CAUSE_LOOKUP = {
    # Digestive
    "acidity":        "spicy food, irregular eating, stress, caffeine, alcohol",
    "acid reflux":    "spicy food, fatty meals, lying down after eating, obesity",
    "indigestion":    "overeating, eating too fast, spicy/fatty food, stress",
    "constipation":   "low fiber diet, dehydration, sedentary lifestyle, stress",
    "gas":            "carbonated drinks, beans, lactose intolerance, swallowing air",
    "bloating":       "gas buildup, overeating, food intolerance, irritable bowel",
    "diarrhea":       "infection, contaminated food/water, food intolerance, stress",
    "loose motion":   "infection, contaminated food, food intolerance, stress",
    "nausea":         "infection, motion sickness, pregnancy, medication side effects",

    # Respiratory
    "cold":           "viral infection, low immunity, cold weather, allergens",
    "cough":          "viral infection, allergens, dry air, acid reflux, smoking",
    "fever":          "viral or bacterial infection, inflammation, heat exhaustion",
    "sore throat":    "viral infection, bacterial infection, dry air, allergens",
    "asthma":         "allergens, pollution, exercise, cold air, stress",
    "sinusitis":      "infection, allergens, nasal polyps, dry air",

    # Pain
    "headache":       "stress, dehydration, poor sleep, eye strain, tension",
    "migraine":       "hormonal changes, stress, certain foods, bright lights, strong smells",
    "joint pain":     "arthritis, inflammation, injury, aging, autoimmune conditions",
    "knee pain":      "arthritis, injury, overuse, obesity, weak muscles",
    "back pain":      "poor posture, muscle strain, disc problems, sedentary lifestyle",
    "tooth pain":     "cavity, infection, gum disease, cracked tooth, sensitivity",

    # Skin
    "acne":           "excess sebum, bacteria, hormonal changes, diet, stress",
    "pimples":        "clogged pores, bacteria, hormonal changes, oily skin",
    "dandruff":       "dry scalp, fungal infection, oily skin, stress, poor hygiene",
    "eczema":         "immune system dysfunction, allergens, dry skin, stress",
    "psoriasis":      "immune system dysfunction, genetics, stress, infections",
    "dark circles":   "lack of sleep, dehydration, genetics, stress, aging",

    # Metabolic
    "diabetes":       "insulin resistance, genetics, obesity, sedentary lifestyle, poor diet",
    "obesity":        "overeating, sedentary lifestyle, hormonal imbalance, genetics",
    "weight gain":    "excess caloric intake, hormonal imbalance, stress, poor sleep",
    "high blood pressure": "stress, high sodium diet, obesity, sedentary lifestyle, genetics",
    "thyroid":        "autoimmune disease, iodine deficiency, genetics, stress",

    # Hair
    "hair fall":      "nutritional deficiency, stress, hormonal imbalance, genetics, scalp infection",
    "hair loss":      "nutritional deficiency, stress, hormonal imbalance, genetics",
    "grey hair":      "genetics, nutritional deficiency, stress, oxidative damage",

    # Other
    "insomnia":       "stress, anxiety, poor sleep hygiene, caffeine, irregular schedule",
    "anxiety":        "stress, hormonal imbalance, genetics, lifestyle factors",
    "fatigue":        "poor sleep, nutritional deficiency, stress, anemia, thyroid issues",
    "anemia":         "iron deficiency, vitamin B12 deficiency, chronic disease, blood loss",
    "urinary infection": "bacterial infection, dehydration, poor hygiene, sexual activity",
    "uti":            "bacterial infection, dehydration, poor hygiene",
}

def lookup_causes(problem: str) -> str:
    if not problem:
        return ""
    pl = problem.lower()
    for condition, causes in CAUSE_LOOKUP.items():
        if condition in pl:
            return causes
    return ""


# ─────────────────────────────────────────
# ENRICH A SINGLE RECORD
# ─────────────────────────────────────────

def enrich_record(record: dict) -> dict:
    # ── Preparation ──────────────────────
    if not record.get("preparation", "").strip():
        # Search remedy text first, then symptoms
        prep = extract_preparation(record.get("remedy", ""))
        if not prep:
            prep = extract_preparation(record.get("symptoms", ""))
        record["preparation"] = prep

    # ── Possible causes ──────────────────
    if not record.get("possible_causes", "").strip():
        # Strategy 1: extract from text
        causes = extract_causes_from_text(
            record.get("remedy", "") + " " + record.get("symptoms", "")
        )
        # Strategy 2: lookup by problem name
        if not causes:
            causes = lookup_causes(record.get("problem", ""))
        record["possible_causes"] = causes

    return record


# ─────────────────────────────────────────
# PROCESS A FILE
# ─────────────────────────────────────────

def enrich_file(filepath: str) -> dict:
    if not os.path.exists(filepath):
        logger.warning(f"  File not found: {filepath}")
        return {"skipped": True}

    records = load_json(filepath)
    if not records:
        logger.warning(f"  Empty file: {filepath}")
        return {"skipped": True}

    total = len(records)

    # Count before
    prep_before   = sum(1 for r in records if r.get("preparation","").strip())
    causes_before = sum(1 for r in records if r.get("possible_causes","").strip())

    # Enrich
    records = [enrich_record(r) for r in records]

    # Count after
    prep_after   = sum(1 for r in records if r.get("preparation","").strip())
    causes_after = sum(1 for r in records if r.get("possible_causes","").strip())

    # Backup original
    backup_path = filepath.replace(".json", "_backup.json")
    shutil.copy(filepath, backup_path)

    # Save enriched
    save_json(records, filepath)

    return {
        "total":          total,
        "prep_before":    prep_before,
        "prep_after":     prep_after,
        "causes_before":  causes_before,
        "causes_after":   causes_after,
    }


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("  SCRIPT 09b — Pre-Merger Field Enrichment")
    print("=" * 55)
    print("\nEnriching: possible_causes + preparation\n")

    total_records    = 0
    total_prep_gain  = 0
    total_cause_gain = 0

    for filepath in FILES_TO_ENRICH:
        fname = os.path.basename(filepath)
        print(f"── {fname} {'─' * (40 - len(fname))}")

        result = enrich_file(filepath)

        if result.get("skipped"):
            print(f"  ⚠ Skipped (not found or empty)\n")
            continue

        n = result["total"]
        prep_gain  = result["prep_after"]  - result["prep_before"]
        cause_gain = result["causes_after"] - result["causes_before"]

        print(f"  Records     : {n}")
        print(f"  preparation : {result['prep_before']}/{n} → {result['prep_after']}/{n}  (+{prep_gain})")
        print(f"  causes      : {result['causes_before']}/{n} → {result['causes_after']}/{n}  (+{cause_gain})")
        print(f"  prep %      : {result['prep_after']/n*100:.1f}%")
        print(f"  causes %    : {result['causes_after']/n*100:.1f}%")
        print()

        total_records    += n
        total_prep_gain  += prep_gain
        total_cause_gain += cause_gain

    print("=" * 55)
    print(f"  Total records enriched : {total_records}")
    print(f"  preparation gain       : +{total_prep_gain}")
    print(f"  possible_causes gain   : +{total_cause_gain}")
    print(f"\n  Originals backed up as *_backup.json")
    print(f"  Next → python script_10_merger.py")
    print("=" * 55)