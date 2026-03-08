"""
SCRIPT 2 — HuggingFace Datasets
=========================================
Datasets used:
1. Abhaykoul/Ancient-Indian-Wisdom   — 616 rows, Indian wisdom/Ayurveda Q&A
2. openlifescienceai/medmcqa         — 190k+ medical MCQs, filter Ayurveda subset
3. deepkaria/indian-culture-dataset  — Indian culture including health practices
"""

import json
import os
import sys
import time

# ── Dependency check ──────────────────────
try:
    from datasets import load_dataset
except ImportError:
    print("'datasets' library not found")
    print("Install it with: pip install datasets")
    sys.exit(1)

try:
    from utils import save_json, get_logger, load_config
except ImportError:
    print("utils.py not found. Run prequisite first")
    sys.exit(1)


# ── Setup ─────────────────────────────────
logger   = get_logger("script_02_huggingface")
config   = load_config()
OUT_DIR  = config["output"]["raw_hf_dir"]
OUT_FILE = os.path.join(OUT_DIR, "hf_remedies.json")

os.makedirs(OUT_DIR, exist_ok=True)


# ─────────────────────────────────────────
# SCHEMA — consistent across all scripts
# ─────────────────────────────────────────

def make_record(
    problem="", symptoms="", possible_causes="",
    remedy="", ingredients="", preparation="",
    traditional_system="", severity_level="",
    doctor_consult=False, source=""
):
    return {
        "problem":            problem.strip(),
        "symptoms":           symptoms.strip(),
        "possible_causes":    possible_causes.strip(),
        "remedy":             remedy.strip(),
        "ingredients":        ingredients.strip(),
        "preparation":        preparation.strip(),
        "traditional_system": traditional_system.strip(),
        "severity_level":     severity_level.strip(),
        "doctor_consult":     doctor_consult,
        "source":             source.strip()
    }


# ─────────────────────────────────────────
# KEYWORDS for filtering remedy-relevant rows
# ─────────────────────────────────────────

REMEDY_KEYWORDS = [
    "remedy", "remedies", "ayurveda", "ayurvedic", "herbal", "herb",
    "turmeric", "neem", "ginger", "tulsi", "ashwagandha", "triphala",
    "amla", "haritaki", "brahmi", "giloy", "karela", "methi",
    "home remedy", "kitchen remedy", "kadha", "churna", "kwath",
    "treatment", "cure", "heal", "medicine", "medicinal",
    "symptoms", "condition", "disease", "ailment", "pain relief",
    "anti-inflammatory", "digestive", "immunity", "detox"
]

def is_remedy_relevant(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in REMEDY_KEYWORDS)


# ─────────────────────────────────────────
# DATASET 1 — Ancient Indian Wisdom
# 616 rows of Indian philosophy, Yoga, Ayurveda Q&A
# Columns: instruction, input, output
# ─────────────────────────────────────────

def fetch_ancient_indian_wisdom():
    records = []
    logger.info("Fetching: Abhaykoul/Ancient-Indian-Wisdom ...")

    try:
        ds = load_dataset("Abhaykoul/Ancient-Indian-Wisdom", split="train")
        logger.info(f"  Raw entries found: {len(ds)}")

        for row in ds:
            instruction = str(row.get("instruction", "") or "")
            output      = str(row.get("output", "") or "")

            if not instruction or not output:
                continue

            combined = instruction + " " + output
            if not is_remedy_relevant(combined):
                continue

            records.append(make_record(
                problem=instruction,
                remedy=output,
                traditional_system="Ayurvedic",
                source="huggingface:Ancient-Indian-Wisdom"
            ))

        logger.info(f"  ✔ Extracted {len(records)} remedy-relevant records")

    except Exception as e:
        logger.error(f"  ✘ Failed: {e}")

    return records


# ─────────────────────────────────────────
# DATASET 2 — MedMCQA
# 190k+ Indian medical entrance exam questions
# Filter: keep only Ayurveda / herbal medicine subjects
# Columns: question, opa, opb, opc, opd, exp, subject_name
# ─────────────────────────────────────────

