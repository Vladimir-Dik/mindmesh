# ============================================================
# Project: MindMesh
# File: collector_agent.py
# Version: v0.7
# Date: 2026-07-03
# Name: AI Collector Agent backend with canonical layer (extractor module)
# ============================================================

import re
import json
import csv
import io
import urllib.request
from html.parser import HTMLParser
from datetime import datetime
try:
    from source_engine.extractors.pdf_extractor import extract_pdf_text
except Exception:
    from web.source_engine.extractors.pdf_extractor import extract_pdf_text


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
        
# ============================================================
#обработка пдф переехала в модули   mindmesh\web\source_engine\extractors
# ============================================================   


# ============================================================
# Universal Source Processing Engine (универсальный движок обработки источников)
# Version: v0.1
# Date: 2026-06-22
# ============================================================

def detect_source_type(filename: str, content_type: str = "") -> str:
    lower_name = (filename or "").lower()
    content_type = (content_type or "").lower()

    if lower_name.endswith((".txt", ".md")):
        return "text"

    if lower_name.endswith(".rtf"):
        return "rtf"

    if lower_name.endswith((".html", ".htm")):
        return "html"

    if lower_name.endswith(".json"):
        return "json"

    if lower_name.endswith(".csv"):
        return "csv"

    if lower_name.endswith(".pdf") or "pdf" in content_type:
        return "pdf"

    return "unknown"


def build_source_object(
    *,
    source_kind: str,
    source_type: str,
    filename: str = "",
    content_type: str = "",
    encoding: str = "",
    text: str = "",
    raw_length: int = 0,
    warnings: list | None = None,
    metadata: dict | None = None,
    processing_state: str = "ready"
) -> dict:
    return {
        "source_kind": source_kind,
        "source_type": source_type,
        "filename": filename,
        "content_type": content_type,
        "encoding": encoding,
        "file_type": source_type,
        "text": text or "",
        "raw_length": raw_length,
        "warnings": warnings or [],
        "metadata": metadata or {},
        "images": [],
        "tables": [],
        "attachments": [],
        "processing_state": processing_state,
        "processing_log": []
    }


def extract_source_from_file(filename: str, raw: bytes, content_type: str = "") -> dict:
    source_type = detect_source_type(filename, content_type)

    if source_type in ("html", "json", "csv", "text", "rtf", "unknown"):
        decoded, encoding = decode_bytes(raw)

        if source_type == "html":
            text = html_to_text(decoded)

        elif source_type == "json":
            text = extract_json_text(decoded)

        elif source_type == "csv":
            text = extract_csv_text(decoded)

        else:
            text = clean_text(decoded)

        return build_source_object(
            source_kind="file",
            source_type=source_type,
            filename=filename,
            content_type=content_type,
            encoding=encoding,
            text=text,
            raw_length=len(text)
        )

    if source_type == "pdf":
        pdf_result = extract_pdf_text(raw)

        warnings = []
        if pdf_result.get("warning"):
            warnings.append(pdf_result.get("warning"))

        pdf_text = pdf_result.get("text", "")

        return build_source_object(
            source_kind="file",
            source_type="pdf",
            filename=filename,
            content_type=content_type,
            encoding="pdf",
            text=pdf_text,
            raw_length=len(pdf_text),
            warnings=warnings,
            metadata={
                "pdf_status": "extracted" if pdf_result.get("ok") else "needs_ocr",
                "page_count": pdf_result.get("page_count", 0)
            },
            processing_state=pdf_result.get("processing_state", "unknown")
        )

    return build_source_object(
        source_kind="file",
        source_type="unknown",
        filename=filename,
        content_type=content_type,
        encoding="unknown",
        text="",
        raw_length=0,
        warnings=[
            "Unsupported source type."
        ]
    )

#
# обработка PDF 
#

