# ============================================================
# Project: MindMesh
# File: intake_engine.py
# Version: 3.0
# Date: 23.03.2026
# Purpose:
# - Simple Mode intake analyzer
# - AI-first structured analysis
# - Rule-based fallback if AI is unavailable
# - Stable output format for /api/simple/analyze
# ============================================================

import os
import re
import json
from pathlib import Path
from collections import Counter

from dotenv import load_dotenv

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# ============================================================
# CONFIG LOADER (Dynamic + Cached)
# ============================================================

CONFIG_DIR = Path(__file__).parent / "intake_config"

_cached_data = {}
_cached_mtime = {}


def load_json_config(filename: str) -> set[str]:
    path = CONFIG_DIR / filename

    if not path.exists():
        return set()

    mtime = os.path.getmtime(path)

    if filename not in _cached_mtime or _cached_mtime[filename] != mtime:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        data = {str(x).strip().lower() for x in raw if str(x).strip()}
        _cached_data[filename] = data
        _cached_mtime[filename] = mtime

    return _cached_data[filename]


def get_stopwords() -> set[str]:
    ru = load_json_config("stopwords_ru.json")
    en = load_json_config("stopwords_en.json")
    he = load_json_config("stopwords_he.json")
    return ru.union(en).union(he)


def get_improvement_markers() -> set[str]:
    return load_json_config("improvement_markers.json")


# ============================================================
# SETTINGS
# ============================================================

MIN_TEXT_LENGTH = 5
MIN_TITLE_LENGTH = 4
MAX_TITLE_LENGTH = 80
MAX_SHORT_LENGTH = 240
MAX_KEYWORDS = 8

DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"

COMMON_BAD_KEYWORDS = {
    "используя", "использовать", "используется",
    "данный", "данная", "данные",
    "который", "которая", "которые",
    "можно", "нужно", "будет", "такой", "такая", "такие",
    "using", "used", "useful", "this", "that", "these", "those",
    "יכול", "יכולה", "יכולים", "שימוש", "משתמש",
}


# ============================================================
# UTILITIES
# ============================================================

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text.strip())
    return text


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"[.!?]\s+|\n+", text)
    return [normalize_text(p) for p in parts if normalize_text(p)]


def extract_words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Zа-яА-ЯёЁא-ת0-9]{4,}", text.lower())


def clean_phrase(text: str) -> str:
    text = normalize_text(text)
    return text.strip(" ,.-;:!?")


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        key = normalize_text(str(item)).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(str(item).strip())
    return result


def is_probably_bad_keyword(word: str, stopwords: set[str]) -> bool:
    if not word:
        return True
    w = word.lower().strip()
    if len(w) < 4:
        return True
    if w in stopwords:
        return True
    if w in COMMON_BAD_KEYWORDS:
        return True
    return False


def detect_language(text: str) -> str:
    if re.search(r"[א-ת]", text):
        return "he"
    if re.search(r"[а-яА-ЯёЁ]", text):
        return "ru"
    return "en"


def clamp_title(title: str, fallback: str) -> str:
    title = clean_phrase(title)
    if len(title) > MAX_TITLE_LENGTH:
        title = title[:MAX_TITLE_LENGTH].rsplit(" ", 1)[0].strip()
    if len(title) < MIN_TITLE_LENGTH:
        title = clean_phrase(fallback[:MAX_TITLE_LENGTH])
    return title


def clamp_short(short: str, fallback: str) -> str:
    short = clean_phrase(short)
    if len(short) > MAX_SHORT_LENGTH:
        short = short[:MAX_SHORT_LENGTH].rsplit(" ", 1)[0].strip()
    if len(short) < MIN_TITLE_LENGTH:
        short = clean_phrase(fallback[:MAX_SHORT_LENGTH])
    return short


def normalize_idea_type(value: str) -> str:
    if not value:
        return "Idea"

    v = value.strip().lower()

    improvement_values = {
        "improvement", "upgrade", "enhancement", "optimization",
        "modernization", "refinement", "improve", "улучшение",
        "доработка", "модернизация", "оптимизация", "усовершенствование",
        "שיפור", "שדרוג", "אופטימיזציה"
    }

    if v in improvement_values:
        return "Improvement"

    return "Idea"