AYURVEDA_SUBJECTS = {
    "ayurveda", "dravyaguna", "rasashastra", "panchakarma",
    "kayachikitsa", "kaumarabhritya", "shalya", "shalakya",
    "prasuti", "agad tantra", "swasthavritta", "samhita"
}

def fetch_medmcqa():
    records = []
    logger.info("Fetching: openlifescienceai/medmcqa (Ayurveda subset) ...")

    try:
        ds = load_dataset(
            "openlifescienceai/medmcqa",
            split="train",
            streaming=True
        )

        count = 0
        checked = 0
        MAX_CHECK = 50000
        MAX_RECORDS = 500

        for row in ds:
            if checked >= MAX_CHECK or count >= MAX_RECORDS:
                break
            checked += 1

            subject     = str(row.get("subject_name", "") or "").lower()
            question    = str(row.get("question", "") or "")
            explanation = str(row.get("exp", "") or "")

            subject_match = any(s in subject for s in AYURVEDA_SUBJECTS)
            text_match    = is_remedy_relevant(question + " " + explanation)

            if not (subject_match or text_match):
                continue

            options = {
                "A": str(row.get("opa", "") or ""),
                "B": str(row.get("opb", "") or ""),
                "C": str(row.get("opc", "") or ""),
                "D": str(row.get("opd", "") or ""),
            }
            correct_key = str(row.get("cop", "") or "")
            correct_ans = options.get(correct_key, "")
            remedy_text = correct_ans if correct_ans else explanation

            records.append(make_record(
                problem=question,
                remedy=remedy_text,
                preparation=explanation,
                traditional_system="Ayurvedic",
                source=f"huggingface:medmcqa:{subject}"
            ))
            count += 1

            if count % 50 == 0:
                logger.info(f"  ... {count} records collected (scanned {checked})")

        logger.info(f"  ✔ Extracted {len(records)} records (scanned {checked} rows)")

    except Exception as e:
        logger.error(f"  ✘ Failed: {e}")

    return records


# ─────────────────────────────────────────
# DATASET 3 — Indian Culture Dataset
# ─────────────────────────────────────────

def fetch_indian_culture():
    records = []
    logger.info("Fetching: deepkaria/indian-culture-dataset ...")

    try:
        ds = load_dataset("deepkaria/indian-culture-dataset", split="train")
        logger.info(f"  Raw entries found: {len(ds)}")

        for row in ds:
            text = (
                str(row.get("text", "") or "") or
                str(row.get("content", "") or "") or
                str(row.get("output", "") or "")
            )
            question = (
                str(row.get("instruction", "") or "") or
                str(row.get("question", "") or "") or
                str(row.get("input", "") or "")
            )

            if not text:
                continue
            if not is_remedy_relevant(text + " " + question):
                continue

            records.append(make_record(
                problem=question,
                remedy=text,
                traditional_system="Indian Traditional",
                source="huggingface:indian-culture-dataset"
            ))

        logger.info(f"  ✔ Extracted {len(records)} remedy-relevant records")

    except Exception as e:
        logger.error(f"  ✘ Failed (dataset may have different structure): {e}")

    return records


# ─────────────────────────────────────────
# DEDUPLICATION
# ─────────────────────────────────────────

def deduplicate(records):
    seen = set()
    unique = []
    for r in records:
        key = (r["problem"][:80].lower(), r["remedy"][:80].lower())
        if key not in seen and (r["problem"] or r["remedy"]):
            seen.add(key)
            unique.append(r)
    return unique


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("SCRIPT 2 — HuggingFace Datasets")
    print("=" * 55)

    all_records = []

    all_records += fetch_ancient_indian_wisdom()
    time.sleep(1)

    all_records += fetch_medmcqa()
    time.sleep(1)

    all_records += fetch_indian_culture()

    before = len(all_records)
    all_records = deduplicate(all_records)
    after = len(all_records)

    print(f"\n  Total records before dedup : {before}")
    print(f"  Total records after dedup  : {after}")
    print(f"  Duplicates removed         : {before - after}")

    save_json(all_records, OUT_FILE)

    print("\n" + "=" * 55)
    print(f"  Output → {OUT_FILE}")
    print("=" * 55)