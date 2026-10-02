from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # Optional locally; required only when DATABASE_URL is configured.
    psycopg = None
    dict_row = None
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "data" / "operations_state"
DB_PATH = STATE_DIR / "disaster_ai.db"
SECRET_PATH = STATE_DIR / ".jwt_secret"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USE_POSTGRES = bool(DATABASE_URL)

if not USE_POSTGRES and not os.getenv("VERCEL"):
    STATE_DIR.mkdir(parents=True, exist_ok=True)

if USE_POSTGRES and psycopg is None:
    raise RuntimeError(
        "DATABASE_URL is configured, but psycopg is not installed. "
        'Add "psycopg[binary]" to requirements.txt.'
    )

CURRENT_USER: ContextVar[dict | None] = ContextVar("current_user", default=None)

ALLOWED_ROLES = {"ADMIN", "RELIEF_COORDINATOR", "FIELD_TEAM", "CITIZEN"}
PUBLIC_REQUEST_ROLES = {"CITIZEN", "RELIEF_COORDINATOR", "FIELD_TEAM"}
ACCOUNT_STATUSES = {"PENDING", "APPROVED", "REJECTED"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class _ConnectionProxy:
    """Small compatibility layer so the existing SQLite code can use Postgres."""

    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql, params=None):
        sql = _adapt_sql(sql)
        return self._connection.execute(sql, params or ())

    def executescript(self, script):
        if not USE_POSTGRES:
            return self._connection.executescript(script)

        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                self._connection.execute(_adapt_sql(statement))
        return self

    def __enter__(self):
        self._connection.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self._connection.__exit__(exc_type, exc_value, traceback)

    def __getattr__(self, name):
        return getattr(self._connection, name)


def _adapt_sql(sql: str) -> str:
    return sql.replace("?", "%s") if USE_POSTGRES else sql


def _connect():
    if USE_POSTGRES:
        return _ConnectionProxy(
            psycopg.connect(
                DATABASE_URL,
                row_factory=dict_row,
                connect_timeout=10,
            )
        )

    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return _ConnectionProxy(connection)


def _load_secret() -> bytes:
    env_secret = os.getenv("DISASTER_AI_SECRET_KEY")
    if env_secret:
        return env_secret.encode("utf-8")

    if USE_POSTGRES or os.getenv("VERCEL"):
        raise RuntimeError(
            "DISASTER_AI_SECRET_KEY must be configured when the backend "
            "runs on Vercel/Postgres."
        )

    if not SECRET_PATH.exists():
        SECRET_PATH.write_text(secrets.token_urlsafe(64), encoding="utf-8")

    return SECRET_PATH.read_text(encoding="utf-8").strip().encode("utf-8")


