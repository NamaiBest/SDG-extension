"""
SCRIPT 6 — StyleCraze Home Remedies Scraper
=====================================================
"""

import os
import sys
import time
import re
import json

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing libraries. Run: pip install requests beautifulsoup4 lxml")
    sys.exit(1)

try:
    from utils import save_json, get_logger, load_config, safe_get
except ImportError:
    print("utils.py not found. Run prerequisite first.")
    sys.exit(1)


# ── Setup ─────────────────────────────────
logger   = get_logger("script_06_stylecraze")
config   = load_config()
OUT_DIR  = config["output"]["raw_website_dir"]
OUT_FILE = os.path.join(OUT_DIR, "stylecraze_remedies.json")
HEADERS  = config["scraping"]["headers"]
DELAY    = config["scraping"]["delay_between_requests_sec"]

os.makedirs(OUT_DIR, exist_ok=True)


# ─────────────────────────────────────────
# ACCESSIBILITY CHECK
# ─────────────────────────────────────────

def check_accessibility():
    test_url = "https://www.stylecraze.com/articles/home-remedies-for-cold/"
    print("\n[Pre-check] Testing StyleCraze accessibility...")
    resp = safe_get(test_url, HEADERS, timeout=10, retries=1)
    status = resp.status_code if resp else "FAILED/BLOCKED"
    print(f"  {status} | {test_url}")
    return resp is not None and resp.status_code == 200


# ─────────────────────────────────────────
# URLS
# ─────────────────────────────────────────

CATEGORY_PAGES = [
    f"https://www.stylecraze.com/articles/category/home-remedies/page/{i}/"
    for i in range(1, 11)
] + [
    f"https://www.stylecraze.com/articles/category/ayurveda/page/{i}/"
    for i in range(1, 6)
] + [
    f"https://www.stylecraze.com/articles/category/health-and-wellness/page/{i}/"
    for i in range(1, 6)
]

DIRECT_ARTICLE_URLS = [
    "https://www.stylecraze.com/articles/home-remedies-for-cold/",
    "https://www.stylecraze.com/articles/home-remedies-for-cough/",
    "https://www.stylecraze.com/articles/home-remedies-for-fever/",
    "https://www.stylecraze.com/articles/home-remedies-for-headache/",
    "https://www.stylecraze.com/articles/home-remedies-for-acidity/",
    "https://www.stylecraze.com/articles/home-remedies-for-constipation/",
    "https://www.stylecraze.com/articles/home-remedies-for-diabetes/",
    "https://www.stylecraze.com/articles/home-remedies-for-high-blood-pressure/",
    "https://www.stylecraze.com/articles/home-remedies-for-sore-throat/",
    "https://www.stylecraze.com/articles/home-remedies-for-hair-fall/",
    "https://www.stylecraze.com/articles/home-remedies-for-dandruff/",
    "https://www.stylecraze.com/articles/home-remedies-for-acne/",
    "https://www.stylecraze.com/articles/home-remedies-for-pimples/",
    "https://www.stylecraze.com/articles/home-remedies-for-dark-circles/",
    "https://www.stylecraze.com/articles/home-remedies-for-knee-pain/",
    "https://www.stylecraze.com/articles/home-remedies-for-back-pain/",
    "https://www.stylecraze.com/articles/home-remedies-for-joint-pain/",
    "https://www.stylecraze.com/articles/home-remedies-for-toothache/",
    "https://www.stylecraze.com/articles/home-remedies-for-indigestion/",
    "https://www.stylecraze.com/articles/home-remedies-for-insomnia/",
    "https://www.stylecraze.com/articles/home-remedies-for-weight-loss/",
    "https://www.stylecraze.com/articles/home-remedies-for-gas-and-bloating/",
    "https://www.stylecraze.com/articles/home-remedies-for-vomiting/",
    "https://www.stylecraze.com/articles/home-remedies-for-loose-motion/",
    "https://www.stylecraze.com/articles/home-remedies-for-dry-cough/",
    "https://www.stylecraze.com/articles/home-remedies-for-mouth-ulcer/",
    "https://www.stylecraze.com/articles/home-remedies-for-eye-infection/",
    "https://www.stylecraze.com/articles/home-remedies-for-ear-pain/",
    "https://www.stylecraze.com/articles/home-remedies-for-thyroid/",
    "https://www.stylecraze.com/articles/home-remedies-for-urinary-tract-infection/",
    "https://www.stylecraze.com/articles/home-remedies-for-oily-skin/",
    "https://www.stylecraze.com/articles/home-remedies-for-dry-skin/",
    "https://www.stylecraze.com/articles/home-remedies-for-psoriasis/",
    "https://www.stylecraze.com/articles/home-remedies-for-eczema/",
    "https://www.stylecraze.com/articles/home-remedies-for-fungal-infection/",
    "https://www.stylecraze.com/articles/home-remedies-for-dark-spots/",
    "https://www.stylecraze.com/articles/home-remedies-for-anxiety/",
    "https://www.stylecraze.com/articles/home-remedies-for-stress/",
    "https://www.stylecraze.com/articles/home-remedies-for-migraine/",
    "https://www.stylecraze.com/articles/home-remedies-for-sinusitis/",
    "https://www.stylecraze.com/articles/home-remedies-for-asthma/",
    "https://www.stylecraze.com/articles/benefits-of-turmeric/",
    "https://www.stylecraze.com/articles/benefits-of-neem/",
    "https://www.stylecraze.com/articles/benefits-of-tulsi/",
    "https://www.stylecraze.com/articles/benefits-of-ashwagandha/",
    "https://www.stylecraze.com/articles/benefits-of-amla/",
    "https://www.stylecraze.com/articles/benefits-of-giloy/",
    "https://www.stylecraze.com/articles/benefits-of-aloe-vera/",
    "https://www.stylecraze.com/articles/benefits-of-ginger/",
    "https://www.stylecraze.com/articles/benefits-of-triphala/",
    "https://www.stylecraze.com/articles/benefits-of-brahmi/",
]


