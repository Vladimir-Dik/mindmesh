# ============================================================
# Project: MindMesh
# File: app.py
# Version: 4.3
# Date: 12.05.2026
# Purpose:
# - Main web app
# - user-management
# - Profile v2
# - Reviewer workspace
# - Feedback and fallback
# - Soft maintenance message for Airtable / PostgreSQL temporary errors
# ============================================================

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, UploadFile, File, Form
from fastapi.responses import JSONResponse
from web import collector_agent

import sys
import os
import uuid
import bcrypt
import json
import datetime
import postgres_db
import psycopg2
import psycopg2.extras


# =====================временный блок=======================================
SUPERADMIN_EMAIL = "searchwave@gmail.com"
SUPERADMIN_PASSWORD = "123456"  # временно, потом вынесем в .env

# INIT APP
# ============================================================

app = FastAPI()

# ============================================================
# SYSTEM HEALTH CHECK (system_health_check)
# ============================================================

@app.get("/api/system/health")
async def system_health():

    import socket

    # --- PostgreSQL LOCAL ---
    pg_local = False
    try:
        conn = postgres_db.get_conn()
        conn.close()
        pg_local = True
    except Exception:
        pg_local = False

    # --- PostgreSQL via No-IP ---
    pg_external = False
    try:
        sock = socket.create_connection(("mindmesh.ddns.net", 5432), timeout=3)
        sock.close()
        pg_external = True
    except Exception:
        pg_external = False

    # --- Airtable ---
    airtable_ok = False
    try:
        import requests
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
        headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}

        r = requests.get(url, headers=headers, timeout=5)

        if r.status_code < 500:
            airtable_ok = True

    except Exception:
        airtable_ok = False

    return {
        "airtable": airtable_ok,
        "postgres_local": pg_local,
        "postgres_external": pg_external
    }

# ============================================================
# Name: Session Heartbeat (пульс сессии)
# ============================================================

@app.get("/api/heartbeat")
def heartbeat(request: Request):

    user = get_current_user(request)

    db_ok = False
    db_error = None

    try:
        db_ok = postgres_db.pg_ping()
    except Exception as e:
        db_ok = False
        db_error = str(e)

    return {
        "status": "ok" if db_ok else "degraded",
        "session": {
            "authenticated": bool(user),
            "user_id": user.get("id") if user else None,
            "role": user.get("fields", {}).get("Role") if user else "guest",
            "email": user.get("fields", {}).get("Email") if user else None
        },
        "database": {
            "postgres_ok": db_ok,
            "error": db_error
        },
        "server_time": datetime.datetime.utcnow().isoformat()
    }


# ============================================================
# IMPORT ADVANCED ROUTERS
# ============================================================

from web.api.advanced.start import router as advanced_start_router
from web.api.advanced.message import router as advanced_message_router
from web.api.advanced.confirm import router as advanced_confirm_router

app.include_router(advanced_start_router)
app.include_router(advanced_message_router)
app.include_router(advanced_confirm_router)

# ============================================================
# IMPORT CORE
# ============================================================

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import core
from intake_engine import analyze_intake

# ============================================================
# TEMPLATES & STATIC
# ============================================================

BASE_DIR = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

app.mount("/static",
          StaticFiles(directory=os.path.join(BASE_DIR, "static")),
          name="static")

# ============================================================
# SYSTEM STATE
# ============================================================

SYSTEM_STATE_FILE = os.path.join(BASE_DIR, "system_state.json")


def load_system_state():
    if not os.path.exists(SYSTEM_STATE_FILE):
        return {
            "test_mode": False,
            "maintenance": "none",
            "activated_by": None,
            "log": []
        }

    with open(SYSTEM_STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_system_state(state):
    with open(SYSTEM_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


system_state = load_system_state()

# ============================================================
# SESSION SYSTEM
# ============================================================

SESSIONS = {}


def get_current_user(request: Request):
    sid = request.cookies.get("mindmesh_session")
    if not sid:
        return None

    session_data = SESSIONS.get(sid)
    if not session_data:
        return None

    # --- local superadmin bypass ---
    if session_data.get("user_id") == "superadmin_local":
        return {
            "id": "superadmin_local",
            "fields": {
                "Email": SUPERADMIN_EMAIL,
                "Name": "SuperAdmin",
                "Role": "superadmin"
            },
            "access_level": "user_full"
        }

    user = core.get_user_by_id(session_data["user_id"])
    if not user:
        return None

    user["access_level"] = session_data.get("access_level", "user_light")
    return user

# ============================================================
# ACCESS CONTROL
# ============================================================

def require_superadmin(user):
    if not user:
        return False

    role = user["fields"].get("Role", "user")
    return role == "superadmin"

@app.post("/api/system/update")
async def update_system(request: Request):

    user = get_current_user(request)
    if not require_superadmin(user):
        return JSONResponse({"error": "Unauthorized"}, status_code=403)

    data = await request.json()

    system_state["test_mode"] = data.get("test_mode", False)
    system_state["maintenance"] = data.get("maintenance", "none")

    system_state["log"].append(
        f"System updated: test_mode={system_state['test_mode']}, maintenance={system_state['maintenance']}"
    )

    save_system_state(system_state)

    return {"status": "ok"}


# ============================================================
# MIDDLEWARE
# ============================================================

class MaintenanceMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):

        path = request.url.path

        # ----------------------------------------------------
        # SYSTEM PATHS (never block)
        # ----------------------------------------------------

        if path.startswith("/static") \
        or path.startswith("/searchwave") \
        or path.startswith("/login") \
        or path.startswith("/favicon"):
            return await call_next(request)

        user = get_current_user(request)
        role = None

        if user:
            role = user["fields"].get("Role", "user")

        # ----------------------------------------------------
        # FULL MAINTENANCE
        # ----------------------------------------------------

        if system_state.get("maintenance") == "full":

            if role != "superadmin":

                return templates.TemplateResponse(
                    "maintenance.html",
                    {"request": request, "system": system_state},
                    status_code=503
                )

        # ----------------------------------------------------
        # SOFT MAINTENANCE
        # ----------------------------------------------------

        if system_state.get("maintenance") == "soft":

            if request.method == "POST":

                if role not in ["admin", "superadmin"]:

                    return JSONResponse(
                        {"error": "System in maintenance mode"},
                        status_code=503
                    )

        # ----------------------------------------------------
        # TEST MODE
        # ----------------------------------------------------

        if system_state.get("test_mode"):

            if role not in ["admin", "superadmin"]:

                return templates.TemplateResponse(
                    "maintenance.html",
                    {"request": request, "system": system_state},
                    status_code=503
                )

        return await call_next(request)


app.add_middleware(MaintenanceMiddleware)

# ============================================================
# INDEX
# ============================================================

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "user": user, "system": system_state}
    )

# ============================================================
# LOGIN
# ============================================================

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "system": system_state}
    )


@app.post("/login")
def login_submit(
        request: Request,
        email: str = Form(...),
        password: str = Form(""),
        next: str = Form("")
):

    email = email.strip().lower()

    # ================= SUPERADMIN BYPASS =================
    if email == SUPERADMIN_EMAIL:
        if not password or password != SUPERADMIN_PASSWORD:
            return templates.TemplateResponse(
                "login.html",
                {
                    "request": request,
                    "error": "Неверный пароль",
                    "system": system_state
                }
            )

        sid = str(uuid.uuid4())

        SESSIONS[sid] = {
            "user_id": "superadmin_local",
            "access_level": "user_full"
        }

        redirect_target = next if next else "/"
        resp = RedirectResponse(redirect_target, status_code=302)
        resp.set_cookie("mindmesh_session", sid, httponly=True)
        return resp

    # ================= NORMAL LOGIN =================
    try:
        user = core.find_user_by_email(email)

    except Exception as e:
        # Soft DB fallback:
        # For temporary Airtable / PostgreSQL failures
        # we do not show technical details to the user.
        if is_system_error(e):
            return templates.TemplateResponse(
                "login.html",
                {
                    "request": request,
                    "error": "Ведутся технические работы. Попробуйте позже.",
                    "system": system_state
                },
                status_code=503
            )

        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Ошибка входа. Проверьте данные.",
                "system": system_state
            },
            status_code=500
        )

    if not user:
        user_id = core.create_user(
            name="",
            email=email,
            password=password if password else None
        )
        access_level = "user_full" if password else "user_light"

    else:
        user_id = user["id"]
        stored_hash = user["fields"].get("PasswordHash")

        if not stored_hash:
            if password:
                core.set_user_password(user_id, password)
                access_level = "user_full"
            else:
                access_level = "user_light"
        else:
            if not password:
                access_level = "user_light"
            else:
                if not bcrypt.checkpw(password.encode(),
                                      stored_hash.encode()):
                    return templates.TemplateResponse(
                        "login.html",
                        {
                            "request": request,
                            "error": "Неверный пароль",
                            "system": system_state
                        }
                    )
                access_level = "user_full"

    # ---------- create session ----------                                          
    sid = str(uuid.uuid4())

    SESSIONS[sid] = {
        "user_id": user_id,
        "access_level": access_level
    }

    redirect_target = next if next else "/"
    resp = RedirectResponse(redirect_target, status_code=302)
    resp.set_cookie("mindmesh_session", sid, httponly=True)
    return resp