# ============================================================
# RULE-BASED FALLBACK
# ============================================================

def build_title_rule_based(raw_text: str, keywords: list[str], sentences: list[str]) -> str:
    first_sentence = sentences[0] if sentences else raw_text
    first_sentence = clean_phrase(first_sentence)

    if MIN_TITLE_LENGTH <= len(first_sentence) <= MAX_TITLE_LENGTH:
        return first_sentence

    if keywords:
        joined = " ".join(keywords[:4])
        return clamp_title(joined, raw_text)

    return clamp_title(raw_text, raw_text)


def extract_keywords_rule_based(raw_text: str, stopwords: set[str]) -> list[str]:
    words = extract_words(raw_text)

    filtered = [
        w for w in words
        if not is_probably_bad_keyword(w, stopwords)
    ]

    counts = Counter(filtered)
    ranked = [word for word, _ in counts.most_common(MAX_KEYWORDS * 3)]
    ranked = dedupe_preserve_order(ranked)

    return ranked[:MAX_KEYWORDS]


def build_short_rule_based(raw_text: str, title: str, keywords: list[str], lang: str) -> str:
    keywords = keywords[:2]

    if lang == "ru":
        if len(keywords) >= 2:
            short = f"Концепция, связанная с {keywords[0]} и {keywords[1]}."
        else:
            short = f"Идея, связанная с: {title.lower()}."
    elif lang == "he":
        if len(keywords) >= 2:
            short = f"קונספט הקשור ל-{keywords[0]} ול-{keywords[1]}."
        else:
            short = f"רעיון הקשור ל-{title}."
    else:
        if len(keywords) >= 2:
            short = f"A concept related to {keywords[0]} and {keywords[1]}."
        else:
            short = f"An idea related to {title.lower()}."

    return clamp_short(short, raw_text)


def detect_idea_type_rule_based(raw_text: str, improvement_markers: set[str]) -> str:
    lowered = raw_text.lower()
    for marker in improvement_markers:
        if marker and marker in lowered:
            return "Improvement"
    return "Idea"


def analyze_with_rules(raw_text: str) -> dict:
    stopwords = get_stopwords()
    improvement_markers = get_improvement_markers()
    sentences = split_sentences(raw_text)
    lang = detect_language(raw_text)

    keywords = extract_keywords_rule_based(raw_text, stopwords)
    title = build_title_rule_based(raw_text, keywords, sentences)
    short = build_short_rule_based(raw_text, title, keywords, lang)
    idea_type = detect_idea_type_rule_based(raw_text, improvement_markers)

    confidence = min(
        0.75,
        (len(raw_text) / 600) + (len(keywords) / 25)
    )

    return {
        "title": title,
        "short": short,
        "full": raw_text,
        "raw_text": raw_text,
        "keywords": keywords[:MAX_KEYWORDS],
        "idea_type": idea_type,
        "confidence": round(confidence, 2),
        "analysis_notes": ["fallback_rule_based"]
    }


# ============================================================
# AI ANALYZER
# ============================================================

def get_openai_client():
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    print("OPENAI KEY EXISTS:", bool(api_key))
    print("OPENAI MODULE EXISTS:", OpenAI is not None)

    if not api_key:
        print("OPENAI CLIENT: no OPENAI_API_KEY")
        return None

    if OpenAI is None:
        print("OPENAI CLIENT: OpenAI import failed")
        return None

    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    print("OPENAI BASE URL:", base_url if base_url else "(default)")

    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)

    return OpenAI(api_key=api_key)


