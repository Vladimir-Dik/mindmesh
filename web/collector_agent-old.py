# ============================================================
# Project: MindMesh
# File: collector_agent.py
# Version: v0.4
# Date: 2026-05-12
# Name: AI Collector Agent backend (бэкенд ИИ-агента сборщика)
# ============================================================

import re
import json
import csv
import io
import urllib.request
from html.parser import HTMLParser
from datetime import datetime

try:
    from intake_engine import analyze_intake
except Exception:
    from web.intake_engine import analyze_intake


class TextExtractor(HTMLParser):

    def __init__(self):
        super().__init__()
        self.skip = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in ("script", "style", "noscript", "svg"):
            self.skip = True

    def handle_endtag(self, tag):
        if tag.lower() in ("script", "style", "noscript", "svg"):
            self.skip = False

    def handle_data(self, data):
        if not self.skip:
            text = data.strip()
            if text:
                self.parts.append(text)


def clean_text(text: str) -> str:
    text = text or ""
    text = text.replace("\r\n", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def decode_bytes(raw: bytes) -> tuple[str, str]:
    encodings = ["utf-8", "cp1251", "koi8-r", "windows-1255", "iso-8859-1"]

    for enc in encodings:
        try:
            return raw.decode(enc), enc
        except Exception:
            pass

    return raw.decode("utf-8", errors="ignore"), "utf-8-ignore"


def html_to_text(html: str) -> str:
    parser = TextExtractor()
    parser.feed(html)
    return clean_text("\n".join(parser.parts))


def fetch_url_text(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "MindMesh Collector Agent v0.4"}
    )

    with urllib.request.urlopen(req, timeout=15) as response:
        raw = response.read()
        content_type = response.headers.get("Content-Type", "")

    decoded, encoding = decode_bytes(raw)

    if "html" in content_type.lower() or "<html" in decoded.lower():
        text = html_to_text(decoded)
    else:
        text = clean_text(decoded)

    return {
        "source_kind": "url",
        "content_type": content_type,
        "encoding": encoding,
        "text": text,
        "raw_length": len(text)
    }


def extract_csv_text(text: str) -> str:
    output = []
    reader = csv.reader(io.StringIO(text))

    for row in reader:
        output.append(" | ".join(row))

    return clean_text("\n".join(output))


def extract_json_text(text: str) -> str:
    try:
        data = json.loads(text)
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception:
        return text


def extract_file_text(filename: str, raw: bytes, content_type: str = "") -> dict:
    decoded, encoding = decode_bytes(raw)

    lower_name = (filename or "").lower()

    if lower_name.endswith((".html", ".htm")):
        text = html_to_text(decoded)
        file_type = "html"

    elif lower_name.endswith(".json"):
        text = extract_json_text(decoded)
        file_type = "json"

    elif lower_name.endswith(".csv"):
        text = extract_csv_text(decoded)
        file_type = "csv"

    elif lower_name.endswith((".txt", ".md", ".rtf")):
        text = clean_text(decoded)
        file_type = "text"

    else:
        text = clean_text(decoded)
        file_type = "unknown_text_attempt"

    return {
        "source_kind": "file",
        "filename": filename,
        "content_type": content_type,
        "encoding": encoding,
        "file_type": file_type,
        "text": text,
        "raw_length": len(text)
    }


def remove_technical_header(text: str) -> str:
    lines = text.splitlines()
    result = []
    skip_meta = True

    for line in lines:
        stripped = line.strip()

        if skip_meta:
            if not stripped:
                continue

            if set(stripped) == {"="}:
                continue

            if re.match(r"^(Project|File|Version|Date|Name):", stripped, re.IGNORECASE):
                continue

            skip_meta = False

        result.append(line)

    return clean_text("\n".join(result))


def extract_labeled_sections(text: str) -> dict:
    labels = {
        "title": [
            "НАЗВАНИЕ ИДЕИ",
            "IDEA TITLE",
            "TITLE"
        ],
        "short": [
            "КРАТКОЕ ОПИСАНИЕ",
            "SHORT DESCRIPTION"
        ],
        "full": [
            "ПОЛНОЕ ОПИСАНИЕ",
            "FULL DESCRIPTION"
        ],
        "category": [
            "КАТЕГОРИЯ",
            "CATEGORY"
        ],
        "keywords": [
            "КЛЮЧЕВЫЕ СЛОВА",
            "KEYWORDS"
        ],
        "region": [
            "РЕГИОН",
            "REGION"
        ],
        "language": [
            "ЯЗЫК",
            "LANGUAGE"
        ],
        "existing_analogues": [
            "СУЩЕСТВУЮЩИЕ АНАЛОГИ",
            "EXISTING ANALOGUES"
        ],
        "patentability": [
            "ПАТЕНТНАЯ ПЕРСПЕКТИВА",
            "PATENTABILITY"
        ],
        "notes": [
            "ЗАМЕТКИ",
            "NOTES"
        ],
        "ai_tags": [
            "ВОЗМОЖНЫЕ AI TAGS",
            "POSSIBLE AI TAGS"
        ],
        "source": [
            "ИСТОЧНИК",
            "SOURCE"
        ]
    }

    label_to_key = {}

    for key, variants in labels.items():
        for variant in variants:
            label_to_key[variant.upper()] = key

    found = []

    for match in re.finditer(r"^([A-ZА-ЯЁ0-9 _\-]+):\s*$", text, flags=re.MULTILINE):
        raw_label = match.group(1).strip().upper()

        if raw_label in label_to_key:
            found.append({
                "key": label_to_key[raw_label],
                "start": match.end(),
                "label_start": match.start()
            })

    sections = {}

    for index, item in enumerate(found):
        start = item["start"]
        end = found[index + 1]["label_start"] if index + 1 < len(found) else len(text)

        value = clean_text(text[start:end])

        if value:
            sections[item["key"]] = value

    return sections