@app.get("/logout")
def logout(request: Request):

    sid = request.cookies.get("mindmesh_session")
    if sid in SESSIONS:
        del SESSIONS[sid]

    resp = RedirectResponse("/", status_code=302)
    resp.delete_cookie("mindmesh_session")
    return resp

# ============================================================
# CABINET
# ============================================================

@app.get("/cabinet", response_class=HTMLResponse)
def cabinet(request: Request):

    user = get_current_user(request)

    if not user:
        return RedirectResponse("/login", status_code=302)

    user_email = (user["fields"].get("Email") or "").strip().lower()

    user_messages_total = 0
    user_messages_answered = 0

    try:
        records = core.list_feedback_records()

        for rec in records:
            fields = rec.get("fields", {})

            email = (
                fields.get("fldnpx1rtg3XjEYx6")
                or fields.get("Email")
                or ""
            ).strip().lower()

            if email != user_email:
                continue

            user_messages_total += 1

            status_value = (
                fields.get("fldH2ZVXQPq07ATdU")
                or fields.get("Status")
                or ""
            )

            if status_value == "Answered":
                user_messages_answered += 1

    except Exception:
        pass
    subscription_status = get_subscription_status(user)
    subscription_label = subscription_label_from_code(subscription_status)

    return templates.TemplateResponse(
        "kabinet.html",
        {
            "request": request,
            "user": user,
            "system": system_state,
            "user_messages_total": user_messages_total,
            "user_messages_answered": user_messages_answered,
            "subscription_label": subscription_label
        }
    )

# ============================================================
# user HELPERS
# ============================================================

def update_user_fields_airtable(record_id: str, fields: dict):
    import requests

    pat = core.load_env()
    url = f"{core.users_url(pat)}/{record_id}"
    headers = core.airtable_headers(pat)

    payload = {
        "fields": fields
    }

    r = requests.patch(url, headers=headers, json=payload)
    r.raise_for_status()
    return r.json()

# ============================================================
# user_management
# ============================================================

@app.get("/user_management", response_class=HTMLResponse)
async def user_management_page(request: Request):

    user = get_current_user(request)

    if not user:
        return RedirectResponse("/login?next=/user_management", status_code=302)

    role = (user.get("fields", {}) or {}).get("Role", "user")

    if role not in ["moderator", "admin", "topadmin", "superadmin"]:
        return RedirectResponse(url="/cabinet", status_code=303)

    return templates.TemplateResponse(
        "user_management.html",
        {
            "request": request,
            "user": user,
            "system": system_state
        }
    )

# ============================================================
# USER MANAGEMENT API
# ============================================================

@app.get("/api/user-management/overview")
def user_management_overview(request: Request):

    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=403)

    role = user["fields"].get("Role", "user")
    if role not in ["moderator", "admin", "topadmin", "superadmin"]:
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    try:
        users = core.get_all_users()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    items = []

    total_users = 0
    authorized_users = 0
    verified_users = 0
    admin_users = 0
    moderator_users = 0
    reviewer_users = 0
    banned_users = 0

    for rec in users:
        fields = rec.get("fields", {})

        role_value = fields.get("Role", "user")
        is_verified = bool(fields.get("IsVerified"))
        account_status = (fields.get("AccountStatus") or "active")
        visit_count = int(fields.get("VisitCount") or 0)
        last_visit = fields.get("LastVisitAt")
        subscription_status = fields.get("SubscriptionStatus") or []

        unanswered_feedback = 0
        try:
            feedback_records = core.list_feedback_records()
            user_email = (fields.get("Email") or "").strip().lower()

            for fb in feedback_records:
                fb_fields = fb.get("fields", {})
                fb_email = (
                    fb_fields.get("fldnpx1rtg3XjEYx6")
                    or fb_fields.get("Email")
                    or ""
                ).strip().lower()

                fb_status = (
                    fb_fields.get("fldH2ZVXQPq07ATdU")
                    or fb_fields.get("Status")
                    or "New"
                )

                if fb_email == user_email and fb_status != "Answered":
                    unanswered_feedback += 1
        except Exception:
            unanswered_feedback = 0

        total_users += 1

        if visit_count > 0 or last_visit:
            authorized_users += 1

        if is_verified:
            verified_users += 1

        if role_value in ["admin", "topadmin", "superadmin"]:
            admin_users += 1

        if role_value == "moderator":
            moderator_users += 1

        if role_value == "reviewer":
            reviewer_users += 1

        if account_status == "banned":
            banned_users += 1

        items.append({
            "record_id": rec.get("id"),
            "user_id": fields.get("UserID"),
            "name": fields.get("Name", ""),
            "last_name": fields.get("LastName", ""),
            "email": fields.get("Email", ""),
            "role": role_value,
            "created_at": fields.get("CreatedAt"),
            "last_visit_at": last_visit,
            "visit_count": visit_count,
            "ideas_created_count": int(fields.get("IdeasCreatedCount") or 0),
            "language": fields.get("Language", ""),
            "preferred_language": fields.get("PreferredLanguage", ""),
            "is_verified": is_verified,
            "verification_level": fields.get("VerificationLevel", ""),
            "account_status": account_status,
            "subscription_status": subscription_status,
            "reviewer_score": int(fields.get("ReviewerScore") or 0),
            "reviews_completed": int(fields.get("ReviewsCompleted") or 0),
            "reviews_approved": int(fields.get("ReviewsApproved") or 0),
            "reviews_rejected": int(fields.get("ReviewsRejected") or 0),
            "profile_edit_count": int(fields.get("ProfileEditCount") or 0),
            "access_control": fields.get("AccessControl", ""),
            "privacy_control": fields.get("PrivacyControl", ""),
            "unanswered_feedback": unanswered_feedback,
            "user_log": []
        })

    unanswered_users = sum(1 for x in items if int(x.get("unanswered_feedback") or 0) > 0)

    return {
        "status": "ok",
        "stats": {
            "total_users": total_users,
            "authorized_users": authorized_users,
            "verified_users": verified_users,
            "admin_users": admin_users,
            "moderator_users": moderator_users,
            "reviewer_users": reviewer_users,
            "banned_users": banned_users,
            "unanswered_users": unanswered_users
        },
        "users": items
    }

# ============================================================
# user_card
# ============================================================

@app.get("/user_card", response_class=HTMLResponse)
async def user_card_page(request: Request):

    user = get_current_user(request)

    if not user:
        return RedirectResponse("/login?next=/user_card", status_code=302)

    role = (user.get("fields", {}) or {}).get("Role", "user")

    # доступ только служебным ролям
    if role not in ["moderator", "admin", "topadmin", "superadmin"]:
        return RedirectResponse(url="/cabinet", status_code=303)

    return templates.TemplateResponse(
        "user_card.html",
        {
            "request": request,
            "user": user,
            "system": system_state
        }
    )

# ============================================================
# USER save  status API
# ============================================================

@app.post("/api/user-management/update-main")
async def user_management_update_main(request: Request):

    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=403)

    actor_role = user["fields"].get("Role", "user")
    if actor_role not in ["admin", "topadmin", "superadmin"]:
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    data = await request.json()

    record_id = data.get("record_id")
    role_value = (data.get("role") or "user").strip()
    account_status = (data.get("account_status") or "active").strip()
    is_verified = bool(data.get("is_verified"))
    verification_level = (data.get("verification_level") or "").strip()
    subscription_status = data.get("subscription_status") or []

    if not record_id:
        return JSONResponse({"error": "record_id required"}, status_code=400)

    try:
        update_user_fields_airtable(record_id, {
            "Role": role_value,
            "AccountStatus": account_status,
            "IsVerified": is_verified,
            "VerificationLevel": verification_level,
            "SubscriptionStatus": subscription_status
        })

        return {"status": "ok"}

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ============================================================
# goto user_card
# ============================================================
@app.get("/user_card", response_class=HTMLResponse)
async def user_card_page(request: Request):

    user = get_current_user(request)

    if not user:
        return RedirectResponse("/login?next=/user_card", status_code=302)

    role = (user.get("fields", {}) or {}).get("Role", "user")

    # доступ только служебным ролям
    if role not in ["moderator", "admin", "topadmin", "superadmin"]:
        return RedirectResponse(url="/cabinet", status_code=303)

    return templates.TemplateResponse(
        "user_card.html",
        {
            "request": request,
            "user": user,
            "system": system_state
        }
    )

