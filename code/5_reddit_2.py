"""
SCRIPT 5B — Reddit Scraper v2
==========================================
Key change from v1: NO comment fetching.
Each post is processed from title + body only.
"""

import os
import sys
import time
import json
import re
import requests

from utils import save_json, load_json, get_logger, load_config, safe_get


# ── Setup ─────────────────────────────────
logger    = get_logger("script_07b_reddit_expansion")
config    = load_config()
OUT_DIR   = config["output"]["raw_reddit_dir"]
OUT_FILE  = os.path.join(OUT_DIR, "reddit_remedies_expanded.json")
ORIG_FILE = os.path.join(OUT_DIR, "reddit_remedies.json")
DELAY     = config["scraping"]["delay_between_requests_sec"]

HEADERS = {
    "User-Agent": "remedy-dataset-research-bot/1.0 (educational project)"
}

os.makedirs(OUT_DIR, exist_ok=True)


# ─────────────────────────────────────────
# SUBREDDITS
# ─────────────────────────────────────────

SUBREDDITS = [
    "AyurvedaHealing",
    "IndianMedicine",
    "traditionalmedicine",
    "spices",
    "IndianDiet",
    "Supplements",
    "ChronicPain",
    "AsianBeauty",
    "SkincareAddiction",
    "PlantBasedDiet",
    "Meditation",
    "Yoga",
    "DIYBeauty",
    "EatCheapAndHealthy",
    "Ayurveda",
    "herbalism",
    "NaturalRemedies",
    "india",
    "alternativemedicine",
]


# ─────────────────────────────────────────
# KEYWORDS
# ─────────────────────────────────────────

KEYWORDS = [
    "kadha",
    "jadi buti",
    "aushadhi",
    "panchakarma",
    "rasayana",
    "chyawanprash",
    "triphala churna",
    "trikatu",
    "acidity remedy india",
    "cold remedy india",
    "hair fall home remedy",
    "skin remedy ayurvedic",
    "diabetes ayurvedic",
    "joint pain remedy india",
    "immunity booster india",
    "digestion remedy india",
    "sleep remedy ayurvedic",
    "weight loss ayurvedic",
    "giloy",
    "brahmi herb",
    "shatavari benefits",
    "ashwagandha churna",
    "neem leaves remedy",
]


# ─────────────────────────────────────────
# RELEVANCE FILTER
# ─────────────────────────────────────────

REMEDY_KEYWORDS = [
    "remedy", "remedies", "ayurveda", "ayurvedic", "herbal", "herb",
    "turmeric", "neem", "ginger", "tulsi", "ashwagandha", "triphala",
    "amla", "giloy", "brahmi", "methi", "fenugreek", "ajwain",
    "cumin", "honey", "aloe vera", "garlic", "ghee", "coconut oil",
    "kadha", "churna", "home remedy", "natural cure", "treatment",
    "symptom", "relief", "heal", "cure", "haldi", "adrak",
    "nuskha", "gharelu", "desi", "traditional", "jadi buti",
    "rasayana", "chyawanprash", "trikatu", "aushadhi"
]

def is_relevant(text: str) -> bool:
    if not text or len(text.strip()) < 30:
        return False
    tl = text.lower()
    return any(kw in tl for kw in REMEDY_KEYWORDS)


# ─────────────────────────────────────────
# TEXT CLEANER
# ─────────────────────────────────────────

def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"/?[ru]/\w+", "", text)
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ─────────────────────────────────────────
# INGREDIENT DETECTION
# ─────────────────────────────────────────

INDIAN_INGREDIENTS = [
    "turmeric", "ginger", "neem", "tulsi", "ashwagandha", "triphala",
    "amla", "giloy", "brahmi", "haritaki", "methi", "fenugreek",
    "ajwain", "cumin", "coriander", "cardamom", "cinnamon", "clove",
    "black pepper", "honey", "mustard", "sesame", "coconut oil",
    "castor oil", "aloe vera", "garlic", "onion", "lemon", "lime",
    "milk", "ghee", "buttermilk", "jeera", "saunf", "fennel",
    "pudina", "mint", "haldi", "adrak", "lahsun", "nimbu", "dahi",
    "kadha", "churna", "neem oil", "camphor", "eucalyptus",
    "arjuna", "shatavari", "guduchi", "moringa", "karela",
    "carom seeds", "hing", "asafoetida", "curry leaves",
    "mulethi", "licorice", "rose water", "apple cider vinegar",
    "baking soda", "salt water", "ginger tea", "herbal tea",
    "chyawanprash", "trikatu", "pippali", "shankhpushpi"
]

def detect_ingredients(text: str) -> str:
    tl = text.lower()
    return ", ".join(i for i in INDIAN_INGREDIENTS if i in tl)


# ─────────────────────────────────────────
# REDDIT API — posts only, no comment fetching
# ─────────────────────────────────────────

def fetch_posts(url: str) -> list:
    resp = safe_get(url, HEADERS, timeout=15, retries=2, delay=2.0)
    if not resp:
        return []
    try:
        return resp.json().get("data", {}).get("children", [])
    except Exception:
        return []

def search_posts(subreddit: str, keyword: str, limit: int = 50) -> list:
    url = (
        f"https://www.reddit.com/r/{subreddit}/search.json"
        f"?q={requests.utils.quote(keyword)}&limit={limit}"
        f"&sort=relevance&restrict_sr=1"
    )
    return fetch_posts(url)

