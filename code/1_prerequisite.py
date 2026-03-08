"""
SCRIPT 1 — Setup & Shared Utilities
====================================
- install dependencies: pip install requests beautifulsoup4 lxml datasets pdfplumber youtube-transcript-api
- Creates the required folder structure
- Writes a config file (config.json) you can edit
- Creates utils.py — a shared helper module imported by all future scripts
- Runs a quick dependency check to check what's missing before execution
"""

import os
import sys
import json
import importlib


# ─────────────────────────────────────────
# 1. FOLDER STRUCTURE
# ─────────────────────────────────────────

FOLDERS = [
    "data/raw/websites",
    "data/raw/reddit",
    "data/raw/youtube",
    "data/raw/pdfs",
    "data/raw/huggingface",
    "data/processed",
    "data/final",
    "logs",
    "scripts",
]

def create_folders():
    print("\nCreating folder structure")
    for folder in FOLDERS:
        os.makedirs(folder, exist_ok=True)
        print(f"   ✔ {folder}")
    print("Done\n")


# ─────────────────────────────────────────
# 2. CONFIG FILE
# ─────────────────────────────────────────

CONFIG = {
    "project_name": "Indian Home Remedies Dataset",
    "version": "1.0",

    "reddit": {
        "client_id": "YOUR_CLIENT_ID",
        "client_secret": "YOUR_CLIENT_SECRET",
        "user_agent": "remedy-scraper-bot/1.0",
        "subreddits": [
            "Ayurveda",
            "IndianFood",
            "india",
            "HomeRemedies",
            "herbalism",
            "desi"
        ],
        "post_limit": 500,
        "search_keywords": [
            "home remedy",
            "dadi ke nuskhe",
            "nani ka nuskha",
            "turmeric milk",
            "kadha recipe",
            "ayurvedic remedy",
            "Indian kitchen remedy",
            "herbal remedy",
            "natural cure"
        ]
    },

    "scraping": {
        "delay_between_requests_sec": 2,
        "max_retries": 3,
        "timeout_sec": 15,
        "headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        }
    },

    "output": {
        "raw_website_dir": "data/raw/websites",
        "raw_reddit_dir": "data/raw/reddit",
        "raw_youtube_dir": "data/raw/youtube",
        "raw_pdf_dir": "data/raw/pdfs",
        "raw_hf_dir": "data/raw/huggingface",
        "processed_dir": "data/processed",
        "final_dir": "data/final",
        "final_filename": "indian_home_remedies_final.json"
    }
}

def write_config():
    config_path = "config.json"
    if os.path.exists(config_path):
        print(f"config.json already exists — skipping overwrite to preserve your settings.")
    else:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(CONFIG, f, indent=2)
        print(f"config.json written.\n")
        print("IMPORTANT: Open config.json and fill in your Reddit credentials")
        print("before running Script 7 (Reddit scraper).\n")


# ─────────────────────────────────────────
# 3. SHARED UTILS MODULE
# ─────────────────────────────────────────

UTILS_CODE = '''"""
utils.py — Shared helper functions used by all scripts
"""

import os
import json
import time
import logging
import requests
from datetime import datetime


# ── Logging ──────────────────────────────

def get_logger(name: str, log_dir: str = "logs") -> logging.Logger:
    """Returns a logger that writes to both console and a log file"""
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # Console
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # File
        log_file = os.path.join(log_dir, f"{name}_{datetime.now().strftime(\'%Y%m%d\')}.log")
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.INFO)

        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
        ch.setFormatter(fmt)
        fh.setFormatter(fmt)

        logger.addHandler(ch)
        logger.addHandler(fh)

    return logger


# ── Config loader ─────────────────────────

def load_config(path: str = "config.json") -> dict:
    """Loads the config file."""
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"config.json not found. Run prerequisite first"
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── HTTP request with retry ───────────────

def safe_get(url: str, headers: dict, timeout: int = 15, retries: int = 3, delay: float = 2.0):
    """
    Makes a GET request with automatic retry on failure.
    Returns a requests.Response or None on total failure.
    """
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                return response
            elif response.status_code == 429:
                wait = delay * attempt * 3
                print(f"   Rate limited. Waiting {wait}s before retry {attempt}...")
                time.sleep(wait)
            elif response.status_code in (403, 404):
                print(f"   HTTP {response.status_code} for {url} — skipping.")
                return None
            else:
                print(f"   HTTP {response.status_code} on attempt {attempt} for {url}")
                time.sleep(delay)
        except requests.exceptions.Timeout:
            print(f"   Timeout on attempt {attempt} for {url}")
            time.sleep(delay)
        except requests.exceptions.ConnectionError:
            print(f"   Connection error on attempt {attempt} for {url}")
            time.sleep(delay * 2)
    return None


# ── JSON save / load ──────────────────────

def save_json(data, filepath: str):
    """Saves a list or dict to a JSON file, creating directories as needed."""
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"   ✔ Saved {len(data) if isinstance(data, list) else 1} records → {filepath}")


def load_json(filepath: str):
    """Loads a JSON file. Returns empty list if file doesn\'t exist"""
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Deduplication ─────────────────────────

def deduplicate(records: list, key: str = "problem") -> list:
    """
    Removes duplicate records based on a given key.
    Keeps the first occurrence.
    """
    seen = set()
    unique = []
    for record in records:
        val = record.get(key, "").strip().lower()
        if val and val not in seen:
            seen.add(val)
            unique.append(record)
    return unique


# ── Progress display ──────────────────────

def print_progress(current: int, total: int, label: str = ""):
    bar_len = 30
    filled = int(bar_len * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\\r   [{bar}] {current}/{total} {label}", end="", flush=True)
    if current == total:
        print()
'''

def write_utils():
    utils_path = "utils.py"
    if os.path.exists(utils_path):
        print("utils.py already exists, skipping overwrite")
    else:
        with open(utils_path, "w", encoding="utf-8") as f:
            f.write(UTILS_CODE)
        print("utils.py written\n")


# ─────────────────────────────────────────
# 4. DEPENDENCY CHECK
# ─────────────────────────────────────────

REQUIRED = {
    "requests":               "pip install requests",
    "bs4":                    "pip install beautifulsoup4",
    "lxml":                   "pip install lxml",
    "praw":                   "pip install praw",
    "pandas":                 "pip install pandas",
    "youtube_transcript_api": "pip install youtube-transcript-api",
    "pdfplumber":             "pip install pdfplumber",
}

def check_dependencies():
    print("Checking dependencies...\n")
    all_good = True
    for module, install_cmd in REQUIRED.items():
        try:
            importlib.import_module(module)
            print(f"   ✅ {module}")
        except ImportError:
            print(f"   ❌ {module} — not found. Install with: {install_cmd}")
            all_good = False
    if all_good:
        print("\nAll dependencies satisfied. You're ready to run the scrapers\n")
    else:
        print("\nSome libraries are missing. Install them before proceeding\n")


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("  Setup")
    print("=" * 55)

    create_folders()
    write_config()
    write_utils()
    check_dependencies()

    print("=" * 55)
    print("  Setup complete")
    print("=" * 55)