# ============================================================
# API сохранения AccessControl
# ============================================================

@app.post("/api/user-management/update-access")
async def user_management_update_access(request: Request):

    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=403)

    actor_role = user["fields"].get("Role", "user")
    if actor_role not in ["admin", "topadmin", "superadmin"]:
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    data = await request.json()

    record_id = data.get("record_id")
    access_control = (data.get("access_control") or "").strip()

    if not record_id:
        return JSONResponse({"error": "record_id required"}, status_code=400)

    try:
        update_user_fields_airtable(record_id, {
            "AccessControl": access_control
        })

        return {"status": "ok"}

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ============================================================
# API сохранения PrivacyControl
# ============================================================

@app.post("/api/user-management/update-privacy")
async def user_management_update_privacy(request: Request):

    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=403)

    actor_role = user["fields"].get("Role", "user")
    if actor_role not in ["moderator", "admin", "topadmin", "superadmin"]:
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    data = await request.json()

    record_id = data.get("record_id")
    privacy_control = (data.get("privacy_control") or "").strip()

    if not record_id:
        return JSONResponse({"error": "record_id required"}, status_code=400)

    try:
        update_user_fields_airtable(record_id, {
            "PrivacyControl": privacy_control
        })

        return {"status": "ok"}

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ============================================================
# WORKDESK
# ============================================================

@app.get("/workdesk", response_class=HTMLResponse)
def workdesk_page(request: Request):

    user = get_current_user(request)

    if not user:
        return RedirectResponse("/login?next=/workdesk", status_code=302)

    return templates.TemplateResponse(
        "workdesk.html",
        {
            "request": request,
            "user": user,
            "system": system_state
        }
    )


# ============================================================
# PROFILE EDIT POLICY
# ============================================================

PROFILE_EDIT_LIMIT = 3

def get_subscription_status(user):
    values = user["fields"].get("SubscriptionStatus") or []
    if not values:
        return "guest"
    return values[0]

def subscription_label_from_code(code: str):
    mapping = {
        "guest": "guest",
        "free": "free",
        "paid": "paid",
        "vip": "vip",
        "friend": "friend"
    }
    return mapping.get(code, code)

# ============================================================
# PROFILE UPDATE
# ============================================================

@app.post("/api/profile/update")
async def profile_update(request: Request):

    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=403)

    subscription_status = get_subscription_status(user)
    profile_edit_count = int(user["fields"].get("ProfileEditCount") or 0)

    user_id = user.get("id")
    has_ideas = False

    try:
        records = core.list_ideas_records()

        for rec in records:
            fields = rec.get("fields", {})
            authors = fields.get("Author", []) or []

            if user_id in authors:
                has_ideas = True
                break

    except Exception:
        return JSONResponse({"error": "Ideas check failed"}, status_code=500)

    if subscription_status in ["guest", "free"]:
        return JSONResponse(
            {"error": "Profile editing is not available for this subscription"},
            status_code=403
        )

    if not has_ideas:
        return JSONResponse(
            {"error": "At least one saved idea is required"},
            status_code=403
        )

    if profile_edit_count >= PROFILE_EDIT_LIMIT:
        return JSONResponse(
            {"error": "Profile edit limit reached"},
            status_code=403
        )

    data = await request.json()

    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    email = (data.get("email") or "").strip()
    country = (data.get("country") or "").strip()
    language = (data.get("language") or "").strip()
    contacts = (data.get("contacts") or "").strip()
    notes = (data.get("notes") or "").strip()

    postal_address = (data.get("postal_address") or "").strip()
    city = (data.get("city") or "").strip()
    postal_code = (data.get("postal_code") or "").strip()
    street = (data.get("street") or "").strip()
    house_number = (data.get("house_number") or "").strip()

    phone_user = (data.get("phone_user") or "").strip()
    avatar_url = (data.get("avatar_url") or "").strip()
    bio = (data.get("bio") or "").strip()
    about = (data.get("about") or "").strip()
    education = (data.get("education") or "").strip()
    interests = (data.get("interests") or "").strip()
    expertise = (data.get("expertise") or "").strip()
    reviewer_level = (data.get("reviewer_level") or "").strip()
    reviewer_specialization = (data.get("reviewer_specialization") or "").strip()
    preferred_language = (data.get("preferred_language") or "").strip()
    notification_settings = (data.get("notification_settings") or "").strip()

    full_name = " ".join(x for x in [first_name, last_name] if x).strip()

    try:
        core.update_user_profile_data(
            user_id=user["id"],
            full_name=full_name,
            last_name=last_name,
            email=email,
            country=country,
            language=language,
            contacts=contacts,
            notes=notes,
            postal_address=postal_address,
            city=city,
            postal_code=postal_code,
            street=street,
            house_number=house_number,
            phone_user=phone_user,
            avatar_url=avatar_url,
            bio=bio,
            about=about,
            education=education,
            interests=interests,
            expertise=expertise,
            reviewer_level=reviewer_level,
            reviewer_specialization=reviewer_specialization,
            preferred_language=preferred_language,
            notification_settings=notification_settings,
            new_edit_count=profile_edit_count + 1
        )
        return {"status": "ok"}

    except Exception as e:
        print("PROFILE UPDATE ERROR:", str(e))
        return JSONResponse({"error": str(e)}, status_code=500)

## ============================================================
# PROFILE
# ============================================================

@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):

    user = get_current_user(request)

    if not user:
        return RedirectResponse("/login", status_code=302)

    subscription_status = get_subscription_status(user)
    subscription_label = subscription_label_from_code(subscription_status)

    profile_edit_count = int(user["fields"].get("ProfileEditCount") or 0)

    user_id = user.get("id")
    has_ideas = False

    try:
        records = core.list_ideas_records()

        for rec in records:
            fields = rec.get("fields", {})
            authors = fields.get("Author", []) or []

            if user_id in authors:
                has_ideas = True
                break

    except Exception:
        has_ideas = False

    can_edit_profile = False
    profile_edit_reason = ""

    if subscription_status == "guest":
        profile_edit_reason = "Редактирование профиля недоступно для гостя."
    elif subscription_status == "free":
        profile_edit_reason = "Редактирование профиля доступно для платных подписчиков."
    elif not has_ideas:
        profile_edit_reason = "Редактирование профиля станет доступно после добавления хотя бы одной идеи."
    elif profile_edit_count >= PROFILE_EDIT_LIMIT:
        profile_edit_reason = "Лимит изменений профиля исчерпан."
    else:
        can_edit_profile = True

    profile_first_name, profile_last_name = split_name(
        user["fields"].get("Name") or ""
    )

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "user": user,
            "system": system_state,

            "subscription_status": subscription_status,
            "subscription_label": subscription_label,

            "profile_edit_count": profile_edit_count,
            "profile_edit_limit": PROFILE_EDIT_LIMIT,
            "can_edit_profile": can_edit_profile,
            "profile_edit_reason": profile_edit_reason,

            "profile_first_name": profile_first_name,
            "profile_last_name": profile_last_name
        }
    )



# ============================================================
# settings
# ============================================================
@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "user": user,
            "system": system_state
        }
    )

# ============================================================
# USER MESSAGES
# ============================================================

@app.get("/my-messages", response_class=HTMLResponse)
def user_messages_page(request: Request):

    user = get_current_user(request)

    if not user:
        return RedirectResponse("/login", status_code=302)

    user_email = (user["fields"].get("Email") or "").strip().lower()

    items = []

    try:
        records = core.list_feedback_records()

        for rec in records:
            fields = rec.get("fields", {})

            email = (
                fields.get("fldnpx1rtg3XjEYx6")
                or fields.get("Email")
                or ""
            ).strip().lower()

            if email != user_email:
                continue

            items.append({
                "id": rec.get("id"),
                "date": fields.get("fldmrXTsjH2P0RrAd") or fields.get("Date"),
                "subject": fields.get("fldFJa7ZFFGallWxH") or fields.get("Subject"),
                "message": fields.get("fld7bhc2zngIgj1B2") or fields.get("Message"),
                "status": fields.get("fldH2ZVXQPq07ATdU") or fields.get("Status") or "New",
                "answer_text": fields.get("fldpb9lEkDObdhFuV") or fields.get("AnswerText")
            })

    except Exception:
        items = []

    answered_count = sum(1 for x in items if x.get("status") == "Answered")

    return templates.TemplateResponse(
        "user_messages.html",
        {
            "request": request,
            "user": user,
            "system": system_state,
            "items": items,
            "answered_count": answered_count
        }
    )