# ─────────────────────────────────────────
# LINK COLLECTOR
# ─────────────────────────────────────────

def collect_article_links(category_pages):
    found = set()
    for url in category_pages:
        logger.info(f"  Scanning: {url}")
        resp = safe_get(url, HEADERS)
        if not resp:
            continue
        soup = BeautifulSoup(resp.text, "lxml")
        for a in soup.find_all("a", href=True):
            href = a["href"].split("?")[0].strip()
            if href.startswith("/articles/"):
                href = "https://www.stylecraze.com" + href
            if (
                "stylecraze.com/articles/" in href
                and href.count("/") == 5
                and "/category/" not in href
                and "/tag/" not in href
            ):
                found.add(href.rstrip("/") + "/")
        logger.info(f"  {len(found)} links so far")
        time.sleep(DELAY)
    return list(found)


# ─────────────────────────────────────────
# TITLE EXTRACTION
# ─────────────────────────────────────────

SC_NOISE = ["stylecraze", "category", "tag", "page not found", "404"]

def is_noise_title(text):
    t = text.lower()
    return len(text) < 10 or any(n in t for n in SC_NOISE)

def extract_title(soup, url):
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        t = re.sub(r"\s*[-|]\s*StyleCraze.*$", "", og["content"],
                   flags=re.IGNORECASE).strip()
        if not is_noise_title(t):
            return t
    tt = soup.find("title")
    if tt:
        t = re.sub(r"\s*[-|]\s*StyleCraze.*$", "", tt.get_text(),
                   flags=re.IGNORECASE).strip()
        if not is_noise_title(t):
            return t
    for h1 in soup.find_all("h1"):
        t = h1.get_text(strip=True)
        if not is_noise_title(t):
            return t
    slug = url.rstrip("/").split("/")[-1]
    return slug.replace("-", " ").title()


# ─────────────────────────────────────────
# SECTION CLASSIFICATION
# Based on actual StyleCraze heading patterns
# observed from HTML inspection:
#
#   "Understanding X And Its Symptoms"  → symptoms
#   "Why Do You Catch/Get X"            → causes
#   "X Most Effective Home Remedies For Y" → remedy
#   "1. Ginger", "2. Turmeric" (numbered h3) → preparation
#   "When To See A Doctor"              → doctor flag
#   "How To Prevent X"                  → preparation
# ─────────────────────────────────────────

SECTION_MAP = {
    "symptoms": [
        "symptom", "signs of", "signs and symptom",
        "understanding", "its symptoms", "and symptoms",
        "how do you know", "warning sign", "types of",
        "what is ", "what are "
    ],
    "causes": [
        "cause", "what causes", "causes of",
        "why do you", "why do we", "why does",
        "why is", "reason", "risk factor",
        "triggered by", "what leads", "factors",
        "how do you get", "how do you catch"
    ],
    "remedy": [
        "home remed", "natural remed", "effective remed",
        "best remed", "top remed", "remedies for",
        "how to treat", "how to cure", "how to get rid",
        "treatment", "relief", "ways to",
        "tips for", "how to manage", "how to control"
    ],
    "preparation": [
        "how to make", "preparation", "method", "procedure",
        "how to use", "how to prepare", "how to consume",
        "how to apply", "recipe", "dosage", "how to do",
        "how to prevent", "steps to"
    ],
}