def estimate_text_quality(text: str) -> dict:
    cleaned = clean_text(text)
    if not cleaned:
        return {"ok": False, "score": 0, "reason": "empty"}

    letters = re.findall(r"[A-Za-zА-Яа-яЁёא-ת]", cleaned)
    words = re.findall(r"[A-Za-zА-Яа-яЁёא-ת]{3,}", cleaned)
    weird = re.findall(r"[#{}<>\\|_^~]{1,}", cleaned)

    letter_ratio = len(letters) / max(len(cleaned), 1)
    word_ratio = len(words) / max(len(cleaned.split()), 1)
    weird_ratio = len(weird) / max(len(cleaned), 1)

    score = 0
    if letter_ratio > 0.45:
        score += 40
    if word_ratio > 0.45:
        score += 40
    if weird_ratio < 0.02:
        score += 20

    return {
        "ok": score >= 55,
        "score": score,
        "letter_ratio": round(letter_ratio, 3),
        "word_ratio": round(word_ratio, 3),
        "weird_ratio": round(weird_ratio, 3),
        "reason": "ok" if score >= 55 else "low_quality_text"
    }


def extract_source(payload: dict, filename: str, raw: bytes, content_type: str = "") -> dict:
    return extract_source_from_file(filename, raw, content_type)