# ============================================================
# DRAFTS
# ============================================================

@app.get("/drafts", response_class=HTMLResponse)
def drafts_page(request: Request):

    user = get_current_user(request)

    if not user:
        return RedirectResponse("/login", status_code=302)

    user_id = user.get("id")
    items = []

    try:
        records = core.list_ideas_records()

        for rec in records:
            fields = rec.get("fields", {})
            authors = fields.get("Author", []) or []
            status_value = fields.get("Status") or ""

            if user_id not in authors:
                continue

            if status_value != "Draft":
                continue

            items.append({
                "id": rec.get("id"),
                "idea_id": fields.get("IdeaID"),
                "title": fields.get("Title"),
                "status": status_value,
                "date": fields.get("Date Added")
            })

    except Exception:
        items = []

    return templates.TemplateResponse(
        "drafts.html",
        {
            "request": request,
            "user": user,
            "system": system_state,
            "items": items
        }
    )


# ============================================================
# FEEDBACK
# ============================================================

@app.get("/feedback", response_class=HTMLResponse)
def feedback_page(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse(
        "feedback.html",
        {
            "request": request,
            "user": user,
            "system": system_state
        }
    )

# ============================================================
# FEEDBACK send
# ============================================================

@app.post("/api/feedback/send")
async def feedback_send(request: Request):

    data = await request.json()

    subject = (data.get("subject") or "").strip()
    message = (data.get("message") or "").strip()
    page = (data.get("page") or "").strip()
    email = (data.get("email") or "").strip()
    name = (data.get("name") or "").strip()

    if not message:
        return JSONResponse(
            {"status": "error", "message": "Message required"},
            status_code=400
        )

    try:
        result = core.create_feedback_record({
            "name": name,
            "email": email,
            "subject": subject,
            "message": message,
            "page": page
        })

        return {
            "status": "ok",
            "id": result.get("id")
        }

    except Exception as e:

        err_text = str(e)
        err_lower = err_text.lower()

        is_temp = (
            "429" in err_text or
            "timeout" in err_lower or
            "connection" in err_lower or
            "503" in err_text or
            "502" in err_text or
            "504" in err_text or
            "500" in err_text
        )

        if is_temp:
            try:
                now_utc = datetime.datetime.utcnow().isoformat()

                buffer_result = core.save_feedback_buffer_record({
                    "created_at": now_utc,
                    "name": name,
                    "email": email,
                    "subject": subject,
                    "message": message,
                    "page": page,
                    "error_text": err_text
                })

                return {
                    "status": "buffer_saved",
                    "local_id": buffer_result.get("local_id"),
                    "message": "Saved to buffer"
                }

            except Exception as buffer_error:
                return JSONResponse(
                    {
                        "status": "hard_fail",
                        "message": str(buffer_error)
                    },
                    status_code=500
                )

        return JSONResponse(
            {"status": "error", "message": err_text},
            status_code=500
        )

# ============================================================
# FEEDBACK STATUS UPDATE
# ============================================================

@app.post("/api/feedback/status")
async def feedback_update_status(request: Request):

    data = await request.json()

    record_id = data.get("id")
    status = data.get("status")

    user = get_current_user(request)

    if not record_id or not status:
        return JSONResponse({"error": "Invalid data"}, status_code=400)

    try:
        name = None
        if user:
            name = user["fields"].get("Name") or user["fields"].get("Email")

        core.update_feedback_status(record_id, status, name)

        return {"status": "ok"}

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ============================================================
# MY IDEAS
# ============================================================

@app.get("/my-ideas", response_class=HTMLResponse)
def my_ideas_page(request: Request):

    user = get_current_user(request)

    if not user:
        return RedirectResponse("/login", status_code=302)

    user_id = user.get("id")
    items = []

    try:
        records = core.list_ideas_records()

        for rec in records:
            fields = rec.get("fields", {})
            authors = fields.get("Author", []) or []

            if user_id not in authors:
                continue

            items.append({
                "id": rec.get("id"),
                "idea_id": fields.get("IdeaID"),
                "title": fields.get("Title"),
                "status": fields.get("Status"),
                "date": fields.get("Date Added")
            })

    except Exception:
        items = []

    return templates.TemplateResponse(
        "my_ideas.html",
        {
            "request": request,
            "user": user,
            "system": system_state,
            "items": items
        }
    )

# ============================================================
# ARCHIVE
# ============================================================

@app.get("/archive", response_class=HTMLResponse)
def archive_page(request: Request):

    user = get_current_user(request)

    if not user:
        return RedirectResponse("/login", status_code=302)

    user_id = user.get("id")
    items = []

    try:
        records = core.list_ideas_records()

        for rec in records:
            fields = rec.get("fields", {})
            authors = fields.get("Author", []) or []
            status_value = fields.get("Status") or ""

            if user_id not in authors:
                continue

            if status_value != "Archived":
                continue

            items.append({
                "id": rec.get("id"),
                "idea_id": fields.get("IdeaID"),
                "title": fields.get("Title"),
                "status": status_value,
                "date": fields.get("Date Added")
            })

    except Exception:
        items = []

    return templates.TemplateResponse(
        "archive.html",
        {
            "request": request,
            "user": user,
            "system": system_state,
            "items": items
        }
    )


# ============================================================
# HELP
# ============================================================

@app.get("/help", response_class=HTMLResponse)
def help_page(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse(
        "help.html",
        {
            "request": request,
            "user": user,
            "system": system_state
        }
    )

# ============================================================
# SET PASSWORD
# ============================================================

@app.get("/set-password", response_class=HTMLResponse)
def set_password_page(request: Request):

    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    return templates.TemplateResponse(
        "set_password.html",
        {"request": request, "user": user, "system": system_state}
    )


@app.post("/set-password")
def set_password_submit(request: Request, password: str = Form(...)):

    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    if len(password) < 3:
        return templates.TemplateResponse(
            "set_password.html",
            {
                "request": request,
                "user": user,
                "error": "Пароль слишком короткий",
                "system": system_state
            }
        )

    core.set_user_password(user["id"], password)

    sid = request.cookies.get("mindmesh_session")
    if sid in SESSIONS:
        SESSIONS[sid]["access_level"] = "user_full"

    return RedirectResponse("/cabinet", status_code=302)


# ============================================================
# SIMPLE & ADVANCED PAGES
# ============================================================

@app.get("/simple", response_class=HTMLResponse)
def simple_page(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse(
        "simple.html",
        {"request": request, "user": user}
    )

# ============================================================
# ADVANCED MODE (unchanged API)
# ============================================================

@app.get("/advanced", response_class=HTMLResponse)
def advanced(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse(
        "advanced.html",
        {"request": request, "user": user}
    )

# ============================================================
# Searchwave API
# ============================================================

@app.get("/api/system/log")
def get_system_log(request: Request):

    user = get_current_user(request)
    if not require_superadmin(user):
        return JSONResponse({"error": "Unauthorized"}, status_code=403)

    return {"log": system_state.get("log", [])}


@app.get("/api/admin/users")
def list_users(request: Request):

    user = get_current_user(request)
    if not require_superadmin(user):
        return JSONResponse({"error": "Unauthorized"}, status_code=403)

    try:
        users = core.get_all_users()
    except AttributeError:
        return {"users": []}

    simplified = []

    for u in users:
        simplified.append({
            "id": u["id"],
            "email": u["fields"].get("Email"),
            "role": u["fields"].get("Role", "user")
        })

    return {"users": simplified}

# ============================================================
# AI Collector Agent
# ============================================================    
    
@app.get("/collector")
def collector_page():
    return FileResponse("web/templates/collector_agent.html")   
    
# ============================================================
# AI Collector Agent duplicates
# ============================================================ 

@app.post("/api/collector/check-duplicates")
async def collector_check_duplicates(request: Request):

    user = get_current_user(request)

    session_info = {
        "authenticated": bool(user),
        "user_id": user.get("id") if user else None,
        "role": user.get("fields", {}).get("Role") if user else "guest",
        "email": user.get("fields", {}).get("Email") if user else None
    }

    data = await request.json()
    idea = data.get("idea") or {}

    title = idea.get("title") or ""
    short = idea.get("short_description") or ""
    full = idea.get("full_description") or ""
    keywords_raw = idea.get("keywords") or ""

    if isinstance(keywords_raw, str):
        keywords = [x.strip() for x in keywords_raw.split(",") if x.strip()]
    else:
        keywords = keywords_raw or []

    query_text = "\n".join([
        title,
        short,
        ", ".join(keywords),
        full[:1200]
    ])

    try:
        result = postgres_db.safe_find_best_duplicate_pg(query_text, keywords)

        candidates = postgres_db.find_duplicate_candidates_pg(
            query_text,
            keywords,
            limit=10
        )

        if not result.get("ok"):
            return {
                "status": "ok",
                "session": session_info,
                "duplicate_found": False,
                "check_degraded": True,
                "message": result.get("error")
            }

        best = result.get("best")
        score = result.get("score") or 0

        if not best:
            return {
                "status": "ok",
                "session": session_info,
                "duplicate_found": False,
                "check_degraded": False,
                "message": "No duplicates found",
                "candidates": candidates,
                "candidates_count": len(candidates),
                 "debug": result
            }

        fields = best.get("fields", {})
        similarity_score = int(score * 100)

        return {
            "status": "ok",
            "session": session_info,
            "duplicate_found": True,
            "check_degraded": False,
            "similarity_score": similarity_score,
            "duplicate_level": "exact" if similarity_score >= 85 else "possible",
            "save_allowed": False if similarity_score >= 85 else True,
            "candidates": candidates,
            "candidates_count": len(candidates),
            
            "debug": best.get("debug") if best else None,
            
            
            "idea": {
                "id": best.get("id"),
                "idea_id": fields.get("IdeaID"),
                "title": fields.get("Title"),
                "short": fields.get("Short Description"),
                "category": fields.get("Category"),
                "status": fields.get("Status"),
                "author": fields.get("Author"),
                "created_at": fields.get("CreatedAt")
            }
        }

    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


# ============================================================
# TOPADMIN PANEL
# ============================================================

@app.get("/topadmin", response_class=HTMLResponse)
def topadmin_panel(request: Request):

    user = get_current_user(request)

    if not user:
        return RedirectResponse("/login?next=/topadmin", status_code=302)

    role = user["fields"].get("Role", "user")

    if role not in ["topadmin", "superadmin"]:
        return RedirectResponse("/", status_code=302)

    return FileResponse(
        os.path.join("web", "search", "topadmin.html")
    )
    # user_management
    

# ============================================================
# ADMIN PANEL
# ============================================================

@app.get("/admin", response_class=HTMLResponse)
def admin_panel(request: Request):

    user = get_current_user(request)

    if not user:
        return RedirectResponse("/login?next=/admin", status_code=302)

    role = user["fields"].get("Role", "user")

    if role not in ["admin", "topadmin", "superadmin"]:
        return RedirectResponse("/", status_code=302)

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "user": user,
            "system": system_state
        }
    )

# ============================================================
# MODERATOR PANEL
# ============================================================

@app.get("/moderator", response_class=HTMLResponse)
def moderator_panel(request: Request):

    user = get_current_user(request)

    if not user:
        return RedirectResponse("/login?next=/moderator", status_code=302)

    role = user["fields"].get("Role", "user")

    if role not in ["moderator", "admin", "topadmin", "superadmin"]:
        return RedirectResponse("/", status_code=302)

    return templates.TemplateResponse(
        "moderator.html",
        {
            "request": request,
            "user": user,
            "system": system_state
        }
    )

# ============================================================
# MESSAGES  
# ============================================================

@app.get("/messages", response_class=HTMLResponse)
def messages_page(request: Request):

    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login?next=/messages", status_code=302)

    role = user["fields"].get("Role", "user")

    if role not in ["moderator", "admin", "topadmin", "superadmin"]:
        return RedirectResponse("/", status_code=302)

    return templates.TemplateResponse(
        "messages.html",
        {
            "request": request,
            "user": user,
            "system": system_state
        }
    )

# ============================================================
# API MESSAGES LIST
# ============================================================

@app.get("/api/messages/list")
def messages_list(request: Request):

    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=403)

    role = user["fields"].get("Role", "user")
    if role not in ["moderator", "admin", "topadmin", "superadmin"]:
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    try:
        records = core.list_feedback_records()

        items = []

        for rec in records:
            fields = rec.get("fields", {})

            items.append({
                "id": rec.get("id"),
                "date": fields.get("fldmrXTsjH2P0RrAd") or fields.get("Date"),
                "name": fields.get("fldQWIPuNzQaPzZ3Q") or fields.get("Name"),
                "email": fields.get("fldnpx1rtg3XjEYx6") or fields.get("Email"),
                "subject": fields.get("fldFJa7ZFFGallWxH") or fields.get("Subject"),
                "message": fields.get("fld7bhc2zngIgj1B2") or fields.get("Message"),
                "page": fields.get("fld23LeOQj9UD5Bls") or fields.get("Page"),
                "status": fields.get("fldH2ZVXQPq07ATdU") or fields.get("Status") or "New",
                "answered_by": fields.get("fldtr3v4oe8jk8eij") or fields.get("AnsweredBy"),
                "answered_at": fields.get("fldPiiU6NgrHZb6gt") or fields.get("AnsweredAt"),
                "answer_text": fields.get("fldpb9lEkDObdhFuV") or fields.get("AnswerText"),
                "answer_status": fields.get("fldwJLeIDcjqgF22U") or fields.get("AnswerStatus")
            })

        unread_count = sum(1 for x in items if x.get("status") == "New")

        return {
            "status": "ok",
            "total": len(items),
            "unread": unread_count,
            "items": items
        }

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ============================================================
# API MESSAGE ITEM
# ============================================================

@app.get("/api/messages/item/{record_id}")
def message_item(record_id: str, request: Request):

    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=403)

    role = user["fields"].get("Role", "user")
    if role not in ["moderator", "admin", "topadmin", "superadmin"]:
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    try:
        rec = core.get_feedback_record(record_id)
        fields = rec.get("fields", {})

        return {
            "status": "ok",
            "item": {
                "id": rec.get("id"),
                "date": fields.get("fldmrXTsjH2P0RrAd") or fields.get("Date"),
                "name": fields.get("fldQWIPuNzQaPzZ3Q") or fields.get("Name"),
                "email": fields.get("fldnpx1rtg3XjEYx6") or fields.get("Email"),
                "subject": fields.get("fldFJa7ZFFGallWxH") or fields.get("Subject"),
                "message": fields.get("fld7bhc2zngIgj1B2") or fields.get("Message"),
                "page": fields.get("fld23LeOQj9UD5Bls") or fields.get("Page"),
                "status_value": fields.get("fldH2ZVXQPq07ATdU") or fields.get("Status") or "New",
                "notes": fields.get("fldLXhVAWAyFmpUn2") or fields.get("Notes"),
                "answered_by": fields.get("fldtr3v4oe8jk8eij") or fields.get("AnsweredBy"),
                "answered_at": fields.get("fldPiiU6NgrHZb6gt") or fields.get("AnsweredAt"),
                "answer_text": fields.get("fldpb9lEkDObdhFuV") or fields.get("AnswerText"),
                "answer_status": fields.get("fldwJLeIDcjqgF22U") or fields.get("AnswerStatus")
            }
        }

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ============================================================
# API MESSAGE STATUS UPDATE
# ============================================================

