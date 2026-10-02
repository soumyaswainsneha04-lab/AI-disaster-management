from pathlib import Path
import json
import hashlib
import math
import pickle
import os
import re
import threading
import time
from collections import defaultdict, deque
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4

import numpy as np
import pandas as pd
import requests
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from ortools.linear_solver import pywraplp
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from pydantic import BaseModel, Field, EmailStr

try:
    from .security_db import (
        CURRENT_USER,
        ALLOWED_ROLES,
        PUBLIC_REQUEST_ROLES,
        authenticate_user_detailed,
        authenticate_google_user,
        create_access_token,
        decode_access_token,
        get_user_by_id,
        get_public_user_by_email,
        list_users as db_list_users,
        list_field_teams as db_list_field_teams,
        create_user as db_create_user,
        register_user as db_register_user,
        register_google_user as db_register_google_user,
        update_user as db_update_user,
        set_user_password as db_set_user_password,
        change_own_password as db_change_own_password,
        request_password_reset as db_request_password_reset,
        list_audit_logs as db_list_audit_logs,
        load_app_state,
        save_app_state,
        audit,
    )
except ImportError:
    # Vercel's FastAPI entrypoint imports main.py as a top-level module.
    from security_db import (
        CURRENT_USER,
        ALLOWED_ROLES,
        PUBLIC_REQUEST_ROLES,
        authenticate_user_detailed,
        authenticate_google_user,
        create_access_token,
        decode_access_token,
        get_user_by_id,
        get_public_user_by_email,
        list_users as db_list_users,
        list_field_teams as db_list_field_teams,
        create_user as db_create_user,
        register_user as db_register_user,
        register_google_user as db_register_google_user,
        update_user as db_update_user,
        set_user_password as db_set_user_password,
        change_own_password as db_change_own_password,
        request_password_reset as db_request_password_reset,
        list_audit_logs as db_list_audit_logs,
        load_app_state,
        save_app_state,
        audit,
    )


# ============================================================
# SWAGGER SECTION NAMES
# ============================================================

TAGS_METADATA = [
    {"name": "Authentication", "description": "Secure server-side login, profile and password management."},
    {"name": "Citizen Safety & Public Access", "description": "Location-based disaster awareness and public safety decision support for people in India."},
    {"name": "User Administration", "description": "Admin-only user, role and audit-log management."},
    {"name": "System Health", "description": "Backend health and model availability."},
    {"name": "Disaster Dataset", "description": "Browse all supported disaster records."},
    {"name": "Resource Demand Prediction", "description": "ML-based food, water, medical-kit and shelter demand prediction."},
    {"name": "Resource Allocation", "description": "Compare predicted demand with available resources and calculate shortages."},
    {"name": "Optimal Allocation & Logistics", "description": "Use OR-Tools linear programming to allocate shared relief inventory across multiple disaster zones."},
    {"name": "Distance & Response ETA", "description": "Calculate geographic distance and a prototype response ETA."},
    {"name": "Shelter & Evacuation Planning", "description": "Estimate shelter deficit, evacuation urgency and temporary camp requirements."},
    {"name": "Emergency Transport Recommendation", "description": "Recommend a response transport mode using disaster type and access conditions."},
    {"name": "Logistics Bottleneck Analysis", "description": "Identify operational factors that may slow relief delivery."},
    {"name": "Relief Stock Monitoring", "description": "Estimate how long current relief stocks may last."},
    {"name": "Emergency Team Deployment", "description": "Generate a rule-based emergency team deployment plan."},
    {"name": "Prediction Confidence", "description": "Estimate Random Forest prediction stability from tree-to-tree variation."},
    {"name": "Model Explainability", "description": "Show global Random Forest feature importance for each disaster model."},
    {"name": "Live Disaster Feeds", "description": "Preview public USGS and GDACS disaster feeds with graceful fallback."},
    {"name": "Disaster Alerts & Notifications", "description": "Location-aware prototype disaster alerts based on India-filtered live feeds and saved user preferences."},
    {"name": "Impact Zone Classification", "description": "Classify disaster zones for operational mapping and prioritization."},
    {"name": "Resource Inventory Management", "description": "Track and update command-center relief inventory."},
    {"name": "Field Reports & Dynamic Demand", "description": "Capture field reports and recalculate operational resource demand."},
    {"name": "Mission Assignment & Tracking", "description": "Assign and track rescue, medical and logistics missions."},
    {"name": "Optimized Delivery Routing", "description": "Generate OR-Tools multi-stop delivery routes from a depot to disaster zones."},
    {"name": "Scenario Simulation", "description": "Simulate severity, response speed, accessibility and resource availability scenarios."},
    {"name": "Operations Analytics", "description": "Aggregate disaster impact and response metrics for post-event analysis."},
    {"name": "Situation Reports", "description": "Generate consolidated incident situation reports for debriefing and coordination."},
]


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Disaster AI India - Emergency Response Intelligence Platform",
    description=(
        "India-focused prototype backend for Flood, Cyclone, Earthquake, Wildfire and Landslide "
        "resource prediction, allocation and operational decision support. "
        "This is an academic prototype and must not be used as a substitute for "
        "official emergency-management procedures."
    ),
    version="6.0.0",

    openapi_tags=TAGS_METADATA,
)

_ALLOW_LAN_ORIGINS = os.getenv(
    "DISASTER_AI_ALLOW_LAN_ORIGINS",
    "true",
).strip().lower() not in {"0", "false", "no", "off"}

_CORS_OPTIONS = {
    "allow_origins": [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}

# LAN access is useful for the student's mobile/PWA testing, but can be
# disabled for a stricter deployment.
if _ALLOW_LAN_ORIGINS:
    _CORS_OPTIONS["allow_origin_regex"] = (
        r"^http://("
        r"localhost|127\.0\.0\.1|"
        r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"192\.168\.\d{1,3}\.\d{1,3}|"
        r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
        r"):5173$"
    )

app.add_middleware(
    CORSMiddleware,
    **_CORS_OPTIONS,
)


PUBLIC_EXACT_PATHS = {
    "/",
    "/health",
    "/auth/login",
    "/auth/register",
    "/auth/google",
    "/auth/password-reset-request",
    "/openapi.json",
    "/favicon.ico",
}
PUBLIC_PREFIXES = ("/docs", "/redoc", "/public/")


# ============================================================
# BASIC SECURITY HARDENING
# ============================================================
# Login throttling is intentionally lightweight and in-memory because this
# project runs as a local academic prototype. It slows repeated password
# guessing without adding another dependency or database table.
_LOGIN_FAILURES = defaultdict(deque)
_LOGIN_RATE_LOCK = threading.RLock()
_LOGIN_MAX_FAILURES = max(3, int(os.getenv("DISASTER_AI_LOGIN_MAX_FAILURES", "6")))
_LOGIN_WINDOW_SECONDS = max(60, int(os.getenv("DISASTER_AI_LOGIN_WINDOW_SECONDS", "300")))


def _login_rate_key(request: Request, email: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}|{email.strip().lower()}"


def _login_is_limited(request: Request, email: str) -> int:
    now = time.monotonic()
    key = _login_rate_key(request, email)
    with _LOGIN_RATE_LOCK:
        attempts = _LOGIN_FAILURES[key]
        while attempts and now - attempts[0] >= _LOGIN_WINDOW_SECONDS:
            attempts.popleft()
        if len(attempts) < _LOGIN_MAX_FAILURES:
            return 0
        return max(1, int(_LOGIN_WINDOW_SECONDS - (now - attempts[0])))


def _record_login_failure(request: Request, email: str) -> None:
    now = time.monotonic()
    key = _login_rate_key(request, email)
    with _LOGIN_RATE_LOCK:
        attempts = _LOGIN_FAILURES[key]
        attempts.append(now)
        while attempts and now - attempts[0] >= _LOGIN_WINDOW_SECONDS:
            attempts.popleft()
        # Prevent unbounded growth if many different emails are probed.
        if len(_LOGIN_FAILURES) > 5000:
            stale_keys = [
                item for item, values in _LOGIN_FAILURES.items()
                if not values or now - values[-1] >= _LOGIN_WINDOW_SECONDS
            ]
            for item in stale_keys[:1000]:
                _LOGIN_FAILURES.pop(item, None)


def _clear_login_failures(request: Request, email: str) -> None:
    key = _login_rate_key(request, email)
    with _LOGIN_RATE_LOCK:
        _LOGIN_FAILURES.pop(key, None)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=()"

    if request.url.path.startswith("/auth/") or request.url.path.startswith("/admin/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"

    return response


def _is_public_path(path: str) -> bool:
    return path in PUBLIC_EXACT_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES)


def _is_admin_only_path(path: str) -> bool:
    if path.startswith("/admin/") or path == "/admin":
        return True
    if path.startswith("/analytics") or path.startswith("/reports"):
        return True
    if path.startswith("/ml/model-explainability"):
        return True
    if re.match(r"^/disasters/\d+/prediction-confidence$", path):
        return True
    return False


STAFF_ROLES = {"ADMIN", "RELIEF_COORDINATOR", "FIELD_TEAM"}


def _is_staff_only_path(path: str) -> bool:
    """Pages/APIs that ordinary Citizen accounts must not access."""
    return (
        path.startswith("/missions")
        or path.startswith("/field-reports")
        or path.startswith("/auth/field-teams")
    )


def _is_inventory_write_request(path: str, method: str) -> bool:
    """Inventory is visible to authenticated users, but only Admin may modify it."""
    return (
        path.startswith("/inventory")
        and method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
    )


@app.middleware("http")
async def authentication_middleware(request: Request, call_next):
    if request.method == "OPTIONS" or _is_public_path(request.url.path):
        return await call_next(request)

    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "Authentication required"})

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
        user = get_user_by_id(int(payload["sub"]))
    except Exception:
        return JSONResponse(status_code=401, content={"detail": "Invalid or expired session"})

    if not user or not user.get("is_active"):
        return JSONResponse(
            status_code=401,
            content={"detail": "User account is inactive"},
        )

    if user.get("account_status") != "APPROVED":
        return JSONResponse(
            status_code=403,
            content={"detail": "Account approval required"},
        )

    role = user.get("role")

    if _is_admin_only_path(request.url.path) and role != "ADMIN":
        return JSONResponse(
            status_code=403,
            content={"detail": "Administrator access required"},
        )

    if _is_staff_only_path(request.url.path) and role not in STAFF_ROLES:
        return JSONResponse(
            status_code=403,
            content={
                "detail": (
                    "Mission Control and Field Reports are restricted to "
                    "Admin, Relief Coordinator and Field Team accounts."
                )
            },
        )

    if _is_inventory_write_request(request.url.path, request.method) and role != "ADMIN":
        return JSONResponse(
            status_code=403,
            content={
                "detail": (
                    "Resource inventory is read-only for non-Admin accounts. "
                    "Only an Administrator can update inventory."
                )
            },
        )

    request.state.user = user
    token_ctx = CURRENT_USER.set(user)
    try:
        return await call_next(request)
    finally:
        CURRENT_USER.reset(token_ctx)


# Vercel Services routes the frontend API through /api. The existing
# backend routes intentionally keep their original paths (/health, /auth/*,
# /disasters/*, ...), so strip the deployment-only /api prefix before
# FastAPI route matching. This middleware is registered after authentication
# so it executes first and the auth layer sees the normalized route.
@app.middleware("http")
async def vercel_api_prefix_middleware(request: Request, call_next):
    if IS_VERCEL and request.scope.get("path", "").startswith("/api"):
        path = request.scope["path"]
        request.scope["path"] = path[4:] or "/"
    return await call_next(request)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "disaster_Dataset_FEATURED.csv"
BACKEND_MODEL_DIR = Path(__file__).resolve().parent / "model"
MODEL_DIR = BACKEND_MODEL_DIR if BACKEND_MODEL_DIR.exists() else BASE_DIR / "model"
FEATURE_PATH = MODEL_DIR / "all_disaster_feature_names.txt"
STATE_DIR = BASE_DIR / "data" / "operations_state"

# Vercel deployment artifact configuration.
# Large dataset/model binaries are kept outside GitHub and downloaded only
# when the deployed backend needs them. Local development still uses the
# original files when they are present.
IS_VERCEL = bool(os.getenv("VERCEL"))
DATASET_URL = os.getenv("DISASTER_AI_DATASET_URL", "").strip()
FEATURES_URL = os.getenv("DISASTER_AI_FEATURES_URL", "").strip()
MODEL_URLS = {
    "Flood": os.getenv("DISASTER_AI_MODEL_FLOOD_URL", "").strip(),
    "Cyclone": os.getenv("DISASTER_AI_MODEL_CYCLONE_URL", "").strip(),
    "Earthquake": os.getenv("DISASTER_AI_MODEL_EARTHQUAKE_URL", "").strip(),
    "Wildfire": os.getenv("DISASTER_AI_MODEL_WILDFIRE_URL", "").strip(),
    "Landslide": os.getenv("DISASTER_AI_MODEL_LANDSLIDE_URL", "").strip(),
}
REMOTE_CACHE_DIR = Path("/tmp/disaster-ai") if IS_VERCEL else STATE_DIR / "remote_cache"
REMOTE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
INVENTORY_PATH = STATE_DIR / "resource_inventory.json"
DEPOT_INVENTORY_PATH = STATE_DIR / "india_resource_depots.json"
MISSIONS_PATH = STATE_DIR / "missions.json"
FIELD_REPORTS_PATH = STATE_DIR / "field_reports.json"
ALERTS_PATH = STATE_DIR / "disaster_alerts.json"
INDIA_BOUNDARY_PATH = Path(__file__).with_name("india_boundary.geojson")

SUPPORTED_DISASTERS = [
    "Flood",
    "Cyclone",
    "Earthquake",
    "Wildfire",
    "Landslide",
]


# ============================================================
# HELPERS FOR MODEL FILES
# ============================================================

def slugify_disaster_type(name: str) -> str:
    return (
        str(name)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("/", "_")
    )


def model_path_for(disaster_type: str) -> Path:
    return MODEL_DIR / f"resource_model_{slugify_disaster_type(disaster_type)}.pkl"


# ============================================================
# LOAD DATASET
# ============================================================

def _download_remote_file(url: str, destination: Path, label: str) -> Path:
    """Download a deployment artifact once into the function's temporary cache."""
    if destination.exists() and destination.stat().st_size > 0:
        return destination

    if not url:
        raise RuntimeError(
            f"{label} is missing. Configure the corresponding deployment URL."
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")

    try:
        with requests.get(
            url,
            stream=True,
            timeout=(15, 600),
            allow_redirects=True,
        ) as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        output.write(chunk)

        temporary.replace(destination)
        return destination
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def _resolve_dataset_path() -> Path:
    if DATA_PATH.exists():
        return DATA_PATH

    if DATASET_URL:
        return _download_remote_file(
            DATASET_URL,
            REMOTE_CACHE_DIR / "disaster_Dataset_FEATURED.csv",
            "Disaster dataset",
        )

    raise RuntimeError(
        f"Dataset not found: {DATA_PATH}. "
        "Set DISASTER_AI_DATASET_URL for the deployed backend."
    )


def _resolve_features_path() -> Path:
    if FEATURE_PATH.exists():
        return FEATURE_PATH

    if FEATURES_URL:
        return _download_remote_file(
            FEATURES_URL,
            REMOTE_CACHE_DIR / "all_disaster_feature_names.txt",
            "Feature list",
        )

    raise RuntimeError(
        f"Feature list not found: {FEATURE_PATH}. "
        "Set DISASTER_AI_FEATURES_URL for the deployed backend."
    )


RESOLVED_DATA_PATH = _resolve_dataset_path()
RESOLVED_FEATURE_PATH = _resolve_features_path()

df = pd.read_csv(RESOLVED_DATA_PATH).reset_index(drop=True)

# Vercel Functions have a small writable /tmp filesystem. The deployed
# dataset is needed in memory for the API, but the downloaded CSV file is not
# needed after pandas has loaded it. Remove the temporary copy immediately so
# large ML model downloads do not compete with the dataset for /tmp space.
if IS_VERCEL and RESOLVED_DATA_PATH.parent == REMOTE_CACHE_DIR:
    try:
        RESOLVED_DATA_PATH.unlink()
    except OSError:
        pass

with open(RESOLVED_FEATURE_PATH, "r", encoding="utf-8") as file:
    features = [line.strip() for line in file if line.strip()]

missing_features = [feature for feature in features if feature not in df.columns]
if missing_features:
    raise RuntimeError(
        "Model features missing from dataset: " + ", ".join(missing_features)
    )


# ============================================================
# LAZY MODEL LOADING
# ============================================================
# The trained Random Forest files are large. Loading all five at startup
# wastes RAM and makes the first backend startup unnecessarily slow.
# Keep only the file availability map in memory and load a model when its
# disaster type is actually requested. Loaded models stay cached for reuse.

models = {}
_model_load_lock = threading.RLock()
model_paths = {
    disaster_type: model_path_for(disaster_type)
    for disaster_type in SUPPORTED_DISASTERS
}


def _model_is_available(disaster_type: str) -> bool:
    path = model_paths.get(disaster_type)
    if path is not None and path.exists():
        return True
    return bool(MODEL_URLS.get(disaster_type))


missing_models = [
    disaster_type
    for disaster_type in SUPPORTED_DISASTERS
    if not _model_is_available(disaster_type)
]



# ============================================================
# AUTHENTICATION & USER ADMINISTRATION
# ============================================================

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=200)


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=200)
    phone: str = Field(default="", max_length=30)
    organization: str = Field(default="", max_length=160)
    state: str = Field(default="", max_length=100)
    district: str = Field(default="", max_length=100)
    requested_role: str = Field(default="CITIZEN")


class GoogleAuthRequest(BaseModel):
    credential: str = Field(..., min_length=20)
    remember: bool = False
    requested_role: str | None = None
    phone: str = Field(default="", max_length=30)
    organization: str = Field(default="", max_length=160)
    state: str = Field(default="", max_length=100)
    district: str = Field(default="", max_length=100)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=8, max_length=200)
    new_password: str = Field(..., min_length=8, max_length=200)


class UserPreferencesRequest(BaseModel):
    home_label: str = Field(default="", max_length=200)
    home_latitude: float | None = None
    home_longitude: float | None = None
    state: str = Field(default="", max_length=100)
    district: str = Field(default="", max_length=100)
    alert_types: list[str] = Field(default_factory=list)


class TranslationBatchRequest(BaseModel):
    language: str = Field(..., min_length=2, max_length=20)
    texts: list[str] = Field(..., min_length=1, max_length=80)


class UserCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=200)
    role: str
    region: str = Field(default="India", min_length=2, max_length=120)


class UserUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    role: str | None = None
    is_active: bool | None = None
    region: str | None = Field(default=None, min_length=2, max_length=120)
    account_status: str | None = None


class AdminPasswordResetRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=200)


def _login_error(code: str):
    messages = {
        "INVALID_CREDENTIALS": (
            401,
            "Invalid email or password",
        ),
        "PENDING_APPROVAL": (
            403,
            "Your account is awaiting administrator approval.",
        ),
        "ACCOUNT_REJECTED": (
            403,
            "This account request was not approved.",
        ),
        "ACCOUNT_DISABLED": (
            403,
            "This account has been disabled. Contact an administrator.",
        ),
        "NOT_REGISTERED": (
            404,
            "No Disaster AI India account exists for this email. Create an account first.",
        ),
    }
    status_code, detail = messages.get(
        code,
        (401, "Unable to sign in"),
    )
    raise HTTPException(status_code=status_code, detail=detail)


@app.post(
    "/auth/login",
    tags=["Authentication"],
    summary="Sign in with an email and password",
)
def login_user(request: Request, credentials: LoginRequest):
    email = str(credentials.email)
    retry_after = _login_is_limited(request, email)
    if retry_after:
        response = JSONResponse(
            status_code=429,
            content={
                "detail": (
                    "Too many failed sign-in attempts. Please wait "
                    f"{retry_after} seconds and try again."
                )
            },
        )
        response.headers["Retry-After"] = str(retry_after)
        return response

    user, error_code = authenticate_user_detailed(
        email,
        credentials.password,
    )
    if not user:
        _record_login_failure(request, email)
        audit(
            "LOGIN_FAILURE",
            "user",
            None,
            {"email": email, "reason": error_code},
        )
        _login_error(error_code or "INVALID_CREDENTIALS")

    _clear_login_failures(request, email)

    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "expires_in_seconds": int(os.getenv("DISASTER_AI_TOKEN_HOURS", "8")) * 3600,
        "user": user,
    }