# Numbered remedy pattern: "1. Ginger", "3. Turmeric Milk" etc.
NUMBERED_HEADING = re.compile(r"^\d+\.\s+.+", re.IGNORECASE)

def classify_heading(text):
    h = text.lower().strip()
    # Numbered h3s are remedy/preparation items
    if NUMBERED_HEADING.match(text):
        return "preparation"
    for field, keywords in SECTION_MAP.items():
        if any(kw in h for kw in keywords):
            return field
    return ""


# ─────────────────────────────────────────
# SECTION TEXT EXTRACTOR
# Collects all content below a heading
# until the next heading of same/higher level
# ─────────────────────────────────────────

def extract_section_text(heading_tag):
    texts = []
    # h2=2, h3=3, h4=4 — strong/b treated as h4
    if heading_tag.name and heading_tag.name[0] == "h":
        level = int(heading_tag.name[1])
    else:
        level = 4

    for sib in heading_tag.find_next_siblings():
        sib_name = sib.name

        # Stop at equal/higher heading
        if sib_name in ["h1","h2","h3","h4","h5"]:
            if int(sib_name[1]) <= level:
                break

        if sib_name == "p":
            t = sib.get_text(separator=" ", strip=True)
            if t and len(t) > 15:
                texts.append(t)

        elif sib_name in ["ul","ol"]:
            for li in sib.find_all("li"):
                t = li.get_text(separator=" ", strip=True)
                if t and len(t) > 10:
                    texts.append(t)

        elif sib_name == "div":
            t = sib.get_text(separator=" ", strip=True)
            if t and 20 < len(t) < 2000:
                texts.append(t)

    return " | ".join(texts)


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
    "arjuna", "shatavari", "guduchi", "manjistha", "bhringraj",
    "harad", "baheda", "moringa", "karela", "bitter gourd",
    "carom seeds", "hing", "asafoetida", "curry leaves", "noni",
    "mulethi", "licorice", "rose water", "sandalwood",
    "apple cider vinegar", "baking soda", "salt water",
    "warm water", "cold compress", "steam", "chicken soup",
    "pineapple juice", "ginger tea", "herbal tea"
]

def detect_ingredients(text):
    tl = text.lower()
    return ", ".join(i for i in INDIAN_INGREDIENTS if i in tl)


# ─────────────────────────────────────────
# SEVERITY + DOCTOR FLAGS
# ─────────────────────────────────────────

def needs_doctor(text):
    keywords = [
        "consult a doctor", "see a doctor", "visit a doctor",
        "medical attention", "seek medical", "doctor immediately",
        "when to see", "emergency", "severe", "chronic"
    ]
    tl = text.lower()
    return any(k in tl for k in keywords)

def detect_severity(text):
    tl = text.lower()
    if any(w in tl for w in ["emergency","severe","critical","life-threatening"]):
        return "high"
    elif any(w in tl for w in ["chronic","persistent","moderate","recurring"]):
        return "medium"
    return "low"


# ─────────────────────────────────────────
# ARTICLE PARSER
# ─────────────────────────────────────────

NOISE_TITLES = ["stylecraze","category","tag","page not found","404","archives"]

def get_main_content(soup):
    # Try known content div classes
    for cls in ["article-body","post-content","entry-content","article-content"]:
        div = soup.find("div", class_=lambda c: c and cls in c.lower() if c else False)
        if div:
            return div
    # Fallback: div with the most paragraphs
    divs = soup.find_all("div")
    if divs:
        return max(divs, key=lambda d: len(d.find_all("p")), default=soup)
    return soup