@app.post("/api/messages/status")
async def message_status_update(request: Request):

    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=403)

    role = user["fields"].get("Role", "user")
    if role not in ["moderator", "admin", "topadmin", "superadmin"]:
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    data = await request.json()

    record_id = data.get("id")
    status_value = data.get("status")

    if not record_id or not status_value:
        return JSONResponse({"error": "Invalid data"}, status_code=400)

    try:
        actor = user["fields"].get("Name") or user["fields"].get("Email") or "Admin"
        core.update_feedback_status(record_id, status_value, actor)

        return {"status": "ok"}

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ============================================================
# API MESSAGE REPLY SAVE
# ============================================================

@app.post("/api/messages/reply")
async def message_reply_save(request: Request):

    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=403)

    role = user["fields"].get("Role", "user")
    if role not in ["moderator", "admin", "topadmin", "superadmin"]:
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    data = await request.json()

    record_id = data.get("id")
    answer_text = (data.get("answer_text") or "").strip()

    if not record_id or not answer_text:
        return JSONResponse({"error": "Invalid data"}, status_code=400)

    try:
        actor = user["fields"].get("Name") or user["fields"].get("Email") or "Admin"
        core.save_feedback_reply(record_id, answer_text, actor)

        return {"status": "ok"}

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ============================================================
# SIMPLE MODE ANALYZE  ✅ PostgreSQL duplicate check
# ============================================================