JWT_SECRET = _load_secret()
JWT_TTL_SECONDS = int(os.getenv("DISASTER_AI_TOKEN_HOURS", "8")) * 3600


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters")
    salt = secrets.token_bytes(16)
    iterations = 260_000
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return f"pbkdf2_sha256${iterations}${_b64url(salt)}${_b64url(derived)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        salt = _b64url_decode(salt_text)
        expected = _b64url_decode(digest_text)
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _ensure_column(conn, table: str, column: str, definition: str) -> None:
    if USE_POSTGRES:
        columns = {
            row["column_name"]
            for row in conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name=? 
                """,
                (table,),
            ).fetchall()
        }
    else:
        columns = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }

    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _public_user(row: sqlite3.Row | dict) -> dict:
    return {
        "user_id": int(row["user_id"]),
        "name": row["name"],
        "email": row["email"],
        "role": row["role"],
        "requested_role": row["requested_role"] or row["role"],
        "is_active": bool(row["is_active"]),
        "account_status": row["account_status"] or "APPROVED",
        "auth_provider": row["auth_provider"] or "PASSWORD",
        "email_verified": bool(row["email_verified"]),
        "phone": row["phone"] or "",
        "organization": row["organization"] or "",
        "state": row["state"] or "",
        "district": row["district"] or "",
        "region": row["region"],
        "created_at": row["created_at"],
        "last_login_at": row["last_login_at"],
        "reset_requested_at": row["reset_requested_at"],
    }


def init_database() -> None:
    if USE_POSTGRES:
        schema = """
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGSERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            region TEXT NOT NULL DEFAULT 'India',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_login_at TEXT
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            audit_id BIGSERIAL PRIMARY KEY,
            timestamp TEXT NOT NULL,
            user_id BIGINT,
            email TEXT,
            role TEXT,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            details_json TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS app_state (
            state_key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    else:
        schema = """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            region TEXT NOT NULL DEFAULT 'India',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_login_at TEXT
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            user_id INTEGER,
            email TEXT,
            role TEXT,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            details_json TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS app_state (
            state_key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """

    with _connect() as conn:
        conn.executescript(schema)

        # Safe schema migration for users created by the previous real-app build.
        _ensure_column(conn, "users", "requested_role", "TEXT")
        _ensure_column(conn, "users", "account_status", "TEXT NOT NULL DEFAULT 'APPROVED'")
        _ensure_column(conn, "users", "auth_provider", "TEXT NOT NULL DEFAULT 'PASSWORD'")
        _ensure_column(conn, "users", "email_verified", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "users", "phone", "TEXT")
        _ensure_column(conn, "users", "organization", "TEXT")
        _ensure_column(conn, "users", "state", "TEXT")
        _ensure_column(conn, "users", "district", "TEXT")
        _ensure_column(conn, "users", "reset_requested_at", "TEXT")

        conn.execute(
            """
            UPDATE users
            SET requested_role = COALESCE(requested_role, role),
                account_status = COALESCE(account_status, 'APPROVED'),
                auth_provider = COALESCE(auth_provider, 'PASSWORD')
            """
        )

        count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        if count == 0:
            now = utc_now()
            seed_users = [
                (
                    "System Administrator",
                    "admin@disasterai.in",
                    os.getenv("DISASTER_AI_ADMIN_PASSWORD", "").strip(),
                    "ADMIN",
                    "National Command Center",
                    "DISASTER_AI_ADMIN_PASSWORD",
                ),
                (
                    "Relief Coordinator",
                    "coordinator@disasterai.in",
                    os.getenv("DISASTER_AI_COORDINATOR_PASSWORD", "").strip(),
                    "RELIEF_COORDINATOR",
                    "Eastern India Operations",
                    "DISASTER_AI_COORDINATOR_PASSWORD",
                ),
                (
                    "Field Team User",
                    "field@disasterai.in",
                    os.getenv("DISASTER_AI_FIELD_PASSWORD", "").strip(),
                    "FIELD_TEAM",
                    "Field Operations",
                    "DISASTER_AI_FIELD_PASSWORD",
                ),
            ]

            missing_bootstrap_passwords = [
                env_name
                for *_, password, env_name in seed_users
                if not password
            ]
            if missing_bootstrap_passwords:
                raise RuntimeError(
                    "The application database is empty. Set the bootstrap "
                    "password environment variables before starting the backend: "
                    + ", ".join(missing_bootstrap_passwords)
                )

            for name, email, password, role, region, _env_name in seed_users:
                conn.execute(
                    """
                    INSERT INTO users
                    (
                        name,email,password_hash,role,is_active,region,
                        created_at,updated_at,requested_role,account_status,
                        auth_provider,email_verified
                    )
                    VALUES (?,?,?,?,1,?,?,?,?, 'APPROVED','PASSWORD',1)
                RETURNING user_id
                    """,
                    (
                        name,
                        email,
                        hash_password(password),
                        role,
                        region,
                        now,
                        now,
                        role,
                    ),
                )


init_database()


def create_access_token(user: dict) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user["user_id"]),
        "email": user["email"],
        "role": user["role"],
        "iat": now,
        "exp": now + JWT_TTL_SECONDS,
        "jti": secrets.token_hex(8),
    }
    header_part = _b64url(
        json.dumps(header, separators=(",", ":")).encode("utf-8")
    )
    payload_part = _b64url(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signing_input = f"{header_part}.{payload_part}".encode("ascii")
    signature = hmac.new(
        JWT_SECRET,
        signing_input,
        hashlib.sha256,
    ).digest()
    return f"{header_part}.{payload_part}.{_b64url(signature)}"


def decode_access_token(token: str) -> dict:
    try:
        header_part, payload_part, signature_part = token.split(".")
        signing_input = f"{header_part}.{payload_part}".encode("ascii")
        expected = hmac.new(
            JWT_SECRET,
            signing_input,
            hashlib.sha256,
        ).digest()
        received = _b64url_decode(signature_part)
        if not hmac.compare_digest(expected, received):
            raise ValueError("Invalid token signature")
        payload = json.loads(
            _b64url_decode(payload_part).decode("utf-8")
        )
        if int(payload.get("exp", 0)) <= int(time.time()):
            raise ValueError("Token expired")
        return payload
    except Exception as exc:
        raise ValueError("Invalid or expired access token") from exc


def get_user_by_id(user_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE user_id=?",
            (int(user_id),),
        ).fetchone()
        return _public_user(row) if row else None


def get_user_record_by_email(email: str) -> sqlite3.Row | None:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE " + ("LOWER(email)=LOWER(?)" if USE_POSTGRES else "email=? COLLATE NOCASE"),
            (email.strip(),),
        ).fetchone()


