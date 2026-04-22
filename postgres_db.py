# ============================================================
# MindMesh
# File: postgres_db.py
# Version: 1.2
# Date: 21.04.2026
# Purpose:
# - PostgreSQL primary storage for MindMesh user flow
# - Users
# - Ideas
# - Duplicate matching
# - Profile updates
# ============================================================

import os
import re
import json
import datetime
import difflib
import bcrypt
import psycopg2
import psycopg2.extras
from psycopg2 import sql


def get_conn():
    return psycopg2.connect(
        dbname=os.getenv("PGDATABASE", "mindmesh"),
        user=os.getenv("PGUSER", "mindmesh_app"),
        password=os.getenv("PGPASSWORD", ""),
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=os.getenv("PGPORT", "5432")
    )

_TABLE_COLUMNS_CACHE = {}


def get_table_columns(table_name: str) -> set[str]:
    if table_name in _TABLE_COLUMNS_CACHE:
        return _TABLE_COLUMNS_CACHE[table_name]

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        """,
        (table_name,)
    )
    cols = {row[0] for row in cur.fetchall()}
    cur.close()
    conn.close()
    _TABLE_COLUMNS_CACHE[table_name] = cols
    return cols


def _filter_existing_fields(table_name: str, field_map: dict) -> dict:
    cols = get_table_columns(table_name)
    return {k: v for k, v in field_map.items() if k in cols and v is not None}


def _now_iso() -> str:
    return datetime.datetime.utcnow().isoformat()


def _user_row_to_airtable_like(row: dict):
    if not row:
        return None
    row = dict(row)
    return {
        "id": str(row.get("id")),
        "fields": {k: row.get(k) for k in row.keys() if k != 'id'}
    }


def _normalize_link_value(value):
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(x) for x in value if x is not None and str(x) != ""]
    if isinstance(value, (tuple, set)):
        return [str(x) for x in value if x is not None and str(x) != ""]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        if raw.startswith('[') and raw.endswith(']'):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed if x is not None and str(x) != ""]
            except Exception:
                pass
        return [raw]
    return [str(value)]


def _idea_row_to_airtable_like(row: dict):
    if not row:
        return None
    row = dict(row)
    rec_id = str(row.get("id"))
    fields = {}
    for key, value in row.items():
        if key == 'id':
            continue
        if key in ['Author', 'RelatedToIdea']:
            fields[key] = _normalize_link_value(value)
        else:
            fields[key] = value
    return {"id": rec_id, "fields": fields}


# USERS

def find_user_by_email_pg(email: str):
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute('SELECT * FROM public."Users" WHERE lower("Email") = lower(%s) LIMIT 1', (email,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return _user_row_to_airtable_like(row)
    except Exception as e:
        print("PG LOGIN ERROR:", str(e))
        raise


def get_user_by_id_pg(user_id):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if isinstance(user_id, int) or str(user_id).isdigit():
        cur.execute('SELECT * FROM public."Users" WHERE id = %s LIMIT 1', (int(user_id),))
    else:
        cur.execute('SELECT * FROM public."Users" WHERE "UserID" = %s LIMIT 1', (str(user_id),))
    row = cur.fetchone()
    cur.close(); conn.close()
    return _user_row_to_airtable_like(row)


def create_user_pg(name: str, email: str, password: str | None = None):
    conn = get_conn()
    cur = conn.cursor()
    password_hash = None
    if password and len(password) >= 3:
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    fields = _filter_existing_fields('Users', {
        'Name': name,
        'Email': email,
        'Role': 'user',
        'CreatedAt': _now_iso(),
        'PasswordHash': password_hash,
        'AccountStatus': 'active',
        'VisitCount': 0,
        'IdeasCreatedCount': 0,
    })
    cols = list(fields.keys())
    vals = [fields[c] for c in cols]
    query = sql.SQL('INSERT INTO public."Users" ({fields}) VALUES ({values}) RETURNING id').format(
        fields=sql.SQL(', ').join(sql.Identifier(c) for c in cols),
        values=sql.SQL(', ').join(sql.Placeholder() for _ in cols),
    )
    cur.execute(query, vals)
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close(); conn.close()
    return str(new_id)


def set_user_password_pg(user_id, password: str):
    if not password or len(password) < 3:
        raise ValueError('Password too short')
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = get_conn(); cur = conn.cursor()
    if isinstance(user_id, int) or str(user_id).isdigit():
        cur.execute('UPDATE public."Users" SET "PasswordHash" = %s WHERE id = %s', (password_hash, int(user_id)))
    else:
        cur.execute('UPDATE public."Users" SET "PasswordHash" = %s WHERE "UserID" = %s', (password_hash, str(user_id)))
    conn.commit(); cur.close(); conn.close()
    return True


def get_all_users_pg():
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT * FROM public."Users" ORDER BY id DESC')
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [_user_row_to_airtable_like(r) for r in rows]


def update_last_visit_pg(user_id):
    conn = get_conn(); cur = conn.cursor()
    if isinstance(user_id, int) or str(user_id).isdigit():
        cur.execute('UPDATE public."Users" SET "LastVisitAt" = %s, "VisitCount" = COALESCE("VisitCount", 0) + 1 WHERE id = %s', (_now_iso(), int(user_id)))
    else:
        cur.execute('UPDATE public."Users" SET "LastVisitAt" = %s, "VisitCount" = COALESCE("VisitCount", 0) + 1 WHERE "UserID" = %s', (_now_iso(), str(user_id)))
    conn.commit(); cur.close(); conn.close(); return True


def sync_airtable_user_id_pg(pg_id, airtable_record_id):
    conn = get_conn(); cur = conn.cursor()
    cur.execute('UPDATE public."Users" SET "UserID" = %s WHERE id = %s', (airtable_record_id, int(pg_id)))
    conn.commit(); cur.close(); conn.close(); return True


def update_user_name_pg(user_id: str, name: str):
    conn = get_conn(); cur = conn.cursor()
    if isinstance(user_id, int) or str(user_id).isdigit():
        cur.execute('UPDATE public."Users" SET "Name" = %s WHERE id = %s', (name, int(user_id)))
    else:
        cur.execute('UPDATE public."Users" SET "Name" = %s WHERE "UserID" = %s', (name, str(user_id)))
    conn.commit(); cur.close(); conn.close(); return True


def update_user_profile_data_pg(**kwargs):
    user_id = kwargs.pop('user_id')
    field_map = _filter_existing_fields('Users', {
        'Name': kwargs.get('full_name'),
        'LastName': kwargs.get('last_name'),
        'Email': kwargs.get('email'),
        'Country': kwargs.get('country'),
        'Language': kwargs.get('language'),
        'Contacts': kwargs.get('contacts'),
        'Notes': kwargs.get('notes'),
        'PostalAddress': kwargs.get('postal_address'),
        'City': kwargs.get('city'),
        'PostalCode': kwargs.get('postal_code'),
        'Street': kwargs.get('street'),
        'HouseNumber': kwargs.get('house_number'),
        'PhoneUser': kwargs.get('phone_user'),
        'AvatarURL': kwargs.get('avatar_url'),
        'Bio': kwargs.get('bio'),
        'About': kwargs.get('about'),
        'Education': kwargs.get('education'),
        'Interests': kwargs.get('interests'),
        'Expertise': kwargs.get('expertise'),
        'ReviewerLevel': kwargs.get('reviewer_level'),
        'ReviewerSpecialization': kwargs.get('reviewer_specialization'),
        'PreferredLanguage': kwargs.get('preferred_language'),
        'NotificationSettings': kwargs.get('notification_settings'),
        'ProfileEditCount': kwargs.get('new_edit_count'),
    })
    if not field_map:
        return True
    assignments=[]; values=[]
    for col,val in field_map.items():
        assignments.append(sql.SQL('{} = %s').format(sql.Identifier(col)))
        values.append(val)
    if isinstance(user_id, int) or str(user_id).isdigit():
        where_sql = sql.SQL('id = %s')
        values.append(int(user_id))
    else:
        where_sql = sql.SQL('"UserID" = %s')
        values.append(str(user_id))
    query = sql.SQL('UPDATE public."Users" SET {assignments} WHERE {where_clause}').format(
        assignments=sql.SQL(', ').join(assignments),
        where_clause=where_sql,
    )
    conn = get_conn(); cur = conn.cursor(); cur.execute(query, values)
    conn.commit(); cur.close(); conn.close(); return True


# IDEAS

def normalize_compare_text(text: str) -> str:
    if not text:
        return ''
    text = text.lower().strip().replace('ё', 'е')
    text = re.sub(r'[^a-zа-я0-9א-ת\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def soften_russian_word(word: str) -> str:
    w = word.lower().strip().replace('ё', 'е')
    endings = ['иями','ями','ами','ого','его','ому','ему','ыми','ими','ая','яя','ое','ее','ий','ый','ой','ах','ях','ам','ям','ов','ев','ом','ем','ую','юю','а','я','ы','и','у','ю','е','о']
    for ending in endings:
        if len(w) > 4 and w.endswith(ending):
            return w[:-len(ending)]
    return w


def extract_compare_keywords(text: str) -> set[str]:
    if not text:
        return set()
    words = re.findall(r'[a-zA-Zа-яА-ЯёЁא-ת0-9]{4,}', text.lower())
    bad = {'используя','использовать','используется','данный','данная','данные','который','которая','которые','можно','нужно','будет','using','used','useful','this','that'}
    result = set()
    for w in words:
        w = soften_russian_word(w.replace('ё','е').strip())
        if len(w) < 3 or w in bad:
            continue
        result.add(w)
    return result


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def keyword_overlap_score(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a.intersection(b))
    union = len(a.union(b))
    return 0.0 if union == 0 else inter / union


def list_ideas_records_pg():
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute('SELECT * FROM public."IdeaHub" ORDER BY id DESC')
        rows = cur.fetchall()

        cur.close()
        conn.close()

        return [_idea_row_to_airtable_like(r) for r in rows]

    except Exception as e:
        print("LIST_IDEAS_PG ERROR:", str(e))
        raise


def find_best_duplicate_pg(title_or_text: str, keywords: list[str]):
    records = list_ideas_records_pg()
    query_raw = title_or_text or ''
    query = normalize_compare_text(query_raw)
    query_kw = set(); query_kw.update(extract_compare_keywords(query_raw)); query_kw.update(extract_compare_keywords(' '.join(keywords or [])))
    best=None; best_score=0.0
    for rec in records:
        fields = rec.get('fields', {})
        title_raw = fields.get('Title') or ''
        short_raw = fields.get('Short Description') or ''
        db_keywords_raw = fields.get('Keywords') or ''
        title = normalize_compare_text(title_raw)
        short = normalize_compare_text(short_raw)
        db_kw=set(); db_kw.update(extract_compare_keywords(title_raw)); db_kw.update(extract_compare_keywords(short_raw)); db_kw.update(extract_compare_keywords(db_keywords_raw))
        title_score = similarity(query, title) if title else 0.0
        short_score = similarity(query, short) if short else 0.0
        kw_score = keyword_overlap_score(query_kw, db_kw)
        text_score = max(title_score, short_score)
        score = (title_score*0.50 + short_score*0.30 + kw_score*0.20)
        if kw_score == 0 and text_score < 0.42:
            continue
        if score > best_score:
            best_score = score; best = rec
    if best_score < 0.44:
        return None, 0.0
    return best, best_score


def safe_find_best_duplicate_pg(title_or_text: str, keywords: list[str]):
    try:
        best, score = find_best_duplicate_pg(title_or_text, keywords)
        return {
            'ok': True,
            'best': best,
            'score': score,
            'degraded': False,
            'error': None
        }
    except Exception as e:
        return {
            'ok': False,
            'best': None,
            'score': 0.0,
            'degraded': True,
            'error': str(e)
        }


def generate_idea_id_pg(record_id) -> str:
    ym = datetime.datetime.now().strftime('%Y-%m')
    return f'{ym}-PG{int(record_id):06d}'


def create_idea_pg(data: dict):
    email = (data.get('author_email') or '').strip()
    if not email:
        raise ValueError('Email required')
    user = find_user_by_email_pg(email)
    if user:
        user_id = str(user['id'])
    else:
        user_id = create_user_pg(name=data.get('author_name',''), email=email, password=None)
    idea_fields = {
        'Title': data.get('title',''),
        'Short Description': data.get('short',''),
        'Full Description': data.get('full',''),
        'Keywords': ', '.join(data.get('keywords_list', [])),
        'Date Added': _now_iso(),
        'Status': data.get('status_override','New'),
        'Raw Input': data.get('raw_input',''),
        'Intake Mode': data.get('intake_mode','simple'),
        'Assistant Version': data.get('assistant_version',''),
        'Your Name': data.get('author_name',''),
        'Your Email': email,
        'Similarity Score': data.get('similarity_score', 0),
        'DuplicateOf': data.get('related_to_id'),
        'RelationType': 'possible_duplicate' if data.get('related_to_id') else None,
        'Author': user_id,
        'DetectedByAI': False,
        'DiscoveredByAI': False,
        'Source': data.get('source','Simple'),
        'AIReviewStatus': 'Done',
        'AIRequest': '',
    }
    if data.get('related_to_id'):
        idea_fields['RelatedToIdea'] = data.get('related_to_id')
    idea_fields = _filter_existing_fields('IdeaHub', idea_fields)
    cols = list(idea_fields.keys())
    vals = [idea_fields[c] for c in cols]
    conn = get_conn(); cur = conn.cursor()
    query = sql.SQL('INSERT INTO public."IdeaHub" ({fields}) VALUES ({values}) RETURNING id').format(
        fields=sql.SQL(', ').join(sql.Identifier(c) for c in cols),
        values=sql.SQL(', ').join(sql.Placeholder() for _ in cols),
    )
    cur.execute(query, vals)
    new_id = cur.fetchone()[0]
    idea_id = generate_idea_id_pg(new_id)
    if 'IdeaID' in get_table_columns('IdeaHub'):
        cur.execute('UPDATE public."IdeaHub" SET "IdeaID" = %s WHERE id = %s', (idea_id, int(new_id)))
    if 'IdeasCreatedCount' in get_table_columns('Users'):
        cur.execute('UPDATE public."Users" SET "IdeasCreatedCount" = COALESCE("IdeasCreatedCount", 0) + 1 WHERE id = %s', (int(user_id),))
    conn.commit(); cur.close(); conn.close()
    return {'record_id': str(new_id), 'idea_id': idea_id}


# compatibility aliases
find_user_by_email = find_user_by_email_pg
get_user_by_id = get_user_by_id_pg
create_user = create_user_pg
set_user_password = set_user_password_pg
get_all_users = get_all_users_pg
update_user_name = update_user_name_pg
update_user_profile_data = update_user_profile_data_pg
list_ideas_records = list_ideas_records_pg
safe_find_best_duplicate = safe_find_best_duplicate_pg
create_idea = create_idea_pg
