# ============================================================
# MindMesh
# File: intake_engine.py
# MindMesh Version: 2.0
# File Version: 1.2
# Date: 15.02.2026
#
# Purpose:
# - Lightweight intake analyzer
# - Dynamic wordlist loading (JSON)
# - Auto-reload on config change
# - Ready for admin editing in future
# ============================================================

import re
import json
import os
from pathlib import Path
from collections import Counter

# ============================================================
# CONFIG LOADER (Dynamic + Cached)
# ============================================================

CONFIG_DIR = Path(__file__).parent / "intake_config"

_cached_data = {}
_cached_mtime = {}

def load_json_config(filename):
    path = CONFIG_DIR / filename

    if not path.exists():
        return set()

    mtime = os.path.getmtime(path)

    if filename not in _cached_mtime or _cached_mtime[filename] != mtime:
        with open(path, encoding="utf-8") as f:
            data = set(json.load(f))

        _cached_data[filename] = data
        _cached_mtime[filename] = mtime

    return _cached_data[filename]


def get_stopwords():
    ru = load_json_config("stopwords_ru.json")
    en = load_json_config("stopwords_en.json")
    he = load_json_config("stopwords_he.json")
    return ru.union(en).union(he)


def get_improvement_markers():
    return load_json_config("improvement_markers.json")

# ============================================================
# ANALYSIS SETTINGS
# ============================================================

MIN_TITLE_LENGTH = 4
MAX_TITLE_LENGTH = 80
MAX_SHORT_LENGTH = 250
MAX_KEYWORDS = 10

# ============================================================
# UTILITIES
# ============================================================

def normalize_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip())

def split_sentences(text: str) -> list[str]:
    return re.split(r"[.!?]\s+", text)

def extract_words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Zа-яА-Яא-ת]{4,}", text.lower())

# ============================================================
# MAIN ANALYSIS FUNCTION
# ============================================================

def analyze_intake(raw_text: str) -> dict:

    raw_text = normalize_text(raw_text)

    if not raw_text or len(raw_text) < 5:
        return {"error": "Text too short"}

    stopwords = get_stopwords()
    improvement_markers = get_improvement_markers()

    sentences = split_sentences(raw_text)

    # ---------------- TITLE ----------------

    first_sentence = sentences[0] if sentences else raw_text
    title = first_sentence.strip()

    if len(title) > MAX_TITLE_LENGTH:
        title = title[:MAX_TITLE_LENGTH].rsplit(" ", 1)[0]

    if len(title) < MIN_TITLE_LENGTH:
        title = raw_text[:MAX_TITLE_LENGTH]

    title = title.rstrip(".!?")

    # ---------------- SHORT ----------------

    short = raw_text[:MAX_SHORT_LENGTH]
    if len(raw_text) > MAX_SHORT_LENGTH:
        short = short.rsplit(" ", 1)[0]

    # ---------------- KEYWORDS ----------------

    words = extract_words(raw_text)

    filtered = [
        w for w in words
        if w not in stopwords and w not in improvement_markers
    ]

    word_counts = Counter(filtered)

    keywords = [
        word for word, _ in word_counts.most_common(MAX_KEYWORDS)
    ]

    # ---------------- IDEA TYPE ----------------

    idea_type = "Idea"

    for marker in improvement_markers:
        if marker in raw_text.lower():
            idea_type = "Improvement"
            break

    # ---------------- CONFIDENCE ----------------

    confidence = min(
        1.0,
        (len(raw_text) / 500) + (len(keywords) / 20)
    )

    return {
        "title": title,
        "short": short,
        "full": raw_text,
        "raw_text": raw_text,  # 🔥 ВАЖНО
        "keywords": keywords,
        "idea_type": idea_type,
        "confidence": round(confidence, 2),
        "analysis_notes": []
    }