def extract_file_text(filename: str, raw: bytes, content_type: str = "") -> dict:
    # Compatibility wrapper (обёртка совместимости)
    return extract_source_from_file(filename, raw, content_type)



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

    bad_labels = {
        "ТИП ИСТОЧНИКА:",
        "ТИП ИСТОЧНИКА",
        "SOURCE TYPE:",
        "SOURCE TYPE",
        "SOURCE:",
        "SOURCE"
    }

    parts = re.split(r"[,\n;]+", raw)

    return [
        p.strip(" -•\t")
        for p in parts
        if p.strip(" -•\t")
         and p.strip(" -•\t").upper() not in bad_labels
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


# ============================================================
# Canonical Layer (канонический слой)
# Version: v0.1
# Date: 2026-06-22
# Purpose:
# - create stable multilingual concept markers
# - improve duplicate checks across RU / EN / HE
# ============================================================

CANONICAL_CONCEPT_MAP = {
    "energy_tower": {
        "label_en": "energy tower",
        "variants": [
            "энергетическая башня",
            "солнечная башня",
            "аэродинамическая башня",
            "energy tower",
            "solar tower",
            "solar updraft tower",
            "airflow tower",
            "מגדל אנרגיה",
            "מגדל סולארי"
        ]
    },
    "updraft_airflow": {
        "label_en": "controlled upward airflow",
        "variants": [
            "восходящий поток",
            "восходящие потоки",
            "вертикальный воздушный поток",
            "термический поток",
            "updraft",
            "upward airflow",
            "vertical airflow",
            "thermal airflow",
            "rising air",
            "זרימת אוויר עולה"
        ]
    },
    "thermal_gradient": {
        "label_en": "thermal gradient",
        "variants": [
            "разница температур",
            "температурный градиент",
            "нагретый воздух",
            "тепловой поток",
            "thermal gradient",
            "temperature difference",
            "heated air",
            "thermal flow",
            "הפרש טמפרטורות"
        ]
    },
    "solar_collector": {
        "label_en": "solar collector",
        "variants": [
            "солнечный коллектор",
            "прозрачный коллектор",
            "тепличная зона",
            "solar collector",
            "transparent collector",
            "greenhouse collector",
            "חממה",
            "קולט שמש"
        ]
    },
    "turbine_generation": {
        "label_en": "turbine electricity generation",
        "variants": [
            "турбина",
            "турбины",
            "выработка электроэнергии",
            "генерация электроэнергии",
            "turbine",
            "turbines",
            "electricity generation",
            "power generation",
            "ייצור חשמל",
            "טורבינה"
        ]
    },
    "industrial_waste_heat": {
        "label_en": "industrial waste heat",
        "variants": [
            "промышленное тепло",
            "утилизация промышленного тепла",
            "избыточное промышленное тепло",
            "industrial heat",
            "waste heat",
            "industrial waste heat",
            "עודפי חום תעשייתי"
        ]
    },
    "geothermal_heating": {
        "label_en": "geothermal heating",
        "variants": [
            "геотермальный нагрев",
            "геотермальный подогрев",
            "geothermal heating",
            "geothermal heat",
            "חימום גיאותרמי"
        ]
    },
    "air_shaft": {
        "label_en": "vertical air shaft",
        "variants": [
            "воздушная шахта",
            "вертикальная шахта",
            "шахта",
            "тоннель",
            "air shaft",
            "vertical shaft",
            "mine shaft",
            "tunnel",
            "פיר אוויר",
            "מנהרה"
        ]
    },
    "renewable_energy": {
        "label_en": "renewable energy",
        "variants": [
            "возобновляемая энергетика",
            "зеленая энергетика",
            "зелёная энергетика",
            "экологичность",
            "renewable energy",
            "green energy",
            "clean energy",
            "אנרגיה מתחדשת"
        ]
    },
    "passive_generation": {
        "label_en": "passive generation",
        "variants": [
            "пассивная генерация",
            "пассивный режим",
            "малое количество движущихся частей",
            "passive generation",
            "passive operation",
            "few moving parts",
            "ייצור פסיבי"
        ]
    },
    "water_desalination": {
        "label_en": "water desalination and moisture collection",
        "variants": [
            "опреснение воды",
            "сбор атмосферной влаги",
            "desalination",
            "atmospheric moisture collection",
            "water desalination",
            "התפלת מים",
            "איסוף לחות"
        ]
    },
    "ai_flow_control": {
        "label_en": "AI flow control",
        "variants": [
            "ии управление потоками",
            "интеллектуальные заслонки",
            "распределенные датчики",
            "ai control",
            "ai flow control",
            "smart dampers",
            "distributed sensors",
            "בקרת ai"
        ]
    }
}


def normalize_canonical_text(text: str) -> str:
    text = (text or "").lower().replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9א-ת\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_canonical_tokens(text: str) -> list[str]:
    normalized = normalize_canonical_text(text)
    result = []

    if not normalized:
        return result

    for token, item in CANONICAL_CONCEPT_MAP.items():
        for variant in item.get("variants", []):
            variant_norm = normalize_canonical_text(variant)

            if variant_norm and variant_norm in normalized:
                result.append(token)
                break

    return sorted(list(set(result)))


def build_canonical_layer(
    title: str,
    short: str,
    full: str,
    keywords: list[str],
    category: str
) -> dict:

    text = "\n".join([
        title or "",
        short or "",
        full[:3000] if full else "",
        ", ".join(keywords or []),
        category or ""
    ])

    tokens = extract_canonical_tokens(text)

    labels = [
        CANONICAL_CONCEPT_MAP[token]["label_en"]
        for token in tokens
        if token in CANONICAL_CONCEPT_MAP
    ]

    canonical_title_en = title or "Untitled idea"

    if labels:
        canonical_summary_en = (
            "Idea concept: " +
            ", ".join(labels) +
            ". Source text describes a technical or project concept with these stable cross-language markers."
        )
    else:
        canonical_summary_en = (
            "Idea concept: " +
            clean_text((short or full or title or "")[:700])
        )

    return {
        "canonical_title_en": canonical_title_en,
        "canonical_summary_en": canonical_summary_en[:1200],
        "canonical_keywords_en": labels,
        "canonical_tokens": tokens,
        "embedding_model": "mindmesh-canonical-v0.1"
    }


def build_analysis_text(cleaned_text: str, sections: dict) -> str:
    parts = []

    for key in ("title", "short", "full", "keywords", "category", "existing_analogues", "notes"):
        value = sections.get(key)

        if value:
            parts.append(value)

    if parts:
        return clean_text("\n\n".join(parts))

    return cleaned_text

# ============================================================
# Name: Idea Candidate Extraction (извлечение кандидатов идей)
# Version: v0.1
# Date: 2026-07-01
# ============================================================

def extract_idea_candidates_from_document(text: str, meta: dict | None = None) -> list[dict]:
    cleaned = clean_text(text)
    meta = meta or {}

    if not cleaned:
        return []

    # Делим PDF по маркерам страниц, которые добавляет extract_pdf_text()
    chunks = re.split(r"--- PDF PAGE \d+ ---", cleaned)

    candidates = []

    markers = [
        "устройство",
        "схема",
        "конструкция",
        "изобретение",
        "станция",
        "машина",
        "приемник",
        "приёмник",
        "передатчик",
        "модель",
        "чертеж",
        "чертёж",
        "двигатель",
        "энергия",
        "электро",
        "автомат",
        "радио",
        "технология",
        "производство",
        "завод",
        "генератор",
        "лаборатория",
        "опыт",
        "эксперимент"
    ]

    for index, chunk in enumerate(chunks, start=1):
        chunk_clean = clean_text(chunk)

        if len(chunk_clean) < 300:
            continue

        low = chunk_clean.lower()

        score = 0
        found_markers = []

        for marker in markers:
            if marker in low:
                score += 1
                found_markers.append(marker)

        if score < 2:
            continue

        # Берём условный заголовок: первая нормальная строка
        lines = [
            line.strip()
            for line in chunk_clean.splitlines()
            if len(line.strip()) >= 8
        ]

        title = lines[0][:140] if lines else f"Document candidate {index}"

        candidates.append({
            "candidate_id": f"doc_candidate_{index}",
            "page_index": index,
            "title": title,
            "score": score,
            "markers": sorted(list(set(found_markers))),
            "text": chunk_clean[:2500]
        })

    candidates.sort(
        key=lambda item: item.get("score", 0),
        reverse=True
    )

    return candidates[:10]



def build_empty_result(
    source_label: str,
    source_type: str,
    instructions: str,
    session_id: str,
    meta: dict
) -> dict:

    file_type = meta.get("file_type") or meta.get("source_type") or source_type
    warnings = meta.get("warnings") or []

    reason = "No extracted text available."

    if file_type == "pdf":
       reason = "PDF contains no usable embedded text. OCR is required."

    if file_type == "pdf_scanned":
        reason = "PDF appears to be scanned. OCR is required."

    notes_ai = (
        "Collector Agent v0.6 (ИИ агент-сборщик v0.6): "
        "source detected, but no usable text was extracted. "
        f"File type: {file_type}. "
        f"Reason: {reason}. "
        f"Warnings: {', '.join(warnings)}. "
        f"Instructions: {instructions}"
    )

    return {
        "status": "empty_source",
        "agent_session_id": session_id,
        "created_at": datetime.utcnow().isoformat(),
        "log": [
            f"Source kind: {meta.get('source_kind', 'unknown')}",
            f"Source type: {file_type}",
            f"Processing state: {meta.get('processing_state', 'unknown')}",
            f"Encoding: {meta.get('encoding', 'unknown')}",
            f"Extracted text length: {meta.get('raw_length', 0)}",
            "No usable text extracted",
            reason
        ],
        "idea": {
            "title": source_label or "Unprocessed source",
            "category": "source_processing",
            "language": "unknown",
            "region": "unknown",
            "keywords": [],
            "ai_tags": [
                "collector_agent",
                "empty_source",
                file_type
            ],
            "short_description": reason,
            "full_description": "",
            "existing_analogues": "",
            "notes_ai": notes_ai,
            "patentability": "unknown",
            "source": source_label,
            "ai_review_status": "draft",
            "canonical_title_en": source_label or "Unprocessed source",
            "canonical_summary_en": reason,
            "canonical_keywords_en": [],
            "vector_embedding": "[]",
            "embedding_model": "none"
        },
        "raw": {
            "original_text": "",
            "cleaned_text": "",
            "analysis_text": "",
            "sections": {},
            "analysis": {},
            "canonical_layer": {},
            "source_meta": meta
        }
    }

# ============================================================
# Name: Document Candidates Result (результат поиска идей в документе)
# Version: v0.1
# Date: 2026-07-02
# ============================================================

def build_document_candidates_result(
    source_label: str,
    source_type: str,
    instructions: str,
    session_id: str,
    meta: dict,
    candidates: list
) -> dict:

    preview = []

    for item in candidates:
        preview.append({
            "candidate_id": item["candidate_id"],
            "page": item["page_index"],
            "title": item["title"],
            "score": item["score"],
            "markers": item["markers"]
        })

    return {
        "status": "idea_candidates",

        "agent_session_id": session_id,

        "created_at": datetime.utcnow().isoformat(),

        "log": [
            f"Source kind: {meta.get('source_kind','unknown')}",
            f"Source type: {source_type}",
            f"Candidates found: {len(candidates)}",
            "Document contains multiple possible ideas."
        ],

        "idea": {
            "title": source_label,
            "category": "multi_document",
            "language": "unknown",
            "region": "unknown",

            "keywords": [],

            "ai_tags": [
                "collector_agent",
                "multi_document",
                "idea_candidates"
            ],

            "short_description":
                f"Найдено {len(candidates)} возможных идей.",

            "full_description":
                "Документ содержит несколько независимых материалов.",

            "existing_analogues": "",

            "notes_ai":
                "Collector Agent обнаружил несколько возможных идей. "
                "Необходимо выбрать материал для анализа.",

            "patentability": "unknown",

            "source": source_label,

            "ai_review_status": "candidate_selection",

            "canonical_title_en":
                "Multiple idea candidates",

            "canonical_summary_en":
                f"{len(candidates)} possible ideas detected.",

            "canonical_keywords_en": [],

            "vector_embedding": "[]",

            "embedding_model": "none"
        },

        "raw": {
            "idea_candidates": candidates,
            "preview": preview,
            "source_meta": meta
        }
    }


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

    canonical_layer = build_canonical_layer(
        title=title,
        short=short,
        full=full,
        keywords=keywords,
        category=category
    )

    canonical_tags = [
        f"canon:{token}"
        for token in canonical_layer.get("canonical_tokens", [])
    ]

    for tag in canonical_tags:
        if tag not in ai_tags:
            ai_tags.append(tag)

    notes_ai = (
        "Collector Agent v0.6 (ИИ агент-сборщик v0.6): "
        "source extracted, cleaned, passed through Simple Intake Engine, "
        "canonical cross-language layer prepared. "
        f"Canonical summary EN: {canonical_layer.get('canonical_summary_en', '')}. "
        f"Canonical tokens: {', '.join(canonical_layer.get('canonical_tokens', []))}. "
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
            f"Canonical tokens: {', '.join(canonical_layer.get('canonical_tokens', [])) if canonical_layer.get('canonical_tokens') else 'none'}",
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
            "ai_review_status": "draft",
            "canonical_title_en": canonical_layer.get("canonical_title_en"),
            "canonical_summary_en": canonical_layer.get("canonical_summary_en"),
            "canonical_keywords_en": canonical_layer.get("canonical_keywords_en"),
            "vector_embedding": json.dumps(
                canonical_layer.get("canonical_tokens", []),
                ensure_ascii=False
            ),
            "embedding_model": canonical_layer.get("embedding_model")
        },
        "raw": {
            "original_text": original_text[:12000],
            "cleaned_text": cleaned_text[:12000],
            "analysis_text": analysis_text[:12000],
            "sections": sections,
            "analysis": analysis,
            "canonical_layer": canonical_layer
        }
    }