@app.post(
    "/auth/register",
    tags=["Authentication"],
    status_code=201,
    summary="Create a public account request",
)
def register_account(request: RegisterRequest):
    requested_role = request.requested_role.strip().upper()
    if requested_role not in PUBLIC_REQUEST_ROLES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Choose Citizen, Relief Coordinator or Field Team access."
            ),
        )

    try:
        user = db_register_user(
            name=request.name,
            email=str(request.email),
            password=request.password,
            requested_role=requested_role,
            phone=request.phone,
            organization=request.organization,
            state=request.state,
            district=request.district,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if requested_role == "CITIZEN":
        return {
            "message": "Citizen account created successfully. You can sign in now.",
            "account_status": "APPROVED",
            "user": user,
        }

    return {
        "message": (
            "Staff access request submitted. An administrator must approve "
            "the requested operational role before you can sign in."
        ),
        "account_status": "PENDING",
        "user": user,
    }


@app.post(
    "/auth/password-reset-request",
    tags=["Authentication"],
    summary="Request an administrator-assisted password reset",
)
def request_password_reset(request: PasswordResetRequest):
    db_request_password_reset(str(request.email))
    return {
        "message": (
            "If an account exists for that email, the password-reset "
            "request has been recorded for an administrator."
        )
    }


@app.post(
    "/auth/google",
    tags=["Authentication"],
    summary="Sign in or request access using Google",
)
def google_auth(request: GoogleAuthRequest):
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        raise HTTPException(
            status_code=503,
            detail=(
                "Google sign-in is not configured on the server. "
                "Set GOOGLE_CLIENT_ID in the backend environment."
            ),
        )

    try:
        from google.auth.transport.requests import Request as GoogleRequest
        from google.oauth2 import id_token

        payload = id_token.verify_oauth2_token(
            request.credential,
            GoogleRequest(),
            client_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail="Google identity verification failed.",
        ) from exc

    email = str(payload.get("email", "")).strip().lower()
    name = str(payload.get("name", "")).strip() or email.split("@")[0]
    verified = bool(payload.get("email_verified"))

    if not email or not verified:
        raise HTTPException(
            status_code=401,
            detail="Google did not provide a verified email address.",
        )

    existing = get_public_user_by_email(email)

    if existing:
        user, error_code = authenticate_google_user(email)
        if not user:
            if error_code == "PENDING_APPROVAL":
                return JSONResponse(
                    status_code=202,
                    content={
                        "message": (
                            "Your Google account is registered and awaiting "
                            "administrator approval."
                        ),
                        "account_status": "PENDING",
                        "user": existing,
                    },
                )
            _login_error(error_code or "ACCOUNT_DISABLED")

        return {
            "access_token": create_access_token(user),
            "token_type": "bearer",
            "expires_in_seconds": int(os.getenv("DISASTER_AI_TOKEN_HOURS", "8")) * 3600,
            "user": user,
        }

    # A completely new Google identity must explicitly request a role.
    if not request.requested_role:
        raise HTTPException(
            status_code=404,
            detail=(
                "No account exists for this Google email. "
                "Use Create Account and choose the role you need."
            ),
        )

    try:
        user = db_register_google_user(
            name=name,
            email=email,
            requested_role=request.requested_role,
            phone=request.phone,
            organization=request.organization,
            state=request.state,
            district=request.district,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if request.requested_role.strip().upper() == "CITIZEN":
        active_user, error_code = authenticate_google_user(email)
        if not active_user:
            _login_error(error_code or "ACCOUNT_DISABLED")
        return {
            "access_token": create_access_token(active_user),
            "token_type": "bearer",
            "expires_in_seconds": int(os.getenv("DISASTER_AI_TOKEN_HOURS", "8")) * 3600,
            "user": active_user,
        }

    return JSONResponse(
        status_code=202,
        content={
            "message": (
                "Google identity verified. Your staff access request is "
                "waiting for administrator approval."
            ),
            "account_status": "PENDING",
            "user": user,
        },
    )


@app.get("/auth/me", tags=["Authentication"], summary="Get the authenticated user profile")
def auth_me():
    user = CURRENT_USER.get()
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return {"user": user}


@app.get(
    "/profile/preferences",
    tags=["Authentication"],
    summary="Get saved citizen location and alert preferences",
)
def get_profile_preferences():
    user = CURRENT_USER.get()
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    value = load_app_state(f"user_preferences:{user['user_id']}") or {}
    return {
        "preferences": {
            "home_label": value.get("home_label", ""),
            "home_latitude": value.get("home_latitude"),
            "home_longitude": value.get("home_longitude"),
            "state": value.get("state", ""),
            "district": value.get("district", ""),
            "alert_types": value.get("alert_types", []),
            "updated_at": value.get("updated_at"),
        }
    }


@app.put(
    "/profile/preferences",
    tags=["Authentication"],
    summary="Save citizen location and alert preferences",
)
def save_profile_preferences(request: UserPreferencesRequest):
    user = CURRENT_USER.get()
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    if (request.home_latitude is None) != (request.home_longitude is None):
        raise HTTPException(
            status_code=400,
            detail="Both latitude and longitude are required for a saved location.",
        )

    if request.home_latitude is not None:
        if not is_india_coordinate(request.home_latitude, request.home_longitude):
            raise HTTPException(
                status_code=400,
                detail="Saved location must be inside the India operating boundary.",
            )

    allowed_alerts = {"Flood", "Cyclone", "Earthquake", "Wildfire", "Landslide"}
    cleaned_alerts = [
        item for item in request.alert_types
        if item in allowed_alerts
    ]

    value = {
        "home_label": request.home_label.strip(),
        "home_latitude": request.home_latitude,
        "home_longitude": request.home_longitude,
        "state": request.state.strip(),
        "district": request.district.strip(),
        "alert_types": cleaned_alerts,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    save_app_state(f"user_preferences:{user['user_id']}", value)
    audit(
        "PROFILE_PREFERENCES_UPDATED",
        "user",
        str(user["user_id"]),
        {
            "saved_location": bool(request.home_latitude is not None),
            "alert_types": cleaned_alerts,
        },
    )
    return {"message": "Preferences saved successfully", "preferences": value}


@app.post("/auth/change-password", tags=["Authentication"], summary="Change the current user's password")
def change_password(request: ChangePasswordRequest):
    user = CURRENT_USER.get()
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        db_change_own_password(user["user_id"], request.current_password, request.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "Password changed successfully"}


@app.get("/auth/field-teams", tags=["Authentication"], summary="List active field-team users")
def field_team_users():
    return {"users": db_list_field_teams()}


@app.get("/admin/users", tags=["User Administration"], summary="List application users")
def admin_list_users():
    return {"users": db_list_users()}


@app.post("/admin/users", tags=["User Administration"], summary="Create an authorized application user")
def admin_create_user(request: UserCreateRequest):
    try:
        user = db_create_user(request.name, str(request.email), request.password, request.role, request.region)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "User created successfully", "user": user}


@app.patch("/admin/users/{user_id}", tags=["User Administration"], summary="Update user role, status or profile")
def admin_update_user(user_id: int, request: UserUpdateRequest):
    current = CURRENT_USER.get()
    if current and current["user_id"] == user_id:
        if request.is_active is False:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
        if request.role is not None and request.role.strip().upper() != "ADMIN":
            raise HTTPException(status_code=400, detail="You cannot remove your own administrator role")
    try:
        user = db_update_user(
            user_id,
            name=request.name,
            role=request.role,
            is_active=request.is_active,
            region=request.region,
            account_status=request.account_status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "User updated successfully", "user": user}


@app.post("/admin/users/{user_id}/reset-password", tags=["User Administration"], summary="Reset a user's password")
def admin_reset_user_password(user_id: int, request: AdminPasswordResetRequest):
    try:
        db_set_user_password(user_id, request.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "Password reset successfully"}


@app.get("/admin/audit-logs", tags=["User Administration"], summary="View application audit activity")
def admin_audit_logs(limit: int = Query(default=100, ge=1, le=500)):
    return {"logs": db_list_audit_logs(limit)}

# ============================================================
# COMMON HELPERS
# ============================================================

def get_disaster(row_id: int):
    if row_id < 0 or row_id >= len(df):
        raise HTTPException(status_code=404, detail="Disaster record not found")
    return df.iloc[row_id]


def safe_float(row, column, default=0.0):
    if column not in row.index or pd.isna(row[column]):
        return float(default)
    try:
        return float(row[column])
    except (TypeError, ValueError):
        return float(default)


def get_disaster_type(row) -> str:
    disaster_type = str(row.get("disaster_type", "")).strip()
    if not disaster_type:
        raise HTTPException(status_code=500, detail="Disaster type missing from record")
    return disaster_type


def get_model_for_disaster(disaster_type: str):
    path = model_paths.get(disaster_type)
    if path is None:
        raise HTTPException(
            status_code=503,
            detail=f"Unsupported disaster model: {disaster_type}.",
        )

    cached = models.get(disaster_type)
    if cached is not None:
        return cached

    with _model_load_lock:
        cached = models.get(disaster_type)
        if cached is not None:
            return cached

        try:
            if not path.exists():
                remote_url = MODEL_URLS.get(disaster_type, "")
                if not remote_url:
                    raise FileNotFoundError(
                        f"No local model and no remote URL configured for {disaster_type}."
                    )

                path = _download_remote_file(
                    remote_url,
                    REMOTE_CACHE_DIR / path.name,
                    f"{disaster_type} resource model",
                )

            with path.open("rb") as file:
                cached = pickle.load(file)

            if hasattr(cached, "n_jobs"):
                # Prediction for one row is usually faster with a single worker
                # and avoids spawning a large thread pool per API request.
                cached.n_jobs = 1

            # The model is now fully deserialized in RAM. On Vercel, keeping the
            # downloaded model file in /tmp would consume hundreds of MB and
            # prevent the next large model from loading. Remove remote copies
            # after deserialization and let the request release the model.
            if IS_VERCEL and path.parent == REMOTE_CACHE_DIR:
                try:
                    path.unlink()
                except OSError:
                    pass

            # Local development benefits from model caching. On Vercel, avoid
            # retaining multiple 100s-of-MB Random Forests in the same warm
            # function instance. The current request keeps its model reference
            # until prediction/explainability work completes.
            if not IS_VERCEL:
                models[disaster_type] = cached

            return cached
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Unable to load the {disaster_type} resource model: {exc}",
            ) from exc


def prediction_to_dict(prediction):
    return {
        "food_packets": max(int(round(prediction[0])), 0),
        "water_litres": max(int(round(prediction[1])), 0),
        "medical_kits": max(int(round(prediction[2])), 0),
        "shelter_people": max(int(round(prediction[3])), 0),
    }


def predict_resources(row_id: int):
    row = get_disaster(row_id)
    disaster_type = get_disaster_type(row)
    model = get_model_for_disaster(disaster_type)

    # Keep the one-row DataFrame so scikit-learn receives the same feature
    # names it saw during training. The featured CSV is already numeric in the
    # model columns, so no expensive per-request type conversion is needed.
    X = df.iloc[[row_id]][features].fillna(0)

    return prediction_to_dict(model.predict(X)[0])


def calculate_shortages(row, prediction):
    return {
        "food_packets": max(
            prediction["food_packets"] - safe_float(row, "food_packets_available"),
            0,
        ),
        "water_litres": max(
            prediction["water_litres"] - safe_float(row, "water_litres_available"),
            0,
        ),
        "medical_kits": max(
            prediction["medical_kits"] - safe_float(row, "medical_kits_available"),
            0,
        ),
        "shelter_people": max(
            prediction["shelter_people"] - safe_float(row, "shelter_capacity"),
            0,
        ),
    }


def calculate_priority_score(row, prediction):
    shortages = calculate_shortages(row, prediction)
    ratios = [
        shortages["food_packets"] / max(prediction["food_packets"], 1),
        shortages["water_litres"] / max(prediction["water_litres"], 1),
        shortages["medical_kits"] / max(prediction["medical_kits"], 1),
        shortages["shelter_people"] / max(prediction["shelter_people"], 1),
    ]

    pressure = sum(ratios) / 4
    severity = min(max(safe_float(row, "severity_score"), 0), 1)
    vulnerability = min(max(safe_float(row, "vulnerability_score"), 0), 1)
    logistics = min(max(safe_float(row, "logistics_difficulty_index"), 0), 1)

    score = 100 * (
        0.40 * min(pressure, 1)
        + 0.25 * severity
        + 0.20 * vulnerability
        + 0.15 * logistics
    )

    return round(min(max(score, 0), 100), 2)


def priority_level(score):
    if score >= 70:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 30:
        return "MEDIUM"
    return "LOW"


def haversine(lat1, lon1, lat2, lon2):
    radius = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return radius * 2 * math.asin(math.sqrt(a))


INDIA_BOUNDS = {
    "south": 6.0,
    "north": 38.0,
    "west": 68.0,
    "east": 98.0,
}

# The rectangular bounds above are useful for map panning, but they also
# include parts of neighbouring countries and the Bay of Bengal.  The
# GeoJSON mask below is therefore used whenever we decide whether a point is
# actually inside the India operating area.
#
# The bundled boundary is a simplified Natural-Earth style country polygon.
# Small island boxes are included separately so Andaman & Nicobar and
# Lakshadweep remain usable for citizen location searches.
INDIA_ISLAND_BOXES = [
    # south, north, west, east
    (6.5, 13.8, 92.0, 94.5),   # Andaman & Nicobar Islands
    (8.0, 12.9, 71.0, 74.5),   # Lakshadweep
]


def _load_india_boundary_polygons():
    try:
        payload = json.loads(INDIA_BOUNDARY_PATH.read_text(encoding="utf-8"))
        feature = (payload.get("features") or [payload])[0]
        geometry = feature.get("geometry", feature)
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates") or []

        if geometry_type == "Polygon":
            return [np.asarray(coordinates[0], dtype=float)] if coordinates else []
        if geometry_type == "MultiPolygon":
            return [np.asarray(poly[0], dtype=float) for poly in coordinates if poly]
    except Exception:
        pass
    return []


INDIA_BOUNDARY_POLYGONS = _load_india_boundary_polygons()
_INDIA_DATASET_MASK_CACHE = None


def _points_in_ring(latitudes: np.ndarray, longitudes: np.ndarray, ring: np.ndarray) -> np.ndarray:
    """Vectorized ray-casting point-in-polygon test for one exterior ring."""
    if ring is None or len(ring) < 3:
        return np.zeros(latitudes.shape, dtype=bool)

    x = longitudes
    y = latitudes
    inside = np.zeros(latitudes.shape, dtype=bool)

    xj, yj = ring[-1]
    for xi, yi in ring:
        denominator = (yj - yi)
        if abs(denominator) < 1e-12:
            denominator = 1e-12
        intersects = ((yi > y) != (yj > y)) & (
            x < ((xj - xi) * (y - yi) / denominator + xi)
        )
        inside ^= intersects
        xj, yj = xi, yi

    return inside


def india_coordinate_mask(latitudes, longitudes) -> np.ndarray:
    """Return a boolean mask for points that fall inside India land geometry."""
    latitudes = np.asarray(latitudes, dtype=float)
    longitudes = np.asarray(longitudes, dtype=float)

    finite = np.isfinite(latitudes) & np.isfinite(longitudes)
    bbox = (
        finite
        & (latitudes >= INDIA_BOUNDS["south"])
        & (latitudes <= INDIA_BOUNDS["north"])
        & (longitudes >= INDIA_BOUNDS["west"])
        & (longitudes <= INDIA_BOUNDS["east"])
    )

    result = np.zeros(latitudes.shape, dtype=bool)
    if not np.any(bbox):
        return result

    if INDIA_BOUNDARY_POLYGONS:
        valid_positions = np.flatnonzero(bbox)
        valid_lat = latitudes[valid_positions]
        valid_lon = longitudes[valid_positions]
        local_inside = np.zeros(valid_lat.shape, dtype=bool)
        for ring in INDIA_BOUNDARY_POLYGONS:
            local_inside |= _points_in_ring(valid_lat, valid_lon, ring)
        result[valid_positions] = local_inside
    else:
        # Conservative fallback if the boundary file is missing.
        result |= bbox

    for south, north, west, east in INDIA_ISLAND_BOXES:
        result |= (
            finite
            & (latitudes >= south)
            & (latitudes <= north)
            & (longitudes >= west)
            & (longitudes <= east)
        )

    return result


def is_india_coordinate(latitude: float, longitude: float) -> bool:
    try:
        return bool(
            india_coordinate_mask(
                np.asarray([float(latitude)]),
                np.asarray([float(longitude)]),
            )[0]
        )
    except Exception:
        return False


def get_india_dataset_mask() -> np.ndarray:
    global _INDIA_DATASET_MASK_CACHE
    if _INDIA_DATASET_MASK_CACHE is None:
        lat_values = pd.to_numeric(df["latitude"], errors="coerce").to_numpy(dtype=float)
        lon_values = pd.to_numeric(df["longitude"], errors="coerce").to_numpy(dtype=float)
        _INDIA_DATASET_MASK_CACHE = india_coordinate_mask(lat_values, lon_values)
    return _INDIA_DATASET_MASK_CACHE


def filter_india_dataframe(work: pd.DataFrame) -> pd.DataFrame:
    if work.empty:
        return work

    # Most callers use a copy/subset of the main dataframe and therefore keep
    # the original integer row index. Reuse the startup-lazy cached mask in
    # that common path instead of re-running point-in-polygon over 212k rows.
    try:
        index_values = work.index.to_numpy(dtype=int)
        if (
            len(index_values)
            and index_values.min() >= 0
            and index_values.max() < len(df)
        ):
            return work.loc[get_india_dataset_mask()[index_values]]
    except Exception:
        pass

    lat_values = pd.to_numeric(work["latitude"], errors="coerce").to_numpy(dtype=float)
    lon_values = pd.to_numeric(work["longitude"], errors="coerce").to_numpy(dtype=float)
    mask = india_coordinate_mask(lat_values, lon_values)
    return work.loc[mask]


def validate_india_coordinate(latitude: float, longitude: float, label: str = "Location"):
    if not is_india_coordinate(latitude, longitude):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{label} must be located inside the India operating area. "
                "Coordinates in neighbouring countries or open sea are not accepted."
            ),
        )


def hazard_signal(row):
    """Return a disaster-specific hazard signal for explanation only."""

    disaster_type = get_disaster_type(row)

    mapping = {
        "Flood": ("flood_depth_m", "Flood depth", "m"),
        "Cyclone": ("wind_speed", "Wind speed", "dataset units"),
        "Earthquake": ("magnitude", "Magnitude", "magnitude"),
        "Wildfire": ("fire_frp_sum", "Fire radiative power sum", "FRP units"),
        "Landslide": ("road_damage_pct", "Road damage", "%"),
    }

    column, label, unit = mapping.get(
        disaster_type,
        ("severity_score", "Severity score", "score"),
    )

    value = safe_float(row, column)

    same_type = df[df["disaster_type"].astype(str) == disaster_type]
    if column in same_type.columns:
        series = pd.to_numeric(same_type[column], errors="coerce").dropna()
    else:
        series = pd.Series(dtype=float)

    percentile = None
    if len(series) > 0:
        percentile = float((series <= value).mean() * 100)

    return {
        "metric": column,
        "label": label,
        "value": round(value, 3),
        "unit": unit,
        "percentile_within_disaster_type": (
            round(percentile, 1) if percentile is not None else None
        ),
    }


# ============================================================
# SYSTEM HEALTH
# ============================================================

@app.get("/", tags=["System Health"])
def root():
    return {
        "message": "Disaster AI India backend is running",
        "version": "5.0.0",
        "operating_country": "India",
        "status": "success",
        "supported_disasters": SUPPORTED_DISASTERS,
    }


@app.get("/health", tags=["System Health"])
def health():
    india_records = int(get_india_dataset_mask().sum())
    return {
        "status": "healthy",
        "operating_country": "India",
        "india_bounds": INDIA_BOUNDS,
        "dataset_records": len(df),
        "india_mapped_records": india_records,
        "supported_disasters": SUPPORTED_DISASTERS,
        "loaded_models": sorted(models.keys()),
        "available_models": sorted(model_paths.keys()),
        "missing_models": missing_models,
        "input_features_per_model": len(features),
    }


# ============================================================
# DISASTER DATASET
# ============================================================

@app.get("/dataset-info", tags=["Disaster Dataset"])
def dataset_info():
    india_work = filter_india_dataframe(df)
    counts = india_work["disaster_type"].value_counts().to_dict()

    return {
        "dataset": DATA_PATH.name,
        "source_total_records": len(df),
        "total_records": len(india_work),
        "total_columns": len(df.columns),
        "disaster_counts": counts,
        "model_features": len(features),
        "geographic_filter": "India boundary polygon",
    }


@app.get("/disasters/types", tags=["Disaster Dataset"])
def disaster_types():
    return {
        "supported_disasters": SUPPORTED_DISASTERS,
        "available_in_dataset": sorted(
            df["disaster_type"].dropna().astype(str).unique().tolist()
        ),
    }


@app.get("/disasters", tags=["Disaster Dataset"])
def get_disasters(
    disaster_type: str | None = Query(default=None),
    limit: int = Query(10, ge=1, le=100),
):
    work = filter_india_dataframe(df)

    if disaster_type:
        work = work[
            work["disaster_type"].astype(str).str.lower()
            == disaster_type.strip().lower()
        ]

    columns = [
        "disaster_type",
        "disaster_subtype",
        "latitude",
        "longitude",
        "affected_population",
        "severity_score",
        "dris_score",
        "road_blockage_probability",
        "logistics_accessibility_score",
    ]

    available_columns = [column for column in columns if column in work.columns]
    selected = work[available_columns].head(limit).copy()
    selected.insert(0, "row_id", selected.index)

    records = json.loads(selected.to_json(orient="records"))

    return {
        "filter_disaster_type": disaster_type,
        "returned_records": len(records),
        "data": records,
    }


@app.get("/disasters/{row_id}", tags=["Disaster Dataset"])
def get_disaster_record(row_id: int):
    row = get_disaster(row_id)
    latitude = safe_float(row, "latitude")
    longitude = safe_float(row, "longitude")
    validate_india_coordinate(latitude, longitude, "Disaster location")
    record = json.loads(df.iloc[[row_id]].to_json(orient="records"))[0]
    nearest = nearest_resource_depots(latitude, longitude, limit=1)
    return {
        "row_id": row_id,
        "disaster_type": get_disaster_type(row),
        "country": "India",
        "nearest_resource_depot": nearest[0] if nearest else None,
        "data": record,
    }


# ============================================================
# RESOURCE DEMAND PREDICTION
# ============================================================

@app.get(
    "/disasters/{row_id}/predict",
    tags=["Resource Demand Prediction"],
    summary="Predict relief-resource demand for any supported disaster",
)
def resource_prediction(row_id: int):
    row = get_disaster(row_id)
    prediction = predict_resources(row_id)
    latitude = safe_float(row, "latitude")
    longitude = safe_float(row, "longitude")
    validate_india_coordinate(latitude, longitude, "Disaster location")
    source_plan = build_resource_source_plan(latitude, longitude, prediction, max_depots=4)

    return {
        "row_id": row_id,
        "disaster_type": get_disaster_type(row),
        "country": "India",
        "location": {"latitude": latitude, "longitude": longitude},
        "affected_population": int(safe_float(row, "affected_population")),
        "severity_score": round(safe_float(row, "severity_score"), 4),
        "predicted_resources": prediction,
        "primary_source_depot": source_plan["primary_depot"],
        "resource_source_preview": source_plan,
    }


# ============================================================
# RESOURCE ALLOCATION
# ============================================================

