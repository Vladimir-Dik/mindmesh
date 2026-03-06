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
import requests
import difflib
import datetime
import bcrypt
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


def find_user_by_email(email: str):
    pat = load_env()
    url = users_url(pat)
    headers = airtable_headers(pat)

    formula = f"{{Email}}='{email}'"
    r = requests.get(url, headers=headers, params={"filterByFormula": formula})
    r.raise_for_status()

    records = r.json().get("records", [])
    return records[0] if records else None


def get_user_by_id(user_id: str):
    pat = load_env()
    url = f"{users_url(pat)}/{user_id}"
    headers = airtable_headers(pat)

    r = requests.get(url, headers=headers)
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
        return []


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


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def find_best_duplicate(pat, title_or_text: str, keywords: list[str]):
    url = ideas_url(pat)
    headers = airtable_headers(pat)
    headers = airtable_headers(pat)

    r = requests.get(url, headers=headers)
    r.raise_for_status()

    records = r.json().get("records", [])

    query = title_or_text.lower().strip()
    best = None
    best_score = 0.0

    for rec in records:
        fields = rec.get("fields", {})
        title = (fields.get("Title") or "").lower()
        short = (fields.get("Short Description") or "").lower()

        score = max(
            similarity(query, title),
            similarity(query, short)
        )

        if score > best_score:
            best_score = score
            best = rec

    return best, best_score


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
        "Assistant Version": data.get("assistant_version", "")
    }

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

    return r.ok