@app.post("/api/simple/analyze")
async def simple_analyze(request: Request):
    data = await request.json()
    raw_text = data.get("raw_text")

    if not raw_text or not str(raw_text).strip():
        return JSONResponse({"error": "No text provided"}, status_code=400)

    # --- intake analysis ---
    analysis = analyze_intake(raw_text)

    if isinstance(analysis, dict) and "error" in analysis:
        return JSONResponse({"error": analysis["error"]}, status_code=400)

    # --- duplicate search (PostgreSQL) ---
    query = analysis.get("title") or analysis.get("full") or str(raw_text)

    dup_result = postgres_db.safe_find_best_duplicate_pg(
        query,
        analysis.get("keywords", [])
    )

    # --- degraded mode: duplicate check unavailable ---
    if not dup_result.get("ok"):
        print("DUPLICATE ERROR:", dup_result.get("error"))

        return {
            "analysis": analysis,
            "duplicate_id": None,
            "duplicate_title": None,
            "similarity": 0,
            "duplicate_check_unavailable": True,
            "read_degraded_mode": True,
            "debug_note": dup_result.get("error")
        }

    best = dup_result.get("best")
    score = dup_result.get("score", 0.0)

    similarity = int(score * 100) if score else 0
    duplicate_id = None
    duplicate_title = None

    if best:
        duplicate_id = best.get("id")
        duplicate_title = best.get("fields", {}).get("Title")

    return {
        "analysis": analysis,
        "duplicate_id": duplicate_id,
        "duplicate_title": duplicate_title,
        "similarity": similarity,
        "duplicate_check_unavailable": False,
        "read_degraded_mode": False
    }
 
# ============================================================
# SIMPLE FAILURE LOG ENDPOINT
# ============================================================

@app.post("/api/simple/failure-log")
async def simple_failure_log(request: Request):

    data = await request.json()

    try:
        core.create_simple_failure_log(data)
        return {"status": "logged"}
    except Exception as e:
        return JSONResponse({"error": "log_failed"}, status_code=500)
 
    # ============================================================
# SIMPLE MODE CONFIRM SAVE
# ============================================================

@app.post("/api/simple/confirm")
async def simple_confirm(request: Request):

    data = await request.json()

    analysis = data.get("analysis") or {}
    raw_text = data.get("raw_text", "")
    duplicate_id = data.get("duplicate_id")
    similarity = data.get("similarity", 0)
    email = data.get("email")
    name = data.get("name", "")

    # --- email required ---
    if not email:
        print("SIMPLE_CONFIRM: need_email")    # === временно
        return JSONResponse(
            {"status": "need_email"},
            status_code=401
        )

    try:
        result = postgres_db.create_idea_pg({
            "title": analysis.get("title", ""),
            "short": analysis.get("short", ""),
            "full": analysis.get("full", ""),
            "keywords_list": analysis.get("keywords", []),
            "author_email": email,
            "author_name": name,
            "raw_input": raw_text,
            "intake_mode": "simple",
            "assistant_version": "Simple 2.0",
            "related_to_id": duplicate_id if duplicate_id else None,
            "status_override": "New"
        })

        return {
            "status": "ok",
            "idea_id": result["idea_id"]
        }

    except Exception as e:
        err_text = str(e)
        err_lower = err_text.lower()

        # --- treat Airtable temporary problems as buffer-save scenario ---
        is_temp = (
            "429" in err_text or
            "timeout" in err_lower or
            "connection" in err_lower or
            "temporary unavailable" in err_lower or
            "503" in err_text or
            "502" in err_text or
            "504" in err_text or
            "500" in err_text
        )

        if is_temp:
            try:
                now_utc = datetime.datetime.utcnow().isoformat()

                buffer_result = core.save_simple_buffer_record({
                    "created_at": now_utc,
                    "raw_text": raw_text,
                    "title": analysis.get("title", ""),
                    "short": analysis.get("short", ""),
                    "full": analysis.get("full", ""),
                    "keywords": analysis.get("keywords", []),
                    "author_name": name,
                    "author_email": email,
                    "duplicate_id": duplicate_id,
                    "similarity": similarity,
                    "intake_mode": "simple",
                    "assistant_version": "Simple 2.0",
                    "error_code": "AIRTABLE_TEMP_UNAVAILABLE",
                    "error_text": err_text,
                    "save_stage": "confirm"
                })

                # optional failure log
                try:
                    core.create_simple_failure_log({
                        "local_id": buffer_result.get("local_id"),
                        "created_at": now_utc,
                        "mode_version": "Simple 2.0",
                        "error_code": "AIRTABLE_TEMP_UNAVAILABLE",
                        "user_message": "Saved to local buffer",
                        "tech_message": err_text,
                        "http_status": 429 if "429" in err_text else 500,
                        "endpoint": "/api/simple/confirm",
                        "email": email,
                        "title": analysis.get("title", ""),
                        "keywords": ", ".join(analysis.get("keywords", [])),
                        "raw_input_length": len(raw_text or ""),
                        "similarity": similarity,
                        "duplicate_id": duplicate_id,
                        "server_time_utc": now_utc,
                        "server_component": "Airtable"
                    })
                except Exception:
                    pass

                return {
                    "status": "buffer_saved",
                    "local_id": buffer_result.get("local_id"),
                    "message": "Database temporarily unavailable. Idea saved to reserve buffer."
                }

            except Exception as buffer_error:
                return JSONResponse(
                    {
                        "status": "hard_fail",
                        "message": f"Buffer save failed: {str(buffer_error)}"
                    },
                    status_code=500
                )

        return JSONResponse(
            {"status": "error", "message": err_text},
            status_code=500
        )

# ============================================================
# SYSTEM STATE API
# ============================================================

@app.get("/api/system/state")
def get_system_state():

    return {
        "status": "working",
        "test_mode": system_state.get("test_mode", False),
        "maintenance": system_state.get("maintenance", "none")
    }


# ============================================================
# SYSTEM MODE CONTROL
# ============================================================

@app.post("/api/system/toggle-test")
def toggle_test():

    system_state["test_mode"] = not system_state.get("test_mode", False)

    return {"ok": True, "test_mode": system_state["test_mode"]}


@app.post("/api/system/maintenance/soft")
def maintenance_soft():

    system_state["maintenance"] = "soft"

    return {"ok": True, "maintenance": "soft"}


@app.post("/api/system/maintenance/full")
def maintenance_full():

    system_state["maintenance"] = "full"

    return {"ok": True, "maintenance": "full"}


@app.post("/api/system/maintenance/disable")
def maintenance_disable():

    system_state["maintenance"] = "none"

    return {"ok": True, "maintenance": "none"}
    
# ============================================================
# USERS_COUNT
# ============================================================  
@app.get("/api/admin/users_count")
def admin_users_count(request: Request):

    user = get_current_user(request)
    if not require_superadmin(user):
        return JSONResponse({"error": "Unauthorized"}, status_code=403)

    try:
        users = core.get_all_users()
        return {"total_users": len(users)}
    except Exception as e:
        return {"total_users": 0, "error": str(e)}
        
# ============================================================
# admin API
# ============================================================        
        
@app.get("/api/admin/ideas_stats")
def ideas_stats():

    from core import load_env, ideas_url, airtable_headers
    import requests
    import datetime

    try:
        pat = load_env()
        url = ideas_url(pat)
        headers = airtable_headers(pat)

        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()

        records = r.json().get("records", [])

        stats = {}
        total = len(records)

        today = datetime.date.today()
        week_start = today - datetime.timedelta(days=7)
        month_start = today - datetime.timedelta(days=30)

        ideas_today = 0
        ideas_week = 0
        ideas_month = 0

        for rec in records:
            fields = rec.get("fields", {})
            status = fields.get("Status", "Unknown")

            stats[status] = stats.get(status, 0) + 1

            date = fields.get("Date Added")
            if date:
                d = datetime.datetime.fromisoformat(
                    date.replace("Z", "")
                ).date()

                if d == today:
                    ideas_today += 1

                if d >= week_start:
                    ideas_week += 1

                if d >= month_start:
                    ideas_month += 1

        return {
            "total": total,
            "today": ideas_today,
            "week": ideas_week,
            "month": ideas_month,
            "stats": stats,
            "degraded": False
        }

    except Exception:
        return {
            "total": 0,
            "today": 0,
            "week": 0,
            "month": 0,
            "stats": {},
            "degraded": True
        }


