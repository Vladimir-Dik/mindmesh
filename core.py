# ============================================================
# MindMesh
# File: core.py
# Version: 1.7
# Date: 19.02.2026
# Purpose:
# - Users
# - Ideas
# - Correct Airtable link handling
# - Password update support (bcrypt)
# - Users list
# ============================================================

import os
import re
import requests
import difflib
import datetime
import bcrypt
import json
class AirtableTemporaryUnavailable(Exception):
    pass
from dotenv import load_dotenv


# ============================================================
# ENV
# ============================================================

def load_env():
    load_dotenv()

    token = os.getenv("AIRTABLE_TOKEN")
    base_id = os.getenv("AIRTABLE_BASE_ID")
    ideas_table = os.getenv("AIRTABLE_TABLE_ID")
    users_table = os.getenv("AIRTABLE_USERS_TABLE_ID")

    if not token or not base_id or not ideas_table or not users_table:
        raise RuntimeError("Missing Airtable env vars")

    return {
        "token": token,
        "base_id": base_id,
        "ideas_table": ideas_table,
        "users_table": users_table
    }


def airtable_headers(pat):
    return {
        "Authorization": f"Bearer {pat['token']}",
        "Content-Type": "application/json"
    }


# ============================================================
# USERS
# ============================================================

def users_url(pat):
    return f"https://api.airtable.com/v0/{pat['base_id']}/{pat['users_table']}"

# USERS email
def find_user_by_email(email: str):
    pat = load_env()
    url = users_url(pat)
    headers = airtable_headers(pat)

    formula = f"{{Email}}='{email}'"

    try:
        r = requests.get(
            url,
            headers=headers,
            params={"filterByFormula": formula},
            timeout=20
        )

        # Временные ошибки Airtable / сети
        if r.status_code == 429 or r.status_code in [500, 502, 503, 504]:
            raise AirtableTemporaryUnavailable(
                f"Airtable temporary unavailable: HTTP {r.status_code}"
            )

        r.raise_for_status()

        records = r.json().get("records", [])
        return records[0] if records else None

    except requests.exceptions.Timeout as e:
        raise AirtableTemporaryUnavailable("Airtable timeout") from e

    except requests.exceptions.ConnectionError as e:
        raise AirtableTemporaryUnavailable("Airtable connection error") from e

    except requests.exceptions.HTTPError as e:
        status = None
        if getattr(e, "response", None) is not None:
            status = e.response.status_code

        if status == 429 or status in [500, 502, 503, 504]:
            raise AirtableTemporaryUnavailable(
                f"Airtable temporary unavailable: HTTP {status}"
            ) from e

        raise

    except requests.exceptions.RequestException as e:
        raise AirtableTemporaryUnavailable("Airtable request failed") from e


def get_user_by_id(user_id: str):
    pat = load_env()
    url = f"{users_url(pat)}/{user_id}"
    headers = airtable_headers(pat)

    r = requests.get(url, headers=headers, timeout=20)
    if not r.ok:
        return None
    return r.json()


def create_user(name: str, email: str, password: str | None = None):
    pat = load_env()
    url = users_url(pat)
    headers = airtable_headers(pat)

    fields = {
        "Email": email,
        "Name": name,
        "Role": "user",
        "CreatedAt": datetime.datetime.utcnow().isoformat()
    }

    if password and len(password) >= 3:
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        fields["PasswordHash"] = hashed

    payload = {"fields": fields}

    r = requests.post(url, headers=headers, json=payload)
    r.raise_for_status()

    return r.json()["id"]
    
    
def get_all_users():
    pat = load_env()
    url = users_url(pat)
    headers = airtable_headers(pat)

    all_records = []
    offset = None

    while True:
        params = {}
        if offset:
            params["offset"] = offset

        r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()

        data = r.json()
        records = data.get("records", [])
        all_records.extend(records)

        offset = data.get("offset")
        if not offset:
            break

    return all_records


# ============================================================
# SET / UPDATE PASSWORD
# ============================================================