def build_collector_result(payload: dict) -> dict:
    source_url = payload.get("source_url", "")
    source_type = payload.get("source_type", "website")
    instructions = payload.get("instructions", "")
    session_id = payload.get("agent_session_id", "")

    fetched = fetch_url_text(source_url)

    if extracted.get("file_type") == "pdf":
        candidates = extract_idea_candidates_from_document(
            extracted_text,
            extracted.get("metadata", {})
        )

        if candidates:
            extracted["metadata"]["idea_candidates"] = candidates
            extracted["processing_state"] = "idea_candidates_found"

            return build_document_candidates_result(
                source_label=filename,
                source_type=real_source_type,
                instructions=instructions,
                session_id=session_id,
                meta=extracted,
                candidates=candidates
            )

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

    extracted = extract_source(payload, filename, raw, content_type)

    real_source_type = (
        extracted.get("file_type")
        or extracted.get("source_type")
        or source_type
    )

    extracted_text = clean_text(extracted.get("text", ""))

    if not extracted_text:
        return build_empty_result(
            source_label=filename,
            source_type=real_source_type,
            instructions=instructions,
            session_id=session_id,
            meta=extracted
        )

    quality = estimate_text_quality(extracted_text)

    if extracted.get("file_type") == "pdf" and not quality.get("ok"):
        extracted["warnings"].append(
            "PDF text was extracted, but quality is too low for reliable idea analysis."
        )
        extracted["metadata"]["text_quality"] = quality
        extracted["processing_state"] = "low_quality_text"

        return build_empty_result(
            source_label=filename,
            source_type=real_source_type,
            instructions=instructions,
            session_id=session_id,
            meta=extracted
        )

    if extracted.get("file_type") == "pdf":
        candidates = extract_idea_candidates_from_document(
            extracted_text,
            extracted.get("metadata", {})
        )

        if candidates:
            extracted["metadata"]["idea_candidates"] = candidates
            extracted["processing_state"] = "idea_candidates_found"

            return build_document_candidates_result(
                source_label=filename,
                source_type=real_source_type,
                instructions=instructions,
                session_id=session_id,
                meta=extracted,
                candidates=candidates
            )

    return build_result_from_text(
        text=extracted["text"],
        source_label=filename,
        source_type=real_source_type,
        instructions=instructions,
        session_id=session_id,
        meta=extracted
    )