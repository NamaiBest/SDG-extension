"""
SCRIPT 5A — Reddit Scraper
=========================================================
  - Scrapes Reddit posts and comments using Reddit's public
  — no API credentials needed
  - Searches remedy-related subreddits using keywords
"""

import os
import sys
import time
import json
import re

try:
    import requests
except ImportError:
    print("requests not found. Run: pip install requests")
    sys.exit(1)

try:
    from utils import save_json, get_logger, load_config, safe_get
except ImportError:
    print("utils.py not found. Run prerequisite first.")
    sys.exit(1)


# ── Setup ─────────────────────────────────
logger   = get_logger("script_07_reddit")
config   = load_config()
OUT_DIR  = config["output"]["raw_reddit_dir"]
OUT_FILE = os.path.join(OUT_DIR, "reddit_remedies.json")
DELAY    = config["scraping"]["delay_between_requests_sec"]

# Reddit requires a descriptive User-Agent for JSON API
# Using the generic browser UA can get rate-limited faster
HEADERS = {
    "User-Agent": "remedy-dataset-research-bot/1.0 (educational project)"
}

os.makedirs(OUT_DIR, exist_ok=True)


# ─────────────────────────────────────────
# SUBREDDITS + KEYWORDS
# ─────────────────────────────────────────

SUBREDDITS = [
    "Ayurveda",
    "HomeRemedies",
    "herbalism",
    "india",
    "IndianFood",
    "desi",
    "NaturalRemedies",
    "alternativemedicine",
]

SEARCH_KEYWORDS = [
    "home remedy",
    "ayurvedic remedy",
    "Indian home remedy",
    "dadi ke nuskhe",
    "nani ka nuskha",
    "turmeric remedy",
    "kitchen remedy",
    "kadha recipe",
    "herbal remedy india",
    "neem remedy",
    "tulsi remedy",
    "haldi doodh",
    "gharelu nuskha",
    "giloy benefits",
    "ashwagandha benefits",
]


# ─────────────────────────────────────────
# RELEVANCE FILTER
# ─────────────────────────────────────────

REMEDY_KEYWORDS = [
    "remedy", "remedies", "ayurveda", "ayurvedic", "herbal", "herb",
    "turmeric", "neem", "ginger", "tulsi", "ashwagandha", "triphala",
    "amla", "giloy", "brahmi", "methi", "fenugreek", "ajwain",
    "cumin", "honey", "aloe vera", "garlic", "ghee", "coconut oil",
    "kadha", "churna", "home remedy", "kitchen remedy", "natural cure",
    "treatment", "symptom", "relief", "heal", "cure",
    "haldi", "adrak", "nuskha", "nuskhe", "dadi", "nani",
    "gharelu", "desi", "traditional"
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
    text = re.sub(r"/?r/\w+", "", text)
    text = re.sub(r"/?u/\w+", "", text)
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
    "baking soda", "salt water", "steam", "ginger tea", "herbal tea"
]

def detect_ingredients(text: str) -> str:
    tl = text.lower()
    return ", ".join(i for i in INDIAN_INGREDIENTS if i in tl)


# ─────────────────────────────────────────
# FETCH POSTS — search endpoint
# ─────────────────────────────────────────

def fetch_search_posts(subreddit: str, keyword: str, limit: int = 50) -> list:
    url = (
        f"https://www.reddit.com/r/{subreddit}/search.json"
        f"?q={requests.utils.quote(keyword)}&limit={limit}"
        f"&sort=relevance&type=link&restrict_sr=1"
    )
    resp = safe_get(url, HEADERS, timeout=15, retries=2, delay=2.0)
    if not resp:
        return []

    try:
        data = resp.json()
        return data.get("data", {}).get("children", [])
    except Exception as e:
        logger.warning(f"  JSON parse error for r/{subreddit} '{keyword}': {e}")
        return []


# ─────────────────────────────────────────
# FETCH POSTS — top posts endpoint
# ─────────────────────────────────────────

def fetch_top_posts(subreddit: str, limit: int = 100) -> list:
    url = (
        f"https://www.reddit.com/r/{subreddit}/top.json"
        f"?t=year&limit={limit}"
    )
    resp = safe_get(url, HEADERS, timeout=15, retries=2, delay=2.0)
    if not resp:
        return []

    try:
        data = resp.json()
        return data.get("data", {}).get("children", [])
    except Exception as e:
        logger.warning(f"  JSON parse error for top posts r/{subreddit}: {e}")
        return []


# ─────────────────────────────────────────
# FETCH COMMENTS for a post
# ─────────────────────────────────────────