def set_user_password(user_id: str, password: str):
    """
    Sets or updates user password (bcrypt hash).
    """

    if not password or len(password) < 3:
        raise ValueError("Password too short")

    pat = load_env()
    url = f"{users_url(pat)}/{user_id}"
    headers = airtable_headers(pat)

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    payload = {
        "fields": {
            "PasswordHash": hashed
        }
    }

    r = requests.patch(url, headers=headers, json=payload)
    r.raise_for_status()

    return True


def ensure_user(email: str, name: str = ""):
    user = find_user_by_email(email)
    if user:
        return user["id"]

    return create_user(name=name, email=email)


# ============================================================
# IDEAS
# ============================================================

def ideas_url(pat):
    return f"https://api.airtable.com/v0/{pat['base_id']}/{pat['ideas_table']}"

# =======================нормализация текста=====================================

def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()
    
def normalize_compare_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = text.replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9א-ת\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def extract_compare_keywords(text: str) -> set[str]:
    if not text:
        return set()

    words = re.findall(r"[a-zA-Zа-яА-ЯёЁא-ת0-9]{4,}", text.lower())
    bad = {
        "используя", "использовать", "используется",
        "данный", "данная", "данные",
        "который", "которая", "которые",
        "можно", "нужно", "будет",
        "using", "used", "useful", "this", "that"
    }

    result = set()
    for w in words:
        w = w.replace("ё", "е").strip()
        if len(w) < 4:
            continue
        if w in bad:
            continue
        result.add(w)

    return result


def keyword_overlap_score(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a.intersection(b))
    union = len(a.union(b))
    if union == 0:
        return 0.0
    return inter / union    
    
# =======================поиск дубликатов=====================================

def find_best_duplicate(pat, title_or_text: str, keywords: list[str]):
    url = ideas_url(pat)
    headers = airtable_headers(pat)

    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()

    records = r.json().get("records", [])

    query_raw = title_or_text or ""
    query = normalize_compare_text(query_raw)
    query_kw = set()
    query_kw.update(extract_compare_keywords(query_raw))
    query_kw.update({normalize_compare_text(k) for k in (keywords or []) if k})

    best = None
    best_score = 0.0

    for rec in records:
        fields = rec.get("fields", {})

        title_raw = fields.get("Title") or ""
        short_raw = fields.get("Short Description") or ""
        db_keywords_raw = fields.get("Keywords") or ""

        title = normalize_compare_text(title_raw)
        short = normalize_compare_text(short_raw)

        # Keywords from DB field + title + short
        db_kw = set()
        db_kw.update(extract_compare_keywords(title_raw))
        db_kw.update(extract_compare_keywords(short_raw))
        db_kw.update(extract_compare_keywords(db_keywords_raw))

        title_score = similarity(query, title) if title else 0.0
        short_score = similarity(query, short) if short else 0.0
        kw_score = keyword_overlap_score(query_kw, db_kw)

        # Weighted score
        score = (
            title_score * 0.55 +
            short_score * 0.25 +
            kw_score * 0.20
        )

        # Hard thematic guard:
        # if keyword overlap is zero and text similarity weak,
        # do not allow random false duplicate
        if kw_score == 0 and max(title_score, short_score) < 0.55:
            continue

        if score > best_score:
            best_score = score
            best = rec

    # Cutoff threshold:
    # below this, we treat as "no reliable duplicate"
    if best_score < 0.58:
        return None, 0.0

    return best, best_score

# =======================degraded=====================================