@app.get(
    "/disasters/{row_id}/allocation",
    tags=["Resource Allocation"],
    summary="Calculate shortages and allocation priority",
)
def resource_allocation(row_id: int):
    row = get_disaster(row_id)
    prediction = predict_resources(row_id)
    latitude = safe_float(row, "latitude")
    longitude = safe_float(row, "longitude")
    validate_india_coordinate(latitude, longitude, "Disaster location")

    source_plan = build_resource_source_plan(latitude, longitude, prediction, max_depots=4)
    available = source_plan["available_resources"]
    allocated = source_plan["planned_allocation"]
    shortages = source_plan["unmet_demand"]

    pressure_ratios = [
        shortages["food_packets"] / max(prediction["food_packets"], 1),
        shortages["water_litres"] / max(prediction["water_litres"], 1),
        shortages["medical_kits"] / max(prediction["medical_kits"], 1),
        shortages["shelter_people"] / max(prediction["shelter_people"], 1),
    ]
    pressure = sum(pressure_ratios) / 4
    severity = min(max(safe_float(row, "severity_score"), 0), 1)
    vulnerability = min(max(safe_float(row, "vulnerability_score"), 0), 1)
    logistics = min(max(safe_float(row, "logistics_difficulty_index"), 0), 1)
    score = round(100 * (0.40 * min(pressure, 1) + 0.25 * severity + 0.20 * vulnerability + 0.15 * logistics), 2)

    return {
        "row_id": row_id,
        "disaster_type": get_disaster_type(row),
        "country": "India",
        "location": {"latitude": latitude, "longitude": longitude},
        "predicted_resources": prediction,
        "available_resources": available,
        "allocated_resources": allocated,
        "shortage": shortages,
        "priority_score": score,
        "priority_level": priority_level(score),
        "primary_source_depot": source_plan["primary_depot"],
        "resource_source_plan": source_plan,
    }



# ============================================================
# OPTIMAL MULTI-ZONE RESOURCE ALLOCATION (OR-TOOLS)
# ============================================================

class OptimizationRequest(BaseModel):
    row_ids: list[int] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Disaster row IDs to optimize together.",
    )
    food_packets_available: int | None = Field(default=None, ge=0)
    water_litres_available: int | None = Field(default=None, ge=0)
    medical_kits_available: int | None = Field(default=None, ge=0)
    shelter_capacity_available: int | None = Field(default=None, ge=0)
    transport_capacity_fraction: float = Field(
        default=1.0,
        ge=0.10,
        le=1.0,
        description="Fraction of normal delivery capacity available after the disaster.",
    )
    priority_overrides: dict[int, float] = Field(
        default_factory=dict,
        description=(
            "Optional manual priority multiplier by row ID. "
            "1.0 = normal, 1.5 = elevated, 2.0 = high override, maximum 3.0."
        ),
    )


def _selected_inventory(rows, column):
    total = 0
    for row in rows:
        total += max(int(round(safe_float(row, column))), 0)
    return total


def _clamp(value, low, high):
    return max(low, min(float(value), high))


@app.post(
    "/optimization/resource-allocation",
    tags=["Optimal Allocation & Logistics"],
    summary="Optimize shared resource allocation across multiple disaster zones",
)
def optimize_resource_allocation(request: OptimizationRequest):
    # Preserve order while removing duplicate row IDs.
    unique_row_ids = list(dict.fromkeys(request.row_ids))

    rows = [get_disaster(row_id) for row_id in unique_row_ids]

    resources = {
        "food_packets": {
            "available_column": "food_packets_available",
            "request_value": request.food_packets_available,
        },
        "water_litres": {
            "available_column": "water_litres_available",
            "request_value": request.water_litres_available,
        },
        "medical_kits": {
            "available_column": "medical_kits_available",
            "request_value": request.medical_kits_available,
        },
        "shelter_people": {
            "available_column": "shelter_capacity",
            "request_value": request.shelter_capacity_available,
        },
    }

    # If total inventory is not supplied by the user, use the sum of
    # inventory currently available in the selected zones as the shared pool.
    inventory = {}
    inventory_source = {}

    for resource_name, config in resources.items():
        supplied = config["request_value"]

        if supplied is None:
            inventory[resource_name] = _selected_inventory(
                rows,
                config["available_column"],
            )
            inventory_source[resource_name] = "SUM_OF_SELECTED_ZONE_INVENTORY"
        else:
            inventory[resource_name] = int(supplied)
            inventory_source[resource_name] = "USER_SUPPLIED_TOTAL"

    predictions = {}
    base_priority_scores = {}
    manual_multipliers = {}
    route_factors = {}
    deliverability_factors = {}

    for row_id, row in zip(unique_row_ids, rows):
        prediction = predict_resources(row_id)
        predictions[row_id] = prediction

        base_score = calculate_priority_score(row, prediction)
        base_priority_scores[row_id] = base_score

        raw_multiplier = request.priority_overrides.get(
            row_id,
            request.priority_overrides.get(str(row_id), 1.0),
        )
        multiplier = _clamp(raw_multiplier, 0.5, 3.0)
        manual_multipliers[row_id] = multiplier

        accessibility = _clamp(
            safe_float(row, "logistics_accessibility_score", 1.0),
            0.0,
            1.0,
        )
        blockage = _clamp(
            safe_float(row, "road_blockage_probability", 0.0),
            0.0,
            1.0,
        )

        # Prototype route/deliverability constraint:
        # poor accessibility and road blockage reduce how much relief can
        # realistically be delivered in the current planning window.
        route_factor = _clamp(accessibility * (1.0 - blockage), 0.25, 1.0)
        route_factors[row_id] = route_factor

        deliverability = _clamp(
            route_factor * request.transport_capacity_fraction,
            0.10,
            1.0,
        )
        deliverability_factors[row_id] = deliverability

    solver = pywraplp.Solver.CreateSolver("GLOP")

    if solver is None:
        raise HTTPException(
            status_code=500,
            detail="OR-Tools GLOP solver is not available.",
        )

    allocation_vars = {}

    # Decision variables:
    # x[row_id, resource] = quantity assigned to that disaster zone.
    for row_id in unique_row_ids:
        for resource_name in resources:
            demand = max(float(predictions[row_id][resource_name]), 0.0)

            # Route / transport constraint for the current planning window.
            deliverable_cap = demand * deliverability_factors[row_id]

            allocation_vars[(row_id, resource_name)] = solver.NumVar(
                0.0,
                deliverable_cap,
                f"x_{row_id}_{resource_name}",
            )

    # Shared inventory constraints.
    for resource_name in resources:
        solver.Add(
            sum(
                allocation_vars[(row_id, resource_name)]
                for row_id in unique_row_ids
            )
            <= float(inventory[resource_name])
        )

    objective = solver.Objective()

    for row_id in unique_row_ids:
        # Higher base priority and manual override receive a larger
        # optimization weight.
        priority_weight = (
            1.0 + (base_priority_scores[row_id] / 100.0) * 2.0
        ) * manual_multipliers[row_id]

        for resource_name in resources:
            demand = max(float(predictions[row_id][resource_name]), 1.0)

            # Normalizing by demand makes the objective reward coverage
            # percentage rather than favoring resources with larger units.
            coefficient = priority_weight / demand
            objective.SetCoefficient(
                allocation_vars[(row_id, resource_name)],
                coefficient,
            )

    objective.SetMaximization()

    status = solver.Solve()

    if status not in (
        pywraplp.Solver.OPTIMAL,
        pywraplp.Solver.FEASIBLE,
    ):
        raise HTTPException(
            status_code=500,
            detail="Optimization solver could not find a feasible allocation.",
        )

    total_demand = {resource: 0.0 for resource in resources}
    total_allocated = {resource: 0.0 for resource in resources}
    zone_results = []

    for row_id, row in zip(unique_row_ids, rows):
        zone_allocation = {}
        zone_shortage = {}
        zone_coverage = {}

        for resource_name in resources:
            demand = max(float(predictions[row_id][resource_name]), 0.0)
            allocated = max(
                allocation_vars[(row_id, resource_name)].solution_value(),
                0.0,
            )
            shortage = max(demand - allocated, 0.0)
            coverage = (allocated / demand * 100.0) if demand > 0 else 100.0

            total_demand[resource_name] += demand
            total_allocated[resource_name] += allocated

            zone_allocation[resource_name] = int(round(allocated))
            zone_shortage[resource_name] = int(round(shortage))
            zone_coverage[resource_name] = round(coverage, 2)

        average_coverage = (
            sum(zone_coverage.values()) / len(zone_coverage)
            if zone_coverage
            else 0.0
        )

        zone_results.append(
            {
                "row_id": row_id,
                "disaster_type": get_disaster_type(row),
                "affected_population": int(
                    safe_float(row, "affected_population")
                ),
                "severity_score": round(
                    safe_float(row, "severity_score"),
                    4,
                ),
                "base_priority_score": base_priority_scores[row_id],
                "manual_priority_multiplier": manual_multipliers[row_id],
                "route_access_factor": round(route_factors[row_id], 4),
                "deliverability_factor": round(
                    deliverability_factors[row_id],
                    4,
                ),
                "predicted_demand": predictions[row_id],
                "optimized_allocation": zone_allocation,
                "unmet_demand": zone_shortage,
                "coverage_percent": zone_coverage,
                "average_zone_coverage_percent": round(
                    average_coverage,
                    2,
                ),
            }
        )

    total_shortage = {
        resource: max(
            total_demand[resource] - total_allocated[resource],
            0.0,
        )
        for resource in resources
    }

    remaining_inventory = {
        resource: max(
            float(inventory[resource]) - total_allocated[resource],
            0.0,
        )
        for resource in resources
    }

    coverage_percent = {
        resource: round(
            (
                total_allocated[resource]
                / max(total_demand[resource], 1.0)
                * 100.0
            ),
            2,
        )
        for resource in resources
    }

    overall_coverage = round(
        sum(coverage_percent.values()) / len(coverage_percent),
        2,
    )

    return {
        "feature": "OR-Tools Multi-Zone Resource Allocation Optimizer",
        "solver": "Google OR-Tools GLOP Linear Programming",
        "solver_status": (
            "OPTIMAL"
            if status == pywraplp.Solver.OPTIMAL
            else "FEASIBLE"
        ),
        "selected_zone_count": len(unique_row_ids),
        "selected_row_ids": unique_row_ids,
        "transport_capacity_fraction": request.transport_capacity_fraction,
        "inventory_source": inventory_source,
        "shared_inventory": {
            key: int(round(value))
            for key, value in inventory.items()
        },
        "total_predicted_demand": {
            key: int(round(value))
            for key, value in total_demand.items()
        },
        "total_optimized_allocation": {
            key: int(round(value))
            for key, value in total_allocated.items()
        },
        "total_unmet_demand": {
            key: int(round(value))
            for key, value in total_shortage.items()
        },
        "remaining_inventory": {
            key: int(round(value))
            for key, value in remaining_inventory.items()
        },
        "coverage_percent": coverage_percent,
        "overall_coverage_percent": overall_coverage,
        "zones": sorted(
            zone_results,
            key=lambda item: (
                -item["manual_priority_multiplier"],
                -item["base_priority_score"],
            ),
        ),
        "note": (
            "Academic prototype optimization. The model maximizes weighted "
            "resource coverage subject to shared inventory and simplified "
            "route/deliverability constraints. Real deployments require "
            "validated inventories, road networks, vehicle capacities and "
            "authorized emergency-management decisions."
        ),
    }



# ============================================================
# DISTANCE & RESPONSE ETA
# ============================================================

class LocationInput(BaseModel):
    row_id: int
    user_latitude: float = Field(ge=-90, le=90)
    user_longitude: float = Field(ge=-180, le=180)


@app.post(
    "/distance-eta",
    tags=["Distance & Response ETA"],
    summary="Calculate distance and prototype response ETA",
)
def distance_eta(location: LocationInput):
    validate_india_coordinate(location.user_latitude, location.user_longitude, "Response location")
    row = get_disaster(location.row_id)

    disaster_lat = safe_float(row, "latitude")
    disaster_lon = safe_float(row, "longitude")

    validate_india_coordinate(disaster_lat, disaster_lon, "Disaster location")

    distance = haversine(
        location.user_latitude,
        location.user_longitude,
        disaster_lat,
        disaster_lon,
    )

    accessibility = safe_float(row, "logistics_accessibility_score", 1)
    blockage = safe_float(row, "road_blockage_probability", 0)

    effective_speed = 50.0 * max(accessibility, 0.30) * max(1 - blockage, 0.30)
    effective_speed = max(10, min(effective_speed, 60))

    travel_minutes = distance / effective_speed * 60
    preparation_minutes = 10
    total_eta = travel_minutes + preparation_minutes

    if total_eta <= 30:
        status = "FAST RESPONSE"
    elif total_eta <= 60:
        status = "MODERATE RESPONSE"
    elif total_eta <= 120:
        status = "DELAYED RESPONSE"
    else:
        status = "CRITICAL DELAY"

    return {
        "row_id": location.row_id,
        "disaster_type": get_disaster_type(row),
        "user_location": {
            "latitude": location.user_latitude,
            "longitude": location.user_longitude,
        },
        "disaster_location": {
            "latitude": disaster_lat,
            "longitude": disaster_lon,
        },
        "distance_km": round(distance, 2),
        "effective_speed_kmph": round(effective_speed, 2),
        "travel_time_minutes": round(travel_minutes, 2),
        "preparation_time_minutes": preparation_minutes,
        "total_eta_minutes": round(total_eta, 2),
        "response_status": status,
        "nearest_resource_depot": nearest_resource_depots(disaster_lat, disaster_lon, limit=1)[0],
        "note": "India-only prototype ETA using Haversine distance and access conditions; not live road navigation.",
    }


# ============================================================
# SHELTER & EVACUATION PLANNING
# ============================================================

@app.get(
    "/disasters/{row_id}/evacuation-plan",
    tags=["Shelter & Evacuation Planning"],
    summary="Estimate shelter deficit and evacuation urgency",
)
def evacuation_plan(row_id: int):
    row = get_disaster(row_id)
    prediction = predict_resources(row_id)

    affected = int(safe_float(row, "affected_population"))
    predicted_shelter = int(prediction["shelter_people"])
    capacity = int(safe_float(row, "shelter_capacity"))

    displaced = int(
        safe_float(
            row,
            "estimated_displaced_population",
            predicted_shelter,
        )
    )

    if displaced <= 0:
        displaced = predicted_shelter

    people_needing_shelter = max(predicted_shelter, displaced)
    deficit = max(people_needing_shelter - capacity, 0)

    temporary_camp_capacity = 300
    additional_camps = math.ceil(deficit / temporary_camp_capacity)

    severity = min(max(safe_float(row, "severity_score"), 0), 1)
    blockage = min(max(safe_float(row, "road_blockage_probability"), 0), 1)
    deficit_ratio = deficit / max(people_needing_shelter, 1)

    score = 100 * (
        0.40 * min(deficit_ratio, 1)
        + 0.30 * blockage
        + 0.30 * severity
    )

    if score >= 70:
        urgency = "CRITICAL"
    elif score >= 50:
        urgency = "HIGH"
    elif score >= 30:
        urgency = "MEDIUM"
    else:
        urgency = "LOW"

    evacuation_required = deficit > 0 or severity >= 0.70

    return {
        "feature": "Shelter & Evacuation Capacity Planner",
        "row_id": row_id,
        "disaster_type": get_disaster_type(row),
        "affected_population": affected,
        "people_requiring_shelter": people_needing_shelter,
        "existing_shelter_capacity": capacity,
        "shelter_deficit": deficit,
        "temporary_camp_capacity_assumption": temporary_camp_capacity,
        "additional_camps_required": additional_camps,
        "nearest_evacuation_center_km": round(
            safe_float(row, "nearest_evacuation_center_distance_km"),
            2,
        ),
        "evacuation_required": evacuation_required,
        "evacuation_urgency": urgency,
        "evacuation_score": round(score, 2),
        "note": "Prototype planning output; real evacuation decisions require official authorities.",
    }


# ============================================================
# EMERGENCY TRANSPORT RECOMMENDATION
# ============================================================

@app.get(
    "/disasters/{row_id}/transport-recommendation",
    tags=["Emergency Transport Recommendation"],
    summary="Recommend a disaster-aware response transport mode",
)
def transport_recommendation(row_id: int):
    row = get_disaster(row_id)
    disaster_type = get_disaster_type(row)

    blockage = min(max(safe_float(row, "road_blockage_probability"), 0), 1)
    accessibility = min(max(safe_float(row, "logistics_accessibility_score", 1), 0), 1)
    depth = max(safe_float(row, "flood_depth_m"), 0)

    if disaster_type == "Flood":
        if depth >= 1.0 or blockage >= 0.70:
            primary = "Boat / water-rescue transport"
            alternatives = ["High-clearance rescue vehicle", "Airlift if officially cleared"]
        elif depth >= 0.30 or accessibility < 0.60:
            primary = "High-clearance 4x4 rescue vehicle"
            alternatives = ["Boat support", "Ambulance where roads remain open"]
        else:
            primary = "Relief truck / ambulance"
            alternatives = ["4x4 rescue vehicle"]

    elif disaster_type == "Cyclone":
        primary = "Protected ground-response vehicle after conditions are declared safe"
        alternatives = ["4x4 rescue vehicle", "Ambulance", "Airlift only after aviation clearance"]

    elif disaster_type == "Earthquake":
        if blockage >= 0.60 or accessibility < 0.50:
            primary = "4x4 / urban-search-and-rescue vehicle"
            alternatives = ["Ambulance staging", "Airlift for isolated areas if cleared"]
        else:
            primary = "Rescue truck and ambulance"
            alternatives = ["4x4 support vehicle"]

    elif disaster_type == "Wildfire":
        primary = "Evacuation bus / emergency ground vehicle"
        alternatives = ["Fire-rescue vehicle", "Ambulance", "Aerial support only when approved and safe"]

    elif disaster_type == "Landslide":
        if blockage >= 0.60 or accessibility < 0.50:
            primary = "4x4 / tracked rescue vehicle"
            alternatives = ["Airlift for cut-off areas if cleared", "Ambulance staging"]
        else:
            primary = "4x4 rescue vehicle"
            alternatives = ["Ambulance", "Relief truck"]

    else:
        primary = "4x4 emergency response vehicle"
        alternatives = ["Ambulance", "Relief truck"]

    return {
        "feature": "Emergency Transport Mode Recommender",
        "row_id": row_id,
        "disaster_type": disaster_type,
        "road_blockage_probability": round(blockage, 3),
        "logistics_accessibility": round(accessibility, 3),
        "disaster_hazard_signal": hazard_signal(row),
        "recommended_primary_mode": primary,
        "alternative_modes": alternatives,
        "safety_note": (
            "Prototype decision-support only. Actual transport deployment must follow "
            "official emergency, road, aviation and weather safety guidance."
        ),
    }


# ============================================================
# LOGISTICS BOTTLENECK ANALYSIS
# ============================================================

@app.get(
    "/disasters/{row_id}/logistics-bottlenecks",
    tags=["Logistics Bottleneck Analysis"],
    summary="Identify likely relief-delivery bottlenecks",
)
def logistics_bottlenecks(row_id: int):
    row = get_disaster(row_id)

    blockage = min(max(safe_float(row, "road_blockage_probability"), 0), 1)
    accessibility = min(max(safe_float(row, "logistics_accessibility_score", 1), 0), 1)
    depot_distance = max(safe_float(row, "nearest_depot_distance_km"), 0)
    hospital_distance = max(safe_float(row, "nearest_hospital_distance_km"), 0)
    evacuation_distance = max(
        safe_float(row, "nearest_evacuation_center_distance_km"), 0
    )

    bottlenecks = []
    risk_score = 0

    if blockage >= 0.70:
        risk_score += 30
        bottlenecks.append({"factor": "Road blockage", "risk": "CRITICAL", "value": f"{blockage * 100:.1f}%"})
    elif blockage >= 0.40:
        risk_score += 20
        bottlenecks.append({"factor": "Road blockage", "risk": "HIGH", "value": f"{blockage * 100:.1f}%"})

    if accessibility <= 0.30:
        risk_score += 25
        bottlenecks.append({"factor": "Low logistics accessibility", "risk": "CRITICAL", "value": round(accessibility, 3)})
    elif accessibility <= 0.60:
        risk_score += 15
        bottlenecks.append({"factor": "Low logistics accessibility", "risk": "HIGH", "value": round(accessibility, 3)})

    if depot_distance >= 50:
        risk_score += 15
        bottlenecks.append({"factor": "Relief depot distance", "risk": "HIGH", "value": f"{depot_distance:.2f} km"})
    elif depot_distance >= 25:
        risk_score += 10
        bottlenecks.append({"factor": "Relief depot distance", "risk": "MEDIUM", "value": f"{depot_distance:.2f} km"})

    if hospital_distance >= 50:
        risk_score += 10
        bottlenecks.append({"factor": "Hospital distance", "risk": "HIGH", "value": f"{hospital_distance:.2f} km"})
    elif hospital_distance >= 25:
        risk_score += 5
        bottlenecks.append({"factor": "Hospital distance", "risk": "MEDIUM", "value": f"{hospital_distance:.2f} km"})

    signal = hazard_signal(row)
    percentile = signal["percentile_within_disaster_type"]

    if percentile is not None and percentile >= 90:
        risk_score += 20
        bottlenecks.append({
            "factor": f"Elevated {signal['label']}",
            "risk": "CRITICAL",
            "value": signal["value"],
            "percentile": percentile,
        })
    elif percentile is not None and percentile >= 75:
        risk_score += 10
        bottlenecks.append({
            "factor": f"Elevated {signal['label']}",
            "risk": "HIGH",
            "value": signal["value"],
            "percentile": percentile,
        })

    risk_score = min(risk_score, 100)

    if risk_score >= 70:
        level = "CRITICAL"
        recommendation = "Use contingency routes, local staging and official specialized-response support."
    elif risk_score >= 50:
        level = "HIGH"
        recommendation = "Pre-position supplies and prepare alternative access routes."
    elif risk_score >= 30:
        level = "MEDIUM"
        recommendation = "Monitor access conditions and keep alternate routes ready."
    else:
        level = "LOW"
        recommendation = "Normal logistics can continue with routine monitoring."

    return {
        "feature": "Logistics Bottleneck Detector",
        "row_id": row_id,
        "disaster_type": get_disaster_type(row),
        "overall_logistics_risk": level,
        "logistics_risk_score": risk_score,
        "nearest_depot_distance_km": round(depot_distance, 2),
        "nearest_hospital_distance_km": round(hospital_distance, 2),
        "nearest_evacuation_center_km": round(evacuation_distance, 2),
        "disaster_hazard_signal": signal,
        "detected_bottlenecks": bottlenecks,
        "recommendation": recommendation,
    }