def fetch_comments(subreddit: str, post_id: str, limit: int = 5) -> list:
    url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json?limit={limit}"
    resp = safe_get(url, HEADERS, timeout=15, retries=2, delay=2.0)
    if not resp:
        return []

    try:
        data = resp.json()
        # data[1] contains comments, data[0] is the post itself
        if len(data) < 2:
            return []
        comments = []
        for child in data[1]["data"]["children"][:limit]:
            body = child.get("data", {}).get("body", "")
            if body and is_relevant(body):
                comments.append(clean_text(body))
        return comments
    except Exception as e:
        logger.warning(f"  Comment fetch error for {post_id}: {e}")
        return []


# ─────────────────────────────────────────
# BUILD RECORD from a raw Reddit post dict
# ─────────────────────────────────────────

def build_record(post_data: dict, comments: list) -> dict | None:
    title     = clean_text(post_data.get("title", ""))
    body      = clean_text(post_data.get("selftext", ""))
    subreddit = post_data.get("subreddit", "")
    post_id   = post_data.get("id", "")

    # Skip deleted/removed posts
    if body in ("[deleted]", "[removed]", ""):
        body = ""

    combined = title + " " + body + " " + " ".join(comments)

    if not is_relevant(combined):
        return None

    remedy_parts = [p for p in [body] + comments if p]
    remedy_text  = " | ".join(remedy_parts)

    if not remedy_text:
        remedy_text = title  # title-only posts (questions with answers in comments)

    ingredients = detect_ingredients(combined)

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
        "remedy":             remedy_text[:2000],
        "ingredients":        ingredients,
        "preparation":        "",
        "traditional_system": system,
        "severity_level":     "",
        "doctor_consult":     False,
        "source":             f"reddit:r/{subreddit}:{post_id}"
    }


# ─────────────────────────────────────────
# DEDUPLICATION — by post ID
# ─────────────────────────────────────────

def deduplicate(records: list) -> list:
    seen = set()
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
    print("Reddit Scraper")
    print("=" * 55)

    # Quick connectivity check
    print("\n[Pre-check] Testing Reddit JSON API...")
    test = safe_get(
        "https://www.reddit.com/r/Ayurveda/top.json?limit=1",
        HEADERS, timeout=10, retries=1
    )
    if not test:
        print("  ❌ Cannot reach Reddit. Check your internet connection")
        sys.exit(1)
    print("  ✔ Reddit JSON API reachable\n")

    all_records = []

    # ── Phase 1: Keyword search ────────────────────
    print("[Phase 1] Keyword search across subreddits...")
    print(f"  {len(SUBREDDITS)} subreddits × {len(SEARCH_KEYWORDS)} keywords")

    for sub in SUBREDDITS:
        sub_count = 0
        for keyword in SEARCH_KEYWORDS:
            logger.info(f"  r/{sub} ← '{keyword}'")
            posts = fetch_search_posts(sub, keyword, limit=25)

            for post_wrapper in posts:
                post_data = post_wrapper.get("data", {})
                post_id   = post_data.get("id", "")

                # Fetch top comments for this post
                comments = fetch_comments(sub, post_id, limit=5)
                time.sleep(1)  # between comment fetches

                record = build_record(post_data, comments)
                if record:
                    all_records.append(record)
                    sub_count += 1

            time.sleep(DELAY)  # between keyword searches

        logger.info(f"  r/{sub} → {sub_count} records collected")

    # ── Phase 2: Top posts from core subreddits ────
    print("\n[Phase 2] Top posts from core remedy subreddits...")
    CORE_SUBS = ["Ayurveda", "HomeRemedies", "herbalism", "NaturalRemedies"]

    for sub in CORE_SUBS:
        logger.info(f"  Top posts: r/{sub}")
        posts = fetch_top_posts(sub, limit=100)
        count = 0

        for post_wrapper in posts:
            post_data = post_wrapper.get("data", {})
            post_id   = post_data.get("id", "")
            comments  = fetch_comments(sub, post_id, limit=5)
            time.sleep(1)

            record = build_record(post_data, comments)
            if record:
                all_records.append(record)
                count += 1

        logger.info(f"  r/{sub} top → {count} records")
        time.sleep(DELAY)

    # ── Dedup + save ───────────────────────────────
    before = len(all_records)
    all_records = deduplicate(all_records)
    after  = len(all_records)

    # Fill rate summary
    if all_records:
        print("\n── Field fill rates ───────────────────────────")
        for f in ["symptoms","possible_causes","remedy","ingredients","preparation"]:
            filled = sum(1 for r in all_records if r.get(f,"").strip())
            pct    = filled / len(all_records) * 100
            bar    = "█" * int(pct // 10) + "░" * (10 - int(pct // 10))
            print(f"  {f:<22} {pct:>5.1f}%  {bar}")
        print("───────────────────────────────────────────────")

    print(f"\n  Raw records collected : {before}")
    print(f"  After dedup           : {after}")

    save_json(all_records, OUT_FILE)

    print("\n" + "=" * 55)
    print(f"  Output → {OUT_FILE}")
    print(f"  Next   → python script_08_youtube.py")
    print("=" * 55)