def get_public_user_by_email(email: str) -> dict | None:
    row = get_user_record_by_email(email)
    return _public_user(row) if row else None


def _mark_login(user_id: int) -> dict:
    now = utc_now()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE users
            SET last_login_at=?, updated_at=?, reset_requested_at=NULL
            WHERE user_id=?
            """,
            (now, now, int(user_id)),
        )
    user = get_user_by_id(user_id)
    audit(
        "LOGIN_SUCCESS",
        "user",
        str(user_id),
        {"email": user["email"] if user else ""},
        user_override=user,
    )
    return user


def authenticate_user_detailed(email: str, password: str) -> tuple[dict | None, str | None]:
    row = get_user_record_by_email(email)

    # Keep invalid-account and invalid-password behavior indistinguishable.
    if not row or not verify_password(password, row["password_hash"]):
        return None, "INVALID_CREDENTIALS"

    status = (row["account_status"] or "APPROVED").upper()
    if status == "PENDING":
        return None, "PENDING_APPROVAL"
    if status == "REJECTED":
        return None, "ACCOUNT_REJECTED"
    if not bool(row["is_active"]):
        return None, "ACCOUNT_DISABLED"

    return _mark_login(int(row["user_id"])), None


def authenticate_google_user(email: str) -> tuple[dict | None, str | None]:
    row = get_user_record_by_email(email)
    if not row:
        return None, "NOT_REGISTERED"

    status = (row["account_status"] or "APPROVED").upper()
    if status == "PENDING":
        return None, "PENDING_APPROVAL"
    if status == "REJECTED":
        return None, "ACCOUNT_REJECTED"
    if not bool(row["is_active"]):
        return None, "ACCOUNT_DISABLED"

    return _mark_login(int(row["user_id"])), None


def list_users() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM users
            ORDER BY
              CASE account_status
                WHEN 'PENDING' THEN 0
                WHEN 'APPROVED' THEN 1
                WHEN 'REJECTED' THEN 2
                ELSE 3
              END,
              role,
              name
            """
        ).fetchall()
        return [_public_user(row) for row in rows]


def list_field_teams() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM users
            WHERE role='FIELD_TEAM'
              AND is_active=1
              AND account_status='APPROVED'
            ORDER BY name
            """
        ).fetchall()
        return [_public_user(row) for row in rows]


def create_user(
    name: str,
    email: str,
    password: str,
    role: str,
    region: str = "India",
) -> dict:
    """Admin-created trusted account."""
    role = role.strip().upper()
    if role not in ALLOWED_ROLES:
        raise ValueError("Invalid role")
    now = utc_now()
    try:
        with _connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users
                (
                    name,email,password_hash,role,is_active,region,
                    created_at,updated_at,requested_role,account_status,
                    auth_provider,email_verified
                )
                VALUES (?,?,?,?,1,?,?,?,?, 'APPROVED','PASSWORD',1)
                RETURNING user_id
                """,
                (
                    name.strip(),
                    email.strip().lower(),
                    hash_password(password),
                    role,
                    region.strip() or "India",
                    now,
                    now,
                    role,
                ),
            )
            user_id = int(cursor.fetchone()["user_id"])
    except Exception as exc:
        if USE_POSTGRES and psycopg is not None and isinstance(exc, psycopg.errors.UniqueViolation):
            raise ValueError("A user with that email already exists") from exc
        if not USE_POSTGRES and isinstance(exc, sqlite3.IntegrityError):
            raise ValueError("A user with that email already exists") from exc
        raise

    user = get_user_by_id(user_id)
    audit(
        "USER_CREATED",
        "user",
        str(user_id),
        {"email": email, "role": role, "source": "ADMIN"},
    )
    return user