# ============================================================
# RELIEF STOCK MONITORING
# ============================================================

@app.get(
    "/disasters/{row_id}/stock-depletion",
    tags=["Relief Stock Monitoring"],
    summary="Estimate duration of current relief stocks",
)
def stock_depletion(row_id: int):
    row = get_disaster(row_id)

    event_hours = max(safe_float(row, "event_duration_hours", 24), 1)

    resources = {
        "food": {
            "demand": safe_float(row, "food_demand"),
            "available": safe_float(row, "food_packets_available"),
            "unit": "packets",
        },
        "water": {
            "demand": safe_float(row, "water_demand_litres"),
            "available": safe_float(row, "water_litres_available"),
            "unit": "litres",
        },
        "medical_kits": {
            "demand": safe_float(row, "medical_kit_demand"),
            "available": safe_float(row, "medical_kits_available"),
            "unit": "kits",
        },
    }

    forecast = {}
    candidates = []

    for name, info in resources.items():
        demand = max(info["demand"], 0)
        available = max(info["available"], 0)

        if demand <= 0:
            hourly_burn = 0.0
            duration_hours = None
            status = "NO CURRENT CONSUMPTION"
        else:
            hourly_burn = demand / event_hours
            duration_hours = available / hourly_burn if hourly_burn > 0 else None

            if duration_hours is not None:
                candidates.append((name, duration_hours))

            status = (
                "SUFFICIENT FOR CURRENT EVENT ESTIMATE"
                if available >= demand
                else "MAY RUN OUT BEFORE CURRENT EVENT ESTIMATE"
            )

        forecast[name] = {
            "available": round(available, 2),
            "estimated_event_demand": round(demand, 2),
            "average_consumption_per_hour": round(hourly_burn, 2),
            "estimated_stock_duration_hours": (
                round(duration_hours, 2) if duration_hours is not None else None
            ),
            "status": status,
            "unit": info["unit"],
        }

    if candidates:
        first_resource, first_hours = min(candidates, key=lambda item: item[1])
    else:
        first_resource, first_hours = None, None

    return {
        "feature": "Relief Stock Depletion Forecast",
        "row_id": row_id,
        "disaster_type": get_disaster_type(row),
        "event_duration_hours": round(event_hours, 2),
        "resource_forecast": forecast,
        "first_resource_expected_to_deplete": first_resource,
        "estimated_first_depletion_hours": (
            round(first_hours, 2) if first_hours is not None else None
        ),
        "note": "Rule-based stock-duration estimate, not an ML forecast.",
    }


# ============================================================
# EMERGENCY TEAM DEPLOYMENT
# ============================================================

@app.get(
    "/disasters/{row_id}/team-deployment",
    tags=["Emergency Team Deployment"],
    summary="Generate a prototype emergency-team deployment plan",
)
def team_deployment(row_id: int):
    row = get_disaster(row_id)

    affected = max(int(safe_float(row, "affected_population")), 0)
    severity = min(max(safe_float(row, "severity_score"), 0), 1)
    blockage = min(max(safe_float(row, "road_blockage_probability"), 0), 1)
    accessibility = min(
        max(safe_float(row, "logistics_accessibility_score", 1), 0),
        1,
    )

    hospital_count = max(int(safe_float(row, "hospital_count")), 0)
    health_center_count = max(int(safe_float(row, "health_center_count")), 0)
    vehicles_available = max(int(safe_float(row, "rescue_vehicles_available")), 0)
    personnel_available = max(int(safe_float(row, "personnel_available")), 0)

    rescue_teams = max(1, math.ceil(affected / 1200 * (0.7 + severity)))
    medical_teams = max(1, math.ceil(affected / 1800 * (0.6 + severity)))
    logistics_teams = max(1, math.ceil(affected / 2500 * (1.0 + blockage)))

    if accessibility < 0.65:
        logistics_teams += 1

    if hospital_count + health_center_count == 0:
        medical_teams += 1

    disaster_type = get_disaster_type(row)

    specialty_map = {
        "Flood": "Water-rescue support",
        "Cyclone": "Debris-clearance and medical support",
        "Earthquake": "Urban search-and-rescue support",
        "Wildfire": "Fire-rescue and evacuation support",
        "Landslide": "Search-and-rescue and access-clearance support",
    }

    specialist_team = specialty_map.get(disaster_type, "General rescue support")

    recommended_vehicles = max(
        1,
        math.ceil((rescue_teams + medical_teams + logistics_teams) * 0.75),
    )

    recommended_personnel = (
        rescue_teams * 6
        + medical_teams * 5
        + logistics_teams * 4
    )

    personnel_gap = max(recommended_personnel - personnel_available, 0)
    vehicle_gap = max(recommended_vehicles - vehicles_available, 0)

    if severity >= 0.80 or personnel_gap > 0 or vehicle_gap > 0:
        response_level = "HIGH"
    elif severity >= 0.60:
        response_level = "MEDIUM"
    else:
        response_level = "STANDARD"

    return {
        "feature": "Emergency Team Deployment Planner",
        "row_id": row_id,
        "disaster_type": disaster_type,
        "response_level": response_level,
        "recommended_specialist_support": specialist_team,
        "recommended_deployment": {
            "rescue_teams": rescue_teams,
            "medical_teams": medical_teams,
            "logistics_teams": logistics_teams,
            "rescue_vehicles": recommended_vehicles,
            "total_personnel": recommended_personnel,
        },
        "currently_available": {
            "rescue_vehicles": vehicles_available,
            "personnel": personnel_available,
            "hospitals": hospital_count,
            "health_centers": health_center_count,
        },
        "deployment_gap": {
            "additional_personnel_needed": personnel_gap,
            "additional_vehicles_needed": vehicle_gap,
        },
        "note": (
            "Prototype rule-based staffing estimate. Real deployments require "
            "authorized emergency-management assessment."
        ),
    }


# ============================================================
# PREDICTION CONFIDENCE
# ============================================================

@app.get(
    "/disasters/{row_id}/prediction-confidence",
    tags=["Prediction Confidence"],
    summary="Show Random Forest prediction stability",
)
def prediction_confidence(row_id: int):
    row = get_disaster(row_id)
    disaster_type = get_disaster_type(row)
    model = get_model_for_disaster(disaster_type)

    if not hasattr(model, "estimators_"):
        raise HTTPException(
            status_code=500,
            detail="Prediction confidence requires a tree-based ensemble model.",
        )

    X = (
        df.iloc[[row_id]][features]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0)
    )

    X_numpy = X.to_numpy()
    tree_predictions = np.asarray(
        [tree.predict(X_numpy)[0] for tree in model.estimators_],
        dtype=float,
    )

    resource_names = [
        "food_packets",
        "water_litres",
        "medical_kits",
        "shelter_people",
    ]

    results = {}
    levels = []

    for index, resource in enumerate(resource_names):
        values = np.maximum(tree_predictions[:, index], 0)
        mean_value = float(np.mean(values))
        std_value = float(np.std(values))
        lower_value = float(np.percentile(values, 5))
        upper_value = float(np.percentile(values, 95))
        relative_uncertainty = std_value / max(abs(mean_value), 1)

        if relative_uncertainty <= 0.05:
            confidence = "HIGH"
        elif relative_uncertainty <= 0.15:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        levels.append(confidence)

        results[resource] = {
            "predicted_value": round(mean_value, 2),
            "lower_estimate": round(lower_value, 2),
            "upper_estimate": round(upper_value, 2),
            "standard_deviation": round(std_value, 2),
            "confidence_level": confidence,
        }

    if "LOW" in levels:
        overall = "LOW"
    elif "MEDIUM" in levels:
        overall = "MEDIUM"
    else:
        overall = "HIGH"

    return {
        "feature": "Prediction Confidence Indicator",
        "row_id": row_id,
        "disaster_type": disaster_type,
        "number_of_trees": len(model.estimators_),
        "resource_predictions": results,
        "overall_confidence": overall,
        "note": (
            "The range is based on variation among Random Forest trees and is "
            "an uncertainty indicator, not a formal statistical confidence interval."
        ),
    }


# ============================================================
# MODEL EXPLAINABILITY
# ============================================================

@app.get(
    "/ml/model-explainability",
    tags=["Model Explainability"],
    summary="Show feature importance for a selected disaster model",
)
def model_explainability(
    disaster_type: str = Query(..., description="Flood, Cyclone, Earthquake, Wildfire or Landslide"),
    top_n: int = Query(10, ge=1, le=50),
):
    canonical = None

    for supported in SUPPORTED_DISASTERS:
        if supported.lower() == disaster_type.strip().lower():
            canonical = supported
            break

    if canonical is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported disaster type. Choose from: {', '.join(SUPPORTED_DISASTERS)}",
        )

    model = get_model_for_disaster(canonical)

    if not hasattr(model, "feature_importances_"):
        raise HTTPException(
            status_code=500,
            detail="Selected model does not expose feature_importances_.",
        )

    importances = np.asarray(model.feature_importances_, dtype=float)

    if len(importances) != len(features):
        raise HTTPException(
            status_code=500,
            detail="Model feature importance count does not match feature list.",
        )

    engineered = {
        "affected_population_ratio",
        "demographic_vulnerability_index",
        "infrastructure_damage_index",
        "logistics_difficulty_index",
        "vulnerability_load",
        "flood_intensity_index",
        "rainfall_pressure_index",
        "response_access_index",
        "average_emergency_distance_km",
        "month",
    }

    order = np.argsort(importances)[::-1]
    ranked = []

    for rank, idx in enumerate(order[:top_n], start=1):
        name = features[int(idx)]
        ranked.append(
            {
                "rank": rank,
                "feature": name,
                "importance": round(float(importances[int(idx)]), 6),
                "importance_pct": round(float(importances[int(idx)] * 100), 2),
                "feature_type": "ENGINEERED" if name in engineered else "ORIGINAL",
            }
        )

    return {
        "feature": "Model Explainability / Feature Importance",
        "disaster_type": canonical,
        "model": "Random Forest Regressor",
        "total_model_inputs": len(features),
        "top_features": ranked,
        "most_influential_feature": ranked[0]["feature"] if ranked else None,
        "note": (
            "This is a global feature-importance view for the selected disaster model, "
            "not a case-specific causal explanation."
        ),
    }
# ============================================================
# FINAL PROJECT OPERATIONS MODULES
# ============================================================

if not IS_VERCEL:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _state_key(path: Path) -> str:
    return path.name


def _read_json(path: Path, default):
    # Operational application state is now stored in SQLite. If an older JSON
    # state file exists, import it once so previous work is not lost.
    stored = load_app_state(_state_key(path))
    if stored is not None:
        return stored
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as file:
                legacy = json.load(file)
            save_app_state(_state_key(path), legacy)
            return legacy
        except (OSError, ValueError, TypeError):
            pass
    return default


def _write_json(path: Path, value):
    save_app_state(_state_key(path), value)


# ============================================================
# DISASTER ALERT & NOTIFICATION ENGINE
# ============================================================
# This is an academic prototype notification engine. It does not replace
# official NDMA, IMD, state-authority or local emergency alerts.
#
# The engine:
#   1. Fetches India-filtered USGS/GDACS live events.
#   2. Normalizes each event to one of the supported disaster types.
#   3. Reads each approved user's saved location + alert preferences.
#   4. Applies a prototype severity and distance threshold.
#   5. Stores a deduplicated in-app alert for matching users.
#
# SMS/email/push delivery is intentionally not implemented here. The stored
# alerts are the backend source that the React application can poll/display.

ALERT_SEVERITY_RANK = {
    "LOW": 1,
    "MODERATE": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}

ALERT_DISASTER_TYPES = set(SUPPORTED_DISASTERS)
ALERT_RADIUS_KM = max(
    10.0,
    float(os.getenv("DISASTER_AI_ALERT_RADIUS_KM", "100")),
)
ALERT_MIN_SEVERITY = str(
    os.getenv("DISASTER_AI_ALERT_MIN_SEVERITY", "MODERATE")
).strip().upper()
if ALERT_MIN_SEVERITY not in ALERT_SEVERITY_RANK:
    ALERT_MIN_SEVERITY = "MODERATE"

ALERT_REFRESH_SECONDS = max(
    60,
    int(os.getenv("DISASTER_AI_ALERT_REFRESH_SECONDS", "300")),
)
ALERT_FORCE_REFRESH_COOLDOWN_SECONDS = max(
    30,
    int(os.getenv("DISASTER_AI_ALERT_FORCE_COOLDOWN_SECONDS", "30")),
)
ALERT_MAX_STORED = max(
    500,
    int(os.getenv("DISASTER_AI_ALERT_MAX_STORED", "5000")),
)

_ALERT_LOCK = threading.RLock()
_ALERT_LAST_REFRESH_MONOTONIC = 0.0
_ALERT_LAST_REFRESH_AT = None
_ALERT_LAST_REFRESH_RESULT = {
    "checked_at": None,
    "new_alerts": 0,
    "matched_events": 0,
    "users_scanned": 0,
    "feed_errors": [],
    "skipped": False,
}


def _canonical_alert_disaster_type(source: str, event: dict):
    """Infer one supported disaster type from a live feed event."""
    if str(source).upper() == "USGS":
        return "Earthquake"

    haystack = " ".join(
        str(event.get(key, "") or "")
        for key in ("title", "description", "place")
    ).lower()

    keyword_groups = [
        (
            "Flood",
            (
                "flood",
                "flash flood",
                "river flood",
                "inundation",
            ),
        ),
        (
            "Cyclone",
            (
                "cyclone",
                "hurricane",
                "typhoon",
                "tropical storm",
                "tropical cyclone",
            ),
        ),
        (
            "Earthquake",
            (
                "earthquake",
                "seismic",
                "quake",
            ),
        ),
        (
            "Wildfire",
            (
                "wildfire",
                "forest fire",
                "bush fire",
                "wild fire",
            ),
        ),
        (
            "Landslide",
            (
                "landslide",
                "mudslide",
                "debris flow",
            ),
        ),
    ]

    for disaster_type, keywords in keyword_groups:
        if any(keyword in haystack for keyword in keywords):
            return disaster_type

    return None


def _prototype_alert_severity(source: str, event: dict):
    """Return a transparent prototype severity level for notification filtering."""
    if str(source).upper() == "USGS":
        magnitude = event.get("magnitude")
        try:
            magnitude = float(magnitude)
        except (TypeError, ValueError):
            magnitude = None

        if magnitude is None:
            return "MODERATE"

        if magnitude >= 6.0:
            return "CRITICAL"
        if magnitude >= 5.0:
            return "HIGH"
        if magnitude >= 4.0:
            return "MODERATE"
        return "LOW"

    text = " ".join(
        str(event.get(key, "") or "")
        for key in ("title", "description")
    ).lower()

    # These are deliberately described as prototype thresholds. The project
    # does not treat feed colour words as an official government warning.
    if any(word in text for word in ("red alert", "red level", "red warning")):
        return "CRITICAL"
    if any(
        word in text
        for word in ("orange alert", "orange level", "orange warning", "severe", "major")
    ):
        return "HIGH"
    if any(
        word in text
        for word in ("yellow alert", "yellow level", "yellow warning", "moderate")
    ):
        return "MODERATE"

    # GDACS records that reach the India-only feed but do not expose a usable
    # severity phrase are kept at MODERATE so the prototype remains useful
    # without pretending to know an official alert level.
    return "MODERATE"


def _normalise_live_alert_event(source: str, event: dict):
    disaster_type = _canonical_alert_disaster_type(source, event)
    if disaster_type not in ALERT_DISASTER_TYPES:
        return None

    try:
        latitude = float(event.get("latitude"))
        longitude = float(event.get("longitude"))
    except (TypeError, ValueError):
        return None

    if not is_india_coordinate(latitude, longitude):
        return None

    severity = _prototype_alert_severity(source, event)

    if source == "USGS":
        title = str(event.get("place") or "India earthquake").strip()
        event_time = event.get("time")
        external_link = event.get("url")
    else:
        title = str(event.get("title") or "India disaster event").strip()
        event_time = event.get("published")
        external_link = event.get("link")

    event_key_material = "|".join(
        [
            str(source).strip().upper(),
            str(event.get("id") or external_link or title).strip(),
            str(event_time or "").strip(),
            f"{latitude:.5f}",
            f"{longitude:.5f}",
        ]
    )
    event_key = hashlib.sha256(
        event_key_material.encode("utf-8")
    ).hexdigest()

    return {
        "event_key": event_key,
        "source": str(source).strip().upper(),
        "disaster_type": disaster_type,
        "severity": severity,
        "severity_rank": ALERT_SEVERITY_RANK[severity],
        "title": title[:300],
        "event_time": event_time,
        "external_link": external_link,
        "latitude": round(latitude, 5),
        "longitude": round(longitude, 5),
        "description": str(event.get("description") or "").strip()[:1000],
    }


def _alert_user_preferences(user_id):
    value = load_app_state(f"user_preferences:{user_id}") or {}
    return {
        "home_label": str(value.get("home_label") or "").strip(),
        "home_latitude": value.get("home_latitude"),
        "home_longitude": value.get("home_longitude"),
        "state": str(value.get("state") or "").strip(),
        "district": str(value.get("district") or "").strip(),
        "alert_types": [
            item
            for item in (value.get("alert_types") or [])
            if item in ALERT_DISASTER_TYPES
        ],
    }


def _eligible_alert_users():
    users = db_list_users()
    eligible = []

    for user in users:
        try:
            user_id = int(user.get("user_id") or user.get("id"))
        except (TypeError, ValueError):
            continue

        if not bool(user.get("is_active", True)):
            continue

        account_status = str(
            user.get("account_status") or "APPROVED"
        ).upper()
        if account_status != "APPROVED":
            continue

        preferences = _alert_user_preferences(user_id)

        if (
            preferences["home_latitude"] is None
            or preferences["home_longitude"] is None
            or not preferences["alert_types"]
        ):
            continue

        try:
            latitude = float(preferences["home_latitude"])
            longitude = float(preferences["home_longitude"])
        except (TypeError, ValueError):
            continue

        if not is_india_coordinate(latitude, longitude):
            continue

        eligible.append(
            {
                "user_id": user_id,
                "preferences": preferences,
                "latitude": latitude,
                "longitude": longitude,
            }
        )

    return eligible


def _load_stored_alerts():
    stored = _read_json(ALERTS_PATH, [])
    if not isinstance(stored, list):
        return []
    return stored


def _save_stored_alerts(alerts):
    # Keep the most recent records so a long-running academic prototype does
    # not grow its SQLite-backed application state without bound.
    alerts = list(alerts)[-ALERT_MAX_STORED:]
    _write_json(ALERTS_PATH, alerts)


def _alert_engine_result(
    *,
    checked_at=None,
    new_alerts=0,
    matched_events=0,
    users_scanned=0,
    feed_errors=None,
    skipped=False,
):
    return {
        "checked_at": checked_at,
        "new_alerts": int(new_alerts),
        "matched_events": int(matched_events),
        "users_scanned": int(users_scanned),
        "feed_errors": list(feed_errors or []),
        "skipped": bool(skipped),
        "radius_km": ALERT_RADIUS_KM,
        "minimum_severity": ALERT_MIN_SEVERITY,
    }


def _refresh_disaster_alerts(force=False):
    """
    Refresh the live-feed alert engine and persist newly matched user alerts.

    The normal refresh interval is five minutes by default. A forced refresh
    is still protected by a short cooldown so a client cannot hammer public
    feeds by repeatedly clicking "Check now".
    """
    global _ALERT_LAST_REFRESH_MONOTONIC
    global _ALERT_LAST_REFRESH_AT
    global _ALERT_LAST_REFRESH_RESULT

    now_monotonic = time.monotonic()

    with _ALERT_LOCK:
        elapsed = now_monotonic - _ALERT_LAST_REFRESH_MONOTONIC

        if _ALERT_LAST_REFRESH_MONOTONIC:
            minimum_wait = (
                _ALERT_FORCE_REFRESH_COOLDOWN_SECONDS
                if force
                else ALERT_REFRESH_SECONDS
            )
            if elapsed < minimum_wait:
                cached = dict(_ALERT_LAST_REFRESH_RESULT)
                cached["skipped"] = True
                cached["skip_reason"] = "refresh_cooldown"
                return cached

        users = _eligible_alert_users()
        feed_events = []
        feed_errors = []

        # Live feed functions are defined later in this module. They are
        # resolved when this function is called, after module startup.
        try:
            usgs = live_usgs(limit=100)
            feed_events.extend(
                ("USGS", event)
                for event in usgs.get("events", [])
            )
        except Exception as exc:
            detail = getattr(exc, "detail", str(exc))
            feed_errors.append(f"USGS: {detail}")

        try:
            gdacs = live_gdacs(limit=100)
            feed_events.extend(
                ("GDACS", event)
                for event in gdacs.get("events", [])
            )
        except Exception as exc:
            detail = getattr(exc, "detail", str(exc))
            feed_errors.append(f"GDACS: {detail}")

        normalised_events = []
        seen_event_keys = set()

        for source, event in feed_events:
            normalised = _normalise_live_alert_event(source, event)
            if not normalised:
                continue

            if normalised["event_key"] in seen_event_keys:
                continue

            seen_event_keys.add(normalised["event_key"])

            if (
                normalised["severity_rank"]
                < ALERT_SEVERITY_RANK[ALERT_MIN_SEVERITY]
            ):
                continue

            normalised_events.append(normalised)

        alerts = _load_stored_alerts()
        existing_keys = {
            (
                str(alert.get("user_id")),
                str(alert.get("event_key")),
            )
            for alert in alerts
            if alert.get("event_key")
        }

        created = []

        for user in users:
            selected_types = set(user["preferences"]["alert_types"])

            for event in normalised_events:
                if event["disaster_type"] not in selected_types:
                    continue

                distance_km = haversine(
                    user["latitude"],
                    user["longitude"],
                    event["latitude"],
                    event["longitude"],
                )

                if distance_km > ALERT_RADIUS_KM:
                    continue

                dedupe_key = (
                    str(user["user_id"]),
                    str(event["event_key"]),
                )
                if dedupe_key in existing_keys:
                    continue

                location_label = (
                    user["preferences"]["home_label"]
                    or user["preferences"]["district"]
                    or user["preferences"]["state"]
                    or "your saved location"
                )

                alert = {
                    "alert_id": uuid4().hex,
                    "user_id": user["user_id"],
                    "event_key": event["event_key"],
                    "source": event["source"],
                    "disaster_type": event["disaster_type"],
                    "severity": event["severity"],
                    "title": event["title"],
                    "message": (
                        f"Prototype {event['disaster_type']} alert: "
                        f"{event['title']} is approximately "
                        f"{distance_km:.1f} km from {location_label}. "
                        "Follow official emergency-management instructions."
                    ),
                    "distance_km": round(distance_km, 2),
                    "latitude": event["latitude"],
                    "longitude": event["longitude"],
                    "event_time": event["event_time"],
                    "external_link": event["external_link"],
                    "created_at": _utc_now(),
                    "read": False,
                    "prototype_notice": (
                        "This is a project-generated notification based on a "
                        "public live feed and saved user preferences. It is "
                        "not an official government emergency warning."
                    ),
                }

                alerts.append(alert)
                existing_keys.add(dedupe_key)
                created.append(alert)

        if created:
            _save_stored_alerts(alerts)

        checked_at = _utc_now()
        result = _alert_engine_result(
            checked_at=checked_at,
            new_alerts=len(created),
            matched_events=len(normalised_events),
            users_scanned=len(users),
            feed_errors=feed_errors,
            skipped=False,
        )

        _ALERT_LAST_REFRESH_MONOTONIC = now_monotonic
        _ALERT_LAST_REFRESH_AT = checked_at
        _ALERT_LAST_REFRESH_RESULT = result

        if created:
            audit(
                "DISASTER_ALERTS_GENERATED",
                "alert-engine",
                None,
                {
                    "new_alerts": len(created),
                    "matched_events": len(normalised_events),
                    "users_scanned": len(users),
                },
            )

        return result