def split_keywords(value) -> list[str]:
    if not value:
        return []

    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]

    raw = str(value)

    parts = re.split(r"[,\n;]+", raw)

    return [
        p.strip(" -•\t")
        for p in parts
        if p.strip(" -•\t")
    ]


def normalize_language(value: str, fallback: str = "unknown") -> str:
    value = (value or "").strip().lower()

    if value in ("русский", "ru", "russian"):
        return "ru"

    if value in ("english", "английский", "en"):
        return "en"

    if value in ("hebrew", "иврит", "he"):
        return "he"

    return fallback


def build_analysis_text(cleaned_text: str, sections: dict) -> str:
    parts = []

    for key in ("title", "short", "full", "keywords", "category", "existing_analogues", "notes"):
        value = sections.get(key)

        if value:
            parts.append(value)

    if parts:
        return clean_text("\n\n".join(parts))

    return cleaned_text


def build_result_from_text(
    text: str,
    source_label: str,
    source_type: str,
    instructions: str,
    session_id: str,
    meta: dict
) -> dict:

    original_text = clean_text(text)
    cleaned_text = remove_technical_header(original_text)
    sections = extract_labeled_sections(cleaned_text)

    analysis_text = build_analysis_text(cleaned_text, sections)

    analysis = analyze_intake(analysis_text)

    if isinstance(analysis, dict) and analysis.get("error"):
        analysis = {
            "title": sections.get("title") or source_label or "Collector draft",
            "short": sections.get("short") or cleaned_text[:400],
            "full": sections.get("full") or cleaned_text,
            "keywords": split_keywords(sections.get("keywords")),
            "analysis_notes": ["collector_fallback_no_intake"]
        }

    title = sections.get("title") or analysis.get("title") or source_label or "Collector draft"
    short = sections.get("short") or analysis.get("short") or cleaned_text[:600]
    full = sections.get("full") or analysis.get("full") or cleaned_text

    keywords = split_keywords(sections.get("keywords")) or analysis.get("keywords") or []

    category = sections.get("category") or "unknown"
    region = sections.get("region") or "unknown"

    language = normalize_language(
        sections.get("language"),
        analysis.get("language") or "unknown"
    )

    existing_analogues = sections.get("existing_analogues") or ""
    patentability = sections.get("patentability") or "unknown"

    ai_tags = split_keywords(sections.get("ai_tags"))

    if not ai_tags:
        ai_tags = [
            "collector_agent",
            source_type,
            meta.get("source_kind", "source")
        ]

    notes_ai = (
        "Collector Agent v0.4 (ИИ агент-сборщик v0.4): "
        "source extracted, cleaned, passed through Simple Intake Engine. "
        f"Analysis notes: {', '.join(analysis.get('analysis_notes', []))}. "
        f"Instructions: {instructions}"
    )

    return {
        "status": "ok",
        "agent_session_id": session_id,
        "created_at": datetime.utcnow().isoformat(),
        "log": [
            f"Source kind: {meta.get('source_kind', 'unknown')}",
            f"Source type: {source_type}",
            f"Encoding: {meta.get('encoding', 'unknown')}",
            f"Extracted text length: {meta.get('raw_length', 0)}",
            f"Structured sections: {', '.join(sections.keys()) if sections else 'none'}",
            "Simple Intake Engine applied",
            "Draft fields prepared"
        ],
        "idea": {
            "title": title[:180],
            "category": category,
            "language": language,
            "region": region,
            "keywords": keywords,
            "ai_tags": ai_tags,
            "short_description": short[:1200],
            "full_description": full[:8000],
            "existing_analogues": existing_analogues,
            "notes_ai": notes_ai,
            "patentability": patentability,
            "source": source_label,
            "ai_review_status": "draft"
        },
        "raw": {
            "original_text": original_text[:12000],
            "cleaned_text": cleaned_text[:12000],
            "analysis_text": analysis_text[:12000],
            "sections": sections,
            "analysis": analysis
        }
    }


def build_collector_result(payload: dict) -> dict:
    source_url = payload.get("source_url", "")
    source_type = payload.get("source_type", "website")
    instructions = payload.get("instructions", "")
    session_id = payload.get("agent_session_id", "")

    fetched = fetch_url_text(source_url)

    return build_result_from_text(
        text=fetched["text"],
        source_label=source_url,
        source_type=source_type,
        instructions=instructions,
        session_id=session_id,
        meta=fetched
    )


def build_collector_result_from_file(
    payload: dict,
    filename: str,
    raw: bytes,
    content_type: str = ""
) -> dict:

    source_type = payload.get("source_type", "file")
    instructions = payload.get("instructions", "")
    session_id = payload.get("agent_session_id", "")

    extracted = extract_file_text(filename, raw, content_type)

    return build_result_from_text(
        text=extracted["text"],
        source_label=filename,
        source_type=source_type,
        instructions=instructions,
        session_id=session_id,
        meta=extracted
    )