def register_user(
    *,
    name: str,
    email: str,
    password: str,
    requested_role: str,
    phone: str = "",
    organization: str = "",
    state: str = "",
    district: str = "",
) -> dict:
    requested_role = requested_role.strip().upper()
    if requested_role not in PUBLIC_REQUEST_ROLES:
        raise ValueError(
            "Choose Citizen, Relief Coordinator or Field Team access"
        )

    # Citizens are ordinary public users and can use the application
    # immediately. Operational staff roles require administrator approval.
    is_citizen = requested_role == "CITIZEN"
    active = 1 if is_citizen else 0
    account_status = "APPROVED" if is_citizen else "PENDING"

    now = utc_now()
    try:
        with _connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users
                (
                    name,email,password_hash,role,is_active,region,
                    created_at,updated_at,requested_role,account_status,
                    auth_provider,email_verified,phone,organization,state,district
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                RETURNING user_id
                """,
                (
                    name.strip(),
                    email.strip().lower(),
                    hash_password(password),
                    requested_role,
                    active,
                    "India",
                    now,
                    now,
                    requested_role,
                    account_status,
                    "PASSWORD",
                    0,
                    phone.strip(),
                    organization.strip(),
                    state.strip(),
                    district.strip(),
                ),
            )
            user_id = int(cursor.fetchone()["user_id"])
    except sqlite3.IntegrityError as exc:
        raise ValueError("An account with that email already exists") from exc

    user = get_user_by_id(user_id)
    audit(
        "CITIZEN_ACCOUNT_CREATED" if is_citizen else "STAFF_ACCESS_REQUESTED",
        "user",
        str(user_id),
        {
            "email": email,
            "requested_role": requested_role,
            "provider": "PASSWORD",
            "account_status": account_status,
        },
        user_override=user,
    )
    return user


def register_google_user(
    *,
    name: str,
    email: str,
    requested_role: str,
    phone: str = "",
    organization: str = "",
    state: str = "",
    district: str = "",
) -> dict:
    requested_role = requested_role.strip().upper()
    if requested_role not in PUBLIC_REQUEST_ROLES:
        raise ValueError(
            "Choose Citizen, Relief Coordinator or Field Team access"
        )

    existing = get_public_user_by_email(email)
    if existing:
        return existing

    is_citizen = requested_role == "CITIZEN"
    active = 1 if is_citizen else 0
    account_status = "APPROVED" if is_citizen else "PENDING"

    # Google users authenticate using their verified Google identity.
    random_password = secrets.token_urlsafe(32)
    now = utc_now()
    try:
        with _connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users
                (
                    name,email,password_hash,role,is_active,region,
                    created_at,updated_at,requested_role,account_status,
                    auth_provider,email_verified,phone,organization,state,district
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                RETURNING user_id
                """,
                (
                    name.strip(),
                    email.strip().lower(),
                    hash_password(random_password),
                    requested_role,
                    active,
                    "India",
                    now,
                    now,
                    requested_role,
                    account_status,
                    "GOOGLE",
                    1,
                    phone.strip(),
                    organization.strip(),
                    state.strip(),
                    district.strip(),
                ),
            )
            user_id = int(cursor.fetchone()["user_id"])
    except sqlite3.IntegrityError as exc:
        raise ValueError("An account with that email already exists") from exc

    user = get_user_by_id(user_id)
    audit(
        "GOOGLE_CITIZEN_CREATED" if is_citizen else "GOOGLE_STAFF_ACCESS_REQUESTED",
        "user",
        str(user_id),
        {
            "email": email,
            "requested_role": requested_role,
            "provider": "GOOGLE",
            "account_status": account_status,
        },
        user_override=user,
    )
    return user