def _current_user_id():
    user = CURRENT_USER.get()
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )
    try:
        return int(user["user_id"])
    except (TypeError, ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Authenticated user identity is invalid",
        ) from exc


# ============================================================
# INDIA PROTOTYPE RELIEF DEPOT NETWORK
# ============================================================
# ============================================================

# These are prototype project depots for demonstration. They are not claimed
# to be official NDMA/SDMA warehouse locations.
# -------------------------------------------------------------------
# PROTOTYPE INDIA STATE RELIEF-DEPOT NETWORK
# -------------------------------------------------------------------
# 28 States x 3 depot nodes = 84 prototype depot locations.
#
# These are academic/project-defined locations placed at district/city
# centres for routing and inventory demonstrations. They are NOT official
# government warehouse locations.
#
# Goa currently has only two districts; the third prototype node is placed
# in Mapusa as an additional North Goa service node so that the application
# still provides three operational depot points for the state.

STATE_DEPOT_NETWORK = [
    {
        "state": "Andhra Pradesh",
        "code": "AP",
        "region": "South-East",
        "nodes": [
            ("Visakhapatnam", "Visakhapatnam", 17.6868, 83.2185),
            ("Vijayawada", "Krishna", 16.5062, 80.6480),
            ("Tirupati", "Tirupati", 13.6288, 79.4192),
        ],
    },
    {
        "state": "Arunachal Pradesh",
        "code": "AR",
        "region": "North-East",
        "nodes": [
            ("Itanagar", "Papum Pare", 27.0844, 93.6053),
            ("Pasighat", "East Siang", 28.0663, 95.3268),
            ("Tawang", "Tawang", 27.5860, 91.8594),
        ],
    },
    {
        "state": "Assam",
        "code": "AS",
        "region": "North-East",
        "nodes": [
            ("Guwahati", "Kamrup Metropolitan", 26.1445, 91.7362),
            ("Dibrugarh", "Dibrugarh", 27.4728, 94.9120),
            ("Silchar", "Cachar", 24.8333, 92.7789),
        ],
    },
    {
        "state": "Bihar",
        "code": "BR",
        "region": "East",
        "nodes": [
            ("Patna", "Patna", 25.5941, 85.1376),
            ("Muzaffarpur", "Muzaffarpur", 26.1209, 85.3647),
            ("Gaya", "Gaya", 24.7955, 85.0002),
        ],
    },
    {
        "state": "Chhattisgarh",
        "code": "CG",
        "region": "Central-East",
        "nodes": [
            ("Raipur", "Raipur", 21.2514, 81.6296),
            ("Bilaspur", "Bilaspur", 22.0797, 82.1409),
            ("Jagdalpur", "Bastar", 19.0741, 82.0080),
        ],
    },
    {
        "state": "Goa",
        "code": "GA",
        "region": "West Coast",
        "nodes": [
            ("Panaji", "North Goa", 15.4909, 73.8278),
            ("Margao", "South Goa", 15.2993, 73.9580),
            ("Mapusa", "North Goa - Mapusa Service Zone", 15.5915, 73.8089),
        ],
    },
    {
        "state": "Gujarat",
        "code": "GJ",
        "region": "West",
        "nodes": [
            ("Ahmedabad", "Ahmedabad", 23.0225, 72.5714),
            ("Surat", "Surat", 21.1702, 72.8311),
            ("Rajkot", "Rajkot", 22.3039, 70.8022),
        ],
    },
    {
        "state": "Haryana",
        "code": "HR",
        "region": "North",
        "nodes": [
            ("Gurugram", "Gurugram", 28.4595, 77.0266),
            ("Hisar", "Hisar", 29.1492, 75.7217),
            ("Ambala", "Ambala", 30.3782, 76.7767),
        ],
    },
    {
        "state": "Himachal Pradesh",
        "code": "HP",
        "region": "North",
        "nodes": [
            ("Shimla", "Shimla", 31.1048, 77.1734),
            ("Mandi", "Mandi", 31.7087, 76.9320),
            ("Dharamshala", "Kangra", 32.2190, 76.3234),
        ],
    },
    {
        "state": "Jharkhand",
        "code": "JH",
        "region": "East",
        "nodes": [
            ("Ranchi", "Ranchi", 23.3441, 85.3096),
            ("Jamshedpur", "East Singhbhum", 22.8046, 86.2029),
            ("Dhanbad", "Dhanbad", 23.7957, 86.4304),
        ],
    },
    {
        "state": "Karnataka",
        "code": "KA",
        "region": "South",
        "nodes": [
            ("Bengaluru", "Bengaluru Urban", 12.9716, 77.5946),
            ("Mysuru", "Mysuru", 12.2958, 76.6394),
            ("Belagavi", "Belagavi", 15.8497, 74.4977),
        ],
    },
    {
        "state": "Kerala",
        "code": "KL",
        "region": "South-West",
        "nodes": [
            ("Thiruvananthapuram", "Thiruvananthapuram", 8.5241, 76.9366),
            ("Kochi", "Ernakulam", 9.9312, 76.2673),
            ("Kozhikode", "Kozhikode", 11.2588, 75.7804),
        ],
    },
    {
        "state": "Madhya Pradesh",
        "code": "MP",
        "region": "Central",
        "nodes": [
            ("Bhopal", "Bhopal", 23.2599, 77.4126),
            ("Indore", "Indore", 22.7196, 75.8577),
            ("Jabalpur", "Jabalpur", 23.1815, 79.9864),
        ],
    },
    {
        "state": "Maharashtra",
        "code": "MH",
        "region": "West",
        "nodes": [
            ("Mumbai", "Mumbai City", 19.0760, 72.8777),
            ("Pune", "Pune", 18.5204, 73.8567),
            ("Nagpur", "Nagpur", 21.1458, 79.0882),
        ],
    },
    {
        "state": "Manipur",
        "code": "MN",
        "region": "North-East",
        "nodes": [
            ("Imphal", "Imphal West", 24.8170, 93.9368),
            ("Churachandpur", "Churachandpur", 24.3333, 93.6833),
            ("Ukhrul", "Ukhrul", 25.1110, 94.3610),
        ],
    },
    {
        "state": "Meghalaya",
        "code": "ML",
        "region": "North-East",
        "nodes": [
            ("Shillong", "East Khasi Hills", 25.5788, 91.8933),
            ("Tura", "West Garo Hills", 25.5138, 90.2031),
            ("Nongpoh", "Ri Bhoi", 25.9023, 91.8764),
        ],
    },
    {
        "state": "Mizoram",
        "code": "MZ",
        "region": "North-East",
        "nodes": [
            ("Aizawl", "Aizawl", 23.7271, 92.7176),
            ("Lunglei", "Lunglei", 22.8870, 92.7470),
            ("Champhai", "Champhai", 23.4560, 93.3280),
        ],
    },
    {
        "state": "Nagaland",
        "code": "NL",
        "region": "North-East",
        "nodes": [
            ("Kohima", "Kohima", 25.6751, 94.1086),
            ("Dimapur", "Dimapur", 25.9091, 93.7266),
            ("Mokokchung", "Mokokchung", 26.3220, 94.5180),
        ],
    },
    {
        "state": "Odisha",
        "code": "OD",
        "region": "East",
        "nodes": [
            ("Bhubaneswar", "Khordha", 20.2961, 85.8245),
            ("Cuttack", "Cuttack", 20.4625, 85.8830),
            ("Sambalpur", "Sambalpur", 21.4669, 83.9812),
        ],
    },
    {
        "state": "Punjab",
        "code": "PB",
        "region": "North",
        "nodes": [
            ("Ludhiana", "Ludhiana", 30.9010, 75.8573),
            ("Amritsar", "Amritsar", 31.6340, 74.8723),
            ("Patiala", "Patiala", 30.3398, 76.3869),
        ],
    },
    {
        "state": "Rajasthan",
        "code": "RJ",
        "region": "North-West",
        "nodes": [
            ("Jaipur", "Jaipur", 26.9124, 75.7873),
            ("Jodhpur", "Jodhpur", 26.2389, 73.0243),
            ("Udaipur", "Udaipur", 24.5854, 73.7125),
        ],
    },
    {
        "state": "Sikkim",
        "code": "SK",
        "region": "North-East",
        "nodes": [
            ("Gangtok", "Gangtok", 27.3389, 88.6065),
            ("Namchi", "Namchi", 27.1645, 88.3638),
            ("Gyalshing", "Gyalshing", 27.2895, 88.2576),
        ],
    },
    {
        "state": "Tamil Nadu",
        "code": "TN",
        "region": "South",
        "nodes": [
            ("Chennai", "Chennai", 13.0827, 80.2707),
            ("Coimbatore", "Coimbatore", 11.0168, 76.9558),
            ("Madurai", "Madurai", 9.9252, 78.1198),
        ],
    },
    {
        "state": "Telangana",
        "code": "TS",
        "region": "South-Central",
        "nodes": [
            ("Hyderabad", "Hyderabad", 17.3850, 78.4867),
            ("Warangal", "Hanumakonda", 17.9689, 79.5941),
            ("Nizamabad", "Nizamabad", 18.6725, 78.0941),
        ],
    },
    {
        "state": "Tripura",
        "code": "TR",
        "region": "North-East",
        "nodes": [
            ("Agartala", "West Tripura", 23.8315, 91.2868),
            ("Udaipur", "Gomati", 23.5335, 91.4837),
            ("Dharmanagar", "North Tripura", 24.3786, 92.1662),
        ],
    },
    {
        "state": "Uttar Pradesh",
        "code": "UP",
        "region": "North",
        "nodes": [
            ("Lucknow", "Lucknow", 26.8467, 80.9462),
            ("Varanasi", "Varanasi", 25.3176, 82.9739),
            ("Meerut", "Meerut", 28.9845, 77.7064),
        ],
    },
    {
        "state": "Uttarakhand",
        "code": "UK",
        "region": "North",
        "nodes": [
            ("Dehradun", "Dehradun", 30.3165, 78.0322),
            ("Haridwar", "Haridwar", 29.9457, 78.1642),
            ("Haldwani", "Nainital", 29.2183, 79.5130),
        ],
    },
    {
        "state": "West Bengal",
        "code": "WB",
        "region": "East",
        "nodes": [
            ("Kolkata", "Kolkata", 22.5726, 88.3639),
            ("Siliguri", "Darjeeling", 26.7271, 88.3953),
            ("Kharagpur", "Paschim Medinipur", 22.3460, 87.2320),
        ],
    },
]

# Resource profiles are intentionally different so the three district depots
# are not exact clones. The existing mentor-requested x3 inventory scaling is
# applied later by INVENTORY_SCALE_FACTOR.
DEPOT_RESOURCE_PROFILES = [
    {
        "food_packets": 30000,
        "water_litres": 84000,
        "medical_kits": 2200,
        "shelter_capacity": 8400,
        "rescue_vehicles": 44,
        "personnel": 620,
    },
    {
        "food_packets": 24000,
        "water_litres": 68000,
        "medical_kits": 1750,
        "shelter_capacity": 6800,
        "rescue_vehicles": 35,
        "personnel": 510,
    },
    {
        "food_packets": 19000,
        "water_litres": 54000,
        "medical_kits": 1400,
        "shelter_capacity": 5400,
        "rescue_vehicles": 29,
        "personnel": 430,
    },
]


def build_prototype_relief_depots():
    depots = []

    for state_entry in STATE_DEPOT_NETWORK:
        for index, (city, district, latitude, longitude) in enumerate(
            state_entry["nodes"],
            start=1,
        ):
            resources = dict(
                DEPOT_RESOURCE_PROFILES[index - 1]
            )

            depots.append(
                {
                    "depot_id": (
                        f"{state_entry['code']}_{index}"
                    ),
                    "name": (
                        f"{district} Relief Depot {index}"
                    ),
                    "city": city,
                    "district": district,
                    "state": state_entry["state"],
                    "region": state_entry["region"],
                    "network_number": index,
                    "latitude": latitude,
                    "longitude": longitude,
                    "resources": resources,
                }
            )

    return depots


PROTOTYPE_RELIEF_DEPOTS = build_prototype_relief_depots()

DEPOT_RESOURCE_KEYS = ["food_packets","water_litres","medical_kits","shelter_capacity","rescue_vehicles","personnel"]

# Mentor update: triple the prototype inventory available at every state/depot.
# The version marker prevents an existing persisted SQLite inventory from being
# multiplied again every time the backend restarts.
INVENTORY_SCALE_FACTOR = 3
INVENTORY_SCALE_VERSION = 3

for _prototype_depot in PROTOTYPE_RELIEF_DEPOTS:
    for _resource_key in DEPOT_RESOURCE_KEYS:
        _prototype_depot["resources"][_resource_key] = int(
            _prototype_depot["resources"][_resource_key]
            * INVENTORY_SCALE_FACTOR
        )



def default_depot_state():
    return {
        "depots": json.loads(json.dumps(PROTOTYPE_RELIEF_DEPOTS)),
        "history": [],
        "inventory_scale_version": INVENTORY_SCALE_VERSION,
    }


def load_depot_state():
    saved = _read_json(DEPOT_INVENTORY_PATH, {})
    defaults = default_depot_state()

    saved_map = {
        str(d.get("depot_id")): d
        for d in saved.get("depots", [])
    }

    saved_has_inventory = bool(saved_map)
    saved_scale_version = int(
        saved.get("inventory_scale_version", 1)
        or 1
    )

    # Existing installations contain the old 1x inventory values.
    # Multiply those saved values by 3 exactly once, then persist version=3.
    migrate_existing_inventory = (
        saved_has_inventory
        and saved_scale_version < INVENTORY_SCALE_VERSION
    )

    for depot in defaults["depots"]:
        existing = saved_map.get(
            depot["depot_id"],
            {},
        )
        existing_resources = existing.get(
            "resources",
            {},
        )

        for key in DEPOT_RESOURCE_KEYS:
            if key in existing_resources:
                quantity = max(
                    int(
                        existing_resources.get(
                            key,
                            0,
                        )
                    ),
                    0,
                )

                if migrate_existing_inventory:
                    quantity *= INVENTORY_SCALE_FACTOR

                depot["resources"][key] = quantity

    defaults["history"] = list(
        saved.get("history", [])
    )[-200:]

    defaults["inventory_scale_version"] = (
        INVENTORY_SCALE_VERSION
    )

    _write_json(
        DEPOT_INVENTORY_PATH,
        defaults,
    )

    return defaults


depot_state = load_depot_state()


def depot_by_id(depot_id: str):
    for depot in depot_state["depots"]:
        if depot["depot_id"].lower() == str(depot_id).lower():
            return depot
    raise HTTPException(status_code=404, detail="Resource depot not found")


def depot_resource_status(depot, key: str):
    baseline = next((d["resources"][key] for d in PROTOTYPE_RELIEF_DEPOTS if d["depot_id"] == depot["depot_id"]), 1)
    ratio = depot["resources"].get(key, 0) / max(baseline, 1)
    if ratio <= 0.20: return "CRITICAL"
    if ratio <= 0.50: return "LOW"
    if ratio <= 0.80: return "MODERATE"
    return "SUFFICIENT"


def overall_depot_status(depot):
    statuses = [depot_resource_status(depot, key) for key in ["food_packets","water_litres","medical_kits","shelter_capacity"]]
    if "CRITICAL" in statuses: return "CRITICAL"
    if "LOW" in statuses: return "LOW"
    if "MODERATE" in statuses: return "MODERATE"
    return "OPERATIONAL"


def depot_view(depot, distance_km=None):
    data = {
        "depot_id": depot["depot_id"],
        "name": depot["name"],
        "city": depot["city"],
        "district": depot.get("district", depot["city"]),
        "state": depot["state"],
        "region": depot["region"],
        "network_number": depot.get("network_number"),
        "country": "India",
        "latitude": depot["latitude"],
        "longitude": depot["longitude"],
        "status": overall_depot_status(depot), "resources": depot["resources"],
        "resource_status": {key: depot_resource_status(depot, key) for key in DEPOT_RESOURCE_KEYS},
    }
    if distance_km is not None: data["distance_km"] = round(float(distance_km), 2)
    return data


def nearest_resource_depots(latitude: float, longitude: float, limit: int = 4):
    validate_india_coordinate(latitude, longitude, "Disaster location")
    ranked = []
    for depot in depot_state["depots"]:
        distance = haversine(latitude, longitude, depot["latitude"], depot["longitude"])
        ranked.append((distance, depot))
    ranked.sort(key=lambda item: item[0])
    return [depot_view(depot, distance) for distance, depot in ranked[:max(1, limit)]]


def national_depot_totals():
    return {key: sum(int(d["resources"].get(key, 0)) for d in depot_state["depots"]) for key in DEPOT_RESOURCE_KEYS}


def build_resource_source_plan(latitude: float, longitude: float, prediction: dict, max_depots: int = 4):
    candidates = nearest_resource_depots(latitude, longitude, limit=max_depots)
    resource_map = {
        "food_packets": "food_packets",
        "water_litres": "water_litres",
        "medical_kits": "medical_kits",
        "shelter_people": "shelter_capacity",
    }
    resources = {}
    available_resources = {"food_packets":0,"water_litres":0,"medical_kits":0,"shelter_capacity":0}
    planned_allocation = {"food_packets":0,"water_litres":0,"medical_kits":0,"shelter_people":0}
    unmet_demand = {"food_packets":0,"water_litres":0,"medical_kits":0,"shelter_people":0}

    for demand_key, depot_key in resource_map.items():
        required = max(int(prediction.get(demand_key, 0)), 0)
        remaining = required
        sources = []
        total_available = 0
        for candidate in candidates:
            stock = max(int(candidate["resources"].get(depot_key, 0)), 0)
            total_available += stock
            quantity = min(stock, remaining)
            if quantity > 0:
                sources.append({
                    "depot_id": candidate["depot_id"], "depot_name": candidate["name"], "city": candidate["city"],
                    "state": candidate["state"], "country": "India", "latitude": candidate["latitude"],
                    "longitude": candidate["longitude"], "distance_km": candidate["distance_km"], "quantity": quantity,
                })
                remaining -= quantity
            if remaining <= 0: break
        planned = required - remaining
        resources[demand_key] = {"required": required, "planned": planned, "unmet": remaining, "sources": sources}
        if depot_key == "shelter_capacity":
            available_resources["shelter_capacity"] = total_available
        else:
            available_resources[demand_key] = total_available
        planned_allocation[demand_key] = planned
        unmet_demand[demand_key] = remaining

    return {
        "primary_depot": candidates[0] if candidates else None,
        "nearby_depots": candidates,
        "available_resources": available_resources,
        "planned_allocation": planned_allocation,
        "unmet_demand": unmet_demand,
        "resources": resources,
        "note": "Resource-source planning uses the nearest prototype Indian relief depots and current depot inventory; it does not deduct stock until an authorized dispatch workflow is implemented.",
    }


def _median_seed(column: str, fallback: int, multiplier: float = 10.0):
    if column not in df.columns:
        return fallback
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    if values.empty:
        return fallback
    return max(int(round(float(values.median()) * multiplier)), fallback)


INVENTORY_META = {
    "food_packets": ("Food Packets", "packets", "food_packets_available", 10000),
    "water_litres": ("Water Litres", "litres", "water_litres_available", 50000),
    "medical_kits": ("Medical Kits", "kits", "medical_kits_available", 1000),
    "shelter_capacity": ("Shelter Capacity", "people", "shelter_capacity", 5000),
    "rescue_vehicles": ("Rescue Vehicles", "vehicles", "rescue_vehicles_available", 25),
    "personnel": ("Personnel", "people", "personnel_available", 250),
}


def default_inventory_state():
    state = {"history": []}
    for key, (_, _, column, fallback) in INVENTORY_META.items():
        state[key] = _median_seed(column, fallback)
    return state


