"""
SCRIPT 3 — 1mg Article Scraper
========================================
"""

import os
import sys
import time
import re

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing libraries. Run: pip install requests beautifulsoup4 lxml")
    sys.exit(1)

try:
    from utils import save_json, get_logger, load_config, safe_get
except ImportError:
    print("utils.py not found. Run prerequisite first")
    sys.exit(1)


# ── Setup ─────────────────────────────────
logger   = get_logger("script_03_1mg")
config   = load_config()
OUT_DIR  = config["output"]["raw_website_dir"]
OUT_FILE = os.path.join(OUT_DIR, "1mg_remedies.json")
HEADERS  = config["scraping"]["headers"]
DELAY    = config["scraping"]["delay_between_requests_sec"]

os.makedirs(OUT_DIR, exist_ok=True)


# ─────────────────────────────────────────
# DIRECT ARTICLE URLs
# ─────────────────────────────────────────

DIRECT_ARTICLE_URLS = [
    "https://www.1mg.com/articles/home-remedies-for-cold-and-cough/",
    "https://www.1mg.com/articles/home-remedies-for-fever/",
    "https://www.1mg.com/articles/home-remedies-for-acidity/",
    "https://www.1mg.com/articles/home-remedies-for-headache/",
    "https://www.1mg.com/articles/home-remedies-for-constipation/",
    "https://www.1mg.com/articles/home-remedies-for-diabetes/",
    "https://www.1mg.com/articles/home-remedies-for-high-blood-pressure/",
    "https://www.1mg.com/articles/home-remedies-for-skin-care/",
    "https://www.1mg.com/articles/home-remedies-for-hair-fall/",
    "https://www.1mg.com/articles/home-remedies-for-sore-throat/",
    "https://www.1mg.com/articles/home-remedies-for-knee-pain/",
    "https://www.1mg.com/articles/home-remedies-for-back-pain/",
    "https://www.1mg.com/articles/home-remedies-for-toothache/",
    "https://www.1mg.com/articles/home-remedies-for-indigestion/",
    "https://www.1mg.com/articles/home-remedies-for-insomnia/",
    "https://www.1mg.com/articles/home-remedies-for-pimples/",
    "https://www.1mg.com/articles/home-remedies-for-weight-loss/",
    "https://www.1mg.com/articles/home-remedies-for-gas-and-bloating/",
    "https://www.1mg.com/articles/home-remedies-for-vomiting/",
    "https://www.1mg.com/articles/home-remedies-for-loose-motion/",
    "https://www.1mg.com/articles/home-remedies-for-dry-cough/",
    "https://www.1mg.com/articles/home-remedies-for-mouth-ulcer/",
    "https://www.1mg.com/articles/home-remedies-for-eye-infection/",
    "https://www.1mg.com/articles/home-remedies-for-ear-pain/",
    "https://www.1mg.com/articles/home-remedies-for-thyroid/",
    "https://www.1mg.com/articles/benefits-of-turmeric/",
    "https://www.1mg.com/articles/benefits-of-ginger/",
    "https://www.1mg.com/articles/benefits-of-neem/",
    "https://www.1mg.com/articles/benefits-of-tulsi/",
    "https://www.1mg.com/articles/benefits-of-ashwagandha/",
    "https://www.1mg.com/articles/benefits-of-amla/",
    "https://www.1mg.com/articles/benefits-of-triphala/",
    "https://www.1mg.com/articles/benefits-of-giloy/",
    "https://www.1mg.com/articles/benefits-of-methi/",
    "https://www.1mg.com/articles/benefits-of-brahmi/",
    "https://www.1mg.com/articles/benefits-of-karela/",
    "https://www.1mg.com/articles/benefits-of-aloe-vera/",
    "https://www.1mg.com/articles/benefits-of-ajwain/",
    "https://www.1mg.com/articles/benefits-of-jeera/",
    "https://www.1mg.com/articles/benefits-of-saunf/",
    "https://www.1mg.com/articles/9-ayurvedic-herbs-to-enhance-your-immunity/",
    "https://www.1mg.com/articles/ayurvedic-remedies-for-cold/",
    "https://www.1mg.com/articles/ayurvedic-treatment-for-diabetes/",
    "https://www.1mg.com/articles/ayurvedic-herbs-for-weight-loss/",
    "https://www.1mg.com/articles/ayurvedic-remedies-for-skin/",
]