# ============================================================
# MODERATION HUB
# ============================================================

@app.get("/moderation", response_class=HTMLResponse)
def moderation_page(request: Request):

    user = get_current_user(request)

    if not user:
        return RedirectResponse("/login?next=/moderation", status_code=302)

    role = user["fields"].get("Role", "user")

    if role not in ["moderator", "admin", "topadmin", "superadmin"]:
        return RedirectResponse("/", status_code=302)

    return templates.TemplateResponse(
        "moderation.html",
        {
            "request": request,
            "user": user,
            "system": system_state
        }
    )


# ============================================================
# UPDATE USER PROFILE
# ============================================================

@app.post("/api/user/update")
async def update_user(request: Request):

    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=403)

    data = await request.json()

    name = (data.get("name") or "").strip()

    if len(name) > 100:
        return JSONResponse({"error": "Name too long"}, status_code=400)

    try:
        core.update_user_name(user["id"], name)
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ============================================================
# PROFILE HELPERS
# ============================================================

PROFILE_EDIT_LIMIT = 4


def get_subscription_status(user):
    values = user["fields"].get("SubscriptionStatus") or []
    if not values:
        return "guest"
    return values[0]


def subscription_label_from_code(code: str):
    mapping = {
        "guest": "guest",
        "free": "free",
        "paid": "paid",
        "vip": "vip",
        "friend": "friend"
    }
    return mapping.get(code, code)


def split_name(full_name: str):
    full_name = (full_name or "").strip()
    if not full_name:
        return "", ""

    parts = full_name.split(" ", 1)
    first_name = parts[0].strip() if len(parts) > 0 else ""
    last_name = parts[1].strip() if len(parts) > 1 else ""

    return first_name, last_name

# ============================================================
# AUTH INFO
# ============================================================

@app.get("/api/auth/me")
def auth_me(request: Request):

    user = get_current_user(request)

    if not user:
        return {
            "is_authenticated": False,
            "role": "guest",
            "name": "Guest",
            "email": None,
            "auth_type": "anonymous"
        }

    return {
        "is_authenticated": True,
        "role": user["fields"].get("Role", "user"),
        "name": user["fields"].get("Name", "") or "User",
        "email": user["fields"].get("Email", ""),
        "auth_type": "local password",
        "access_level": user.get("access_level", "user_light")
    }
    

# ============================================================
# REVIEWER
# ============================================================

@app.get("/reviewer", response_class=HTMLResponse)
def reviewer_page(request: Request):

    user = get_current_user(request)

    if not user:
        return RedirectResponse("/login?next=/reviewer", status_code=302)

    role = user["fields"].get("Role", "user")

    if role not in ["moderator", "admin", "topadmin", "superadmin"]:
        return RedirectResponse("/", status_code=302)

    return templates.TemplateResponse(
        "reviewer.html",
        {
            "request": request,
            "user": user,
            "system": system_state
        }
    )

# ============================================================
# REVIEWER API - QUEUE
# ============================================================

@app.get("/api/reviewer/queue")
def reviewer_queue(request: Request):

    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=403)

    role = user["fields"].get("Role", "user")
    if role not in ["moderator", "admin", "topadmin", "superadmin"]:
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    try:
        records = core.list_ideas_records()

        items = []

        for rec in records:
            f = rec.get("fields", {})

            # === ФИЛЬТР ДЛЯ REVIEWER ===
            # идеи, найденные ИИ и ещё не проверенные

            ai_status = f.get("AIReviewStatus")
            detected = f.get("DetectedByAI") or f.get("DiscoveredByAI")
            done = f.get("Done")

            if not detected:
                continue

            if ai_status in ["Done", "Approved"]:
                continue

            if done:
                continue

            items.append({
                "id": rec.get("id"),
                "fields": f
            })

        return {
            "status": "ok",
            "records": items
        }

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ============================================================
# HIDDEN ENTRY — SEARCHWAVE
# ============================================================

SECRET_KEY = "7391"


@app.get("/searchwave", response_class=HTMLResponse)
def hidden_entry(request: Request, key: str = ""):

    user = get_current_user(request)

    if key != SECRET_KEY:
        return RedirectResponse("/", status_code=302)

    if not user:
        return RedirectResponse(
            f"/login?next=/searchwave?key={SECRET_KEY}",
            status_code=302
        )

    role = user["fields"].get("Role", "user")

    if role != "superadmin" or user.get("access_level") != "user_full":
        return RedirectResponse("/", status_code=302)

    return FileResponse(
        os.path.join("web", "search", "searchwave.html")
    )

# ============================================================
#system_error
# ============================================================

    
def is_system_error(e: Exception) -> bool:
    msg = str(e).lower()

    return any(x in msg for x in [
        "airtable",
        "postgres",
        "connection",
        "timeout",
        "refused",
        "429",
        "too many requests"
    ])    


# ============================================================
#collector_agent endpoint
# ============================================================
# Endpoint: /api/collector/run
# Version: v0.3
# Date: 2026-05-07
# Name: Collector Agent Run (запуск агента-сборщика)
# ============================================================

@app.post("/api/collector/run")
async def collector_run(
    agent_session_id: str = Form(""),
    source_url: str = Form(""),
    source_type: str = Form("website"),
    instructions: str = Form(""),
    mode: str = Form("collector_agent"),
    mode_version: str = Form("Collector Agent v0.3"),
    source_file: UploadFile | None = File(None)
):
    source_url = (source_url or "").strip()

    payload = {
        "agent_session_id": agent_session_id,
        "source_url": source_url,
        "source_type": source_type,
        "instructions": instructions,
        "mode": mode,
        "mode_version": mode_version
    }

    try:
        if source_file is not None and source_file.filename:
            raw = await source_file.read()

            if not raw:
                return JSONResponse(
                    {"status": "error", "message": "Uploaded file is empty"},
                    status_code=400
                )

            result = collector_agent.build_collector_result_from_file(
                payload=payload,
                filename=source_file.filename,
                raw=raw,
                content_type=source_file.content_type or ""
            )

            return result

        if not source_url:
            return JSONResponse(
                {"status": "error", "message": "Source URL or file is required"},
                status_code=400
            )

        if not source_url.startswith(("http://", "https://")):
            return JSONResponse(
                {"status": "error", "message": "Only http/https URLs are allowed"},
                status_code=400
            )

        result = collector_agent.build_collector_result(payload)
        return result

    except Exception as e:
        return JSONResponse(
            {
                "status": "error",
                "message": str(e)
            },
            status_code=500
        )
 
# ============================================================
# Name: Collector Save Draft (сохранение черновика сборщика)
# ============================================================

@app.post("/api/collector/save-draft")
async def collector_save_draft(request: Request):

    data = await request.json()

    try:

        buffer_result = core.save_collector_buffer(data)

        if not buffer_result.get("ok"):

            return JSONResponse(
                {
                    "status": "error",
                    "message": buffer_result.get("error")
                },
                status_code=500
            )

        return {
            "status": "ok",
            "saved_as": "buffer_collector",
            "buffer_file": buffer_result.get("filename"),
            "idea_id": buffer_result.get("filename")
        }

    except Exception as e:

        return JSONResponse(
            {
                "status": "error",
                "message": str(e)
            },
            status_code=500
        )

# ============================================================
# Collector Agent Save Ready
# ============================================================
# Endpoint: /api/collector/save-ready
# Version: v0.4
# Date: 2026-05-13
# Name: Collector Save Ready (сохранение готовой идеи сборщика)
# ============================================================