def load_inventory_state():
    current = _read_json(INVENTORY_PATH, {})
    defaults = default_inventory_state()
    for key in INVENTORY_META:
        defaults[key] = max(int(current.get(key, defaults[key])), 0)
    defaults["history"] = list(current.get("history", []))[-100:]
    _write_json(INVENTORY_PATH, defaults)
    return defaults


inventory_state = load_inventory_state()
for _key, _value in national_depot_totals().items():
    if _key in inventory_state:
        inventory_state[_key] = _value
_write_json(INVENTORY_PATH, inventory_state)
missions_state = list(_read_json(MISSIONS_PATH, []))
field_reports_state = list(_read_json(FIELD_REPORTS_PATH, []))


def inventory_status(key: str, quantity: int):
    baseline = max(default_inventory_state().get(key, 1), 1)
    ratio = quantity / baseline
    if ratio <= 0.20:
        return "CRITICAL"
    if ratio <= 0.50:
        return "LOW"
    if ratio <= 0.80:
        return "MODERATE"
    return "SUFFICIENT"


def inventory_payload():
    totals = national_depot_totals()
    resources = {}
    for key, (label, unit, _, _) in INVENTORY_META.items():
        quantity = int(totals.get(key, inventory_state.get(key, 0)))
        resources[key] = {
            "label": label, "quantity": quantity, "unit": unit,
            "status": inventory_status(key, quantity),
        }
    return {
        "feature": "India Resource Depot Inventory",
        "country": "India",
        "depot_count": len(depot_state["depots"]),
        "state_count": len({
            depot["state"]
            for depot in depot_state["depots"]
        }),
        "depots_per_state": 3,
        "resources": resources,
        "national_totals": totals,
        "depots": [depot_view(depot) for depot in depot_state["depots"]],
        "history": list(depot_state.get("history", []))[-20:][::-1],
        "note": "Prototype India relief-depot network for academic demonstration: three operational depot nodes are provided per state. Locations are project-defined district/city centres and are not claimed to be official government warehouses. Goa has two districts, so its third node is an additional North Goa service point.",
    }


class InventoryUpdateRequest(BaseModel):
    quantity: int = Field(..., ge=0)
    reason: str = Field(default="Manual inventory update", min_length=1, max_length=200)


class InventoryAdjustmentRequest(BaseModel):
    change: int
    reason: str = Field(default="Operational inventory adjustment", min_length=1, max_length=200)


class DepotInventoryUpdateRequest(BaseModel):
    quantity: int = Field(..., ge=0)
    reason: str = Field(default="Depot inventory update", min_length=1, max_length=200)


@app.get("/inventory/depots", tags=["Resource Inventory Management"], summary="List Indian prototype resource depots")
def list_resource_depots():
    return {"country":"India", "depots":[depot_view(d) for d in depot_state["depots"]]}


@app.put("/inventory/depots/{depot_id}/{resource_name}", tags=["Resource Inventory Management"], summary="Update one resource at an Indian relief depot")
def set_depot_inventory(depot_id: str, resource_name: str, request: DepotInventoryUpdateRequest):
    global inventory_state
    if resource_name not in DEPOT_RESOURCE_KEYS:
        raise HTTPException(status_code=400, detail=f"Unsupported resource. Choose from: {', '.join(DEPOT_RESOURCE_KEYS)}")
    depot = depot_by_id(depot_id)
    old = int(depot["resources"].get(resource_name, 0))
    depot["resources"][resource_name] = int(request.quantity)
    depot_state.setdefault("history", []).append({
        "timestamp": _utc_now(), "depot_id": depot["depot_id"], "depot_name": depot["name"],
        "resource": resource_name, "old_quantity": old, "new_quantity": int(request.quantity),
        "change": int(request.quantity) - old, "reason": request.reason,
    })
    depot_state["history"] = depot_state["history"][-200:]
    _write_json(DEPOT_INVENTORY_PATH, depot_state)
    audit("DEPOT_INVENTORY_UPDATED", "depot", depot["depot_id"], {"resource": resource_name, "old_quantity": old, "new_quantity": int(request.quantity), "reason": request.reason})
    totals = national_depot_totals()
    for key, value in totals.items():
        if key in inventory_state:
            inventory_state[key] = value
    _write_json(INVENTORY_PATH, inventory_state)
    return {"message":"Depot inventory updated", "depot":depot_view(depot), "resource":resource_name, "old_quantity":old, "new_quantity":int(request.quantity)}


@app.get("/inventory", tags=["Resource Inventory Management"], summary="Get current command-center relief inventory")
def get_inventory():
    return inventory_payload()


@app.put("/inventory/{resource_name}", tags=["Resource Inventory Management"], summary="Set inventory quantity")
def set_inventory(resource_name: str, request: InventoryUpdateRequest):
    if resource_name not in INVENTORY_META:
        raise HTTPException(status_code=400, detail=f"Unsupported resource: {resource_name}")
    old = max(int(inventory_state.get(resource_name, 0)), 0)
    new = int(request.quantity)
    inventory_state[resource_name] = new
    inventory_state.setdefault("history", []).append({
        "timestamp": _utc_now(),
        "resource": resource_name,
        "label": INVENTORY_META[resource_name][0],
        "old_quantity": old,
        "new_quantity": new,
        "change": new - old,
        "reason": request.reason,
    })
    inventory_state["history"] = inventory_state["history"][-100:]
    _write_json(INVENTORY_PATH, inventory_state)
    audit("INVENTORY_UPDATED", "inventory", resource_name, {"old_quantity": old, "new_quantity": new, "reason": request.reason})
    return {"message": "Inventory updated", "resource": resource_name, "old_quantity": old, "new_quantity": new, "status": inventory_status(resource_name, new)}


@app.post("/inventory/{resource_name}/adjust", tags=["Resource Inventory Management"], summary="Add or remove inventory stock")
def adjust_inventory(resource_name: str, request: InventoryAdjustmentRequest):
    if resource_name not in INVENTORY_META:
        raise HTTPException(status_code=400, detail=f"Unsupported resource: {resource_name}")
    old = max(int(inventory_state.get(resource_name, 0)), 0)
    new = old + int(request.change)
    if new < 0:
        raise HTTPException(status_code=400, detail="Adjustment would create negative inventory")
    return set_inventory(resource_name, InventoryUpdateRequest(quantity=new, reason=request.reason))


@app.post("/inventory/reset", tags=["Resource Inventory Management"], summary="Reset inventory to prototype baseline")
def reset_inventory():
    global inventory_state, depot_state
    depot_state = default_depot_state()
    _write_json(DEPOT_INVENTORY_PATH, depot_state)
    inventory_state = default_inventory_state()
    for key, value in national_depot_totals().items():
        if key in inventory_state:
            inventory_state[key] = value
    _write_json(INVENTORY_PATH, inventory_state)
    return inventory_payload()


# ----------------------------
# LIVE FEEDS
# ----------------------------

HTTP_HEADERS = {
    "User-Agent": "DisasterAI-India-Academic-Prototype/1.0 (+http://localhost)",
    "Accept": "application/json, application/xml, text/xml, */*",
}


@app.get("/feeds/status", tags=["Live Disaster Feeds"], summary="Show configured data-feed status")
def feed_status():
    return {
        "operating_country": "India",
        "local_dataset": {
            "status": "READY",
            "records": len(df),
            "source": f"{RESOLVED_DATA_PATH.name} (India operating region)",
        },
        "usgs_earthquakes": {
            "status": "LIVE_ON_REQUEST",
            "source": "USGS all-day GeoJSON filtered by the bundled India boundary mask",
        },
        "gdacs": {
            "status": "LIVE_ON_REQUEST",
            "source": "GDACS GeoRSS filtered by India coordinates / India place names",
        },
        "ndma": {
            "status": "DEPLOYMENT_INTEGRATION_REQUIRED",
            "note": "No stable public API is assumed in this local prototype.",
        },
        "satellite_imagery": {
            "status": "API_KEY_OR_PROVIDER_REQUIRED",
            "note": "Satellite damage-estimation provider must be configured for deployment.",
        },
        "disaster_alert_engine": {
            "status": "LIVE_ON_REQUEST",
            "source": "India-filtered USGS/GDACS feeds matched against saved user locations and alert preferences",
        },
    }