# ─────────────────────────────────────────
# SEED LISTING PAGES — to discover more URLs
# ─────────────────────────────────────────

SEED_URLS = [
    "https://www.1mg.com/articles/home-remedies/",
    "https://www.1mg.com/articles/ayurveda/",
    "https://www.1mg.com/articles/herbs/",
]

def collect_article_links(seed_urls):
    found = set()
    for url in seed_urls:
        logger.info(f"  Scanning: {url}")
        resp = safe_get(url, HEADERS)
        if not resp:
            continue
        soup = BeautifulSoup(resp.text, "lxml")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/articles/"):
                href = "https://www.1mg.com" + href
            if "1mg.com/articles/" in href and href.count("/") >= 5:
                found.add(href.split("?")[0])
        time.sleep(DELAY)
    return list(found)


# ─────────────────────────────────────────
# TITLE EXTRACTION — fixed
# 1mg pages have a brand h1 at the top ("Tata 1mg")
# The actual article title is usually in a different element
# ─────────────────────────────────────────

# Strings that indicate a tag is the SITE header, not article title
SITE_NOISE = [
    "tata", "1mg", "capsule", "tablet", "syrup", "medicine",
    "buy", "order", "shop", "price", "mg ", "ml "
]

def is_noise_title(text: str) -> bool:
    t = text.lower()
    return any(n in t for n in SITE_NOISE) or len(text) < 10

def extract_title(soup, url: str) -> str:
    """
    Will try multiple strategies to get the real article title
    Falls back to URL slug only if everything else fails
    """

    # Strategy 1: og:title meta tag (most reliable for article pages)
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        t = og["content"].strip()
        t = re.sub(r"\s*[-|]\s*(1mg|tata).*$", "", t, flags=re.IGNORECASE).strip()
        if not is_noise_title(t):
            return t

    # Strategy 2: <title> tag, strip site suffix
    title_tag = soup.find("title")
    if title_tag:
        t = title_tag.get_text(strip=True)
        t = re.sub(r"\s*[-|]\s*(1mg|tata).*$", "", t, flags=re.IGNORECASE).strip()
        if not is_noise_title(t):
            return t

    # Strategy 3: First h1 that isn't the site brand
    for h1 in soup.find_all("h1"):
        t = h1.get_text(strip=True)
        if not is_noise_title(t):
            return t

    # Strategy 4: First h2 on the page
    h2 = soup.find("h2")
    if h2:
        t = h2.get_text(strip=True)
        if not is_noise_title(t):
            return t

    # Strategy 5: URL slug as last resort
    slug = url.rstrip("/").split("/")[-1]
    return slug.replace("-", " ").title()


# ─────────────────────────────────────────
# SECTION CLASSIFICATION
# ─────────────────────────────────────────

SECTION_MAP = {
    "symptoms":   ["symptom", "signs", "sign and symptom", "how to know",
                   "warning sign", "symptoms of"],
    "causes":     ["cause", "reason", "why does", "risk factor",
                   "what causes", "causes of"],
    "remedy":     ["remedy", "remedies", "home remedy", "home treatment",
                   "natural remedy", "treatment", "how to treat",
                   "how to cure", "management", "relief", "benefits"],
    "ingredients":["ingredient", "what you need", "you will need",
                   "things needed", "material", "require"],
    "preparation":["how to make", "preparation", "method", "procedure",
                   "steps", "directions", "how to use", "usage",
                   "how to prepare", "recipe"],
}

def classify_heading(text: str) -> str:
    h = text.lower().strip()
    for field, keywords in SECTION_MAP.items():
        if any(kw in h for kw in keywords):
            return field
    return ""

def extract_section_text(heading_tag) -> str:
    texts = []
    level = int(heading_tag.name[1])
    for sib in heading_tag.find_next_siblings():
        if sib.name in ["h1","h2","h3","h4"]:
            if int(sib.name[1]) <= level:
                break
        if sib.name in ["p","li","ul","ol","div","span"]:
            t = sib.get_text(separator=" ", strip=True)
            if t and len(t) > 10:
                texts.append(t)
    return " | ".join(texts)