@app.post("/api/collector/save-ready")
async def collector_save_ready(request: Request):

    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=403)

    data = await request.json()

    idea = data.get("idea") or {}
    raw_agent_result = data.get("raw_agent_result") or {}
    duplicate_data = data.get("duplicate_data") or {}
    duplicate_decision = data.get("duplicate_decision")

    if not duplicate_data:
        return JSONResponse(
            {
                "status": "error",
                "message": "Duplicate check required before save"
            },
            status_code=400
        )

    duplicate_found = bool(duplicate_data.get("duplicate_found"))
    duplicate_level = duplicate_data.get("duplicate_level")
    duplicate_idea = duplicate_data.get("idea") or {}
    duplicate_id = duplicate_idea.get("id")
    duplicate_title = duplicate_idea.get("title")
    similarity_score = duplicate_data.get("similarity_score") or 0

    # --------------------------------------------------------
    # DECISION REQUIRED FOR FOUND DUPLICATE
    # --------------------------------------------------------

    if duplicate_found and not duplicate_decision:
        return JSONResponse(
            {
                "status": "error",
                "message": "Duplicate decision required before save"
            },
            status_code=400
        )

    # --------------------------------------------------------
    # EXACT DUPLICATE BLOCK
    # only independent save is blocked.
    # linked_duplicate and send_to_review are allowed.
    # --------------------------------------------------------

    if (
        duplicate_found
        and duplicate_level == "exact"
        and duplicate_decision not in ["linked_duplicate", "send_to_review"]
    ):
        return JSONResponse(
            {
                "status": "error",
                "message": "Exact duplicate found. Saving as new idea is blocked.",
                "duplicate_id": duplicate_id,
                "duplicate_title": duplicate_title,
                "similarity_score": similarity_score
            },
            status_code=409
        )

    user_fields = user.get("fields", {})
    user_id = user.get("id")
    user_email = user_fields.get("Email") or ""
    user_name = user_fields.get("Name") or user_email or "Admin"
    user_role = user_fields.get("Role") or "admin"

    if not user_email:
        return JSONResponse(
            {"status": "error", "message": "User email required"},
            status_code=400
        )

    try:
        keywords_raw = idea.get("keywords") or ""

        if isinstance(keywords_raw, str):
            keywords_list = [
                x.strip()
                for x in keywords_raw.split(",")
                if x.strip()
            ]
        else:
            keywords_list = keywords_raw

        # ----------------------------------------------------
        # RELATION DECISION
        # ----------------------------------------------------

        related_to_id = None
        relation_type = None
        moderation_note = "Collector Agent submission. Requires moderation."

        if duplicate_found and duplicate_decision == "linked_duplicate":
            related_to_id = duplicate_id
            relation_type = "duplicate"
            moderation_note = (
                "Collector Agent submission. "
                "Saved as linked duplicate. "
                f"Duplicate match: {duplicate_title}. "
                f"Similarity: {similarity_score}%."
            )

        elif duplicate_found and duplicate_decision == "send_to_review":
            related_to_id = duplicate_id
            relation_type = "needs_review"
            moderation_note = (
                "Collector Agent submission. "
                "Duplicate found; sent to moderator review. "
                f"Possible match: {duplicate_title}. "
                f"Similarity: {similarity_score}%."
            )

        elif duplicate_found:
            related_to_id = duplicate_id
            relation_type = "possible_duplicate"
            moderation_note = (
                "Collector Agent submission. "
                "Possible duplicate. Requires moderator verification. "
                f"Possible match: {duplicate_title}. "
                f"Similarity: {similarity_score}%."
            )

        # ----------------------------------------------------
        # CREATE IDEA DATA
        # ----------------------------------------------------

        create_data = {
            "title": idea.get("title") or "Collector idea",
            "short": idea.get("short_description") or "",
            "full": idea.get("full_description") or "",
            "keywords_list": keywords_list,

            "author_email": user_email,
            "author_name": user_name,

            "category": idea.get("category"),
            "region": idea.get("region"),
            "language": idea.get("language"),

            "source": "CollectorAgent",
            "existing_analogues": idea.get("existing_analogues"),
            "patentability": idea.get("patentability"),

            "notes_ai": idea.get("notes_ai"),
            "ai_tags": idea.get("ai_tags"),

            "raw_input": idea.get("full_description") or "",

            "detected_by_ai": True,
            "discovered_by_ai": True,

            "ai_review_status": "NeedsModeration",
            "status_override": "Review",
            "intake_mode": "collector_agent",
            "assistant_version": "Collector Agent v0.7",

            "related_to_id": related_to_id,
            "similarity_score": similarity_score,
            "relation_type": relation_type,

            "requires_moderation": True,
            "visibility_status": "internal",
            "confidentiality_level": "Internal",

            "checked_by_user_id": user_id,
            "checked_by_role": user_role,
            "checked_by_name": user_name,
            "checked_by_email": user_email,
            "checked_at": datetime.datetime.utcnow().isoformat(),

            "collector_session_id": data.get("agent_session_id"),
            "collector_source_filename": idea.get("source"),
            "collector_source_url": data.get("source_url"),
            "collector_source_type": "file_or_url",
            "collector_raw_agent_result": raw_agent_result,

            "moderation_notes": moderation_note
        }

        created = postgres_db.create_idea_pg(create_data)

        return {
           "status": "ok",

           "idea_id": created.get("idea_id"),
           "record_id": created.get("record_id"),
           "saved_as": "ready",

           "status_name": "Review",
           "review_queue": "moderator",

           "duplicate_found": duplicate_found,
           "duplicate_decision": duplicate_decision,

           "duplicate_id": duplicate_id,
           "duplicate_title": duplicate_title,
           "similarity_score": similarity_score,

           "relation_type": relation_type,

           "sent_to": "moderator",
           "review_required": True,
           "review_reason": moderation_note
        }

    except Exception as e:
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )
 
# ============================================================
#тестовый модуль удалить после настройки
# ============================================================    

def _pg_conn():
    return psycopg2.connect(
        dbname=os.getenv("PGDATABASE", "mindmesh"),
        user=os.getenv("PGUSER", "mindmesh_app"),
        password=os.getenv("PGPASSWORD", "mindmesh123"),
        host=os.getenv("PGHOST", "mindmesh.ddns.net"),
        port=os.getenv("PGPORT", "5432")
    )


@app.get("/proverka-airtab", response_class=HTMLResponse)
def proverka_airtab_page(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse(
        "proverka_airtab.html",
        {"request": request, "user": user, "system": system_state}
    )


@app.get("/api/proverka-airtab/health")
def proverka_airtab_health(request: Request):
    try:
        conn = _pg_conn()
        cur = conn.cursor()
        cur.execute("SELECT NOW()")
        now_value = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM public."Users"')
        users_count = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM public."IdeaHub"')
        ideas_count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return {
            "status": "ok",
            "db_host": os.getenv("PGHOST"),
            "db_port": os.getenv("PGPORT"),
            "server_time": str(now_value),
            "users_count": users_count,
            "ideas_count": ideas_count,
        }
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e)
        }, status_code=500)


@app.get("/api/proverka-airtab/read-users")
def proverka_airtab_read_users(request: Request):
    try:
        conn = _pg_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute('''
            SELECT id, "Name", "Email", "Role", "AccountStatus", "CreatedAt"
            FROM public."Users"
            ORDER BY id DESC
            LIMIT 20
        ''')
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {"status": "ok", "items": rows}
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e)
        }, status_code=500)


@app.get("/api/proverka-airtab/read-ideas")
def proverka_airtab_read_ideas(request: Request):
    try:
        conn = _pg_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute('''
            SELECT id, "Title", "Short Description", "Status", "Your Email", "CreatedAt"
            FROM public."IdeaHub"
            ORDER BY id DESC
            LIMIT 20
        ''')
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {"status": "ok", "items": rows}
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e)
        }, status_code=500)


@app.post("/api/proverka-airtab/write-user")
async def proverka_airtab_write_user(request: Request):
    payload = await request.json()
    try:
        conn = _pg_conn()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO public."Users"
            ("Name", "Email", "Role", "AccountStatus", "Country", "Language", "CreatedAt")
            VALUES (%s, %s, %s, %s, %s, %s, NOW()::text)
            RETURNING id
        ''', (
            payload.get("Name"),
            payload.get("Email"),
            payload.get("Role", "user"),
            payload.get("AccountStatus", "active"),
            payload.get("Country", ""),
            payload.get("Language", "")
        ))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "ok", "inserted_id": new_id, "payload": payload}
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "payload": payload
        }, status_code=500)


@app.post("/api/proverka-airtab/write-idea")
async def proverka_airtab_write_idea(request: Request):
    payload = await request.json()
    try:
        conn = _pg_conn()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO public."IdeaHub"
            ("Title", "Short Description", "Full Description", "Your Name", "Your Email", "Status", "CreatedAt")
            VALUES (%s, %s, %s, %s, %s, %s, NOW()::text)
            RETURNING id
        ''', (
            payload.get("Title"),
            payload.get("Short Description"),
            payload.get("Full Description"),
            payload.get("Your Name"),
            payload.get("Your Email"),
            payload.get("Status", "New")
        ))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "ok", "inserted_id": new_id, "payload": payload}
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "payload": payload
        }, status_code=500)