def build_ai_prompt(raw_text: str) -> str:
    return f"""
You are an idea intake analyzer for the MindMesh project.

Task:
Analyze the user's raw idea text and return STRICT JSON only.

Requirements:
1. title:
   - short and clear
   - 4 to 80 characters if possible
   - should sound like a compact project or concept title
   - do NOT simply copy the full raw text unless unavoidable

2. short:
   - one concise sentence
   - should summarize the idea more clearly than the raw text
   - must be meaningfully different from full

3. full:
   - normalized version of the original text
   - preserve the meaning
   - keep the original language

4. keywords:
   - 3 to 8 meaningful keywords or short key phrases
   - avoid filler words
   - avoid generic words like "using", "this", "idea"
   - prefer technical or semantic terms
   - keep the original language where possible

5. idea_type:
   - only "Idea" or "Improvement"

Output format:
{{
  "title": "...",
  "short": "...",
  "full": "...",
  "keywords": ["...", "..."],
  "idea_type": "Idea"
}}

User raw idea text:
\"\"\"{raw_text}\"\"\"
""".strip()


def parse_ai_json(text: str) -> dict | None:
    if not text:
        return None

    text = text.strip()

    # try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # try fenced json
    fenced = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except Exception:
            pass

    # try first JSON object
    obj = re.search(r"(\{.*\})", text, re.DOTALL)
    if obj:
        try:
            return json.loads(obj.group(1))
        except Exception as e:
          print("AI ERROR:", str(e))
          return None

    return None


def sanitize_ai_result(raw_text: str, ai_data: dict) -> dict:
    title = clamp_title(str(ai_data.get("title", "") or ""), raw_text)
    full = normalize_text(str(ai_data.get("full", "") or raw_text))
    short = clamp_short(str(ai_data.get("short", "") or ""), raw_text)

    if normalize_text(short).lower() == normalize_text(full).lower():
        # keep short different from full when possible
        short = analyze_with_rules(raw_text)["short"]

    keywords_raw = ai_data.get("keywords", [])
    if not isinstance(keywords_raw, list):
        keywords_raw = []

    keywords = []
    for item in keywords_raw:
        kw = clean_phrase(str(item))
        if kw and len(kw) >= 2:
            keywords.append(kw)

    keywords = dedupe_preserve_order(keywords)[:MAX_KEYWORDS]

    if not keywords:
        keywords = analyze_with_rules(raw_text)["keywords"]

    idea_type = normalize_idea_type(str(ai_data.get("idea_type", "") or "Idea"))

    confidence = 0.9
    if len(title) < MIN_TITLE_LENGTH or not short or not full:
        confidence = 0.65

    return {
        "title": title,
        "short": short,
        "full": full,
        "raw_text": raw_text,
        "keywords": keywords,
        "idea_type": idea_type,
        "confidence": round(confidence, 2),
        "analysis_notes": ["ai_primary"]
    }


def analyze_with_ai(raw_text: str) -> dict | None:
    client = get_openai_client()

    if client is None:
        print("AI: client is None → fallback")
        return None

    model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL
    prompt = build_ai_prompt(raw_text)

    print("OPENAI MODEL:", model)

    try:
        response = client.responses.create(
            model=model,
            input=prompt,
            temperature=0.2,
            max_output_tokens=400,
        )

        text = getattr(response, "output_text", "") or ""

        print("=== AI RAW OUTPUT START ===")
        print(text)
        print("=== AI RAW OUTPUT END ===")

        if not text.strip():
            print("AI ERROR: empty response")
            return None

        cleaned = text.replace("```json", "").replace("```", "").strip()

        try:
            parsed = json.loads(cleaned)
            print("AI PARSED OK:", parsed)
            return sanitize_ai_result(raw_text, parsed)
        except Exception as e:
            print("AI PARSE ERROR:", str(e))
            return None

    except Exception as e:
        print("AI ERROR:", str(e))
        return None


# ============================================================
# MAIN ANALYSIS FUNCTION
# ============================================================

def analyze_intake(raw_text: str) -> dict:
    raw_text = normalize_text(raw_text)

    if not raw_text or len(raw_text) < MIN_TEXT_LENGTH:
        return {"error": "Text too short"}

    # 1. AI first
    ai_result = analyze_with_ai(raw_text)
    if ai_result:
        return ai_result

    # 2. Fallback
    return analyze_with_rules(raw_text)