# ─────────────────────────────────────────
# INGREDIENT AUTO-DETECTION
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
    "triphala", "arjuna", "shatavari", "guduchi", "manjistha",
    "kutki", "punarnava", "bhringraj", "harad", "baheda"
]

def detect_ingredients(text: str) -> str:
    tl = text.lower()
    return ", ".join(i for i in INDIAN_INGREDIENTS if i in tl)


# ─────────────────────────────────────────
# PARSE A SINGLE ARTICLE
# ─────────────────────────────────────────

def parse_article(url: str) -> dict | None:
    resp = safe_get(url, HEADERS)
    if not resp:
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    # ── Title ──────────────────────
    problem = extract_title(soup, url)

    # ── Section extraction ─────────────────
    fields = {k: [] for k in ["symptoms","causes","remedy","ingredients","preparation"]}

    for heading in soup.find_all(["h2","h3","h4"]):
        field = classify_heading(heading.get_text(strip=True))
        if field:
            text = extract_section_text(heading)
            if text:
                fields[field].append(text)

    # ── Full paragraph text as fallback ────
    all_text = " ".join(
        p.get_text(strip=True)
        for p in soup.find_all("p")
        if len(p.get_text(strip=True)) > 20
    )

    remedy_text = " | ".join(fields["remedy"]) or all_text[:800]

    if not remedy_text:
        return None

    # ── Ingredients ────────────────────────
    ingredients = " | ".join(fields["ingredients"])
    if not ingredients:
        ingredients = detect_ingredients(remedy_text + " " + all_text)

    # ── Traditional system ─────────────────
    combined_lower = (url + " " + all_text).lower()
    if "ayurveda" in combined_lower or "ayurvedic" in combined_lower:
        system = "Ayurvedic"
    elif "herb" in combined_lower:
        system = "Herbal"
    else:
        system = "Home Remedy"

    return {
        "problem":            problem,
        "symptoms":           " | ".join(fields["symptoms"]),
        "possible_causes":    " | ".join(fields["causes"]),
        "remedy":             remedy_text,
        "ingredients":        ingredients,
        "preparation":        " | ".join(fields["preparation"]),
        "traditional_system": system,
        "severity_level":     "",
        "doctor_consult":     False,
        "source":             f"1mg:{url}"
    }


# ─────────────────────────────────────────
# DEDUPLICATION — by URL (not title)
# ─────────────────────────────────────────

def deduplicate(records):
    seen = set()
    unique = []
    for r in records:
        # Use source URL as the unique key
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
    print("  SCRIPT 3 — 1mg Scraper")
    print("=" * 55)

    # Collect extra links from listing pages
    print("\n[Step 1] Collecting links from listing pages...")
    extra_links = collect_article_links(SEED_URLS)
    logger.info(f"  Found {len(extra_links)} links from listing pages")

    all_urls = list(set(extra_links + DIRECT_ARTICLE_URLS))
    logger.info(f"  Total URLs to scrape: {len(all_urls)}")

    # Scrape each article
    print(f"\n[Step 2] Scraping {len(all_urls)} articles...")
    records = []
    failed  = 0

    for i, url in enumerate(all_urls, 1):
        logger.info(f"  [{i}/{len(all_urls)}] {url}")
        record = parse_article(url)

        if record:
            records.append(record)
            logger.info(f"    ✔ problem: {record['problem'][:70]}")
            logger.info(f"      symptoms: {record['symptoms'][:60] or '(none)'}")
            logger.info(f"      ingredients: {record['ingredients'][:60] or '(none)'}")
        else:
            failed += 1
            logger.warning(f"    ✘ Skipped")

        time.sleep(DELAY)

    before = len(records)
    records = deduplicate(records)
    after   = len(records)

    # Print first record in full for manual verification
    if records:
        print("\n── Sample record (first) ──────────────────────")
        import json
        print(json.dumps(records[0], indent=2, ensure_ascii=False))
        print("───────────────────────────────────────────────")

    print(f"\n  Articles attempted  : {len(all_urls)}")
    print(f"  Successfully parsed : {before}")
    print(f"  Failed / skipped    : {failed}")
    print(f"  After dedup         : {after}")

    save_json(records, OUT_FILE)

    print("\n" + "=" * 55)
    print(f"  Output → {OUT_FILE}")
    print("=" * 55)