def safe_find_best_duplicate(pat, title_or_text: str, keywords: list[str]):
    """
    Safe wrapper for duplicate search.
    Returns:
      {
        "ok": True/False,
        "best": rec or None,
        "score": float,
        "degraded": True/False,
        "error": str or None
      }
    """

    try:
        best, score = find_best_duplicate(pat, title_or_text, keywords)
        return {
            "ok": True,
            "best": best,
            "score": score,
            "degraded": False,
            "error": None
        }

    except requests.exceptions.Timeout:
        return {
            "ok": False,
            "best": None,
            "score": 0.0,
            "degraded": True,
            "error": "Airtable timeout"
        }

    except requests.exceptions.ConnectionError:
        return {
            "ok": False,
            "best": None,
            "score": 0.0,
            "degraded": True,
            "error": "Airtable connection error"
        }

    except requests.exceptions.HTTPError as e:
        status = None
        if getattr(e, "response", None) is not None:
            status = e.response.status_code

        if status == 429 or status in [500, 502, 503, 504]:
            return {
                "ok": False,
                "best": None,
                "score": 0.0,
                "degraded": True,
                "error": f"Airtable temporary unavailable: HTTP {status}"
            }

        raise

    except requests.exceptions.RequestException as e:
        return {
            "ok": False,
            "best": None,
            "score": 0.0,
            "degraded": True,
            "error": f"Airtable request failed: {str(e)}"
        }

# =======================airtable_error=====================================

def _extract_airtable_error_info(exc: Exception) -> dict:
    http_status = None
    error_code = "UNKNOWN"
    message = str(exc)

    if isinstance(exc, requests.Timeout):
        error_code = "TIMEOUT"
    elif isinstance(exc, requests.ConnectionError):
        error_code = "CONNECTION_ERROR"
    elif isinstance(exc, requests.RequestException):
        response = getattr(exc, "response", None)
        if response is not None:
            http_status = response.status_code
            error_code = f"HTTP_{http_status}"
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    message = payload.get("error", {}).get("message") \
                        or payload.get("message") \
                        or response.text
                else:
                    message = response.text
            except Exception:
                message = response.text or str(exc)

    return {
        "http_status": http_status,
        "error_code": error_code,
        "message": message
    }


def is_temporary_airtable_error(exc: Exception) -> bool:
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True

    if isinstance(exc, requests.RequestException):
        response = getattr(exc, "response", None)
        if response is None:
            return True

        return response.status_code in [429, 500, 502, 503, 504]

    return False


def generate_idea_id(record_id: str):
    now = datetime.datetime.now()
    ym = now.strftime("%Y-%m")
    suffix = record_id[-6:]
    return f"{ym}-{suffix}"


# ============================================================
# SAVE IDEA (CORRECT AUTHOR LINK)
# ============================================================

def prepare_and_create_idea(data: dict):

    pat = load_env()
    url = ideas_url(pat)
    headers = airtable_headers(pat)

    email = data.get("author_email")

    if not email:
        raise ValueError("Email required")

    user_id = ensure_user(
        email=email,
        name=data.get("author_name", "")
    )

    fields = {
        "Title": data["title"],
        "Short Description": data["short"],
        "Full Description": data["full"],
        "Keywords": ", ".join(data.get("keywords_list", [])),
        "Author": [user_id],
        "Date Added": datetime.datetime.now().strftime("%Y-%m-%d"),
        "Status": data.get("status_override", "Idea"),
        "Raw Input": data.get("raw_input", ""),
        "Intake Mode": data.get("intake_mode", ""),
        "Assistant Version": data.get("assistant_version", ""),

# --- STRICT_DB_MODE compatibility ---
        "AIReviewStatus": "Done",
        "AIRequest": "",

# --- Vector Strategy preparation ---
        "VectorEmbedding": "",
        "EmbeddingModel": ""
         }
# --- -------"LanguageOriginal": ""

# --- LanguageOriginal (singleSelect safe) ---
    lang = data.get("language_original")

    if not lang:
     lang = "Auto"

    if lang in ["RU", "EN", "HE", "Auto"]:
     fields["LanguageOriginal"] = lang
   

    if data.get("related_to_id"):
        fields["RelatedToIdea"] = [data["related_to_id"]]

    payload = {"fields": fields}

    r = requests.post(url, headers=headers, json=payload)

    if not r.ok:
        print("Airtable error:", r.text)
        r.raise_for_status()

    created = r.json()
    record_id = created["id"]

    idea_id = generate_idea_id(record_id)

    requests.patch(
        f"{url}/{record_id}",
        headers=headers,
        json={"fields": {"IdeaID": idea_id}}
    )

    return {
        "record_id": record_id,
        "idea_id": idea_id
    }