def _http_get(url: str, *, timeout: int = 10, params: dict | None = None):
    response = requests.get(
        url,
        params=params,
        headers=HTTP_HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    return response


def _fetch_json_url(url: str, timeout: int = 10, params: dict | None = None):
    return _http_get(url, timeout=timeout, params=params).json()


def _xml_local_text(parent, local_names):
    wanted = {name.lower() for name in local_names}
    for node in parent.iter():
        local_name = node.tag.split("}")[-1].lower()
        if local_name in wanted and node.text:
            value = node.text.strip()
            if value:
                return value
    return None


def _gdacs_coordinates(item):
    point = _xml_local_text(item, {"point"})
    if point:
        pieces = point.replace(",", " ").split()
        if len(pieces) >= 2:
            try:
                return float(pieces[0]), float(pieces[1])
            except ValueError:
                pass

    lat_text = _xml_local_text(item, {"lat", "latitude"})
    lon_text = _xml_local_text(item, {"long", "lon", "longitude"})
    if lat_text and lon_text:
        try:
            return float(lat_text), float(lon_text)
        except ValueError:
            pass

    return None, None


INDIA_TEXT_TERMS = [
    "india",
    "odisha",
    "west bengal",
    "assam",
    "bihar",
    "uttar pradesh",
    "delhi",
    "maharashtra",
    "gujarat",
    "madhya pradesh",
    "telangana",
    "andhra pradesh",
    "tamil nadu",
    "karnataka",
    "kerala",
    "rajasthan",
    "jharkhand",
    "chhattisgarh",
    "uttarakhand",
    "himachal pradesh",
    "sikkim",
    "meghalaya",
    "manipur",
    "mizoram",
    "nagaland",
    "tripura",
    "arunachal pradesh",
    "goa",
    "punjab",
    "haryana",
    "jammu",
    "kashmir",
    "ladakh",
    "chandigarh",
    "puducherry",
    "andaman",
    "nicobar",
    "lakshadweep",
]


@app.get("/feeds/usgs", tags=["Live Disaster Feeds"], summary="Fetch recent USGS earthquakes inside India")
def live_usgs(limit: int = Query(20, ge=1, le=100)):
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
    try:
        payload = _fetch_json_url(url)
        events = []

        for feature in payload.get("features", []):
            coords = feature.get("geometry", {}).get("coordinates", [None, None, None])
            props = feature.get("properties", {})
            longitude = coords[0] if len(coords) > 0 else None
            latitude = coords[1] if len(coords) > 1 else None

            if latitude is None or longitude is None:
                continue
            if not is_india_coordinate(latitude, longitude):
                continue

            events.append(
                {
                    "id": feature.get("id"),
                    "magnitude": props.get("mag"),
                    "place": props.get("place") or "India earthquake",
                    "time": props.get("time"),
                    "url": props.get("url"),
                    "longitude": round(float(longitude), 5),
                    "latitude": round(float(latitude), 5),
                    "depth_km": coords[2] if len(coords) > 2 else None,
                    "country": "India",
                }
            )

            if len(events) >= limit:
                break

        return {
            "source": "USGS",
            "country": "India",
            "filter": "India boundary polygon",
            "live": True,
            "returned": len(events),
            "events": events,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"USGS India-only live feed unavailable: {exc}",
        ) from exc


@app.get("/feeds/gdacs", tags=["Live Disaster Feeds"], summary="Fetch current GDACS events affecting India")
def live_gdacs(limit: int = Query(20, ge=1, le=100)):
    url = "https://www.gdacs.org/xml/rss.xml"
    try:
        response = _http_get(url, timeout=10)
        root = ET.fromstring(response.content)
        items = []

        for item in root.findall(".//item"):
            title = _xml_local_text(item, {"title"}) or ""
            description = _xml_local_text(item, {"description", "summary"}) or ""
            link = _xml_local_text(item, {"link"})
            published = _xml_local_text(item, {"pubdate", "published", "updated"})
            latitude, longitude = _gdacs_coordinates(item)

            coordinate_match = (
                latitude is not None
                and longitude is not None
                and is_india_coordinate(latitude, longitude)
            )

            haystack = f"{title} {description}".lower()
            text_match = any(term in haystack for term in INDIA_TEXT_TERMS)

            # If GDACS provides coordinates, coordinates are authoritative for
            # this India-only view.  Text matching is used only when the RSS
            # item has no point geometry.
            if latitude is not None and longitude is not None:
                if not coordinate_match:
                    continue
            elif not text_match:
                continue

            items.append(
                {
                    "title": title,
                    "link": link,
                    "published": published,
                    "description": description,
                    "latitude": round(latitude, 5) if latitude is not None else None,
                    "longitude": round(longitude, 5) if longitude is not None else None,
                    "country": "India",
                }
            )

            if len(items) >= limit:
                break

        return {
            "source": "GDACS",
            "country": "India",
            "filter": "India GeoRSS coordinates / India place names",
            "live": True,
            "returned": len(items),
            "events": items,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"GDACS India-only live feed unavailable: {exc}",
        ) from exc


# ----------------------------
# IMPACT ZONE CLASSIFICATION
# ----------------------------

def classify_impact(row):
    severity = safe_float(row, "severity_score")
    dris = safe_float(row, "dris_score")
    impact = safe_float(row, "impact_score")
    score = max(severity * 100.0, dris, impact * 100.0)
    if score >= 80:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 40:
        return "MODERATE"
    return "LOW"


# The operations-zone endpoint is based entirely on the static featured dataset.
# Cache the completed JSON-ready response for each (disaster type, limit) pair so
# revisiting the Operations Map does not repeatedly scan/sort 212k rows. The
# cache is deliberately small because the frontend normally uses only a handful
# of combinations. It is safe to keep for the lifetime of the backend because
# this endpoint never mutates the source dataframe.
_OPERATIONS_ZONE_CACHE: dict[tuple[str | None, int], dict] = {}
_OPERATIONS_ZONE_CACHE_LOCK = threading.RLock()
_OPERATIONS_ZONE_CACHE_MAX_ENTRIES = 24


def _operations_zone_cache_key(disaster_type: str | None, limit: int):
    normalized_type = (
        disaster_type.strip().lower()
        if disaster_type and disaster_type.strip()
        else None
    )
    return normalized_type, int(limit)


def _cache_operations_zones(key, payload):
    with _OPERATIONS_ZONE_CACHE_LOCK:
        # Keep the cache bounded. A simple FIFO eviction is sufficient because
        # the number of query combinations is tiny and the data is static.
        if key not in _OPERATIONS_ZONE_CACHE and len(_OPERATIONS_ZONE_CACHE) >= _OPERATIONS_ZONE_CACHE_MAX_ENTRIES:
            oldest_key = next(iter(_OPERATIONS_ZONE_CACHE))
            _OPERATIONS_ZONE_CACHE.pop(oldest_key, None)
        _OPERATIONS_ZONE_CACHE[key] = payload


@app.get("/operations/zones", tags=["Impact Zone Classification"], summary="Return classified disaster zones for the operations map")
def operations_zones(
    disaster_type: str | None = Query(default=None),
    limit: int = Query(100, ge=1, le=500),
):
    cache_key = _operations_zone_cache_key(disaster_type, limit)

    with _OPERATIONS_ZONE_CACHE_LOCK:
        cached = _OPERATIONS_ZONE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    work = filter_india_dataframe(df)

    if disaster_type:
        work = work[
            work["disaster_type"].astype(str).str.lower()
            == disaster_type.strip().lower()
        ]

    if work.empty:
        return {
            "country": "India",
            "filter": "India boundary polygon",
            "returned_zones": 0,
            "impact_class_counts": {},
            "zones": [],
        }

    # Avoid returning the first N rows from a sorted dataset.  The old
    # behaviour produced a horizontal cluster of points and could make the map
    # look as though only one part of India had disasters.  We spatially thin
    # the dataset and balance the sample by disaster type instead.
    work = work.copy()
    lat = pd.to_numeric(work["latitude"], errors="coerce")
    lon = pd.to_numeric(work["longitude"], errors="coerce")

    def numeric_series(column_name: str):
        if column_name not in work.columns:
            return pd.Series(0.0, index=work.index)
        return pd.to_numeric(work[column_name], errors="coerce").fillna(0)

    severity = numeric_series("severity_score")
    dris = numeric_series("dris_score") / 100.0
    impact = numeric_series("impact_score")

    work["_zone_score"] = np.maximum.reduce(
        [severity.to_numpy(dtype=float), dris.to_numpy(dtype=float), impact.to_numpy(dtype=float)]
    )
    work["_lat_grid"] = np.floor(lat * 1.5) / 1.5
    work["_lon_grid"] = np.floor(lon * 1.5) / 1.5

    selected_parts = []
    if disaster_type:
        thinned = (
            work.sort_values("_zone_score", ascending=False)
            .drop_duplicates(["_lat_grid", "_lon_grid"])
            .head(limit)
        )
        selected_parts.append(thinned)
    else:
        types = [
            dtype
            for dtype in SUPPORTED_DISASTERS
            if dtype in set(work["disaster_type"].astype(str))
        ]
        per_type = max(1, limit // max(len(types), 1))

        for dtype in types:
            group = work[work["disaster_type"].astype(str) == dtype]
            group = (
                group.sort_values("_zone_score", ascending=False)
                .drop_duplicates(["_lat_grid", "_lon_grid"])
                .head(per_type)
            )
            selected_parts.append(group)

        selected = (
            pd.concat(selected_parts, axis=0)
            if selected_parts
            else work.iloc[0:0]
        )

        if len(selected) < limit:
            remaining = work.drop(index=selected.index, errors="ignore")
            remaining = (
                remaining.sort_values("_zone_score", ascending=False)
                .drop_duplicates(["disaster_type", "_lat_grid", "_lon_grid"])
                .head(limit - len(selected))
            )
            selected_parts.append(remaining)

    selected_work = (
        pd.concat(selected_parts, axis=0)
        .loc[lambda frame: ~frame.index.duplicated(keep="first")]
        .head(limit)
    )

    records = []
    for row_id, row in selected_work.iterrows():
        records.append(
            {
                "row_id": int(row_id),
                "grid_id": str(row.get("grid_id", row_id)),
                "disaster_type": get_disaster_type(row),
                "disaster_subtype": str(row.get("disaster_subtype", "")),
                "latitude": round(safe_float(row, "latitude"), 5),
                "longitude": round(safe_float(row, "longitude"), 5),
                "affected_population": int(safe_float(row, "affected_population")),
                "severity_score": round(safe_float(row, "severity_score"), 4),
                "dris_score": round(safe_float(row, "dris_score"), 2),
                "impact_class": classify_impact(row),
                "resource_shortage_index": round(safe_float(row, "resource_shortage_index"), 4),
                "road_blockage_probability": round(safe_float(row, "road_blockage_probability"), 4),
                "logistics_accessibility_score": round(safe_float(row, "logistics_accessibility_score"), 4),
            }
        )

    counts = {}
    for item in records:
        counts[item["impact_class"]] = counts.get(item["impact_class"], 0) + 1

    response = {
        "country": "India",
        "filter": "India boundary polygon + spatially balanced sampling",
        "returned_zones": len(records),
        "impact_class_counts": counts,
        "zones": records,
    }
    _cache_operations_zones(cache_key, response)
    return response


# ----------------------------
# FIELD REPORTS + DYNAMIC DEMAND
# ----------------------------

class FieldReportRequest(BaseModel):
    row_id: int
    injured_count: int = Field(default=0, ge=0)
    missing_count: int = Field(default=0, ge=0)
    reported_severity: float = Field(default=0.5, ge=0, le=1)
    road_status: str = Field(default="OPEN", min_length=1, max_length=80)
    notes: str = Field(default="", max_length=500)


def dynamic_demand_from_report(row_id: int, report: FieldReportRequest):
    row = get_disaster(row_id)
    base = predict_resources(row_id)
    affected = max(int(safe_float(row, "affected_population")), 1)
    injury_ratio = min(report.injured_count / affected, 0.50)
    missing_ratio = min(report.missing_count / affected, 0.30)
    severity_multiplier = 0.85 + report.reported_severity * 0.50
    road_multiplier = 1.10 if report.road_status.strip().upper() not in {"OPEN", "CLEAR", "NORMAL"} else 1.0
    return {
        "food_packets": int(round(base["food_packets"] * severity_multiplier * (1 + missing_ratio * 0.35))),
        "water_litres": int(round(base["water_litres"] * severity_multiplier * (1 + missing_ratio * 0.30))),
        "medical_kits": int(round(base["medical_kits"] * severity_multiplier * (1 + injury_ratio * 1.75))),
        "shelter_people": int(round(base["shelter_people"] * severity_multiplier * road_multiplier)),
    }


@app.get("/field-reports", tags=["Field Reports & Dynamic Demand"], summary="List field reports")
def list_field_reports(row_id: int | None = Query(default=None)):
    rows = field_reports_state
    if row_id is not None:
        rows = [item for item in rows if int(item.get("row_id", -1)) == row_id]
    return {"returned": len(rows), "reports": rows[-50:][::-1]}


@app.post("/field-reports", tags=["Field Reports & Dynamic Demand"], summary="Submit a field report and recalculate dynamic demand")
def create_field_report(request: FieldReportRequest):
    get_disaster(request.row_id)
    updated = dynamic_demand_from_report(request.row_id, request)
    baseline = predict_resources(request.row_id)
    current = CURRENT_USER.get()
    report = {
        "report_id": str(uuid4())[:8],
        "timestamp": _utc_now(),
        "reported_by_user_id": current.get("user_id") if current else None,
        "reported_by_name": current.get("name") if current else None,
        **request.model_dump(),
        "baseline_demand": baseline,
        "updated_dynamic_demand": updated,
    }
    field_reports_state.append(report)
    del field_reports_state[:-200]
    _write_json(FIELD_REPORTS_PATH, field_reports_state)
    audit("FIELD_REPORT_CREATED", "field_report", report["report_id"], {"row_id": request.row_id})
    return report


# ----------------------------
# MISSION ASSIGNMENT + TRACKING
# ----------------------------

MISSION_STATUSES = ["ASSIGNED", "EN_ROUTE", "ON_SITE", "COMPLETED", "CANCELLED"]


class MissionCreateRequest(BaseModel):
    row_id: int
    mission_name: str = Field(..., min_length=2, max_length=120)
    rescue_teams: int = Field(default=1, ge=0, le=100)
    medical_teams: int = Field(default=1, ge=0, le=100)
    logistics_teams: int = Field(default=1, ge=0, le=100)
    vehicles: int = Field(default=1, ge=0, le=200)
    personnel: int = Field(default=10, ge=0, le=5000)
    assigned_to_user_id: int | None = None
    notes: str = Field(default="", max_length=500)


class MissionStatusRequest(BaseModel):
    status: str
    note: str = Field(default="", max_length=300)


@app.get("/missions", tags=["Mission Assignment & Tracking"], summary="List response missions")
def list_missions(status: str | None = Query(default=None), row_id: int | None = Query(default=None)):
    items = list(missions_state)
    user = CURRENT_USER.get()
    if user and user.get("role") == "FIELD_TEAM":
        items = [m for m in items if int(m.get("assigned_to_user_id") or -1) == int(user["user_id"])]
    if status:
        items = [m for m in items if str(m.get("status", "")).upper() == status.upper()]
    if row_id is not None:
        items = [m for m in items if int(m.get("row_id", -1)) == row_id]
    return {"returned": len(items), "missions": items[::-1]}


@app.post("/missions", tags=["Mission Assignment & Tracking"], summary="Create a field mission")
def create_mission(request: MissionCreateRequest):
    current = CURRENT_USER.get()
    if current and current.get("role") == "FIELD_TEAM":
        raise HTTPException(status_code=403, detail="Field Team users cannot create missions")
    row = get_disaster(request.row_id)
    assigned_user = None
    if request.assigned_to_user_id is not None:
        candidate = get_user_by_id(request.assigned_to_user_id)
        if not candidate or candidate.get("role") != "FIELD_TEAM" or not candidate.get("is_active"):
            raise HTTPException(status_code=400, detail="Choose an active Field Team user")
        assigned_user = candidate
    mission = {
        "mission_id": str(uuid4())[:8],
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "created_by_user_id": current.get("user_id") if current else None,
        "created_by_name": current.get("name") if current else None,
        "assigned_to_user_id": assigned_user.get("user_id") if assigned_user else None,
        "assigned_to_name": assigned_user.get("name") if assigned_user else "Unassigned",
        "status": "ASSIGNED",
        "disaster_type": get_disaster_type(row),
        "latitude": safe_float(row, "latitude"),
        "longitude": safe_float(row, "longitude"),
        **{k:v for k,v in request.model_dump().items() if k != "assigned_to_user_id"},
        "status_history": [{"timestamp": _utc_now(), "status": "ASSIGNED", "note": "Mission created"}],
    }
    missions_state.append(mission)
    del missions_state[:-200]
    _write_json(MISSIONS_PATH, missions_state)
    audit("MISSION_CREATED", "mission", mission["mission_id"], {"row_id": request.row_id, "assigned_to_user_id": mission["assigned_to_user_id"]})
    return mission


@app.patch("/missions/{mission_id}/status", tags=["Mission Assignment & Tracking"], summary="Update mission tracking status")
def update_mission_status(mission_id: str, request: MissionStatusRequest):
    status = request.status.strip().upper()
    if status not in MISSION_STATUSES:
        raise HTTPException(status_code=400, detail=f"Choose status from: {', '.join(MISSION_STATUSES)}")
    for mission in missions_state:
        if mission.get("mission_id") == mission_id:
            current = CURRENT_USER.get()
            if current and current.get("role") == "FIELD_TEAM" and int(mission.get("assigned_to_user_id") or -1) != int(current["user_id"]):
                raise HTTPException(status_code=403, detail="You can update only missions assigned to you")
            mission["status"] = status
            mission["updated_at"] = _utc_now()
            mission.setdefault("status_history", []).append({"timestamp": _utc_now(), "status": status, "note": request.note})
            _write_json(MISSIONS_PATH, missions_state)
            audit("MISSION_STATUS_UPDATED", "mission", mission_id, {"status": status, "note": request.note})
            return mission
    raise HTTPException(status_code=404, detail="Mission not found")


# ----------------------------
# OR-TOOLS DELIVERY ROUTING
# ----------------------------

class RoutePlanRequest(BaseModel):
    depot_latitude: float = Field(ge=-90, le=90)
    depot_longitude: float = Field(ge=-180, le=180)
    row_ids: list[int] = Field(..., min_length=1, max_length=15)
    vehicle_count: int = Field(default=1, ge=1, le=5)
    average_speed_kmph: float = Field(default=40, ge=10, le=80)


def _road_distance_matrix(coords: list[tuple[float, float]]):
    """Return OSRM road-distance matrix in kilometres, or None on failure."""
    if len(coords) < 2:
        return None

    coordinate_string = ";".join(
        f"{float(lon):.6f},{float(lat):.6f}"
        for lat, lon in coords
    )
    url = f"https://router.project-osrm.org/table/v1/driving/{coordinate_string}"

    try:
        response = requests.get(
            url,
            params={"annotations": "distance,duration"},
            headers=HTTP_HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != "Ok":
            return None

        distances = payload.get("distances")
        durations = payload.get("durations")
        if not distances or len(distances) != len(coords):
            return None

        km_matrix = []
        for row in distances:
            if row is None or len(row) != len(coords):
                return None
            km_row = []
            for value in row:
                if value is None:
                    return None
                km_row.append(float(value) / 1000.0)
            km_matrix.append(km_row)

        duration_matrix = None
        if durations and len(durations) == len(coords):
            try:
                duration_matrix = [
                    [float(value) / 60.0 for value in row]
                    for row in durations
                ]
            except Exception:
                duration_matrix = None

        return {
            "distance_km": km_matrix,
            "duration_minutes": duration_matrix,
        }
    except Exception:
        return None


def _road_route_from_stops(stops: list[dict]):
    """Fetch road-following geometry from the public OSRM demo service.

    Returns None when the public service is unavailable; callers then keep the
    deterministic Haversine/OR-Tools fallback used by the academic prototype.
    """
    if len(stops) < 2:
        return None

    coordinate_string = ";".join(
        f"{float(stop['longitude']):.6f},{float(stop['latitude']):.6f}"
        for stop in stops
    )
    url = f"https://router.project-osrm.org/route/v1/driving/{coordinate_string}"

    try:
        response = requests.get(
            url,
            params={
                "overview": "full",
                "geometries": "geojson",
                "steps": "false",
            },
            headers=HTTP_HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != "Ok" or not payload.get("routes"):
            return None

        route = payload["routes"][0]
        geometry = route.get("geometry", {}).get("coordinates") or []
        if not geometry:
            return None

        return {
            "distance_km": round(float(route.get("distance", 0.0)) / 1000.0, 2),
            "duration_minutes": round(float(route.get("duration", 0.0)) / 60.0, 1),
            # Leaflet consumes [lat, lon], while GeoJSON/OSRM returns [lon, lat].
            "geometry": [
                [round(float(lat), 6), round(float(lon), 6)]
                for lon, lat in geometry
            ],
        }
    except Exception:
        return None


@app.post("/routing/optimize", tags=["Optimized Delivery Routing"], summary="Optimize depot-to-zone delivery routes using OR-Tools")
def optimize_delivery_routes(request: RoutePlanRequest):
    validate_india_coordinate(
        request.depot_latitude,
        request.depot_longitude,
        "Depot location",
    )

    row_ids = list(dict.fromkeys(request.row_ids))
    rows = [get_disaster(row_id) for row_id in row_ids]

    for row in rows:
        validate_india_coordinate(
            safe_float(row, "latitude"),
            safe_float(row, "longitude"),
            "Disaster location",
        )

    vehicle_count = min(request.vehicle_count, len(row_ids))
    coords = [
        (request.depot_latitude, request.depot_longitude)
    ] + [
        (safe_float(row, "latitude"), safe_float(row, "longitude"))
        for row in rows
    ]

    factors = [1.0]
    for row in rows:
        access = max(
            safe_float(row, "logistics_accessibility_score", 1.0),
            0.20,
        )
        blockage = min(
            max(safe_float(row, "road_blockage_probability", 0.0), 0.0),
            0.90,
        )
        factors.append(max(access * (1 - blockage), 0.20))

    n = len(coords)
    costs = [[0] * n for _ in range(n)]
    straight_line = [[0.0] * n for _ in range(n)]

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            straight_line[i][j] = haversine(
                coords[i][0],
                coords[i][1],
                coords[j][0],
                coords[j][1],
            )

    road_matrix = _road_distance_matrix(coords)
    routing_distance = (
        road_matrix["distance_km"]
        if road_matrix
        else straight_line
    )
    optimization_distance_source = (
        "OSRM road-distance matrix"
        if road_matrix
        else "Haversine fallback matrix"
    )

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            penalty = 1.0 / max(factors[j], 0.20)
            costs[i][j] = int(round(routing_distance[i][j] * 1000 * penalty))

    manager = pywrapcp.RoutingIndexManager(n, vehicle_count, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        return costs[
            manager.IndexToNode(from_index)
        ][
            manager.IndexToNode(to_index)
        ]

    transit_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_index)
    routing.AddDimension(
        transit_index,
        0,
        50_000_000,
        True,
        "Distance",
    )
    routing.GetDimensionOrDie("Distance").SetGlobalSpanCostCoefficient(100)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    params.time_limit.seconds = 2

    solution = routing.SolveWithParameters(params)
    if solution is None:
        raise HTTPException(
            status_code=500,
            detail="Route optimizer could not find a solution",
        )

    routes = []
    total_distance_km = 0.0
    road_routes_found = 0

    for vehicle_id in range(vehicle_count):
        index = routing.Start(vehicle_id)
        node_sequence = []
        planning_distance_km = 0.0

        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            node_sequence.append(node)

            next_index = solution.Value(routing.NextVar(index))
            next_node = manager.IndexToNode(next_index)

            if not routing.IsEnd(next_index):
                planning_distance_km += routing_distance[node][next_node]
            elif node != 0:
                planning_distance_km += routing_distance[node][0]

            index = next_index

        node_sequence.append(0)

        stops = []
        for stop_number, node in enumerate(node_sequence):
            if node == 0:
                stops.append(
                    {
                        "type": "DEPOT",
                        "stop_number": stop_number,
                        "latitude": request.depot_latitude,
                        "longitude": request.depot_longitude,
                    }
                )
            else:
                row_id = row_ids[node - 1]
                row = rows[node - 1]
                stops.append(
                    {
                        "type": "DISASTER_ZONE",
                        "stop_number": stop_number,
                        "row_id": row_id,
                        "disaster_type": get_disaster_type(row),
                        "latitude": coords[node][0],
                        "longitude": coords[node][1],
                        "access_factor": round(factors[node], 4),
                    }
                )

        visited_zone_nodes = [node for node in node_sequence if node != 0]
        avg_factor = (
            sum(factors[node] for node in visited_zone_nodes)
            / max(len(visited_zone_nodes), 1)
        )

        road_route = _road_route_from_stops(stops)
        if road_route:
            road_routes_found += 1
            route_distance_km = road_route["distance_km"]
            # OSRM supplies normal-road travel time.  The response estimate is
            # conservatively adjusted using the same accessibility/blockage
            # factor used by the optimization model.
            estimated_minutes = round(
                road_route["duration_minutes"] / max(avg_factor, 0.35),
                1,
            )
            route_geometry = road_route["geometry"]
            route_source = "OSRM road network"
            base_road_minutes = road_route["duration_minutes"]
        else:
            route_distance_km = round(planning_distance_km, 2)
            effective_speed = max(
                request.average_speed_kmph * avg_factor,
                10,
            )
            estimated_minutes = round(
                planning_distance_km / effective_speed * 60,
                1,
            )
            route_geometry = [
                [float(stop["latitude"]), float(stop["longitude"])]
                for stop in stops
            ]
            route_source = "Haversine fallback"
            base_road_minutes = None

        total_distance_km += route_distance_km

        routes.append(
            {
                "vehicle_id": vehicle_id + 1,
                "distance_km": round(route_distance_km, 2),
                "planning_straight_line_km": round(planning_distance_km, 2),
                "estimated_minutes": estimated_minutes,
                "base_road_minutes": base_road_minutes,
                "route_source": route_source,
                "route_geometry": route_geometry,
                "stops": stops,
            }
        )

    return {
        "feature": "OR-Tools Optimized Delivery Routing",
        "country": "India",
        "solver": "OR-Tools RoutingModel",
        "optimization_distance_source": optimization_distance_source,
        "vehicle_count": vehicle_count,
        "total_route_distance_km": round(total_distance_km, 2),
        "road_routes_found": road_routes_found,
        "routes": routes,
        "note": (
            "Stop order is optimized with OR-Tools using an OSRM road-distance matrix when available. "
            "The map also follows OSRM road geometry and road distance when available. "
            "If OSRM is unavailable, the app clearly falls back to straight-line "
            "prototype routing. Accessibility/blockage values are used only as "
            "planning penalties, not as live road-closure data."
        ),
    }


# ----------------------------
# SCENARIO SIMULATION
# ----------------------------

class ScenarioRequest(BaseModel):
    row_id: int
    severity_multiplier: float = Field(default=1.0, ge=0.5, le=2.0)
    resource_availability_percent: float = Field(default=100, ge=10, le=200)
    response_speed_percent: float = Field(default=100, ge=50, le=200)
    accessibility_multiplier: float = Field(default=1.0, ge=0.5, le=1.5)


@app.post("/scenario/simulate", tags=["Scenario Simulation"], summary="Simulate changed severity, resources and response conditions")
def simulate_scenario(request: ScenarioRequest):
    row = get_disaster(request.row_id)
    baseline = predict_resources(request.row_id)
    severity_factor = 1 + 0.75 * (request.severity_multiplier - 1)
    demand = {key: max(int(round(value * severity_factor)), 0) for key, value in baseline.items()}
    central = {
        "food_packets": inventory_state["food_packets"],
        "water_litres": inventory_state["water_litres"],
        "medical_kits": inventory_state["medical_kits"],
        "shelter_people": inventory_state["shelter_capacity"],
    }
    available = {key: int(round(value * request.resource_availability_percent / 100.0)) for key, value in central.items()}
    shortage = {key: max(demand[key] - available[key], 0) for key in demand}
    coverage = {key: round(min(available[key] / max(demand[key], 1), 1) * 100, 2) for key in demand}
    distance = max(safe_float(row, "nearest_depot_distance_km"), 1.0)
    access = min(max(safe_float(row, "logistics_accessibility_score", 1) * request.accessibility_multiplier, 0.2), 1.0)
    speed = max(40 * (request.response_speed_percent / 100.0) * access, 10)
    eta = distance / speed * 60 + 10
    return {"feature": "Response Scenario Simulation", "row_id": request.row_id, "disaster_type": get_disaster_type(row), "baseline_prediction": baseline, "simulated_demand": demand, "simulated_available_resources": available, "simulated_shortage": shortage, "coverage_percent": coverage, "average_coverage_percent": round(sum(coverage.values()) / len(coverage), 2), "estimated_response_eta_minutes": round(eta, 1), "scenario_inputs": request.model_dump(), "note": "Scenario values are planning what-if estimates derived from the baseline ML prediction; they are not a newly trained model prediction."}


# ----------------------------
# POST-EVENT ANALYTICS
# ----------------------------

def _sum_column(column):
    if column not in df.columns:
        return 0
    return float(pd.to_numeric(df[column], errors="coerce").fillna(0).sum())


def _mean_column(column):
    if column not in df.columns:
        return 0
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    return float(values.mean()) if len(values) else 0


@app.get("/analytics/summary", tags=["Operations Analytics"], summary="Generate post-event disaster-response analytics")
def analytics_summary():
    disaster_counts = df["disaster_type"].value_counts().to_dict()
    by_type = []
    for disaster_type, group in df.groupby("disaster_type"):
        by_type.append({
            "disaster_type": str(disaster_type),
            "records": int(len(group)),
            "affected_population": int(pd.to_numeric(group.get("affected_population", 0), errors="coerce").fillna(0).sum()),
            "average_severity": round(float(pd.to_numeric(group.get("severity_score", 0), errors="coerce").fillna(0).mean()), 4),
            "average_dris": round(float(pd.to_numeric(group.get("dris_score", 0), errors="coerce").fillna(0).mean()), 2),
        })
    severity = pd.to_numeric(df.get("severity_score", pd.Series(dtype=float)), errors="coerce").fillna(0)
    severity_distribution = {
        "CRITICAL": int((severity >= 0.8).sum()),
        "HIGH": int(((severity >= 0.65) & (severity < 0.8)).sum()),
        "MODERATE": int(((severity >= 0.45) & (severity < 0.65)).sum()),
        "LOW": int((severity < 0.45).sum()),
    }
    active_missions = sum(1 for m in missions_state if m.get("status") not in {"COMPLETED", "CANCELLED"})
    return {
        "total_records": len(df),
        "disaster_counts": disaster_counts,
        "by_disaster_type": by_type,
        "severity_distribution": severity_distribution,
        "total_affected_population": int(_sum_column("affected_population")),
        "historical_resource_demand": {
            "food_packets": int(_sum_column("food_demand")),
            "water_litres": int(_sum_column("water_demand_litres")),
            "medical_kits": int(_sum_column("medical_kit_demand")),
            "shelter_people": int(_sum_column("shelter_demand")),
        },
        "average_response_time_minutes": round(_mean_column("response_time_minutes"), 2),
        "average_resource_fulfillment_percent": round(_mean_column("resource_fulfillment_pct"), 2),
        "field_reports_recorded": len(field_reports_state),
        "missions_total": len(missions_state),
        "missions_active": active_missions,
    }


# ----------------------------
# CONSOLIDATED SITUATION REPORT
# ----------------------------

@app.get("/reports/situation/{row_id}", tags=["Situation Reports"], summary="Generate a consolidated incident situation report")
def situation_report(row_id: int):
    row = get_disaster(row_id)
    report_missions = [m for m in missions_state if int(m.get("row_id", -1)) == row_id]
    reports = [r for r in field_reports_state if int(r.get("row_id", -1)) == row_id]
    return {
        "report_type": "Emergency Situation Report",
        "generated_at": _utc_now(),
        "incident": {
            "row_id": row_id,
            "event_id": str(row.get("event_id", "")),
            "disaster_type": get_disaster_type(row),
            "disaster_subtype": str(row.get("disaster_subtype", "")),
            "latitude": safe_float(row, "latitude"),
            "longitude": safe_float(row, "longitude"),
            "affected_population": int(safe_float(row, "affected_population")),
            "severity_score": round(safe_float(row, "severity_score"), 4),
            "dris_score": round(safe_float(row, "dris_score"), 2),
            "impact_class": classify_impact(row),
        },
        "resource_prediction": resource_prediction(row_id),
        "resource_allocation": resource_allocation(row_id),
        "evacuation_plan": evacuation_plan(row_id),
        "transport_recommendation": transport_recommendation(row_id),
        "logistics_bottlenecks": logistics_bottlenecks(row_id),
        "stock_monitoring": stock_depletion(row_id),
        "team_deployment": team_deployment(row_id),
        "field_reports": reports[-10:],
        "missions": report_missions[-10:],
        "limitations": [
            "Academic prototype using local dataset and model artifacts.",
            "ETA and routing are planning estimates, not live turn-by-turn navigation.",
            "External feeds depend on internet/provider availability.",
        ],
    }

# ============================================================
# MULTILINGUAL UI TRANSLATION
# ============================================================

# FREE LOCAL TRANSLATION
# ----------------------
# No paid API, API key, subscription, or cloud translation service is used.
# The NLLB-200 distilled 600M model runs locally through PyTorch.
# The model is downloaded once by the setup script and then cached locally.
#
# IMPORTANT LICENSE NOTE:
# facebook/nllb-200-distilled-600M is released under CC-BY-NC-4.0.
# It is suitable for this academic/non-commercial project, but do not use
# this model in a commercial product without checking its license.

TRANSLATION_LANGUAGE_CODES = {
    "en": "eng_Latn",
    "hi": "hin_Deva",
    "as": "asm_Beng",
    "bn": "ben_Beng",
    "gu": "guj_Gujr",
    "kn": "kan_Knda",
    "kok": "gom_Deva",
    "ml": "mal_Mlym",
    "mr": "mar_Deva",
    "mni": "mni_Mtei",
    "lus": "lus_Latn",
    "ne": "npi_Deva",
    "or": "ory_Orya",
    "pa": "pan_Guru",
    "ta": "tam_Taml",
    "te": "tel_Telu",
    "ur": "urd_Arab",
    "ks": "kas_Arab",
}

LOCAL_TRANSLATION_MODEL = "facebook/nllb-200-distilled-600M"
LOCAL_TRANSLATION_CACHE_FILE = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "operations_state"
    / "ui_translation_cache.json"
)

_TRANSLATION_CACHE: dict[tuple[str, str], str] = {}
_TRANSLATION_MODEL = None
_TRANSLATION_TOKENIZER = None
_TRANSLATION_LOCK = None


def _translation_lock():
    global _TRANSLATION_LOCK
    if _TRANSLATION_LOCK is None:
        import threading
        _TRANSLATION_LOCK = threading.RLock()
    return _TRANSLATION_LOCK


def _load_translation_cache():
    if _TRANSLATION_CACHE:
        return

    try:
        if not LOCAL_TRANSLATION_CACHE_FILE.exists():
            return

        payload = json.loads(
            LOCAL_TRANSLATION_CACHE_FILE.read_text(encoding="utf-8")
        )

        if not isinstance(payload, dict):
            return

        for language, values in payload.items():
            if not isinstance(values, dict):
                continue
            for source, translated in values.items():
                if (
                    isinstance(source, str)
                    and isinstance(translated, str)
                    and translated.strip()
                    and translated.strip() != source.strip()
                ):
                    _TRANSLATION_CACHE[(language, source)] = translated
    except Exception:
        # A corrupt cache must never prevent the emergency application from
        # starting. It will simply be rebuilt as translations are requested.
        pass


def _save_translation_cache():
    try:
        LOCAL_TRANSLATION_CACHE_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        grouped: dict[str, dict[str, str]] = {}
        for (language, source), translated in _TRANSLATION_CACHE.items():
            grouped.setdefault(language, {})[source] = translated

        temporary = LOCAL_TRANSLATION_CACHE_FILE.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                grouped,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(LOCAL_TRANSLATION_CACHE_FILE)
    except Exception:
        # Translation persistence is an optimization, never a hard dependency.
        pass


def _load_local_translation_model():
    global _TRANSLATION_MODEL
    global _TRANSLATION_TOKENIZER

    if (
        IS_VERCEL
        and os.getenv("DISASTER_AI_ENABLE_LOCAL_TRANSLATION", "").strip().lower()
        not in {"1", "true", "yes", "on"}
    ):
        raise RuntimeError(
            "Local NLLB translation is disabled on Vercel. "
            "The frontend reviewed translation dictionary remains active."
        )

    if _TRANSLATION_MODEL is not None and _TRANSLATION_TOKENIZER is not None:
        return _TRANSLATION_TOKENIZER, _TRANSLATION_MODEL

    with _translation_lock():
        if _TRANSLATION_MODEL is not None and _TRANSLATION_TOKENIZER is not None:
            return _TRANSLATION_TOKENIZER, _TRANSLATION_MODEL

        try:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "Local translation dependencies are missing. Run "
                "setup_local_translation.ps1 first."
            ) from exc

        print(
            "[Disaster AI India] Loading FREE local translation model "
            f"{LOCAL_TRANSLATION_MODEL} ..."
        )

        tokenizer = AutoTokenizer.from_pretrained(
            LOCAL_TRANSLATION_MODEL,
        )
        model = AutoModelForSeq2SeqLM.from_pretrained(
            LOCAL_TRANSLATION_MODEL,
        )

        # CPU dynamic INT8 reduces the runtime RAM footprint substantially.
        # GPU users keep the regular model and use float16 when possible.
        if torch.cuda.is_available():
            model = model.to("cuda")
            try:
                model = model.half()
            except Exception:
                pass
        else:
            try:
                model = torch.ao.quantization.quantize_dynamic(
                    model,
                    {torch.nn.Linear},
                    dtype=torch.qint8,
                )
            except Exception as exc:
                print(
                    "[Disaster AI India] CPU INT8 optimization unavailable; "
                    f"continuing with CPU model: {exc}"
                )

        model.eval()

        _TRANSLATION_TOKENIZER = tokenizer
        _TRANSLATION_MODEL = model

        print("[Disaster AI India] Local translation model ready.")

        return tokenizer, model


def _translate_local_batch(texts: list[str], language: str) -> dict[str, str]:
    target = TRANSLATION_LANGUAGE_CODES.get(language)

    if not target or target == "eng_Latn":
        return {text: text for text in texts}

    _load_translation_cache()

    pending = []
    output: dict[str, str] = {}

    for text in texts:
        cached = _TRANSLATION_CACHE.get((language, text))
        if cached and cached.strip() and cached.strip() != text.strip():
            output[text] = cached
        else:
            pending.append(text)

    if not pending:
        return output

    tokenizer, model = _load_local_translation_model()

    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    target_id = tokenizer.convert_tokens_to_ids(target)

    if target_id is None or target_id == tokenizer.unk_token_id:
        raise RuntimeError(
            f"Unsupported NLLB target language code: {target}"
        )

    # Keep the inference batch modest so the app remains usable on normal
    # student laptops. The frontend can send batches of up to 24 phrases; 12 keeps memory reasonable while reducing model.generate calls.
    batch_size = 12

    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]

        encoded = tokenizer(
            batch,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=256,
        )

        if device == "cuda":
            encoded = {
                key: value.to(device)
                for key, value in encoded.items()
            }

        tokenizer.src_lang = "eng_Latn"

        with torch.inference_mode():
            generated = model.generate(
                **encoded,
                forced_bos_token_id=target_id,
                max_new_tokens=96,
                num_beams=2,
                do_sample=False,
            )

        translated_values = tokenizer.batch_decode(
            generated,
            skip_special_tokens=True,
        )

        for source, translated in zip(batch, translated_values):
            value = " ".join(str(translated or "").split()).strip()

            # Never cache an empty response or an unchanged English source.
            if value and value != source.strip():
                output[source] = value
                _TRANSLATION_CACHE[(language, source)] = value

    if output:
        with _translation_lock():
            _save_translation_cache()

    return output


@app.post(
    "/public/translate-batch",
    tags=["Citizen Safety & Public Access"],
    summary="Translate visible Disaster AI India UI text locally",
)
def public_translate_batch(request: TranslationBatchRequest):
    language = request.language.strip()

    if language not in TRANSLATION_LANGUAGE_CODES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported application language.",
        )

    unique_texts: list[str] = []
    seen = set()

    for value in request.texts:
        clean = " ".join(str(value or "").split()).strip()

        if (
            not clean
            or len(clean) > 300
            or clean in seen
        ):
            continue

        seen.add(clean)
        unique_texts.append(clean)

    if language == "en" or (
        IS_VERCEL
        and os.getenv("DISASTER_AI_ENABLE_LOCAL_TRANSLATION", "").strip().lower()
        not in {"1", "true", "yes", "on"}
    ):
        return {
            "language": language,
            "translations": {
                text: text
                for text in unique_texts
            },
            "translated_count": 0,
            "requested_count": len(unique_texts),
            "provider": "frontend-local",
            "model": None,
            "note": (
                "Vercel deployment uses the reviewed frontend translation "
                "dictionary. Local NLLB inference remains enabled for local development."
            ),
        }

    try:
        translations = _translate_local_batch(
            unique_texts,
            language,
        )
    except Exception as exc:
        # Never break emergency functionality because translation failed.
        print(
            "[Disaster AI India] Local translation unavailable: "
            f"{exc}"
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Local translation model is not ready. "
                "Run setup_local_translation.ps1 and restart the backend."
            ),
        ) from exc

    # Preserve untranslated items as English. The frontend already has its
    # reviewed local dictionary and will use it for critical/common labels.
    response_translations = {
        text: translations.get(text, text)
        for text in unique_texts
    }

    translated_count = sum(
        1
        for source, translated in response_translations.items()
        if translated.strip() != source.strip()
    )

    return {
        "language": language,
        "translations": response_translations,
        "translated_count": translated_count,
        "requested_count": len(unique_texts),
        "provider": "local",
        "model": LOCAL_TRANSLATION_MODEL,
    }