def update_user(
    user_id: int,
    *,
    name: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    region: str | None = None,
    account_status: str | None = None,
) -> dict:
    current = get_user_by_id(user_id)
    if not current:
        raise ValueError("User not found")

    fields = []
    values: list[Any] = []

    if name is not None:
        fields.append("name=?")
        values.append(name.strip())

    if role is not None:
        role = role.strip().upper()
        if role not in ALLOWED_ROLES:
            raise ValueError("Invalid role")
        fields.append("role=?")
        values.append(role)

    if region is not None:
        fields.append("region=?")
        values.append(region.strip() or "India")

    if account_status is not None:
        account_status = account_status.strip().upper()
        if account_status not in ACCOUNT_STATUSES:
            raise ValueError("Invalid account status")
        fields.append("account_status=?")
        values.append(account_status)

        # Approval activates the account. Pending/rejected accounts cannot login.
        fields.append("is_active=?")
        values.append(1 if account_status == "APPROVED" else 0)
    elif is_active is not None:
        fields.append("is_active=?")
        values.append(1 if is_active else 0)

    if fields:
        fields.append("updated_at=?")
        values.append(utc_now())
        values.append(int(user_id))
        with _connect() as conn:
            conn.execute(
                f"UPDATE users SET {', '.join(fields)} WHERE user_id=?",
                values,
            )

    user = get_user_by_id(user_id)
    audit(
        "USER_UPDATED",
        "user",
        str(user_id),
        {
            "changes": {
                "name": name,
                "role": role,
                "is_active": is_active,
                "region": region,
                "account_status": account_status,
            }
        },
    )
    return user


def set_user_password(user_id: int, new_password: str) -> None:
    if not get_user_by_id(user_id):
        raise ValueError("User not found")
    with _connect() as conn:
        conn.execute(
            """
            UPDATE users
            SET password_hash=?, updated_at=?, reset_requested_at=NULL,
                auth_provider=CASE
                    WHEN auth_provider='GOOGLE' THEN 'GOOGLE+PASSWORD'
                    ELSE auth_provider
                END
            WHERE user_id=?
            """,
            (
                hash_password(new_password),
                utc_now(),
                int(user_id),
            ),
        )
    audit("PASSWORD_RESET", "user", str(user_id), {})


def change_own_password(
    user_id: int,
    current_password: str,
    new_password: str,
) -> None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE user_id=?",
            (int(user_id),),
        ).fetchone()
        if not row or not verify_password(
            current_password,
            row["password_hash"],
        ):
            raise ValueError("Current password is incorrect")
        conn.execute(
            """
            UPDATE users
            SET password_hash=?, updated_at=?, reset_requested_at=NULL
            WHERE user_id=?
            """,
            (
                hash_password(new_password),
                utc_now(),
                int(user_id),
            ),
        )
    audit("PASSWORD_CHANGED", "user", str(user_id), {})


def request_password_reset(email: str) -> None:
    row = get_user_record_by_email(email)
    if not row:
        # Deliberately do nothing to avoid revealing whether an email exists.
        return
    with _connect() as conn:
        conn.execute(
            """
            UPDATE users
            SET reset_requested_at=?, updated_at=?
            WHERE user_id=?
            """,
            (utc_now(), utc_now(), int(row["user_id"])),
        )
    user = get_user_by_id(int(row["user_id"]))
    audit(
        "PASSWORD_RESET_REQUESTED",
        "user",
        str(row["user_id"]),
        {"email": row["email"]},
        user_override=user,
    )


def audit(
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    details: dict | None = None,
    user_override: dict | None = None,
) -> None:
    user = user_override or CURRENT_USER.get()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO audit_logs
            (
                timestamp,user_id,email,role,action,
                entity_type,entity_id,details_json
            )
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                utc_now(),
                user.get("user_id") if user else None,
                user.get("email") if user else None,
                user.get("role") if user else None,
                action,
                entity_type,
                entity_id,
                json.dumps(details or {}, separators=(",", ":")),
            ),
        )


def list_audit_logs(limit: int = 100) -> list[dict]:
    limit = max(1, min(int(limit), 500))
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM audit_logs
            ORDER BY audit_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            try:
                item["details"] = json.loads(
                    item.pop("details_json") or "{}"
                )
            except Exception:
                item["details"] = {}
            results.append(item)
        return results


def load_app_state(key: str) -> Any | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT value_json FROM app_state WHERE state_key=?",
            (key,),
        ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["value_json"])
        except Exception:
            return None


def save_app_state(key: str, value: Any) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO app_state(state_key,value_json,updated_at)
            VALUES (?,?,?)
            ON CONFLICT(state_key)
            DO UPDATE SET
              value_json=excluded.value_json,
              updated_at=excluded.updated_at
            """,
            (
                key,
                json.dumps(value, separators=(",", ":")),
                utc_now(),
            ),
        )