def top_posts(subreddit: str, limit: int = 100) -> list:
    return fetch_posts(
        f"https://www.reddit.com/r/{subreddit}/top.json?t=year&limit={limit}"
    )

def hot_posts(subreddit: str, limit: int = 100) -> list:
    return fetch_posts(
        f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    )


# ─────────────────────────────────────────
# RECORD BUILDER — title + body only
# ─────────────────────────────────────────

def build_record(post_data: dict) -> dict | None:
    title     = clean_text(post_data.get("title", ""))
    body      = clean_text(post_data.get("selftext", ""))
    subreddit = post_data.get("subreddit", "")
    post_id   = post_data.get("id", "")

    if body in ("[deleted]", "[removed]"):
        body = ""

    combined = title + " " + body
    if not is_relevant(combined):
        return None

    tl = combined.lower()
    if "ayurveda" in tl or "ayurvedic" in tl:
        system = "Ayurvedic"
    elif "herb" in tl or "herbal" in tl:
        system = "Herbal"
    else:
        system = "Home Remedy"

    return {
        "problem":            title,
        "symptoms":           body[:600] if body else "",
        "possible_causes":    "",
        "remedy":             body[:2000] if body else title,
        "ingredients":        detect_ingredients(combined),
        "preparation":        "",
        "traditional_system": system,
        "severity_level":     "",
        "doctor_consult":     False,
        "source":             f"reddit:r/{subreddit}:{post_id}"
    }

def process_posts(posts: list) -> list:
    records = []
    for pw in posts:
        record = build_record(pw.get("data", {}))
        if record:
            records.append(record)
    return records


# ─────────────────────────────────────────
# DEDUPLICATION
# ─────────────────────────────────────────

def load_existing_ids() -> set:
    if not os.path.exists(ORIG_FILE):
        return set()
    existing = load_json(ORIG_FILE)
    return {r["source"].lower() for r in existing}

def deduplicate(records: list, existing_ids: set) -> list:
    seen = set(existing_ids)
    unique = []
    for r in records:
        key = r["source"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("  SCRIPT 07b — Reddit Expansion (Fast, No Comments)")
    print("=" * 55)

    print("\n[Pre-check] Testing Reddit API...")
    test = safe_get(
        "https://www.reddit.com/r/Ayurveda/top.json?limit=1",
        HEADERS, timeout=10, retries=1
    )
    if not test:
        print("  ❌ Can't reach Reddit.")
        sys.exit(1)
    print("  ✔ Reddit API reachable")

    existing_ids = load_existing_ids()
    print(f"  Existing records to skip: {len(existing_ids)}\n")

    all_records = []
    total_combos = len(SUBREDDITS) * len(KEYWORDS)
    done = 0

    # ── Phase 1: Search ───────────────────────
    print(f"[Phase 1] Search: {len(SUBREDDITS)} subreddits × {len(KEYWORDS)} keywords")
    print(f"  ({total_combos} combinations, ~{total_combos * 3 // 60} min estimated)\n")

    for sub in SUBREDDITS:
        sub_count = 0
        for keyword in KEYWORDS:
            posts   = search_posts(sub, keyword, limit=50)
            records = process_posts(posts)
            all_records += records
            sub_count   += len(records)
            done += 1
            if done % 25 == 0:
                print(f"  [{done}/{total_combos}] {len(all_records)} records so far")
            time.sleep(DELAY)
        logger.info(f"  r/{sub} → {sub_count} records")

    print(f"\n  Phase 1 done: {len(all_records)} raw records\n")

    # ── Phase 2: Top + Hot feeds ──────────────
    print("[Phase 2] Top + Hot feeds from core subreddits...")
    FEED_SUBS = [
        "Ayurveda", "herbalism", "NaturalRemedies",
        "AyurvedaHealing", "IndianMedicine", "traditionalmedicine",
        "india", "Supplements", "alternativemedicine"
    ]

    for sub in FEED_SUBS:
        for feed_name, feed_fn in [("top", top_posts), ("hot", hot_posts)]:
            posts   = feed_fn(sub, limit=100)
            records = process_posts(posts)
            all_records += records
            logger.info(f"  r/{sub} {feed_name} → {len(records)} records")
            time.sleep(DELAY)

    print(f"  Phase 2 done: {len(all_records)} total raw records\n")

    # ── Dedup + save ──────────────────────────
    before = len(all_records)
    all_records = deduplicate(all_records, existing_ids)
    after = len(all_records)

    if all_records:
        print("── Field fill rates ───────────────────────────")
        for f in ["symptoms","possible_causes","remedy","ingredients","preparation"]:
            filled = sum(1 for r in all_records if r.get(f,"").strip())
            pct    = filled / len(all_records) * 100
            bar    = "█" * int(pct // 10) + "░" * (10 - int(pct // 10))
            print(f"  {f:<22} {pct:>5.1f}%  {bar}")
        print("───────────────────────────────────────────────")

    print(f"\n  Raw collected         : {before}")
    print(f"  Dupes removed         : {before - after}")
    print(f"  New unique records    : {after}")
    print(f"  Original Reddit total : {len(existing_ids)}")
    print(f"  Combined Reddit total : {len(existing_ids) + after}")

    save_json(all_records, OUT_FILE)

    print("\n" + "=" * 55)
    print(f"  Output → {OUT_FILE}")
    print("=" * 55)