# ============================================================
# BACKGROUND TRANSLATION MODEL WARM-UP
# ============================================================

_TRANSLATION_WARMUP_STARTED = False
_TRANSLATION_WARMUP_READY = False
_TRANSLATION_WARMUP_ERROR = None


def _translation_warmup_worker():
    global _TRANSLATION_WARMUP_READY
    global _TRANSLATION_WARMUP_ERROR

    try:
        print(
            "[Disaster AI India] Starting background translation-model warm-up..."
        )
        _load_local_translation_model()
        _TRANSLATION_WARMUP_READY = True
        print(
            "[Disaster AI India] Background translation-model warm-up complete."
        )
    except Exception as exc:
        _TRANSLATION_WARMUP_ERROR = str(exc)
        print(
            "[Disaster AI India] Background translation warm-up failed; "
            "the model will load on the first translation request: "
            f"{exc}"
        )


@app.on_event("startup")
def _start_translation_warmup():
    """Load NLLB in the background so the first translated page is not blocked."""
    global _TRANSLATION_WARMUP_STARTED

    if _TRANSLATION_WARMUP_STARTED:
        return

    if (
        IS_VERCEL
        and os.getenv("DISASTER_AI_ENABLE_LOCAL_TRANSLATION", "").strip().lower()
        not in {"1", "true", "yes", "on"}
    ):
        _TRANSLATION_WARMUP_STARTED = True
        _TRANSLATION_WARMUP_ERROR = (
            "Local NLLB translation disabled for Vercel deployment."
        )
        return

    _TRANSLATION_WARMUP_STARTED = True
    thread = threading.Thread(
        target=_translation_warmup_worker,
        name="disaster-ai-translation-warmup",
        daemon=True,
    )
    thread.start()

# ============================================================
# CITIZEN SAFETY & PUBLIC ACCESS
# ============================================================

CITIZEN_SAFETY_GUIDANCE = {
    "Flood": [
        "Avoid walking or driving through floodwater.",
        "Move toward higher ground if water levels are rising or authorities advise evacuation.",
        "Keep drinking water, medicines, identification and a charged phone ready.",
    ],
    "Cyclone": [
        "Stay indoors away from windows during severe wind conditions.",
        "Secure loose outdoor objects and keep emergency supplies ready.",
        "Follow IMD, NDMA and local-authority evacuation instructions.",
    ],
    "Earthquake": [
        "During shaking: Drop, Cover and Hold On away from windows.",
        "After shaking stops, move carefully and avoid visibly damaged structures.",
        "Expect aftershocks and follow local emergency-authority instructions.",
    ],
    "Wildfire": [
        "Move away from smoke and fire-affected areas when authorities advise.",
        "Keep doors and windows closed if smoke is present nearby.",
        "Do not enter restricted fire-response zones or blocked roads.",
    ],
    "Landslide": [
        "Avoid steep slopes, damaged roads and areas with falling debris.",
        "Move away from channels or slopes showing fresh cracks or movement.",
        "Follow local evacuation and road-closure instructions.",
    ],
}


def _nearest_disaster_records(latitude: float, longitude: float, limit: int = 8):
    validate_india_coordinate(latitude, longitude, "User location")

    lat_values = pd.to_numeric(df["latitude"], errors="coerce").to_numpy(dtype=float)
    lon_values = pd.to_numeric(df["longitude"], errors="coerce").to_numpy(dtype=float)

    valid = get_india_dataset_mask()

    valid_indices = np.flatnonzero(valid)
    if len(valid_indices) == 0:
        return []

    lat1 = np.radians(float(latitude))
    lon1 = np.radians(float(longitude))
    lat2 = np.radians(lat_values[valid_indices])
    lon2 = np.radians(lon_values[valid_indices])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    distances = 6371.0 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))

    count = min(max(int(limit), 1), len(valid_indices))
    if count == len(valid_indices):
        local_positions = np.argsort(distances)
    else:
        local_positions = np.argpartition(distances, count - 1)[:count]
        local_positions = local_positions[np.argsort(distances[local_positions])]

    results = []
    for pos in local_positions:
        row_id = int(valid_indices[pos])
        row = df.iloc[row_id]
        severity = max(0.0, min(safe_float(row, "severity_score"), 1.0))
        results.append(
            {
                "row_id": row_id,
                "disaster_type": get_disaster_type(row),
                "disaster_subtype": str(row.get("disaster_subtype", "")).strip(),
                "distance_km": round(float(distances[pos]), 2),
                "latitude": round(safe_float(row, "latitude"), 5),
                "longitude": round(safe_float(row, "longitude"), 5),
                "severity_score": round(severity, 4),
                "affected_population": max(int(round(safe_float(row, "affected_population"))), 0),
                "dris_score": round(safe_float(row, "dris_score"), 2),
                "road_blockage_probability": round(safe_float(row, "road_blockage_probability"), 4),
                "logistics_accessibility_score": round(safe_float(row, "logistics_accessibility_score"), 4),
                "date": str(row.get("date", "")) if not pd.isna(row.get("date", "")) else "",
            }
        )

    return results


def _citizen_risk_level(severity: float, distance_km: float):
    # A transparent prototype decision-support score. It is not an official alert.
    proximity = max(0.0, 1.0 - min(max(distance_km, 0.0), 300.0) / 300.0)
    score = severity * 65.0 + proximity * 35.0

    if distance_km > 300:
        level = "LOW"
    elif score >= 75:
        level = "CRITICAL"
    elif score >= 55:
        level = "HIGH"
    elif score >= 35:
        level = "MODERATE"
    else:
        level = "LOW"

    return round(score, 1), level


@app.get(
    "/public/india-boundary",
    tags=["Citizen Safety & Public Access"],
    summary="Return the India boundary used by the prototype map filters",
)
def public_india_boundary():
    try:
        return json.loads(INDIA_BOUNDARY_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"India boundary data is unavailable: {exc}",
        ) from exc


@app.get(
    "/public/geocode",
    tags=["Citizen Safety & Public Access"],
    summary="Search any city, town or locality in India",
)
def public_geocode(
    q: str = Query(..., min_length=2, max_length=120),
    limit: int = Query(8, ge=1, le=12),
):
    """Use OpenStreetMap Nominatim to resolve arbitrary Indian place names."""
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": q,
                "format": "jsonv2",
                "addressdetails": 1,
                "countrycodes": "in",
                "limit": limit,
                "accept-language": "en",
            },
            headers={
                **HTTP_HEADERS,
                "User-Agent": "DisasterAI-India-Academic-Prototype/1.0 citizen-geocoder",
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"India place search is temporarily unavailable: {exc}",
        ) from exc

    results = []
    for item in payload:
        try:
            latitude = float(item.get("lat"))
            longitude = float(item.get("lon"))
        except (TypeError, ValueError):
            continue

        address = item.get("address") or {}
        if str(address.get("country_code", "")).lower() != "in":
            continue

        # Nominatim is country-restricted; the broad numeric bounds prevent
        # accidental malformed coordinates without excluding legitimate
        # border/island localities returned as India by the geocoder.
        if not (
            INDIA_BOUNDS["south"] <= latitude <= INDIA_BOUNDS["north"]
            and INDIA_BOUNDS["west"] <= longitude <= INDIA_BOUNDS["east"]
        ):
            continue

        city_name = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("municipality")
            or address.get("county")
            or q
        )
        state_name = address.get("state") or address.get("state_district") or "India"
        label = item.get("display_name") or f"{city_name}, {state_name}"

        results.append(
            {
                "label": label,
                "city": city_name,
                "state": state_name,
                "latitude": round(latitude, 6),
                "longitude": round(longitude, 6),
            }
        )

    return {
        "country": "India",
        "query": q,
        "returned": len(results),
        "results": results,
    }


@app.get(
    "/public/nearby-disasters",
    tags=["Citizen Safety & Public Access"],
    summary="Find disaster records nearest to a citizen location in India",
)
def public_nearby_disasters(
    latitude: float = Query(..., ge=INDIA_BOUNDS["south"], le=INDIA_BOUNDS["north"]),
    longitude: float = Query(..., ge=INDIA_BOUNDS["west"], le=INDIA_BOUNDS["east"]),
    limit: int = Query(8, ge=1, le=20),
):
    records = _nearest_disaster_records(latitude, longitude, limit=limit)
    return {
        "operating_country": "India",
        "user_location": {"latitude": latitude, "longitude": longitude},
        "nearby_disasters": records,
        "disclaimer": (
            "Dataset-based academic prototype. This is not an official emergency alert. "
            "Follow NDMA, IMD, state authorities and local emergency instructions."
        ),
    }


@app.get(
    "/public/relief-centers",
    tags=["Citizen Safety & Public Access"],
    summary="Find nearby prototype relief resource centers in India",
)
def public_relief_centers(
    latitude: float = Query(..., ge=INDIA_BOUNDS["south"], le=INDIA_BOUNDS["north"]),
    longitude: float = Query(..., ge=INDIA_BOUNDS["west"], le=INDIA_BOUNDS["east"]),
    limit: int = Query(4, ge=1, le=10),
):
    depots = nearest_resource_depots(latitude, longitude, limit=limit)
    return {
        "user_location": {"latitude": latitude, "longitude": longitude},
        "relief_centers": depots,
        "note": (
            "These are project-defined prototype relief depots for academic demonstration, "
            "not verified government warehouse or public shelter locations."
        ),
    }


@app.get(
    "/public/safety-assessment",
    tags=["Citizen Safety & Public Access"],
    summary="Generate location-based citizen disaster decision support",
)
def public_safety_assessment(
    latitude: float = Query(..., ge=INDIA_BOUNDS["south"], le=INDIA_BOUNDS["north"]),
    longitude: float = Query(..., ge=INDIA_BOUNDS["west"], le=INDIA_BOUNDS["east"]),
):
    nearby = _nearest_disaster_records(latitude, longitude, limit=6)
    depots = nearest_resource_depots(latitude, longitude, limit=3)

    if not nearby:
        return {
            "user_location": {"latitude": latitude, "longitude": longitude},
            "risk_level": "UNKNOWN",
            "risk_score": None,
            "nearest_disaster": None,
            "nearby_disasters": [],
            "nearest_relief_center": depots[0] if depots else None,
            "safety_actions": ["Monitor official NDMA, IMD and local-authority alerts."],
            "disclaimer": "No usable nearby records were found in the prototype dataset.",
        }

    nearest = nearby[0]
    risk_score, risk_level = _citizen_risk_level(
        nearest["severity_score"],
        nearest["distance_km"],
    )

    prediction = predict_resources(nearest["row_id"])
    source_plan = build_resource_source_plan(
        safe_float(df.iloc[nearest["row_id"]], "latitude"),
        safe_float(df.iloc[nearest["row_id"]], "longitude"),
        prediction,
        max_depots=3,
    )

    if risk_level in {"CRITICAL", "HIGH"}:
        decision = (
            "Be ready to act quickly. Follow official local alerts and evacuation "
            "instructions if issued."
        )
    elif risk_level == "MODERATE":
        decision = (
            "Stay alert, keep emergency essentials ready and monitor official updates."
        )
    else:
        decision = (
            "No high prototype risk is indicated at this location, but continue to "
            "monitor official alerts because conditions can change."
        )

    return {
        "feature": "Citizen Location Safety Assessment",
        "operating_country": "India",
        "user_location": {"latitude": latitude, "longitude": longitude},
        "risk_score": risk_score,
        "risk_level": risk_level,
        "decision_summary": decision,
        "nearest_disaster": nearest,
        "nearby_disasters": nearby,
        "safety_actions": CITIZEN_SAFETY_GUIDANCE.get(
            nearest["disaster_type"],
            ["Follow official emergency-management instructions for your area."],
        ),
        "nearest_relief_center": depots[0] if depots else None,
        "nearby_relief_centers": depots,
        "area_relief_snapshot": {
            "predicted_area_demand": prediction,
            "planned_from_nearby_depots": source_plan["planned_allocation"],
            "unmet_demand": source_plan["unmet_demand"],
            "primary_source_depot": source_plan["primary_depot"],
        },
        "disclaimer": (
            "Academic decision-support prototype based on the project dataset and prototype "
            "relief depots. It is not a live government warning, evacuation order or public "
            "shelter directory. Follow NDMA, IMD, state and local-authority instructions."
        ),
    }


# ============================================================
# DISASTER ALERT API
# ============================================================

@app.get(
    "/alerts",
    tags=["Disaster Alerts & Notifications"],
    summary="List the current user's location-aware disaster alerts",
)
def list_disaster_alerts(
    unread_only: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
):
    user_id = _current_user_id()

    # Normal requests refresh at most once per ALERT_REFRESH_SECONDS.
    refresh_result = _refresh_disaster_alerts(force=False)

    alerts = [
        alert
        for alert in _load_stored_alerts()
        if str(alert.get("user_id")) == str(user_id)
    ]

    if unread_only:
        alerts = [
            alert
            for alert in alerts
            if not bool(alert.get("read"))
        ]

    alerts.sort(
        key=lambda item: str(item.get("created_at") or ""),
        reverse=True,
    )

    return {
        "alerts": alerts[:limit],
        "unread_count": sum(
            1
            for alert in alerts
            if not bool(alert.get("read"))
        ),
        "refresh": refresh_result,
        "configuration": {
            "radius_km": ALERT_RADIUS_KM,
            "minimum_severity": ALERT_MIN_SEVERITY,
            "refresh_seconds": ALERT_REFRESH_SECONDS,
        },
        "disclaimer": (
            "Prototype in-app notifications based on public live feeds and "
            "saved user preferences. They are not official government warnings."
        ),
    }


@app.get(
    "/alerts/unread-count",
    tags=["Disaster Alerts & Notifications"],
    summary="Return the current user's unread disaster-alert count",
)
def disaster_alert_unread_count():
    user_id = _current_user_id()
    refresh_result = _refresh_disaster_alerts(force=False)

    alerts = _load_stored_alerts()
    unread_count = sum(
        1
        for alert in alerts
        if str(alert.get("user_id")) == str(user_id)
        and not bool(alert.get("read"))
    )

    return {
        "unread_count": unread_count,
        "refresh": refresh_result,
    }


@app.post(
    "/alerts/check",
    tags=["Disaster Alerts & Notifications"],
    summary="Force a live disaster-alert feed check",
)
def check_disaster_alerts():
    _current_user_id()
    result = _refresh_disaster_alerts(force=True)
    return {
        "message": "Disaster alert engine checked the configured live feeds.",
        "refresh": result,
        "disclaimer": (
            "This prototype check does not replace official emergency "
            "warnings or instructions."
        ),
    }


@app.post(
    "/alerts/{alert_id}/read",
    tags=["Disaster Alerts & Notifications"],
    summary="Mark one disaster alert as read",
)
def mark_disaster_alert_read(alert_id: str):
    user_id = _current_user_id()
    alerts = _load_stored_alerts()

    found = False
    for alert in alerts:
        if (
            str(alert.get("alert_id")) == str(alert_id)
            and str(alert.get("user_id")) == str(user_id)
        ):
            alert["read"] = True
            alert["read_at"] = _utc_now()
            found = True
            break

    if not found:
        raise HTTPException(
            status_code=404,
            detail="Disaster alert not found",
        )

    _save_stored_alerts(alerts)
    return {
        "message": "Disaster alert marked as read.",
        "alert_id": alert_id,
    }


@app.post(
    "/alerts/read-all",
    tags=["Disaster Alerts & Notifications"],
    summary="Mark all current user's disaster alerts as read",
)
def mark_all_disaster_alerts_read():
    user_id = _current_user_id()
    alerts = _load_stored_alerts()
    changed = 0
    read_at = _utc_now()

    for alert in alerts:
        if (
            str(alert.get("user_id")) == str(user_id)
            and not bool(alert.get("read"))
        ):
            alert["read"] = True
            alert["read_at"] = read_at
            changed += 1

    if changed:
        _save_stored_alerts(alerts)

    return {
        "message": "Disaster alerts marked as read.",
        "updated": changed,
    }