def parse_article(url):
    resp = safe_get(url, HEADERS)
    if not resp:
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    content = get_main_content(soup)

    problem = extract_title(soup, url)
    if any(n in problem.lower() for n in NOISE_TITLES):
        return None

    # Walk ALL headings and classify each
    fields = {k: [] for k in ["symptoms","causes","remedy","preparation"]}
    # Ingredients extracted separately via detection
    numbered_items = []   # collect numbered h3 item names for ingredients

    for heading in content.find_all(["h2","h3","h4"]):
        heading_text = heading.get_text(strip=True)
        field = classify_heading(heading_text)

        if field:
            text = extract_section_text(heading)
            if text:
                fields[field].append(text)

        # Collect numbered item names (e.g. "1. Ginger") as ingredient hints
        if NUMBERED_HEADING.match(heading_text):
            # Strip the number prefix to get just the ingredient/remedy name
            name = re.sub(r"^\d+\.\s*", "", heading_text).strip()
            numbered_items.append(name)

    # Full paragraph text for fallback + ingredient detection
    all_text = " ".join(
        p.get_text(separator=" ", strip=True)
        for p in content.find_all("p")
        if len(p.get_text(strip=True)) > 20
    )

    remedy_text = " | ".join(fields["remedy"]) or all_text[:1000]
    if not remedy_text:
        return None

    # Build ingredients from:
    # 1. Numbered heading names
    # 2. Auto-detection from full text
    ingredients_from_headings = ", ".join(numbered_items) if numbered_items else ""
    ingredients_from_text     = detect_ingredients(
        remedy_text + " " + " | ".join(fields["preparation"]) + " " + all_text
    )
    # Merge both, prefer heading-derived names
    ingredients = ingredients_from_headings
    if ingredients_from_text:
        existing = set(i.lower().strip() for i in ingredients.split(",") if i.strip())
        extras   = [i for i in ingredients_from_text.split(", ")
                    if i.lower().strip() not in existing]
        if extras:
            ingredients += (", " if ingredients else "") + ", ".join(extras)

    # Traditional system
    combined = (url + " " + all_text).lower()
    if "ayurveda" in combined or "ayurvedic" in combined:
        system = "Ayurvedic"
    elif "herb" in combined or "herbal" in combined:
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
        "severity_level":     detect_severity(all_text),
        "doctor_consult":     needs_doctor(all_text),
        "source":             f"stylecraze:{url}"
    }


# ─────────────────────────────────────────
# DEDUP
# ─────────────────────────────────────────

def deduplicate(records):
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
    print("  SCRIPT 6 — StyleCraze Scraper (Fixed)")
    print("=" * 55)

    if not check_accessibility():
        print("\n⚠️  StyleCraze not accessible. Saving empty file.")
        save_json([], OUT_FILE)
        sys.exit(0)

    # Step 1: collect links
    print("\n[Step 1] Collecting article links...")
    extra_links = collect_article_links(CATEGORY_PAGES)
    all_urls = list(set(extra_links + DIRECT_ARTICLE_URLS))
    logger.info(f"  Total URLs to scrape: {len(all_urls)}")

    # Step 2: scrape
    print(f"\n[Step 2] Scraping {len(all_urls)} articles...")
    records = []
    failed  = 0

    for i, url in enumerate(all_urls, 1):
        logger.info(f"  [{i}/{len(all_urls)}] {url}")
        record = parse_article(url)
        if record:
            records.append(record)
            logger.info(f"    ✔ {record['problem'][:65]}")
            logger.info(f"      symptoms    : {record['symptoms'][:60] or '(none)'}")
            logger.info(f"      causes      : {record['possible_causes'][:60] or '(none)'}")
            logger.info(f"      ingredients : {record['ingredients'][:60] or '(none)'}")
            logger.info(f"      preparation : {record['preparation'][:60] or '(none)'}")
        else:
            failed += 1
            logger.warning(f"    ✘ Skipped")
        time.sleep(DELAY)

    before  = len(records)
    records = deduplicate(records)
    after   = len(records)

    # Sample record
    if records:
        print("\n── Sample record (first) ──────────────────────")
        print(json.dumps(records[0], indent=2, ensure_ascii=False))
        print("───────────────────────────────────────────────")

    # Fill rate summary
    if records:
        print("\n── Field fill rates ───────────────────────────")
        for f in ["symptoms","possible_causes","remedy","ingredients","preparation"]:
            filled = sum(1 for r in records if r.get(f,"").strip())
            pct    = filled / len(records) * 100
            bar    = "█" * int(pct // 10) + "░" * (10 - int(pct // 10))
            print(f"  {f:<22} {pct:>5.1f}%  {bar}")
        print("───────────────────────────────────────────────")

    print(f"\n  Articles attempted  : {len(all_urls)}")
    print(f"  Successfully parsed : {before}")
    print(f"  Failed / skipped    : {failed}")
    print(f"  After dedup         : {after}")

    save_json(records, OUT_FILE)

    print("\n" + "=" * 55)
    print(f"  Output → {OUT_FILE}")
    print("=" * 55)