# ============================================================
# SIMPLE FAILURE LOGGING
# ============================================================

def simple_failure_logs_url(pat):
    return f"https://api.airtable.com/v0/{pat['base_id']}/{os.getenv('AIRTABLE_SIMPLE_FAILURE_TABLE_ID')}"


def create_simple_failure_log(data: dict):

    pat = load_env()
    url = simple_failure_logs_url(pat)
    headers = airtable_headers(pat)

    fields = {
        "LocalID": data.get("local_id"),
        "CreatedAt": data.get("created_at"),
        "Mode": "Simple",
        "ModeVersion": data.get("mode_version"),
        "ErrorCode": data.get("error_code"),
        "UserMessage": data.get("user_message"),
        "TechMessage": data.get("tech_message"),
        "HTTPStatus": data.get("http_status"),
        "Endpoint": data.get("endpoint"),
        "RequestId": data.get("request_id"),
        "Email": data.get("email"),
        "FirstName": data.get("first_name"),
        "LastName": data.get("last_name"),
        "IsLoggedIn": data.get("is_logged_in", False),
        "SessionIdPresent": data.get("session_present", False),
        "Title": data.get("title"),
        "Keywords": data.get("keywords"),
        "RawInputLength": data.get("raw_input_length"),
        "Similarity": data.get("similarity"),
        "DuplicateID": data.get("duplicate_id"),
        "ClientOnline": data.get("client_online"),
        "ClientUserAgent": data.get("client_user_agent"),
        "ClientLanguage": data.get("client_language"),
        "ClientTime": data.get("client_time"),
        "ClientTZOffsetMin": data.get("client_tz_offset"),
        "ClientBuild": data.get("client_build"),
        "ServerTimeUTC": data.get("server_time_utc"),
        "ServerComponent": data.get("server_component"),
        "AirtableErrorType": data.get("airtable_error_type"),
        "AirtableErrorSnippet": data.get("airtable_error_snippet"),
    }

    payload = {"fields": fields}

    r = requests.post(url, headers=headers, json=payload)

    if not r.ok:
        print("FailureLog write error:", r.text)
        print(dup_result)

    return r.ok
    
# ============================================================
# SIMPLE BUFFER STORAGE
# ============================================================

BUFFER_DIR = os.path.join(os.path.dirname(__file__), "buffer_simple")


def ensure_buffer_dir():
    os.makedirs(BUFFER_DIR, exist_ok=True)


def save_simple_buffer_record(data: dict):
    """
    Saves failed simple-mode idea to local JSON buffer.
    One record = one JSON file.
    """

    ensure_buffer_dir()

    local_id = data.get("local_id") or f"MM-BUF-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
    created_at = data.get("created_at") or datetime.datetime.utcnow().isoformat()

    record = {
        "local_id": local_id,
        "created_at": created_at,
        "status": "pending",

        "mode": "simple",
        "mode_version": data.get("mode_version", "Simple 2.0"),

        "raw_text": data.get("raw_text", ""),
        "title": data.get("title", ""),
        "short": data.get("short", ""),
        "full": data.get("full", ""),
        "keywords": data.get("keywords", []),

        "author_name": data.get("author_name", ""),
        "author_email": data.get("author_email", ""),

        "duplicate_id": data.get("duplicate_id"),
        "similarity": data.get("similarity", 0),

        "intake_mode": data.get("intake_mode", "simple"),
        "assistant_version": data.get("assistant_version", "Simple 2.0"),

        "error_code": data.get("error_code", ""),
        "error_text": data.get("error_text", ""),
        "save_stage": data.get("save_stage", "confirm"),

        "schema_version": "0.1"
    }

    filename = f"{local_id}.json"
    path = os.path.join(BUFFER_DIR, filename)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    return {
        "ok": True,
        "local_id": local_id,
        "path": path
    }    