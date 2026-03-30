# ============================================================
# Project: MindMesh
# File: app.py
# Version: 3.5 (Stable Searchwave Redirect Fix)
# Date: 19.02.2026
# ============================================================

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

import sys
import os
import uuid
import bcrypt
import json
import datetime

# =====================временный блок=======================================
SUPERADMIN_EMAIL = "searchwave@gmail.com"
SUPERADMIN_PASSWORD = "123456"  # временно, потом вынесем в .env


# INIT APP
# ============================================================

app = FastAPI()

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

    except core.AirtableTemporaryUnavailable:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "База пользователей временно недоступна. Попробуйте позже.",
                "system": system_state
            },
            status_code=503
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

    return templates.TemplateResponse(
        "kabinet.html",
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
# API для списка сообщений   заглушка временная
# ============================================================
@app.get("/api/messages/list")
def messages_list(request: Request):

    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=403)

    return {
        "items": [
            {
                "title": "System notification",
                "preview": "Messages module created and ready for development.",
                "time": "now"
            },
            {
                "title": "Moderator note",
                "preview": "User clarification flow will be added next.",
                "time": "today"
            }
        ]
    }

# ============================================================
# SIMPLE MODE ANALYZE  ✅ FIXED
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

    pat = core.load_env()
    query = analysis.get("title") or analysis.get("full") or str(raw_text)

    dup_result = core.safe_find_best_duplicate(
        pat,
        query,
        analysis.get("keywords", [])
    )

    # --- degraded mode: Airtable duplicate check unavailable ---
    if dup_result.get("degraded"):
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
        return JSONResponse(
            {"status": "need_email"},
            status_code=401
        )

    try:
        result = core.prepare_and_create_idea({
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

    pat = load_env()
    url = ideas_url(pat)
    headers = airtable_headers(pat)

    r = requests.get(url, headers=headers)
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
        "stats": stats
    }

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