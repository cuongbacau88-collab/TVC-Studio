
import os, sqlite3, secrets, hashlib, hmac, mimetypes, shutil, time, json, sys, logging, subprocess, uuid
import urllib.error
import urllib.request
import ipaddress
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request, Response, UploadFile, File, Form, HTTPException, Header
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

try:
    from payos import PayOS
    from payos.type import PaymentData, ItemData
except ImportError:
    PayOS = None
    PaymentData = None
    ItemData = None

from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from gpu_api_client import GPUAPIClient, GPUAPIConfig, GPUAPIError
from service_registry import SERVICES, PUBLIC_SERVICE_CONFIG, get_service, MOTION_MODELS
from service_worker_adapters import build_adapters, build_video_upscale_adapter, WorkerAdapterError
from storage_backend import build_storage

import video_upscale_pipeline
BASE = Path(__file__).resolve().parent
# Railway's container filesystem is ephemeral. Set PERSISTENT_DATA_DIR to the
# mounted volume path in production so the database and uploaded outputs survive deploys.
PERSISTENT_DATA_DIR = os.getenv("PERSISTENT_DATA_DIR", "").strip()
RAILWAY_VOLUME_PATH = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
DATA = Path(RAILWAY_VOLUME_PATH or PERSISTENT_DATA_DIR).expanduser() if (RAILWAY_VOLUME_PATH or PERSISTENT_DATA_DIR) else BASE / "data"
UPLOADS = DATA / "uploads"
OUTPUTS = DATA / "outputs"
DB_PATH = DATA / "motionhub.db"

UPLOADS.mkdir(parents=True, exist_ok=True)
OUTPUTS.mkdir(parents=True, exist_ok=True)

SESSION_DAYS = 30
VISITOR_COOKIE = "tvc_visitor_id"
VISITOR_DAYS = 180
MAX_IMAGE_MB = 25
MAX_VIDEO_MB = 300
try:
    WORKER_MAX_OUTPUT_BYTES = max(1, int(os.getenv("WORKER_MAX_OUTPUT_MB", "2048")) * 1024 * 1024)
except ValueError:
    WORKER_MAX_OUTPUT_BYTES = 2048 * 1024 * 1024
MAX_MOTION_DURATION_SECONDS = 20.0
JOB_SUBMIT_INFLIGHT_SECONDS = 600
JOB_SUBMIT_COOLDOWN_SECONDS = 8
RENDER_MODE = os.getenv("RENDER_MODE", "worker").strip().lower()
MOCK_VIDEO_DURATION = os.getenv("MOCK_VIDEO_DURATION", "10").strip() or "10"

WORKER_TOKEN = os.getenv("WORKER_TOKEN", "change-worker-token")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "cuongtv.bx92@gmail.com").lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Cuong123@")
DEFAULT_GOOGLE_CLIENT_ID = "839956952093-d9jubsvlu5sh64275j2rve1t36704v3r.apps.googleusercontent.com"
# Google OAuth Client ID is public by design. Railway env still takes priority;
# the fallback prevents the login button from disappearing if the service has
# not picked up the variable yet.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", DEFAULT_GOOGLE_CLIENT_ID).strip() or DEFAULT_GOOGLE_CLIENT_ID
TEST_MODE = os.getenv("TEST_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}
try:
    TEST_INITIAL_CREDITS = max(0, int(os.getenv("TEST_INITIAL_CREDITS", "100") or "100"))
except ValueError:
    TEST_INITIAL_CREDITS = 0
try:
    WORKER_UNAVAILABLE_TIMEOUT_SECONDS = max(
        1, int(os.getenv(
            "WORKER_UNAVAILABLE_TIMEOUT_SECONDS",
            os.getenv("JOB_QUEUE_TIMEOUT_SECONDS", "60" if TEST_MODE else "300"),
        ) or "300")
    )
except ValueError:
    WORKER_UNAVAILABLE_TIMEOUT_SECONDS = 60 if TEST_MODE else 300
try:
    WORKER_HEARTBEAT_TIMEOUT_SECONDS = max(
        1, int(os.getenv("WORKER_HEARTBEAT_TIMEOUT_SECONDS", "90") or "90")
    )
except ValueError:
    WORKER_HEARTBEAT_TIMEOUT_SECONDS = 90
try:
    JOB_RENDER_TIMEOUT_SECONDS = max(
        1, int(os.getenv("JOB_RENDER_TIMEOUT_SECONDS", "180") or "1800")
    )
except ValueError:
    JOB_RENDER_TIMEOUT_SECONDS = 180
try:
    JOB_RECONCILE_INTERVAL_SECONDS = max(
        5, int(os.getenv("JOB_RECONCILE_INTERVAL_SECONDS", "30") or "30")
    )
except ValueError:
    JOB_RECONCILE_INTERVAL_SECONDS = 30
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").strip().lower() not in {"0", "false", "no", "off"}
GPU_BACKEND_ENABLED = os.getenv("GPU_BACKEND_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
GPU_API_BASE_URL = os.getenv("GPU_API_BASE_URL", "").strip()
GPU_API_SERVICE_TOKEN = os.getenv("GPU_API_SERVICE_TOKEN", "").strip()
GPU_API_CONNECT_TIMEOUT_SECONDS = float(os.getenv("GPU_API_CONNECT_TIMEOUT_SECONDS", "5") or "5")
GPU_API_READ_TIMEOUT_SECONDS = float(os.getenv("GPU_API_READ_TIMEOUT_SECONDS", "30") or "30")
gpu_api = GPUAPIClient(GPUAPIConfig(
    GPU_BACKEND_ENABLED, GPU_API_BASE_URL, GPU_API_SERVICE_TOKEN,
    GPU_API_CONNECT_TIMEOUT_SECONDS, GPU_API_READ_TIMEOUT_SECONDS,
))
service_adapters = build_adapters()
video_upscale_adapter = build_video_upscale_adapter()
storage = build_storage(DATA)
WORKER_POLL_INTERVAL = max(1.0, float(os.getenv("WORKER_POLL_INTERVAL", "4") or "4"))

app = FastAPI(title="TVC Studio AI Business V3.3.46")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
TRUST_PROXY = os.getenv("TRUST_PROXY", "false").strip().lower() in {"1", "true", "yes", "on"}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def db():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=30000")
    con.execute("PRAGMA foreign_keys=ON")
    return con

def hash_password(password: str):
    salt = secrets.token_bytes(16)
    iterations = 220_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"

def verify_password(password: str, encoded: str):
    try:
        scheme, iterations, salt_hex, digest_hex = encoded.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        credits INTEGER NOT NULL DEFAULT 0,
        role TEXT NOT NULL DEFAULT 'user',
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sessions(
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS admin_access_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip_address TEXT NOT NULL,
        user_id INTEGER,
        method TEXT NOT NULL,
        path TEXT NOT NULL,
        status_code INTEGER NOT NULL,
        user_agent TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS security_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        event TEXT NOT NULL,
        severity TEXT NOT NULL,
        user_id INTEGER,
        email TEXT,
        role TEXT,
        ip_address TEXT NOT NULL,
        user_agent TEXT,
        method TEXT NOT NULL,
        path TEXT NOT NULL,
        http_status INTEGER,
        request_id TEXT,
        metadata TEXT
    );
    CREATE TABLE IF NOT EXISTS jobs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        model TEXT NOT NULL,
        aspect_ratio TEXT NOT NULL,
        quality TEXT NOT NULL,
        prompt TEXT,
        cost INTEGER NOT NULL,
        image_path TEXT NOT NULL,
        video_path TEXT NOT NULL,
        output_path TEXT,
        status TEXT NOT NULL DEFAULT 'waiting',
        progress INTEGER NOT NULL DEFAULT 0,
        error TEXT,
        claimed_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS worker_heartbeats(
        worker_id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        current_job_id INTEGER,
        last_heartbeat TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS job_submit_guards(
        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        job_id INTEGER,
        locked_until REAL NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS topups(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        package TEXT NOT NULL,
        amount_vnd INTEGER NOT NULL,
        credits INTEGER NOT NULL,
        note TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        reviewed_at TEXT
    );
    CREATE TABLE IF NOT EXISTS credit_ledger(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        delta INTEGER NOT NULL,
        reason TEXT NOT NULL,
        ref_type TEXT,
        ref_id INTEGER,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS admin_tools(
        service_key TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        thumbnail TEXT NOT NULL DEFAULT '',
        badge TEXT NOT NULL DEFAULT '',
        price_credits INTEGER NOT NULL DEFAULT 0,
        is_free INTEGER NOT NULL DEFAULT 0,
        cta_text TEXT NOT NULL DEFAULT 'Tạo ngay',
        enabled INTEGER NOT NULL DEFAULT 1,
        sort_order INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS affiliate_rewards(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        source_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        topup_id INTEGER NOT NULL REFERENCES topups(id) ON DELETE CASCADE,
        reward_type TEXT NOT NULL,
        amount_credits REAL NOT NULL,
        rate REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        UNIQUE(user_id, topup_id, reward_type)
    );
    CREATE TABLE IF NOT EXISTS affiliate_commissions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        source_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        topup_id INTEGER NOT NULL REFERENCES topups(id) ON DELETE CASCADE,
        commission_type TEXT NOT NULL,
        amount_vnd INTEGER NOT NULL,
        rate REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        reviewed_at TEXT,
        paid_at TEXT,
        admin_note TEXT,
        UNIQUE(user_id, topup_id, commission_type)
    );
    CREATE TABLE IF NOT EXISTS affiliate_reward_credit_ledger(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reward_id INTEGER NOT NULL UNIQUE REFERENCES affiliate_rewards(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        delta REAL NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS affiliate_withdrawals(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        amount_credits REAL NOT NULL,
        amount_vnd INTEGER NOT NULL,
        method TEXT NOT NULL,
        account TEXT NOT NULL,
        note TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        reviewed_at TEXT,
        admin_note TEXT
    );
    CREATE TABLE IF NOT EXISTS affiliate_wallet_transactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        type TEXT NOT NULL,
        affiliate_amount_vnd INTEGER NOT NULL,
        credits_received REAL NOT NULL DEFAULT 0,
        exchange_rate INTEGER NOT NULL,
        idempotency_key TEXT,
        status TEXT NOT NULL DEFAULT 'completed',
        created_at TEXT NOT NULL,
        UNIQUE(user_id, type, idempotency_key)
    );
    CREATE TABLE IF NOT EXISTS affiliate_audit_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor_user_id INTEGER,
        actor_role TEXT NOT NULL,
        target_user_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        amount_vnd INTEGER NOT NULL DEFAULT 0,
        status_before TEXT,
        status_after TEXT,
        ip_address TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS affiliate_settings(
        id INTEGER PRIMARY KEY CHECK(id=1),
        enabled INTEGER NOT NULL DEFAULT 1,
        silver_rate_percent REAL NOT NULL DEFAULT 10,
        gold_rate_percent REAL NOT NULL DEFAULT 15,
        buyer_bonus_percent REAL NOT NULL DEFAULT 10,
        gold_threshold_credits INTEGER NOT NULL DEFAULT 1000,
        parent_override_percent REAL NOT NULL DEFAULT 50,
        updated_at TEXT NOT NULL
    );
    """)
    for table in ("admin_access_logs", "security_logs"):
        columns = {row["name"] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}
        if "visitor_id" not in columns:
            con.execute(f"ALTER TABLE {table} ADD COLUMN visitor_id TEXT")
    con.execute("CREATE INDEX IF NOT EXISTS idx_security_logs_visitor_id ON security_logs(visitor_id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_admin_access_logs_visitor_id ON admin_access_logs(visitor_id)")
    con.execute("""INSERT OR IGNORE INTO affiliate_settings(
        id,enabled,silver_rate_percent,gold_rate_percent,buyer_bonus_percent,
        gold_threshold_credits,parent_override_percent,updated_at
    ) VALUES(1,1,10,15,10,1000,50,?)""", (now_iso(),))

    # Safe schema migration for databases created by older versions.
    job_cols = {r["name"] for r in con.execute("PRAGMA table_info(jobs)").fetchall()}
    if "request_key" not in job_cols:
        con.execute("ALTER TABLE jobs ADD COLUMN request_key TEXT")
    phase4b_columns = {
        "client_job_id": "TEXT", "gpu_job_id": "TEXT", "gpu_status": "TEXT",
        "gpu_error": "TEXT", "gpu_image_upload_id": "TEXT", "gpu_motion_upload_id": "TEXT",
        "credit_reserved": "INTEGER NOT NULL DEFAULT 0",
        "credit_charged": "INTEGER NOT NULL DEFAULT 0",
        "credit_refunded": "INTEGER NOT NULL DEFAULT 0",
    }
    for column, definition in phase4b_columns.items():
        if column not in job_cols:
            con.execute(f"ALTER TABLE jobs ADD COLUMN {column} {definition}")
    service_columns = {
        "service": "TEXT NOT NULL DEFAULT 'motion_studio'",
        "input_json": "TEXT", "worker_job_id": "TEXT", "worker_status": "TEXT",
        "output_media_type": "TEXT", "priority": "INTEGER NOT NULL DEFAULT 100",
        "video_upscale_job_id": "TEXT", "video_upscale_status": "TEXT",
        "video_upscale_attempted": "INTEGER NOT NULL DEFAULT 0",
        "video_upscale_error": "TEXT",
        "original_output_available": "INTEGER NOT NULL DEFAULT 0",
    }
    job_cols = {r["name"] for r in con.execute("PRAGMA table_info(jobs)").fetchall()}
    for column, definition in service_columns.items():
        if column not in job_cols:
            con.execute(f"ALTER TABLE jobs ADD COLUMN {column} {definition}")
    con.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_service_request_key
                   ON jobs(user_id,service,request_key)
                   WHERE request_key IS NOT NULL AND request_key!=''""")
    con.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_service_worker_job
                   ON jobs(service,worker_job_id)
                   WHERE worker_job_id IS NOT NULL AND worker_job_id!=''""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_jobs_priority_queue ON jobs(status,priority DESC,id)")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_user_request_key ON jobs(user_id, request_key) WHERE request_key IS NOT NULL AND request_key!=''")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_client_job_id ON jobs(client_job_id) WHERE client_job_id IS NOT NULL AND client_job_id!=''")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_gpu_job_id ON jobs(gpu_job_id) WHERE gpu_job_id IS NOT NULL AND gpu_job_id!=''")
    con.execute("CREATE INDEX IF NOT EXISTS idx_job_submit_guards_until ON job_submit_guards(locked_until)")

    cols = {r["name"] for r in con.execute("PRAGMA table_info(users)").fetchall()}
    if "is_locked" not in cols:
        con.execute("ALTER TABLE users ADD COLUMN is_locked INTEGER NOT NULL DEFAULT 0")
    if "referral_code" not in cols:
        con.execute("ALTER TABLE users ADD COLUMN referral_code TEXT")
    if "referred_by_user_id" not in cols:
        con.execute("ALTER TABLE users ADD COLUMN referred_by_user_id INTEGER")
    if "referred_at" not in cols:
        con.execute("ALTER TABLE users ADD COLUMN referred_at TEXT")
    if "google_sub" not in cols:
        con.execute("ALTER TABLE users ADD COLUMN google_sub TEXT")
    if "avatar_url" not in cols:
        con.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
    topup_cols = {r["name"] for r in con.execute("PRAGMA table_info(topups)").fetchall()}
    for column, definition in {
        "order_code": "INTEGER",
        "payment_link_id": "TEXT",
        "checkout_url": "TEXT",
        "paid_at": "TEXT",
        "payment_reference": "TEXT",
        "cancelled_at": "TEXT",
        "needs_review": "INTEGER NOT NULL DEFAULT 0",
    }.items():
        if column not in topup_cols:
            con.execute(f"ALTER TABLE topups ADD COLUMN {column} {definition}")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_topups_order_code ON topups(order_code) WHERE order_code IS NOT NULL")
    reward_cols = {r["name"] for r in con.execute("PRAGMA table_info(affiliate_rewards)").fetchall()}
    if "status" not in reward_cols:
        con.execute("ALTER TABLE affiliate_rewards ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'")
    if "reviewed_at" not in reward_cols:
        con.execute("ALTER TABLE affiliate_rewards ADD COLUMN reviewed_at TEXT")
    if "admin_note" not in reward_cols:
        con.execute("ALTER TABLE affiliate_rewards ADD COLUMN admin_note TEXT")
    try:
        con.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_affiliate_rewards_once
                       ON affiliate_rewards(user_id,topup_id,reward_type)""")
    except sqlite3.IntegrityError:
        # Preserve legacy duplicate history; new settlement paths enforce idempotency
        # with their own ledger and existence checks instead of deleting old rows.
        con.execute("CREATE INDEX IF NOT EXISTS idx_affiliate_rewards_lookup ON affiliate_rewards(user_id,topup_id,reward_type)")
    withdrawal_cols = {r["name"] for r in con.execute("PRAGMA table_info(affiliate_withdrawals)").fetchall()}
    for column, definition in {
        "account_name": "TEXT NOT NULL DEFAULT ''",
        "bank_name": "TEXT NOT NULL DEFAULT ''",
        "paid_at": "TEXT",
    }.items():
        if column not in withdrawal_cols:
            con.execute(f"ALTER TABLE affiliate_withdrawals ADD COLUMN {column} {definition}")
    settings_cols = {r["name"] for r in con.execute("PRAGMA table_info(affiliate_settings)").fetchall()}
    if "minimum_withdrawal_vnd" not in settings_cols:
        con.execute("ALTER TABLE affiliate_settings ADD COLUMN minimum_withdrawal_vnd INTEGER NOT NULL DEFAULT 50000")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by_user_id)")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub ON users(google_sub) WHERE google_sub IS NOT NULL AND google_sub!=''")
    con.execute("CREATE INDEX IF NOT EXISTS idx_security_logs_created_at ON security_logs(created_at DESC)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_security_logs_event ON security_logs(event)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_security_logs_ip ON security_logs(ip_address)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_affiliate_rewards_user ON affiliate_rewards(user_id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_affiliate_commissions_user ON affiliate_commissions(user_id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_affiliate_commissions_status ON affiliate_commissions(status)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_affiliate_withdrawals_user ON affiliate_withdrawals(user_id)")

    tool_defaults = [
        ("motion_studio", "AI Motion Studio", "Sao chép chuyển động từ video mẫu", "/static/images/card_motion.png", "DỊCH VỤ CHÍNH", 2, 0, "Tạo video", 1, 1),
        ("video_generation", "AI Video Creator", "Tạo video AI từ prompt hoặc ảnh", "/static/images/services/ai-tao-video.png", "AI VIDEO", 2, 0, "Tạo video", 1, 2),
        ("outfit_change", "AI Đổi Trang Phục", "Thay trang phục, giữ nguyên nhân vật", "/static/images/services/ai-doi-trang-phuc.png", "MIỄN PHÍ", 0, 1, "Tạo ảnh", 1, 3),
        ("background_change", "AI Đổi Bối Cảnh", "Thay cảnh nhân vật", "/static/images/services/ai-doi-boi-canh.png", "MIỄN PHÍ", 0, 1, "Tạo ảnh", 1, 4),
        ("image_upscale", "AI Nâng Cấp Ảnh", "Tăng độ nét và chất lượng ảnh", "/static/images/services/ai-nang-cap-anh.png", "MIỄN PHÍ", 0, 1, "Nâng cấp ảnh", 1, 5),
    ]
    con.executemany("""INSERT OR IGNORE INTO admin_tools(
        service_key,name,description,thumbnail,badge,price_credits,is_free,cta_text,enabled,sort_order,updated_at
    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""", [(*tool, now_iso()) for tool in tool_defaults])

    row = con.execute("SELECT id FROM users WHERE email=?", (ADMIN_EMAIL,)).fetchone()
    if not row:
        # Migrate the old default admin account instead of creating a duplicate.
        legacy_admin = con.execute(
            "SELECT id FROM users WHERE email=? AND role='admin'",
            ("admin@motionhub.local",)
        ).fetchone()
        if legacy_admin:
            con.execute(
                "UPDATE users SET email=?, name=?, password_hash=?, role='admin' WHERE id=?",
                (ADMIN_EMAIL, "Administrator", hash_password(ADMIN_PASSWORD), legacy_admin["id"])
            )
            row = {"id": legacy_admin["id"]}
        else:
            cur = con.execute(
                "INSERT INTO users(email,name,password_hash,credits,role,created_at) VALUES(?,?,?,?,?,?)",
                (ADMIN_EMAIL, "Administrator", hash_password(ADMIN_PASSWORD), 10000, "admin", now_iso())
            )
            admin_id = cur.lastrowid
            con.execute(
                "INSERT INTO credit_ledger(user_id,delta,reason,created_at) VALUES(?,?,?,?)",
                (admin_id, 10000, "Khởi tạo tài khoản admin", now_iso())
            )
            row = {"id": admin_id}

    # Keep admin password/role synchronized with the configured values.
    con.execute(
        "UPDATE users SET password_hash=?, role='admin' WHERE id=?",
        (hash_password(ADMIN_PASSWORD), row["id"])
    )

    # Give every old/new account a unique referral code.
    missing = con.execute("SELECT id,email FROM users WHERE referral_code IS NULL OR referral_code=''").fetchall()
    for u in missing:
        for _ in range(20):
            code = f"tvc{u['id']}{secrets.token_hex(2)}".lower()
            exists = con.execute("SELECT 1 FROM users WHERE referral_code=?", (code,)).fetchone()
            if not exists:
                con.execute("UPDATE users SET referral_code=? WHERE id=?", (code, u["id"]))
                break

    con.commit()
    con.close()

def access_log_ip(request: Request) -> str:
    if TRUST_PROXY:
        cloudflare_ip = request.headers.get("cf-connecting-ip", "").strip()
        if cloudflare_ip:
            return cloudflare_ip[:100]
        true_client_ip = request.headers.get("true-client-ip", "").strip()
        if true_client_ip:
            return true_client_ip[:100]
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if forwarded:
            return forwarded[:100]
    return (request.client.host if request.client else "unknown")[:100]

def request_visitor_id(request: Request) -> str | None:
    visitor_id = getattr(request.state, "visitor_id", None)
    if visitor_id:
        return visitor_id
    value = request.cookies.get(VISITOR_COOKIE, "").strip()
    return value[:100] if value.startswith("v_") else None

async def identify_visitor(request: Request, call_next):
    visitor_id = request.cookies.get(VISITOR_COOKIE, "").strip()
    created = not visitor_id.startswith("v_")
    if created:
        visitor_id = f"v_{secrets.token_urlsafe(24)}"
    request.state.visitor_id = visitor_id[:100]
    response = await call_next(request)
    if created:
        response.set_cookie(
            VISITOR_COOKIE, request.state.visitor_id, httponly=True,
            secure=COOKIE_SECURE, samesite="lax", max_age=VISITOR_DAYS * 86400, path="/"
        )
    return response

app.middleware("http")(identify_visitor)

def create_security_log(request: Request, event: str, severity: str, user=None,
                        http_status: int | None = None, metadata: dict | None = None):
    try:
        con = db()
        user_id = user.get("id") if user else None
        email = user.get("email") if user else None
        role = user.get("role") if user else None
        known_ip = False
        if event == "google_login_success" and user_id:
            known_ip = bool(con.execute(
                "SELECT 1 FROM security_logs WHERE user_id=? AND event='google_login_success' AND ip_address=? LIMIT 1",
                (user_id, access_log_ip(request)),
            ).fetchone())
        con.execute(
            "INSERT INTO security_logs(created_at,event,severity,user_id,email,role,ip_address,user_agent,method,path,http_status,request_id,metadata,visitor_id) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (now_iso(), event, severity, user_id, email, role, access_log_ip(request),
             request.headers.get("user-agent", "")[:500], request.method,
             request.url.path[:500], http_status, request.headers.get("x-request-id") or str(uuid.uuid4()),
             json.dumps(metadata, ensure_ascii=True) if metadata else None, request_visitor_id(request)),
        )
        if event == "google_login_success" and user_id and not known_ip:
            con.execute(
                "INSERT INTO security_logs(created_at,event,severity,user_id,email,role,ip_address,user_agent,method,path,http_status,request_id,metadata,visitor_id) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (now_iso(), "new_ip_login", "notice", user_id, email, role, access_log_ip(request),
                 request.headers.get("user-agent", "")[:500], request.method, request.url.path[:500],
                 http_status, request.headers.get("x-request-id") or str(uuid.uuid4()), None, request_visitor_id(request)),
            )
        con.commit()
        con.close()
    except Exception:
        logging.exception("Could not write security log event=%s", event)

async def log_admin_access(request: Request, call_next):
    is_admin_path = request.url.path == "/admin" or request.url.path.startswith("/api/admin/")
    response = await call_next(request)
    if is_admin_path:
        try:
            user = current_user(request, required=False)
            con = db()
            con.execute(
                "INSERT INTO admin_access_logs(ip_address,user_id,method,path,status_code,user_agent,created_at,visitor_id) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (access_log_ip(request), user["id"] if user else None, request.method,
                 request.url.path[:500], response.status_code,
                 request.headers.get("user-agent", "")[:500], now_iso(), request_visitor_id(request)),
            )
            con.commit()
            con.close()
            if response.status_code in {401, 403}:
                create_security_log(request, "admin_access_denied", "high", user, response.status_code)
            elif response.status_code == 429:
                create_security_log(request, "security_rate_limited", "high", user, response.status_code)
            elif request.method in {"POST", "PUT", "PATCH", "DELETE"} and response.status_code < 400:
                create_security_log(request, "admin_sensitive_action", "notice", user, response.status_code)
        except Exception:
            logging.exception("Could not write admin access log")
    return response

app.middleware("http")(log_admin_access)

init_db()

def current_user(request: Request, required=True):
    token = request.cookies.get("mh_session")
    if not token:
        auth_header = request.headers.get("Authorization") or ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
    if not token:
        if required:
            raise HTTPException(401, "Chưa đăng nhập")
        return None
    con = db()
    row = con.execute("""
        SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id
        WHERE s.token=? AND s.expires_at>?
    """, (token, now_iso())).fetchone()
    con.close()
    if row and row["role"] != "admin" and row["is_locked"]:
        raise HTTPException(403, "Tài khoản đã bị khóa")
    if not row and required:
        raise HTTPException(401, "Phiên đăng nhập đã hết hạn")
    return dict(row) if row else None

def require_admin(request: Request):
    u = current_user(request)
    if u["role"] != "admin":
        raise HTTPException(403, "Không có quyền admin")
    return u

def get_tool_config(service_key: str):
    con = db()
    row = con.execute("SELECT * FROM admin_tools WHERE service_key=?", (service_key,)).fetchone()
    con.close()
    return dict(row) if row else None


AFFILIATE_VND_PER_CREDIT = 2500
AFFILIATE_GOLD_SALES_CREDITS = 1000
DEFAULT_SIGNUP_CREDITS = int(os.environ.get("DEFAULT_SIGNUP_CREDITS", "1000"))
REFERRAL_BUYER_BONUS_RATE = 0.10
LEGACY_AFFILIATE_REWARDS_ENABLED = True

def affiliate_settings(con):
    row = con.execute("SELECT * FROM affiliate_settings WHERE id=1").fetchone()
    if not row:
        return {
            "enabled": True, "silver_rate_percent": 10.0, "gold_rate_percent": 15.0,
            "buyer_bonus_percent": 10.0, "gold_threshold_credits": 1000,
            "parent_override_percent": 50.0, "minimum_withdrawal_vnd": 50000,
        }
    return dict(row)

def affiliate_sales_credits(con, user_id: int):
    row = con.execute("""
        SELECT COALESCE(SUM(t.credits),0) AS total
        FROM topups t
        JOIN users child ON child.id=t.user_id
        WHERE child.referred_by_user_id=? AND t.status IN ('approved','paid','completed')
    """, (user_id,)).fetchone()
    return float(row["total"] or 0)

def affiliate_tier(con, user_id: int):
    settings = affiliate_settings(con)
    sales = affiliate_sales_credits(con, user_id)
    if sales >= settings["gold_threshold_credits"]:
        return {
            "key": "gold", "name": "Vàng", "rate": settings["gold_rate_percent"] / 100,
            "rate_percent": settings["gold_rate_percent"], "override_percent": settings["parent_override_percent"],
            "sales_credits": sales, "next_sales_credits": None,
        }
    return {
        "key": "silver", "name": "Bạc", "rate": settings["silver_rate_percent"] / 100,
        "rate_percent": settings["silver_rate_percent"], "override_percent": 0,
        "sales_credits": sales, "next_sales_credits": settings["gold_threshold_credits"],
    }

def affiliate_totals(con, user_id: int):
    money = con.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN status='pending' THEN amount_vnd ELSE 0 END),0) AS pending_vnd,
            COALESCE(SUM(CASE WHEN status='approved' THEN amount_vnd ELSE 0 END),0) AS approved_vnd,
            COALESCE(SUM(CASE WHEN status='paid' THEN amount_vnd ELSE 0 END),0) AS paid_vnd
        FROM affiliate_commissions WHERE user_id=?
    """, (user_id,)).fetchone()
    reward_pending = con.execute("""
        SELECT COALESCE(SUM(r.amount_credits),0) total
        FROM affiliate_rewards r
        WHERE r.user_id=? AND r.reward_type='buyer_bonus' AND r.status='pending'
    """, (user_id,)).fetchone()["total"] or 0
    reward_approved = con.execute("""
        SELECT COALESCE(SUM(delta),0) total
        FROM affiliate_reward_credit_ledger WHERE user_id=?
    """, (user_id,)).fetchone()["total"] or 0
    return {
        "money_pending_vnd": int(money["pending_vnd"] or 0),
        "money_approved_vnd": int(money["approved_vnd"] or 0),
        "money_paid_vnd": int(money["paid_vnd"] or 0),
        "money_due_vnd": int(money["approved_vnd"] or 0),
        "reward_pending_credits": round(float(reward_pending), 2),
        "reward_approved_credits": round(float(reward_approved), 2),
        # Compatibility fields: new code must use the explicit money/reward keys.
        "total_rewards": round(float(reward_approved), 2),
        "available": round(float(money["approved_vnd"] or 0) / AFFILIATE_VND_PER_CREDIT, 2),
        "paid": round(float(money["paid_vnd"] or 0) / AFFILIATE_VND_PER_CREDIT, 2),
        "pending": round(float(money["pending_vnd"] or 0) / AFFILIATE_VND_PER_CREDIT, 2),
        "reserved": 0,
        "converted": 0,
    }

def affiliate_commission_vnd(amount_vnd: int, rate: float) -> int:
    """Calculate cash commission from the amount actually paid."""
    return int(round(int(amount_vnd) * float(rate)))

def affiliate_audit(con, actor, target_user_id, action, amount_vnd=0,
                    status_before=None, status_after=None, request=None):
    con.execute(
        "INSERT INTO affiliate_audit_logs(actor_user_id,actor_role,target_user_id,action,amount_vnd,status_before,status_after,ip_address,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (actor.get("id") if actor else None, actor.get("role", "user") if actor else "system", target_user_id,
         action, int(amount_vnd or 0), status_before, status_after,
         access_log_ip(request) if request else None, now_iso())
    )

def find_referrer_by_code(con, code: str):
    code = (code or "").strip().lower()
    if not code:
        return None
    return con.execute(
        "SELECT id,email,name,referral_code FROM users WHERE lower(referral_code)=?",
        (code,)
    ).fetchone()

def capture_referral_attribution(request: Request, response: Response):
    code = (request.query_params.get("ref") or "").strip().lower()
    if not code or len(code) > 80:
        return
    con = db()
    valid = find_referrer_by_code(con, code)
    con.close()
    if valid and not current_user(request, required=False):
        response.set_cookie(
            "tvc_referral_code", code, max_age=30 * 24 * 60 * 60,
            httponly=True, secure=COOKIE_SECURE, samesite="lax", path="/"
        )

def ensure_user_referral_code(con, user_id: int):
    row = con.execute("SELECT referral_code FROM users WHERE id=?", (user_id,)).fetchone()
    if row and row["referral_code"]:
        return row["referral_code"]
    for _ in range(20):
        code = f"tvc{user_id}{secrets.token_hex(2)}".lower()
        if not con.execute("SELECT 1 FROM users WHERE referral_code=?", (code,)).fetchone():
            con.execute("UPDATE users SET referral_code=? WHERE id=?", (code, user_id))
            return code
    raise RuntimeError("Không thể tạo mã giới thiệu")

async def save_upload(upload: UploadFile, dest: Path, allowed_exts, max_mb):
    ext = Path(upload.filename or "").suffix.lower()
    if ext not in allowed_exts:
        raise HTTPException(400, f"Định dạng không hỗ trợ: {ext}")
    content_type = (upload.content_type or "").lower()
    image_extensions = {".png", ".jpg", ".jpeg", ".webp"}
    video_extensions = {".mp4", ".mov", ".webm", ".mkv"}
    if ext in image_extensions and content_type and not content_type.startswith("image/"):
        raise HTTPException(415, "Nội dung file ảnh không hợp lệ")
    if ext in video_extensions and content_type and not (
        content_type.startswith("video/") or content_type == "application/octet-stream"
    ):
        raise HTTPException(415, "Nội dung file video không hợp lệ")
    max_bytes = max_mb * 1024 * 1024
    size = 0
    with dest.open("wb") as f:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"File vượt quá {max_mb}MB")
            f.write(chunk)
    if size == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, "File tải lên đang trống")
    return size

@app.get("/")
def home(request: Request):
    response = FileResponse(BASE / "static" / "index.html")
    capture_referral_attribution(request, response)
    return response

@app.get("/referral")
def referral_page(request: Request):
    if current_user(request, required=False):
        response = RedirectResponse("/app#affiliate")
    else:
        response = RedirectResponse("/app?return_to=%2Freferral#login")
    capture_referral_attribution(request, response)
    return response

@app.get("/app")
@app.get("/history")
@app.get("/lich-su")
def app_page(request: Request):
    response = FileResponse(BASE / "static" / "app.html")
    capture_referral_attribution(request, response)
    return response

@app.get("/admin")
def admin_page():
    return FileResponse(BASE / "static" / "admin.html")

@app.get("/pricing")
@app.get("/nap-vip")
@app.get("/bang-gia")
def pricing_page():
    return FileResponse(BASE / "static" / "pricing.html")

@app.get("/about")
@app.get("/gioi-thieu")
def about_page():
    return FileResponse(BASE / "static" / "about.html")

@app.get("/tools")
def tools_redirect():
    return RedirectResponse(url="/app", status_code=302)

@app.get("/contact")
def contact_page():
    return FileResponse(BASE / "static" / "contact.html")

@app.get("/terms")
def terms_page():
    return FileResponse(BASE / "static" / "terms.html")

@app.get("/privacy")
def privacy_page():
    return FileResponse(BASE / "static" / "privacy.html")

@app.get("/refund")
def refund_page():
    return FileResponse(BASE / "static" / "refund.html")

@app.get("/ai-content-policy")
def ai_content_policy_page():
    return FileResponse(BASE / "static" / "ai-content-policy.html")

@app.get("/services/{service_key}")
def service_page(service_key: str):
    if service_key not in SERVICES:
        raise HTTPException(404, "Dịch vụ không tồn tại")
    return FileResponse(BASE / "static" / "service.html")

def create_session(con, user_id: int, response: Response):
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat()
    con.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)", (token, user_id, expires))
    response.set_cookie(
        "mh_session", token, httponly=True, samesite="lax", secure=COOKIE_SECURE,
        max_age=SESSION_DAYS * 86400, path="/"
    )
    return token

@app.get("/api/auth/google-config")
def google_auth_config():
    # Client ID is public by design and is safe to expose to the browser.
    env_value = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    return {
        "enabled": bool(GOOGLE_CLIENT_ID),
        "client_id": GOOGLE_CLIENT_ID,
        "source": "railway_env" if env_value else "built_in_fallback",
    }

@app.post("/api/auth/google")
async def google_login(request: Request, response: Response):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google Login chưa được cấu hình")

    body = await request.json()
    credential = (body.get("credential") or "").strip()
    referral_code = (body.get("referral_code") or request.cookies.get("tvc_referral_code") or "").strip().lower()
    if not credential:
        create_security_log(request, "google_login_failed", "warning", http_status=400,
                            metadata={"reason": "missing_credential"})
        raise HTTPException(400, "Thiếu Google credential")

    try:
        info = google_id_token.verify_oauth2_token(
            credential, google_requests.Request(), GOOGLE_CLIENT_ID
        )
    except Exception:
        create_security_log(request, "google_token_invalid", "warning", http_status=401)
        raise HTTPException(401, "Google credential không hợp lệ hoặc đã hết hạn")

    # verify_oauth2_token validates signature, exp, issuer and audience.
    if info.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        create_security_log(request, "google_token_invalid", "warning", http_status=401,
                            metadata={"reason": "invalid_issuer"})
        raise HTTPException(401, "Google issuer không hợp lệ")
    if info.get("aud") != GOOGLE_CLIENT_ID:
        create_security_log(request, "google_token_invalid", "warning", http_status=401,
                            metadata={"reason": "invalid_audience"})
        raise HTTPException(401, "Google audience không hợp lệ")
    if info.get("email_verified") is not True:
        create_security_log(request, "google_login_failed", "warning", http_status=401,
                            metadata={"reason": "email_not_verified"})
        raise HTTPException(401, "Email Google chưa được xác minh")

    google_sub = (info.get("sub") or "").strip()
    email = (info.get("email") or "").strip().lower()
    name = (info.get("name") or email.split("@", 1)[0] or "Google User").strip()[:80]
    avatar_url = (info.get("picture") or "").strip()[:500]
    if not google_sub or "@" not in email:
        create_security_log(request, "google_login_failed", "warning", http_status=401,
                            metadata={"reason": "invalid_account_info"})
        raise HTTPException(401, "Google không trả về thông tin tài khoản hợp lệ")

    con = db()
    try:
        by_sub = con.execute("SELECT * FROM users WHERE google_sub=?", (google_sub,)).fetchone()
        by_email = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

        if by_sub and by_email and by_sub["id"] != by_email["id"]:
            raise HTTPException(409, "Google ID và email đang thuộc hai tài khoản khác nhau")

        user = by_sub or by_email
        if user:
            existing_sub = user["google_sub"] if "google_sub" in user.keys() else None
            if existing_sub and existing_sub != google_sub:
                raise HTTPException(409, "Email này đã liên kết với một tài khoản Google khác")
            con.execute(
                "UPDATE users SET google_sub=?, avatar_url=COALESCE(NULLIF(?,''),avatar_url) WHERE id=?",
                (google_sub, avatar_url, user["id"])
            )
            user_id = user["id"]
        else:
            referrer = find_referrer_by_code(con, referral_code) if referral_code else None
            if referral_code and not referrer:
                raise HTTPException(400, "Mã giới thiệu không tồn tại")

            # Google-only accounts receive a random unusable local password hash.
            # Test credits are assigned only at account creation; returning users
            # keep their persisted database balance unchanged.
            initial_credits = TEST_INITIAL_CREDITS if TEST_MODE else 0
            random_password = secrets.token_urlsafe(48)
            cur = con.execute(
                """INSERT INTO users(
                    email,name,password_hash,credits,role,created_at,referred_by_user_id,referred_at,google_sub,avatar_url
                ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    email, name, hash_password(random_password), initial_credits, "user", now_iso(),
                    referrer["id"] if referrer else None,
                    now_iso() if referrer else None, google_sub, avatar_url
                )
            )
            user_id = cur.lastrowid
            ensure_user_referral_code(con, user_id)
            if initial_credits:
                con.execute(
                    """INSERT INTO credit_ledger(user_id,delta,reason,ref_type,ref_id,created_at)
                       VALUES(?,?,?,?,?,?)""",
                    (user_id, initial_credits, "TEST MODE: Google signup credits",
                     "test_google_signup", user_id, now_iso())
                )

        token = create_session(con, user_id, response)
        con.commit()
        response.delete_cookie("tvc_referral_code", path="/")
        user = dict(con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
        con.close()
        create_security_log(request, "google_login_success", "info", user, 200)
        return {"ok": True, "token": token, "role": user["role"], "new_user": by_sub is None and by_email is None}
    except HTTPException:
        con.rollback()
        create_security_log(request, "google_login_failed", "warning", http_status=409)
        raise
    except sqlite3.IntegrityError:
        con.rollback()
        raise HTTPException(409, "Tài khoản Google đã được liên kết")
    finally:
        con.close()

@app.post("/api/register")
async def register(request: Request, response: Response):
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    name = (body.get("name") or "").strip()[:80]
    password = body.get("password") or ""
    referral_code = (body.get("referral_code") or request.cookies.get("tvc_referral_code") or "").strip().lower()

    if "@" not in email or len(password) < 8 or not name:
        raise HTTPException(400, "Tên, email hoặc mật khẩu chưa hợp lệ")

    con = db()
    referrer = find_referrer_by_code(con, referral_code) if referral_code else None
    if referral_code and not referrer:
        con.close()
        raise HTTPException(400, "Mã giới thiệu không tồn tại")

    try:
        cur = con.execute(
            "INSERT INTO users(email,name,password_hash,credits,role,created_at,referred_by_user_id,referred_at) VALUES(?,?,?,?,?,?,?,?)",
            (
                email, name, hash_password(password), 0, "user", now_iso(),
                referrer["id"] if referrer else None,
                now_iso() if referrer else None
            )
        )
        uid = cur.lastrowid
        ensure_user_referral_code(con, uid)
        con.commit()
    except sqlite3.IntegrityError:
        con.close()
        raise HTTPException(409, "Email đã tồn tại")
    con.close()
    response.delete_cookie("tvc_referral_code", path="/")
    return {"ok": True}

@app.post("/api/login")
async def login(request: Request, response: Response):
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    con = db()
    u = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not u or not verify_password(password, u["password_hash"]):
        con.close()
        raise HTTPException(401, "Sai email hoặc mật khẩu")
    token = create_session(con, u["id"], response)
    con.commit()
    con.close()
    return {"ok": True, "token": token, "role": u["role"]}

@app.post("/api/admin/login")
async def admin_login(request: Request, response: Response):
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email or not password:
        raise HTTPException(400, "Thiếu email hoặc mật khẩu admin")
    con = db()
    u = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not u or not verify_password(password, u["password_hash"]):
        con.close()
        raise HTTPException(401, "Sai email hoặc mật khẩu admin")
    if u["role"] != "admin":
        con.close()
        raise HTTPException(403, "Tài khoản này không có quyền admin")
    create_session(con, u["id"], response)
    con.commit()
    con.close()
    return {"ok": True, "role": u["role"], "email": u["email"], "name": u["name"]}

@app.post("/api/logout")
def logout(request: Request, response: Response):
    user = current_user(request, required=False)
    token = request.cookies.get("mh_session")
    if token:
        con = db()
        con.execute("DELETE FROM sessions WHERE token=?", (token,))
        con.commit()
        con.close()
    response.delete_cookie("mh_session", path="/")
    create_security_log(request, "logout", "info", user, 200)
    return {"ok": True}

def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_local_output(job, output_path: Path) -> str | None:
    try:
        output = output_path.resolve(strict=True)
    except (OSError, RuntimeError):
        return "Worker không tạo file kết quả"
    if not output.is_file() or output.stat().st_size <= 0:
        return "Worker tạo file kết quả rỗng"
    motion_value = str(job["video_path"] or "") if "video_path" in job.keys() else ""
    if motion_value:
        motion = (BASE / motion_value).resolve()
        if output == motion:
            return "Worker trả video chuyển động đầu vào làm kết quả"
        if motion.is_file() and output.stat().st_size == motion.stat().st_size and _file_digest(output) == _file_digest(motion):
            return "Worker trả video chuyển động đầu vào làm kết quả"
    demo_root = (BASE / "static" / "videos").resolve()
    if demo_root.is_dir():
        output_digest = None
        for candidate in demo_root.iterdir():
            if not candidate.is_file() or candidate.suffix.lower() not in {".mp4", ".mov", ".webm"}:
                continue
            if output == candidate.resolve():
                return "Worker trả video demo/sample làm kết quả"
            if candidate.stat().st_size == output.stat().st_size:
                output_digest = output_digest or _file_digest(output)
                if output_digest == _file_digest(candidate):
                    return "Worker trả video demo/sample làm kết quả"
    return None


def fail_job_once(job_id: int, error: str) -> bool:
    con = db()
    try:
        con.execute("BEGIN IMMEDIATE")
        job = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not job or job["status"] in {"failed", "cancelled"}:
            con.commit()
            return False
        charged = con.execute(
            "SELECT 1 FROM credit_ledger WHERE user_id=? AND ref_type='job' AND ref_id=? LIMIT 1",
            (job["user_id"], job_id)
        ).fetchone()
        should_refund = bool((job["credit_charged"] or charged) and not job["credit_refunded"])
        if should_refund:
            con.execute("UPDATE users SET credits=credits+? WHERE id=?", (job["cost"], job["user_id"]))
            con.execute(
                "INSERT INTO credit_ledger(user_id,delta,reason,ref_type,ref_id,created_at) VALUES(?,?,?,?,?,?)",
                (job["user_id"], job["cost"], f"Hoàn lượt job lỗi #{job_id}", "job_refund", job_id, now_iso())
            )
        con.execute(
            "UPDATE jobs SET status='failed',error=?,output_path=NULL,credit_reserved=0,credit_refunded=?,updated_at=? WHERE id=?",
            (str(error or "Render thất bại")[:1000], 1 if should_refund or job["credit_refunded"] else 0, now_iso(), job_id)
        )
        con.commit()
        return True
    finally:
        con.close()


def record_worker_heartbeat(worker_id: str, status: str, current_job_id: int | None = None):
    worker_id = worker_id if isinstance(worker_id, str) else "default-worker"
    worker_id = (worker_id or "default-worker").strip()[:128] or "default-worker"
    normalized = status if status in {"idle", "busy"} else "idle"
    con = db()
    con.execute(
        """INSERT INTO worker_heartbeats(worker_id,status,current_job_id,last_heartbeat)
           VALUES(?,?,?,?)
           ON CONFLICT(worker_id) DO UPDATE SET status=excluded.status,
             current_job_id=excluded.current_job_id,last_heartbeat=excluded.last_heartbeat""",
        (worker_id, normalized, current_job_id, now_iso()),
    )
    con.commit()
    con.close()


def worker_presence(reference_time: datetime | None = None) -> dict:
    reference_time = reference_time or datetime.now(timezone.utc)
    con = db()
    rows = con.execute("SELECT * FROM worker_heartbeats").fetchall()
    con.close()
    fresh = []
    for row in rows:
        try:
            heartbeat = datetime.fromisoformat(row["last_heartbeat"])
            if heartbeat.tzinfo is None:
                heartbeat = heartbeat.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        if (reference_time - heartbeat).total_seconds() <= WORKER_HEARTBEAT_TIMEOUT_SECONDS:
            fresh.append(dict(row))
    if not fresh:
        return {"state": "offline", "workers": []}
    state = "busy" if all(row["status"] == "busy" for row in fresh) else "idle"
    return {"state": state, "workers": fresh}


def recover_stale_jobs(user_id: int | None = None, reference_time: datetime | None = None) -> int:
    reference_time = reference_time or datetime.now(timezone.utc)
    con = db()
    sql = "SELECT id,status,updated_at FROM jobs WHERE status IN ('waiting','running','upscaling','submit_retry')"
    params = ()
    if user_id is not None:
        sql += " AND user_id=?"
        params = (user_id,)
    rows = con.execute(sql, params).fetchall()
    con.close()
    stale = []
    presence = worker_presence(reference_time)
    for row in rows:
        try:
            updated = datetime.fromisoformat(row["updated_at"])
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            updated = datetime.fromtimestamp(0, timezone.utc)
        queued = row["status"] in {"waiting", "submit_retry"}
        age = (reference_time - updated).total_seconds()
        if queued:
            if presence["state"] in {"idle", "busy"}:
                continue
            if age > WORKER_UNAVAILABLE_TIMEOUT_SECONDS:
                stale.append((row["id"], "Không có GPU worker khả dụng trong thời gian cho phép"))
            continue
        current_ids = {
            worker["current_job_id"] for worker in presence["workers"]
            if worker.get("current_job_id") is not None
        }
        heartbeat_matches = row["id"] in current_ids
        if not heartbeat_matches and age > WORKER_HEARTBEAT_TIMEOUT_SECONDS:
            stale.append((row["id"], "GPU worker mất heartbeat khi đang render"))
        elif age > JOB_RENDER_TIMEOUT_SECONDS:
            stale.append((row["id"], "Render vượt quá thời gian xử lý cho phép"))
    for job_id, error in stale:
        fail_job_once(job_id, error)
    return len(stale)


def _remote_output_error(job, payload: dict, response) -> str | None:
    locator = next((str(payload[key]) for key in ("output_id", "output_url", "video_url") if payload.get(key)), "")
    lowered = locator.lower()
    if any(marker in lowered for marker in ("/static/videos/", "demo.", "sample.", "placeholder")):
        return "Worker trả video demo/sample làm kết quả"
    inputs = {str(job[key]) for key in ("gpu_motion_upload_id", "video_path") if key in job.keys() and job[key]}
    if locator and locator in inputs:
        return "Worker trả video chuyển động đầu vào làm kết quả"
    headers = getattr(response, "headers", {}) or {}
    if str(headers.get("content-length", "")).strip() == "0":
        return "Worker trả file kết quả rỗng"
    content_type = str(headers.get("content-type", "")).lower()
    if content_type and not content_type.startswith("video/"):
        return "Worker trả kết quả không phải video"
    return None


GPU_STATUS_MAP = {
    "queued": ("waiting", 0), "running": ("running", 50),
    "succeeded": ("done", 100), "failed": ("failed", 100),
    "cancelled": ("cancelled", 100),
}


def gpu_http_error(error: GPUAPIError):
    safe_status = error.status if error.status in {400, 401, 403, 404, 409, 413, 415, 422, 502, 503, 504} else 502
    return HTTPException(safe_status, error.message)


def apply_gpu_status(user_id: int, local_job_id: int, payload: dict):
    gpu_status = str(payload.get("status") or "")
    if gpu_status not in GPU_STATUS_MAP:
        return
    local_status, progress = GPU_STATUS_MAP[gpu_status]
    error_value = payload.get("error")
    if isinstance(error_value, dict):
        error_text = str(error_value.get("message") or error_value.get("code") or "")[:1000]
    else:
        error_text = None
    con = db()
    try:
        con.execute("BEGIN IMMEDIATE")
        job = con.execute("SELECT * FROM jobs WHERE id=? AND user_id=?", (local_job_id, user_id)).fetchone()
        if not job:
            con.rollback(); return
        if gpu_status == "succeeded":
            try:
                upstream = gpu_api.output(str(user_id), job["gpu_job_id"])
                validation_error = _remote_output_error(job, payload, upstream)
                upstream.close()
            except GPUAPIError as exc:
                validation_error = exc.message
            if validation_error:
                con.rollback()
                fail_job_once(local_job_id, validation_error)
                return
        if gpu_status in {"failed", "cancelled"} and job["credit_charged"] and not job["credit_refunded"]:
            con.execute("UPDATE users SET credits=credits+? WHERE id=?", (job["cost"], user_id))
            con.execute(
                "INSERT INTO credit_ledger(user_id,delta,reason,ref_type,ref_id,created_at) VALUES(?,?,?,?,?,?)",
                (user_id, job["cost"], f"Hoàn lượt job #{local_job_id}", "job_refund", local_job_id, now_iso())
            )
            con.execute("UPDATE jobs SET credit_refunded=1 WHERE id=?", (local_job_id,))

        con.execute("""UPDATE jobs SET status=?,progress=?,gpu_status=?,gpu_error=?,error=?,updated_at=?
                       WHERE id=? AND user_id=?""",
                    (local_status, progress, gpu_status, error_text, error_text, now_iso(), local_job_id, user_id))
        con.commit()
    finally:
        con.close()
    if gpu_status == "succeeded":
        con = db()
        completed = con.execute("SELECT * FROM jobs WHERE id=?", (local_job_id,)).fetchone()
        con.close()
        if completed:
            values = video_upscale_pipeline.start(sys.modules[__name__], dict(completed))
            video_upscale_pipeline.persist(sys.modules[__name__], local_job_id, values)


def refresh_gpu_jobs(user_id: int):
    con = db()
    hd_rows = con.execute("SELECT * FROM jobs WHERE user_id=? AND status='upscaling' ORDER BY id DESC LIMIT 20", (user_id,)).fetchall()
    con.close()
    for row in hd_rows:
        values = video_upscale_pipeline.poll(sys.modules[__name__], dict(row))
        video_upscale_pipeline.persist(sys.modules[__name__], row["id"], values)
    if not GPU_BACKEND_ENABLED:
        return
    con = db()
    rows = con.execute("""SELECT id,gpu_job_id FROM jobs
                          WHERE user_id=? AND gpu_job_id IS NOT NULL
                          AND status IN ('waiting','running') ORDER BY id DESC LIMIT 20""", (user_id,)).fetchall()
    con.close()
    for row in rows:
        try:
            apply_gpu_status(user_id, row["id"], gpu_api.status(str(user_id), row["gpu_job_id"]))
        except GPUAPIError:
            continue


async def create_gpu_job(u: dict, image: UploadFile, motion: UploadFile, model: str,
                         aspect_ratio: str, prompt: str, request_key: str):
    owner_id = str(u["id"])
    request_key = (request_key or secrets.token_urlsafe(24)).strip()[:128]
    client_job_id = f"tvc-{owner_id}-{request_key}"
    configured_motion = get_tool_config("motion_studio")
    cost = int(configured_motion["price_credits"]) if configured_motion else 1
    if configured_motion and configured_motion.get("is_free"):
        cost = 0
    con = db()
    try:
        con.execute("BEGIN IMMEDIATE")
        existing = con.execute("SELECT * FROM jobs WHERE user_id=? AND request_key=?",
                               (u["id"], request_key)).fetchone()
        if existing and existing["credit_charged"]:
            con.commit()
            return {"ok": True, "job_id": existing["id"], "cost": cost,
                    "duplicate": True, "status": existing["status"]}
        if existing:
            job_id = existing["id"]
        else:
            available = con.execute("SELECT credits FROM users WHERE id=?", (u["id"],)).fetchone()
            reserved = con.execute("SELECT COALESCE(SUM(cost),0) total FROM jobs WHERE user_id=? AND credit_reserved=1",
                                   (u["id"],)).fetchone()["total"]
            if not available or available["credits"] - reserved < cost:
                raise HTTPException(402, "Không đủ lượt")
            cur = con.execute("""INSERT INTO jobs(
                user_id,model,aspect_ratio,quality,prompt,cost,image_path,video_path,status,progress,
                created_at,updated_at,request_key,client_job_id,credit_reserved
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""", (
                u["id"], model[:120], aspect_ratio, "720", prompt[:2000], cost, "", "",
                "uploading", 0, now_iso(), now_iso(), request_key, client_job_id
            ))
            job_id = cur.lastrowid
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

    job_dir = UPLOADS / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    image_ext = Path(image.filename or ".png").suffix.lower()
    motion_ext = Path(motion.filename or ".mp4").suffix.lower()
    image_dest = job_dir / ("character" + image_ext)
    motion_dest = job_dir / ("motion" + motion_ext)
    try:
        await save_upload(image, image_dest, {".png",".jpg",".jpeg",".webp"}, MAX_IMAGE_MB)
        await save_upload(motion, motion_dest, {".mp4",".mov",".webm"}, MAX_VIDEO_MB)
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            raise HTTPException(503, "Không thể kiểm tra thời lượng video chuyển động")
        try:
            probe = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(motion_dest)],
                capture_output=True, text=True, timeout=20, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise HTTPException(503, "Không thể kiểm tra thời lượng video chuyển động") from error
        try:
            motion_duration = float(probe.stdout.strip())
        except (TypeError, ValueError):
            motion_duration = None
        if probe.returncode != 0 or motion_duration is None:
            raise HTTPException(400, "Không đọc được thời lượng video chuyển động")
        if motion_duration > MAX_MOTION_DURATION_SECONDS:
            raise HTTPException(400, "Video chuyển động tối đa 20 giây. Vui lòng chọn video ngắn hơn.")
        with image_dest.open("rb") as source:
            gpu_image = gpu_api.upload(owner_id, image_dest.name, image.content_type or mimetypes.guess_type(image_dest.name)[0] or "application/octet-stream", source)
        with motion_dest.open("rb") as source:
            gpu_motion = gpu_api.upload(owner_id, motion_dest.name, motion.content_type or mimetypes.guess_type(motion_dest.name)[0] or "application/octet-stream", source)
        accepted = gpu_api.submit(owner_id, client_job_id, str(gpu_image["id"]), str(gpu_motion["id"]),
                                  aspect_ratio, prompt[:2000])
    except GPUAPIError as error:
        con = db()
        con.execute("""UPDATE jobs SET status='submit_retry',gpu_error=?,error=?,image_path=?,video_path=?,updated_at=?
                       WHERE id=? AND user_id=?""",
                    (error.code, error.message, str(image_dest.relative_to(BASE)) if image_dest.exists() else "",
                     str(motion_dest.relative_to(BASE)) if motion_dest.exists() else "", now_iso(), job_id, u["id"]))
        con.commit(); con.close()
        raise gpu_http_error(error)
    except Exception:
        shutil.rmtree(job_dir, ignore_errors=True)
        con = db()
        con.execute("DELETE FROM jobs WHERE id=? AND user_id=? AND credit_charged=0", (job_id, u["id"]))
        con.commit(); con.close()
        raise

    gpu_job_id = str(accepted.get("id") or "")
    if not gpu_job_id:
        raise HTTPException(502, "Dịch vụ GPU không xác nhận job")
    local_status, progress = GPU_STATUS_MAP.get(str(accepted.get("status")), ("waiting", 0))
    con = db()
    try:
        con.execute("BEGIN IMMEDIATE")
        job = con.execute("SELECT * FROM jobs WHERE id=? AND user_id=?", (job_id, u["id"])).fetchone()
        if not job:
            raise HTTPException(409, "Job cục bộ không tồn tại")
        if not job["credit_charged"]:
            charged = con.execute("UPDATE users SET credits=credits-? WHERE id=? AND credits>=?",
                                  (cost, u["id"], cost))
            if charged.rowcount != 1:
                raise HTTPException(402, "Không đủ lượt")
            con.execute("""INSERT INTO credit_ledger(user_id,delta,reason,ref_type,ref_id,created_at)
                           VALUES(?,?,?,?,?,?)""",
                        (u["id"], -cost, f"Tạo job #{job_id}", "job", job_id, now_iso()))
        con.execute("""UPDATE jobs SET image_path=?,video_path=?,gpu_job_id=?,gpu_image_upload_id=?,
                       gpu_motion_upload_id=?,gpu_status=?,status=?,progress=?,credit_reserved=0,
                       credit_charged=1,error=NULL,gpu_error=NULL,updated_at=?
                       WHERE id=? AND user_id=?""",
                    (str(image_dest.relative_to(BASE)), str(motion_dest.relative_to(BASE)), gpu_job_id,
                     str(gpu_image["id"]), str(gpu_motion["id"]), str(accepted.get("status") or "queued"),
                     local_status, progress, now_iso(), job_id, u["id"]))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return {"ok": True, "job_id": job_id, "cost": cost,
            "duplicate": bool(accepted.get("duplicate")), "status": local_status}


@app.get("/api/version")
def api_version():
    return {"version": "3.3.45", "single_video_price": True, "quality_user_selectable": False}

@app.get("/api/me")
def me(request: Request):
    u = current_user(request)
    result = {k: u.get(k) for k in ("id","email","name","credits","role","created_at","referral_code","referred_by_user_id","avatar_url","google_sub")}
    result["usage_balance"] = result["credits"]
    result["usage_unit"] = "lượt"
    return result

@app.get("/api/jobs")
def my_jobs(request: Request):
    u = current_user(request)
    refresh_gpu_jobs(u["id"])
    con = db()
    service_rows = con.execute("SELECT id FROM jobs WHERE user_id=? AND service IS NOT NULL AND service!='motion_studio' AND status IN ('waiting','running','upscaling') ORDER BY id DESC LIMIT 20", (u["id"],)).fetchall()
    con.close()
    from service_routes import refresh_job as refresh_service_job
    for service_row in service_rows:
        refresh_service_job(u["id"], service_row["id"])
    recover_stale_jobs(u["id"])
    con = db()
    rows = con.execute("""
        SELECT id,model,service,aspect_ratio,quality,prompt,cost,status,progress,error,created_at,updated_at,
               CASE WHEN status='done' AND (output_path IS NOT NULL OR gpu_job_id IS NOT NULL OR worker_job_id IS NOT NULL) THEN 1 ELSE 0 END AS has_output,
               CASE WHEN gpu_job_id IS NOT NULL AND status='waiting' THEN 1 ELSE 0 END AS can_cancel
        FROM jobs WHERE user_id=? ORDER BY id DESC LIMIT 100
    """, (u["id"],)).fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.post("/api/jobs")
async def create_job(
    request: Request,
    image: UploadFile = File(...),
    motion: UploadFile = File(...),
    model: str = Form("Wan Animate 2 • Distill INT8"),
    aspect_ratio: str = Form("9:16"),
    prompt: str = Form(""),
    request_key: str = Form("")
):
    u = current_user(request)
    if MOTION_MODELS:
        model = MOTION_MODELS[0]
    if aspect_ratio not in {"9:16","16:9","1:1"}:
        raise HTTPException(400, "Tỷ lệ không hợp lệ")
    if GPU_BACKEND_ENABLED:
        return await create_gpu_job(u, image, motion, model, aspect_ratio, prompt, request_key)
    # V3.3.46: one public render mode / one price.
    # The client no longer sends a quality field. Extra legacy form fields are
    # ignored by FastAPI, while the server always uses one internal profile.
    # This removes the old "Chất lượng không hợp lệ" path permanently.
    quality = "720"  # internal worker compatibility only; not a user choice
    cost = 1
    request_key = (request_key or "").strip()[:128]
    now_ts = time.time()

    # Layer 1 (backend): atomic per-user guard + idempotency key.
    # This protects against double taps, duplicated browser requests and retries.
    con = db()
    try:
        con.execute("BEGIN IMMEDIATE")

        if request_key:
            existing = con.execute(
                "SELECT id,cost,status FROM jobs WHERE user_id=? AND request_key=? LIMIT 1",
                (u["id"], request_key)
            ).fetchone()
            if existing:
                con.commit(); con.close()
                return {
                    "ok": True, "job_id": existing["id"], "cost": existing["cost"],
                    "duplicate": True, "status": existing["status"]
                }

        guard = con.execute(
            "SELECT job_id,locked_until FROM job_submit_guards WHERE user_id=?",
            (u["id"],)
        ).fetchone()
        if guard and float(guard["locked_until"] or 0) > now_ts:
            existing = None
            if guard["job_id"]:
                existing = con.execute(
                    "SELECT id,cost,status FROM jobs WHERE id=? AND user_id=?",
                    (guard["job_id"], u["id"])
                ).fetchone()
            con.commit(); con.close()
            if existing:
                return {
                    "ok": True, "job_id": existing["id"], "cost": existing["cost"],
                    "duplicate": True, "status": existing["status"]
                }
            raise HTTPException(409, "Yêu cầu tạo video đang được xử lý, vui lòng chờ vài giây")

        fresh = con.execute("SELECT credits FROM users WHERE id=?", (u["id"],)).fetchone()
        if not fresh or fresh["credits"] < cost:
            con.rollback(); con.close()
            raise HTTPException(402, "Không đủ lượt")

        cur = con.execute("""
            INSERT INTO jobs(user_id,model,aspect_ratio,quality,prompt,cost,image_path,video_path,status,progress,created_at,updated_at,request_key)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            u["id"], model[:120], aspect_ratio, quality, prompt[:2000], cost,
            "", "", "uploading", 0, now_iso(), now_iso(), request_key or None
        ))
        job_id = cur.lastrowid
        con.execute("""
            INSERT INTO job_submit_guards(user_id,job_id,locked_until)
            VALUES(?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET job_id=excluded.job_id,locked_until=excluded.locked_until
        """, (u["id"], job_id, now_ts + JOB_SUBMIT_INFLIGHT_SECONDS))
        con.commit(); con.close()
    except HTTPException:
        try:
            con.rollback(); con.close()
        except Exception:
            pass
        raise
    except sqlite3.IntegrityError:
        # A simultaneous request with the same idempotency key won the race.
        try:
            con.rollback()
            if request_key:
                existing = con.execute(
                    "SELECT id,cost,status FROM jobs WHERE user_id=? AND request_key=? LIMIT 1",
                    (u["id"], request_key)
                ).fetchone()
                con.close()
                if existing:
                    return {
                        "ok": True, "job_id": existing["id"], "cost": existing["cost"],
                        "duplicate": True, "status": existing["status"]
                    }
            con.close()
        except Exception:
            pass
        raise HTTPException(409, "Yêu cầu tạo video đã được nhận")
    except Exception:
        try:
            con.rollback(); con.close()
        except Exception:
            pass
        raise

    job_dir = UPLOADS / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    image_dest = job_dir / ("character" + Path(image.filename or ".png").suffix.lower())
    video_dest = job_dir / ("motion" + Path(motion.filename or ".mp4").suffix.lower())

    try:
        await save_upload(image, image_dest, {".png",".jpg",".jpeg",".webp"}, MAX_IMAGE_MB)
        await save_upload(motion, video_dest, {".mp4",".mov",".webm",".mkv"}, MAX_VIDEO_MB)
    except Exception:
        shutil.rmtree(job_dir, ignore_errors=True)
        cleanup = db()
        try:
            cleanup.execute("BEGIN IMMEDIATE")
            cleanup.execute("DELETE FROM jobs WHERE id=? AND user_id=? AND status='uploading'", (job_id, u["id"]))
            cleanup.execute("DELETE FROM job_submit_guards WHERE user_id=? AND job_id=?", (u["id"], job_id))
            cleanup.commit()
        finally:
            cleanup.close()
        raise

    # Charge TVC and publish to the worker queue atomically.
    con = db()
    try:
        con.execute("BEGIN IMMEDIATE")
        charged = con.execute(
            "UPDATE users SET credits=credits-? WHERE id=? AND credits>=?",
            (cost, u["id"], cost)
        )
        if charged.rowcount != 1:
            con.execute("DELETE FROM jobs WHERE id=? AND user_id=? AND status='uploading'", (job_id, u["id"]))
            con.execute("DELETE FROM job_submit_guards WHERE user_id=? AND job_id=?", (u["id"], job_id))
            con.commit(); con.close()
            shutil.rmtree(job_dir, ignore_errors=True)
            raise HTTPException(402, "Không đủ lượt")

        con.execute(
            "INSERT INTO credit_ledger(user_id,delta,reason,ref_type,ref_id,created_at) VALUES(?,?,?,?,?,?)",
            (u["id"], -cost, f"Tạo job #{job_id}", "job", job_id, now_iso())
        )
        con.execute("""
            UPDATE jobs SET image_path=?,video_path=?,status='waiting',credit_charged=1,updated_at=? WHERE id=?
        """, (str(image_dest.relative_to(BASE)), str(video_dest.relative_to(BASE)), now_iso(), job_id))
        con.execute(
            "UPDATE job_submit_guards SET locked_until=? WHERE user_id=? AND job_id=?",
            (time.time() + JOB_SUBMIT_COOLDOWN_SECONDS, u["id"], job_id)
        )
        con.commit(); con.close()
    except HTTPException:
        raise
    except Exception:
        try:
            con.rollback(); con.close()
        except Exception:
            pass
        # No charge survives a rollback. Remove the unfinished job and release the guard.
        cleanup = db()
        try:
            cleanup.execute("BEGIN IMMEDIATE")
            cleanup.execute("DELETE FROM jobs WHERE id=? AND user_id=? AND status='uploading'", (job_id, u["id"]))
            cleanup.execute("DELETE FROM job_submit_guards WHERE user_id=? AND job_id=?", (u["id"], job_id))
            cleanup.commit()
        finally:
            cleanup.close()
        shutil.rmtree(job_dir, ignore_errors=True)
        raise

    return {"ok": True, "job_id": job_id, "cost": cost, "duplicate": False}

@app.get("/api/jobs/{job_id}/output")
def job_output(job_id: int, request: Request):
    u = current_user(request)
    con = db()
    row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    con.close()
    if not row:
        raise HTTPException(404, "Không tìm thấy job")
    if row["user_id"] != u["id"] and u["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    is_download = False
    try:
        is_download = request.query_params.get("download") == "1"
    except Exception:
        is_download = False
    disposition_type = "attachment" if is_download else "inline"
    filename_hd = f"tvc_job_{job_id}_hd.mp4"
    filename_std = f"tvc_job_{job_id}.mp4"

    if row["status"] != "done":
        raise HTTPException(409, "Kết quả chưa sẵn sàng")
    if row["video_upscale_status"] == "completed" and row["video_upscale_job_id"]:
        try:
            upstream = video_upscale_adapter.result(row["video_upscale_job_id"])
            return StreamingResponse(
                gpu_api.stream(upstream),
                media_type=upstream.headers.get("content-type", "video/mp4"),
                headers={
                    "Accept-Ranges": "bytes",
                    "Content-Disposition": f'{disposition_type}; filename="{filename_hd}"'
                }
            )
        except WorkerAdapterError:
            pass
    if row["gpu_job_id"]:
        try:
            upstream = gpu_api.output(str(row["user_id"]), row["gpu_job_id"])
        except GPUAPIError as error:
            raise gpu_http_error(error)
        content_type = upstream.headers.get("content-type", "video/mp4")
        return StreamingResponse(
            gpu_api.stream(upstream),
            media_type=content_type,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Disposition": f'{disposition_type}; filename="{filename_std}"'
            }
        )
    if not row["output_path"]:
        raise HTTPException(404, "Job chưa có kết quả")
    path = BASE / row["output_path"]
    validation_error = validate_local_output(row, path)
    if validation_error:
        fail_job_once(job_id, validation_error)
        raise HTTPException(404, validation_error)
    
    ext = path.suffix or ".mp4"
    filename = f"tvc_job_{job_id}{ext}"
    media_type = "video/mp4" if ext in {".mp4", ".mov", ".webm"} else "application/octet-stream"
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'{disposition_type}; filename="{filename}"'
    }
    return FileResponse(path, media_type=media_type, headers=headers)


@app.delete("/api/jobs/{job_id}")
def cancel_customer_job(job_id: int, request: Request):
    u = current_user(request)
    con = db()
    row = con.execute("SELECT * FROM jobs WHERE id=? AND user_id=?", (job_id, u["id"])).fetchone()
    con.close()
    if not row:
        raise HTTPException(404, "Không tìm thấy job")
    if not GPU_BACKEND_ENABLED or not row["gpu_job_id"]:
        raise HTTPException(409, "Job này không hỗ trợ hủy")
    try:
        payload = gpu_api.cancel(str(u["id"]), row["gpu_job_id"])
    except GPUAPIError as error:
        raise gpu_http_error(error)
    apply_gpu_status(u["id"], job_id, payload)
    return {"ok": True, "job_id": job_id, "status": GPU_STATUS_MAP.get(str(payload.get("status")), ("waiting", 0))[0]}


@app.get("/api/ledger")
def ledger(request: Request):
    u = current_user(request)
    con = db()
    rows = con.execute("SELECT * FROM credit_ledger WHERE user_id=? ORDER BY id DESC LIMIT 100", (u["id"],)).fetchall()
    con.close()
    return [dict(r) for r in rows]

PACKAGES = {
    "starter": (20_000, 20),
    "basic": (49_000, 50),
    "creator": (199_000, 220),
    "professional": (499_000, 575),
}
PAYOS_API_URL = "https://api-merchant.payos.vn/v2/payment-requests"
PAYOS_CLIENT_ID = os.getenv("PAYOS_CLIENT_ID", "").strip()
PAYOS_API_KEY = os.getenv("PAYOS_API_KEY", "").strip()
PAYOS_CHECKSUM_KEY = os.getenv("PAYOS_CHECKSUM_KEY", "").strip()
PAYOS_RETURN_URL = os.getenv("PAYOS_RETURN_URL", "https://tvcstudioai.info/app#wallet").strip()
PAYOS_CANCEL_URL = os.getenv("PAYOS_CANCEL_URL", "https://tvcstudioai.info/api/payments/cancel").strip()
if PAYOS_CANCEL_URL == "https://tvcstudioai.info/app#wallet":
    PAYOS_CANCEL_URL = "https://tvcstudioai.info/api/payments/cancel"

def payos_ready() -> bool:
    return bool(PAYOS_CLIENT_ID and PAYOS_API_KEY and PAYOS_CHECKSUM_KEY)

def get_payos_client() -> Optional[Any]:
    if not payos_ready():
        return None
    if PayOS is None:
        return None
    return PayOS(
        client_id=PAYOS_CLIENT_ID,
        api_key=PAYOS_API_KEY,
        checksum_key=PAYOS_CHECKSUM_KEY
    )

def payos_signature(values: dict) -> str:
    payload = "&".join(f"{key}={values[key]}" for key in sorted(values) if values[key] is not None)
    return hmac.new(PAYOS_CHECKSUM_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()

def payos_payment_status(order_code: int) -> dict | None:
    """Read a payment link status for reconciliation when webhook delivery lags."""
    if not payos_ready():
        return None
    url = f"https://api-merchant.payos.vn/v2/payment-requests/{int(order_code)}"
    request = urllib.request.Request(
        url, method="GET",
        headers={"Content-Type": "application/json", "x-client-id": PAYOS_CLIENT_ID, "x-api-key": PAYOS_API_KEY},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode())
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        if isinstance(data.get("data"), dict):
            data = data["data"]
        if str(payload.get("code", "00")) not in {"00", ""}:
            logging.warning("PayOS reconciliation order %s returned code %s", order_code, payload.get("code"))
            return None
        status = str(data.get("status") or data.get("paymentStatus") or data.get("transactionStatus") or "").upper()
        logging.info("PayOS reconciliation order %s status=%s", order_code, status or "UNKNOWN")
        return {"status": status or None, "amount": _webhook_amount(data),
                "reference": data.get("reference"), "payment_link_id": data.get("paymentLinkId")}
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        logging.warning("PayOS reconciliation failed for order %s: %s", order_code, exc)
        return None

def reconcile_pending_topups(rows) -> None:
    pending_rows = [row for row in rows if row["status"] in {"pending", "pending_payment"} and row["order_code"]][:20]
    for row in pending_rows:
        payment = payos_payment_status(row["order_code"])
        if payment and payment["status"] == "PAID" and payment["amount"] == int(row["amount_vnd"]):
            try:
                approve_topup(row["id"], None, _internal=True, verified_amount=payment["amount"],
                              payment_reference=payment["reference"], payment_link_id=payment["payment_link_id"])
            except HTTPException as exc:
                if exc.status_code != 409:
                    logging.warning("Could not auto-approve topup %s: %s", row["id"], exc.detail)

def payos_create_payment(order_code: int, amount: int, description: str, items: Optional[list] = None) -> dict:
    if not payos_ready():
        raise HTTPException(503, "PayOS chưa được cấu hình trên máy chủ")

    try:
        payos_inst = get_payos_client()
    except Exception as exc:
        logging.warning("PayOS SDK client initialization failed: %s", exc)
        payos_inst = None
    if payos_inst and PaymentData:
        try:
            payos_items = None
            if items and ItemData:
                payos_items = [
                    ItemData(name=it.get("name", description), quantity=int(it.get("quantity", 1)), price=int(it.get("price", amount)))
                    for it in items
                ]
            payment_data = PaymentData(
                orderCode=order_code,
                amount=amount,
                description=description[:25],
                cancelUrl=PAYOS_CANCEL_URL,
                returnUrl=PAYOS_RETURN_URL,
                items=payos_items
            )
            res = payos_inst.createPaymentLink(payment_data)
            checkout_url = getattr(res, "checkoutUrl", None) or (res.get("checkoutUrl") if isinstance(res, dict) else None)
            payment_link_id = getattr(res, "paymentLinkId", None) or (res.get("paymentLinkId") if isinstance(res, dict) else None)
            if checkout_url:
                return {"checkoutUrl": checkout_url, "paymentLinkId": payment_link_id}
        except Exception as exc:
            logging.warning("PayOS SDK payment-link request failed: %s", exc)

    values = {
        "amount": amount, "cancelUrl": PAYOS_CANCEL_URL,
        "description": description[:25], "orderCode": order_code,
        "returnUrl": PAYOS_RETURN_URL,
    }
    if items:
        values["items"] = items
    values["signature"] = payos_signature(values)
    request = urllib.request.Request(
        PAYOS_API_URL, data=json.dumps(values).encode(), method="POST",
        headers={"Content-Type": "application/json", "x-client-id": PAYOS_CLIENT_ID, "x-api-key": PAYOS_API_KEY},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode()).get("desc")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            detail = None
        logging.warning("PayOS HTTP error %s: %s", exc.code, detail or exc.reason)
        raise HTTPException(502, detail or "PayOS từ chối yêu cầu thanh toán") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        logging.warning("PayOS connection error: %s", exc)
        raise HTTPException(502, "Không thể kết nối PayOS") from exc
    if not payload.get("code") == "00" or not payload.get("data", {}).get("checkoutUrl"):
        raise HTTPException(502, payload.get("desc") or "PayOS không tạo được link thanh toán")
    return payload["data"]

def payos_webhook_valid(body: dict) -> bool:
    payos_inst = get_payos_client()
    if payos_inst:
        try:
            payos_inst.webhooks.verify(body)
            return True
        except Exception:
            try:
                payos_inst.verifyPaymentWebhookData(body)
                return True
            except Exception:
                pass
    signature = str(body.get("signature") or "")
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    if not signature or not isinstance(data, dict):
        return False
    values = {key: data[key] for key in data if key != "signature" and data[key] is not None}
    return hmac.compare_digest(signature.lower(), payos_signature(values).lower())

def _webhook_data(body: dict) -> dict:
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    return data if isinstance(data, dict) else {}

def _webhook_amount(data: dict):
    value = data.get("amount")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None

@app.post("/api/payments/create-link")
@app.post("/api/topups")
async def create_payment_link(request: Request):
    u = current_user(request)
    body = await request.json()
    package = body.get("package")
    amount = body.get("amount")
    credits = body.get("credits")
    note = (body.get("note") or "")[:300]
    user_id = u["id"]

    if package in PACKAGES:
        pkg_amount, pkg_credits = PACKAGES[package]
        amount = pkg_amount
        credits = pkg_credits
    elif amount is not None and int(amount) > 0:
        amount = int(amount)
        credits = int(credits) if credits is not None else int(amount // 1000)
        package = package or f"custom_{amount}"
    else:
        raise HTTPException(400, "Gói không hợp lệ")

    order_code = int(f"{int(time.time())}{secrets.randbelow(1000):03d}")
    con = db()
    cur = con.execute("""
        INSERT INTO topups(user_id,package,amount_vnd,credits,note,status,created_at,order_code,payment_link_id,checkout_url)
        VALUES(?,?,?,?,?,'pending_payment',?,?,?,?)
    """, (user_id, package, amount, credits, note, now_iso(), order_code, None, None))
    con.commit()
    tid = cur.lastrowid
    con.close()

    try:
        payment = payos_create_payment(
            order_code, amount, f"Nap xu {credits}",
            items=[{"name": f"Goi {credits} xu", "quantity": 1, "price": amount}]
        )
    except Exception:
        con = db()
        con.execute("DELETE FROM topups WHERE id=? AND status='pending_payment'", (tid,))
        con.commit()
        con.close()
        raise

    checkout_url = payment.get("checkoutUrl") or payment.get("checkout_url")
    con = db()
    con.execute(
        "UPDATE topups SET payment_link_id=?,checkout_url=? WHERE id=? AND status='pending_payment'",
        (payment.get("paymentLinkId"), checkout_url, tid)
    )
    con.commit()
    con.close()
    return {
        "ok": True,
        "success": True,
        "topup_id": tid,
        "topupId": tid,
        "amount_vnd": amount,
        "amount": amount,
        "credits": credits,
        "order_code": order_code,
        "orderCode": order_code,
        "checkout_url": checkout_url,
        "checkoutUrl": checkout_url
    }

@app.get("/api/payments/webhook")
@app.get("/api/payos/webhook")
async def payos_webhook_health():
    return {"success": True, "status": "active", "message": "PayOS Webhook endpoint is active and ready"}

@app.post("/api/payments/webhook")
@app.post("/api/payos/webhook")
async def payos_webhook(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"success": True, "message": "Empty or non-JSON request received"}

    # Handle webhook URL confirmation from PayOS
    if isinstance(body, dict) and ("webhookUrl" in body or "webhook_url" in body):
        return {"success": True, "message": "Webhook URL confirmed"}

    data = _webhook_data(body)
    raw_order_code = data.get("orderCode") or data.get("order_code")
    logging.info("PAYOS_WEBHOOK_RECEIVED orderCode=%s", raw_order_code or "unknown")
    if not payos_webhook_valid(body):
        logging.warning("PAYOS_WEBHOOK_INVALID_SIGNATURE orderCode=%s", raw_order_code or "unknown")
        if isinstance(body, dict) and body.get("data") is None and not body.get("signature"):
            return {"success": True, "message": "Test ping received"}
        raise HTTPException(400, "Webhook PayOS không hợp lệ hoặc sai chữ ký")
    logging.info("PAYOS_WEBHOOK_VERIFIED orderCode=%s", raw_order_code or "unknown")

    if not isinstance(data, dict):
        return {"success": True}

    if str(data.get("code", "00")) not in {"00", ""} or data.get("success") is False:
        return {"success": True}

    payment_status = str(data.get("status") or data.get("paymentStatus") or "").upper()
    if payment_status and payment_status not in {"PAID", "SUCCESS", "COMPLETED"}:
        logging.info("PAYOS_NON_PAYMENT orderCode=%s status=%s", raw_order_code, payment_status)
        return {"success": True, "message": "Payment is not completed"}

    if not raw_order_code:
        return {"success": True, "message": "Ping received without orderCode"}

    try:
        order_code = int(raw_order_code)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(400, "Webhook thiếu orderCode") from exc

    con = db()
    topup = con.execute("SELECT * FROM topups WHERE order_code=?", (order_code,)).fetchone()
    con.close()

    if not topup:
        # For test webhook verification from PayOS dashboard or test order codes
        logging.warning("PAYOS_UNKNOWN_ORDER orderCode=%s", order_code)
        return {"success": True, "message": f"Order {order_code} acknowledged"}

    if topup["status"] in {"approved", "paid", "completed"}:
        logging.info("PAYOS_WEBHOOK_DUPLICATE orderCode=%s", order_code)
        return {"success": True}

    webhook_amount = _webhook_amount(data)
    webhook_link_id = data.get("paymentLinkId") or data.get("payment_link_id")
    if topup["payment_link_id"] and webhook_link_id and str(topup["payment_link_id"]) != str(webhook_link_id):
        logging.warning("PAYOS_PAYMENT_LINK_MISMATCH orderCode=%s topup_id=%s", order_code, topup["id"])
        con = db(); con.execute("UPDATE topups SET needs_review=1 WHERE id=? AND status IN ('pending','pending_payment')", (topup["id"],)); con.commit(); con.close()
        return {"success": True, "message": "Payment link mismatch requires review"}
    if webhook_amount is None or webhook_amount != int(topup["amount_vnd"]):
        logging.warning("PAYOS_AMOUNT_MISMATCH orderCode=%s topup_id=%s expected=%s received=%s",
                        order_code, topup["id"], topup["amount_vnd"], webhook_amount)
        con = db()
        con.execute("UPDATE topups SET needs_review=1 WHERE id=? AND status IN ('pending','pending_payment')", (topup["id"],))
        con.commit(); con.close()
        return {"success": True, "message": "Amount mismatch requires review"}

    # Reuse the same idempotent settlement path as admin approval.
    approve_topup(topup["id"], request, _internal=True,
                  verified_amount=webhook_amount,
                  payment_reference=data.get("reference"),
                  payment_link_id=webhook_link_id)
    logging.info("TOPUP_AUTO_CREDITED topup_id=%s user_id=%s credits=%s",
                 topup["id"], topup["user_id"], topup["credits"])
    return {"success": True}

@app.get("/api/payments/cancel")
async def payos_payment_cancel(request: Request):
    raw_order_code = request.query_params.get("orderCode") or request.query_params.get("order_code")
    if raw_order_code:
        try:
            order_code = int(raw_order_code)
        except (TypeError, ValueError):
            order_code = None
        if order_code is not None:
            con = db()
            changed = con.execute(
                "UPDATE topups SET status='cancelled',cancelled_at=?,reviewed_at=? "
                "WHERE order_code=? AND status IN ('pending','pending_payment')",
                (now_iso(), now_iso(), order_code),
            ).rowcount
            con.commit()
            con.close()
            if changed:
                logging.info("PAYOS_PAYMENT_CANCELLED orderCode=%s", order_code)
    return RedirectResponse("/app#wallet", status_code=303)

@app.get("/api/topups")
def my_topups(request: Request):
    u = current_user(request)
    con = db()
    rows = con.execute("SELECT *, CASE WHEN order_code IS NOT NULL THEN 'PAYOS' ELSE 'MANUAL' END payment_method "
                       "FROM topups WHERE user_id=? ORDER BY id DESC", (u["id"],)).fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.get("/api/topups/{topup_id}")
def my_topup_status(topup_id: int, request: Request):
    u = current_user(request)
    con = db()
    row = con.execute("SELECT * FROM topups WHERE id=? AND user_id=?", (topup_id, u["id"])).fetchone()
    con.close()
    if not row:
        raise HTTPException(404, "Không tìm thấy giao dịch")
    return {
        "id": row["id"], "status": row["status"], "credits": row["credits"],
        "amount_vnd": row["amount_vnd"], "paid_at": row["paid_at"],
        "payment_reference": row["payment_reference"],
        "payment_method": "PAYOS" if row["order_code"] else "MANUAL",
        "cancelled_at": row["cancelled_at"],
    }


# ---------- AFFILIATE / REFERRAL ----------
@app.get("/api/affiliate/summary")
def affiliate_summary(request: Request):
    u = current_user(request)
    con = db()
    code = ensure_user_referral_code(con, u["id"])
    user_row = con.execute(
        "SELECT id,referral_code,referred_by_user_id FROM users WHERE id=?", (u["id"],)
    ).fetchone()
    direct_count = con.execute(
        "SELECT COUNT(*) c FROM users WHERE referred_by_user_id=?", (u["id"],)
    ).fetchone()["c"]
    paying_count = con.execute("""
        SELECT COUNT(DISTINCT child.id) c
        FROM users child
        JOIN topups t ON t.user_id=child.id AND t.status IN ('approved','paid','completed')
        WHERE child.referred_by_user_id=?
    """, (u["id"],)).fetchone()["c"]
    tier = affiliate_tier(con, u["id"])
    settings = affiliate_settings(con)
    totals = affiliate_totals(con, u["id"])
    referrer = None
    if user_row["referred_by_user_id"]:
        referrer = con.execute(
            "SELECT id,name,email,referral_code FROM users WHERE id=?",
            (user_row["referred_by_user_id"],)
        ).fetchone()
    con.commit()
    con.close()

    base_url = str(request.base_url).rstrip("/")
    if tier["next_sales_credits"]:
        progress = min(100, round(tier["sales_credits"] / tier["next_sales_credits"] * 100, 1))
        remaining = max(0, tier["next_sales_credits"] - tier["sales_credits"])
    else:
        progress = 100
        remaining = 0

    return {
        "referral_code": code,
        "referral_link": f"{base_url}/referral?ref={code}",
        "direct_referrals": direct_count,
        "paying_referrals": paying_count,
        "tier": tier,
        "total_rewards": totals["money_approved_vnd"],
        "available": totals["money_due_vnd"],
        "paid": totals["money_paid_vnd"],
        "available_vnd": totals["money_due_vnd"],
        "money_pending_vnd": totals["money_pending_vnd"],
        "money_approved_vnd": totals["money_approved_vnd"],
        "money_paid_vnd": totals["money_paid_vnd"],
        "reward_pending_credits": totals["reward_pending_credits"],
        "reward_approved_credits": totals["reward_approved_credits"],
        "next_payout_date": next_affiliate_payout_date(),
        "vnd_per_credit": AFFILIATE_VND_PER_CREDIT,
        "progress_percent": progress,
        "credits_to_gold": remaining,
        "referrer": dict(referrer) if referrer else None,
        "can_apply_code": not bool(user_row["referred_by_user_id"]),
        "buyer_bonus_percent": settings["buyer_bonus_percent"] if settings["enabled"] else 0,
        "reward_program_active": bool(settings["enabled"]),
        "commission_rates": {
            "silver_percent": settings["silver_rate_percent"],
            "gold_percent": settings["gold_rate_percent"],
            "buyer_bonus_percent": settings["buyer_bonus_percent"],
            "gold_threshold_credits": settings["gold_threshold_credits"],
            "parent_override_percent": settings["parent_override_percent"],
        },
    }

@app.get("/api/referrals")
def my_referrals(request: Request):
    u = current_user(request)
    con = db()
    rows = con.execute(
        "SELECT id,name,email,created_at FROM users WHERE referred_by_user_id=? ORDER BY id DESC LIMIT 100",
        (u["id"],)
    ).fetchall()

    def masked_email(value: str):
        value = (value or "").strip()
        if "@" not in value:
            return "—"
        local, domain = value.split("@", 1)
        if len(local) <= 2:
            shown = local[:1] + "***"
        else:
            shown = local[:2] + "***" + local[-1:]
        return f"{shown}@{domain}"

    result = []
    for r in rows:
        qualified = con.execute(
            "SELECT 1 FROM topups WHERE user_id=? AND status IN ('approved','paid','completed') LIMIT 1",
            (r["id"],)
        ).fetchone()
        reward = con.execute(
            "SELECT COALESCE(SUM(amount_vnd),0) total FROM affiliate_commissions WHERE user_id=? AND source_user_id=?",
            (u["id"], r["id"])
        ).fetchone()["total"] or 0
        sales_vnd = con.execute(
            "SELECT COALESCE(SUM(amount_vnd),0) total FROM topups WHERE user_id=? AND status IN ('approved','paid','completed')",
            (r["id"],)
        ).fetchone()["total"] or 0
        status = "Đã nhận thưởng" if reward > 0 else "Đủ điều kiện" if qualified else "Đã đăng ký"
        result.append({
            "id": r["id"], "name": r["name"], "email_masked": masked_email(r["email"]),
            "created_at": r["created_at"], "status": status,
            "sales_vnd": int(sales_vnd), "commission_vnd": int(reward),
        })
    con.close()
    return result

@app.post("/api/affiliate/apply-code")
async def affiliate_apply_code(request: Request):
    u = current_user(request)
    body = await request.json()
    code = (body.get("code") or "").strip().lower()
    if not code:
        raise HTTPException(400, "Hãy nhập mã giới thiệu")

    con = db()
    try:
        con.execute("BEGIN IMMEDIATE")
        me_row = con.execute(
            "SELECT id,referred_by_user_id,referral_code FROM users WHERE id=?", (u["id"],)
        ).fetchone()
        if me_row["referred_by_user_id"]:
            raise HTTPException(409, "Tài khoản đã có người giới thiệu; không tạo reward mới")
        referrer = find_referrer_by_code(con, code)
        if not referrer:
            raise HTTPException(404, "Mã giới thiệu không tồn tại")
        if referrer["id"] == u["id"]:
            raise HTTPException(400, "Không thể nhập mã của chính mình")

        con.execute(
            "UPDATE users SET referred_by_user_id=?,referred_at=? WHERE id=? AND referred_by_user_id IS NULL",
            (referrer["id"], now_iso(), u["id"])
        )
        con.commit()
        return {"ok": True, "referrer_name": referrer["name"], "rewards_created": 0}
    except HTTPException:
        con.rollback()
        raise
    finally:
        con.close()

@app.get("/api/affiliate/rewards")
def affiliate_rewards(request: Request):
    u = current_user(request)
    con = db()
    rows = con.execute("""
         SELECT r.*, src.name AS source_name, src.email AS source_email,
             COALESCE(t.credits, 0) AS source_credits
        FROM affiliate_rewards r
        JOIN users src ON src.id=r.source_user_id
         LEFT JOIN topups t ON t.id=r.topup_id
        WHERE r.user_id=?
        ORDER BY r.id DESC LIMIT 100
    """, (u["id"],)).fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.get("/api/affiliate/withdrawals")
def affiliate_withdrawals(request: Request):
    u = current_user(request)
    con = db()
    rows = con.execute("""
        SELECT * FROM affiliate_withdrawals
        WHERE user_id=? ORDER BY id DESC LIMIT 100
    """, (u["id"],)).fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.get("/api/affiliate/wallet")
def affiliate_wallet(request: Request):
    u = current_user(request)
    con = db()
    totals = affiliate_totals(con, u["id"])
    commissions = con.execute("""
        SELECT c.*, src.name AS source_name, src.email AS source_email,
               t.package, t.amount_vnd AS topup_amount_vnd
        FROM affiliate_commissions c
        JOIN users src ON src.id=c.source_user_id
        JOIN topups t ON t.id=c.topup_id
        WHERE c.user_id=? ORDER BY c.id DESC LIMIT 100
    """, (u["id"],)).fetchall()
    rewards = con.execute("""
        SELECT r.*, src.name AS source_name, src.email AS source_email
        FROM affiliate_rewards r
        JOIN users src ON src.id=r.source_user_id
        WHERE r.user_id=? ORDER BY r.id DESC LIMIT 100
    """, (u["id"],)).fetchall()
    legacy_conversions = con.execute("SELECT * FROM affiliate_wallet_transactions WHERE user_id=? ORDER BY id DESC LIMIT 100", (u["id"],)).fetchall()
    legacy_withdrawals = con.execute("SELECT * FROM affiliate_withdrawals WHERE user_id=? ORDER BY id DESC LIMIT 100", (u["id"],)).fetchall()
    con.close()
    return {
        "money_pending_vnd": totals["money_pending_vnd"],
        "money_approved_vnd": totals["money_approved_vnd"],
        "money_paid_vnd": totals["money_paid_vnd"],
        "money_due_vnd": totals["money_due_vnd"],
        "reward_pending_credits": totals["reward_pending_credits"],
        "reward_approved_credits": totals["reward_approved_credits"],
        "vnd_per_credit": AFFILIATE_VND_PER_CREDIT,
        "commissions": [dict(row) for row in commissions],
        "rewards": [dict(row) for row in rewards],
        "legacy_conversions": [dict(row) for row in legacy_conversions],
        "legacy_withdrawals": [dict(row) for row in legacy_withdrawals],
    }

@app.post("/api/affiliate/convert")
async def affiliate_convert(request: Request):
    current_user(request)
    raise HTTPException(410, "Đổi Affiliate sang Xu đã được tắt; Xu thưởng Affiliate được Admin duyệt riêng")

@app.post("/api/affiliate/withdrawals")
async def affiliate_request_withdrawal(request: Request):
    current_user(request)
    raise HTTPException(410, "Affiliate được thanh toán định kỳ vào ngày 25; vui lòng liên hệ Admin nếu cần hỗ trợ")


# ---------- ADMIN ----------
@app.get("/api/admin/security-logs")
def admin_security_logs(request: Request):
    require_admin(request)
    try:
        page = max(1, int(request.query_params.get("page", "1")))
        limit = min(100, max(1, int(request.query_params.get("limit", "50"))))
    except ValueError:
        raise HTTPException(400, "Phân trang không hợp lệ")
    event = request.query_params.get("event", "").strip()[:80]
    severity = request.query_params.get("severity", "").strip()[:20].lower()
    severity_min = request.query_params.get("severity_min", "").strip()[:20].lower()
    email = request.query_params.get("email", "").strip()[:200]
    ip = request.query_params.get("ip", "").strip()[:100]
    search = request.query_params.get("search", "").strip()[:200]
    clauses, values = ["NOT (event='admin_access' AND LOWER(severity)='info' AND http_status=200)"], []
    for field, value in (("event", event), ("severity", severity), ("email", email), ("ip_address", ip)):
        if value:
            clauses.append(f"{field} LIKE ?")
            values.append(f"%{value}%")
    if search:
        clauses.append("(email LIKE ? OR ip_address LIKE ?)")
        values.extend([f"%{search}%", f"%{search}%"])
    if severity_min in {"info", "notice", "warning", "high", "critical"}:
        severity_order = {"info": 10, "notice": 20, "warning": 30, "high": 40, "critical": 50}
        clauses.append("CASE LOWER(severity) WHEN 'info' THEN 10 WHEN 'notice' THEN 20 WHEN 'warning' THEN 30 WHEN 'high' THEN 40 WHEN 'critical' THEN 50 ELSE 0 END >= ?")
        values.append(severity_order[severity_min])
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    con = db()
    total = con.execute("SELECT COUNT(*) AS count FROM security_logs" + where, values).fetchone()["count"]
    rows = con.execute(
        "SELECT * FROM security_logs" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
        (*values, limit, (page - 1) * limit),
    ).fetchall()
    timezone_name = request.query_params.get("timezone", "").strip()[:80]
    try:
        local_zone = ZoneInfo(timezone_name or os.getenv("APP_TIMEZONE", "Asia/Ho_Chi_Minh"))
    except Exception:
        local_zone = ZoneInfo("Asia/Ho_Chi_Minh")
    local_today = datetime.now(local_zone).date()
    start_local = datetime.combine(local_today, datetime.min.time(), local_zone)
    end_local = start_local + timedelta(days=1)
    start_utc, end_utc = start_local.astimezone(timezone.utc).isoformat(), end_local.astimezone(timezone.utc).isoformat()
    stats = {
        "logins_today": con.execute("SELECT COUNT(*) AS count FROM security_logs WHERE event='google_login_success' AND created_at>=? AND created_at<?", (start_utc, end_utc)).fetchone()["count"],
        "new_ips_today": con.execute("SELECT COUNT(*) AS count FROM security_logs WHERE event='new_ip_login' AND created_at>=? AND created_at<?", (start_utc, end_utc)).fetchone()["count"],
        "warnings_today": con.execute("SELECT COUNT(*) AS count FROM security_logs WHERE LOWER(severity)='warning' AND created_at>=? AND created_at<?", (start_utc, end_utc)).fetchone()["count"],
        "danger_today": con.execute("SELECT COUNT(*) AS count FROM security_logs WHERE LOWER(severity) IN ('high','critical') AND created_at>=? AND created_at<?", (start_utc, end_utc)).fetchone()["count"],
    }
    con.close()
    return {"page": page, "limit": limit, "total": total, "stats": stats, "items": [dict(row) for row in rows]}

@app.get("/api/admin/security-devices")
def admin_security_devices(request: Request):
    require_admin(request)
    con = db()
    rows = con.execute("""
        WITH activity AS (
            SELECT id AS row_id, user_id, email, role, visitor_id, ip_address, user_agent,
                   created_at, event, severity, http_status,
                    CASE WHEN visitor_id IS NOT NULL
                        THEN 'visitor:' || visitor_id
                        ELSE 'user:' || user_id || ':' || ip_address || ':' || COALESCE(user_agent, '') END AS identity_key
            FROM security_logs
            WHERE NOT (event='admin_access' AND LOWER(severity)='info' AND http_status=200)
            UNION ALL
            SELECT l.id AS row_id, l.user_id, u.email, u.role, l.visitor_id, l.ip_address, l.user_agent,
                   l.created_at, NULL AS event, NULL AS severity, l.status_code AS http_status,
                    CASE WHEN l.visitor_id IS NOT NULL
                        THEN 'visitor:' || l.visitor_id
                        ELSE 'user:' || l.user_id || ':' || l.ip_address || ':' || COALESCE(l.user_agent, '') END AS identity_key
            FROM admin_access_logs l
            LEFT JOIN users u ON u.id=l.user_id
        ), summary AS (
            SELECT identity_key, MAX(created_at) AS last_seen, MIN(created_at) AS first_seen,
                   COUNT(*) AS request_count,
                   SUM(CASE WHEN event='google_login_success' THEN 1 ELSE 0 END) AS login_count,
                   SUM(CASE WHEN LOWER(severity) IN ('warning','high','critical') THEN 1 ELSE 0 END) AS warning_count,
                   SUM(CASE WHEN event IN ('new_ip_login','new_device_login') THEN 1 ELSE 0 END) AS new_event_count,
                   SUM(CASE WHEN LOWER(severity) IN ('high','critical') OR event IN ('admin_access_denied','security_rate_limited') OR http_status IN (401,403,429) THEN 1 ELSE 0 END) AS danger_count,
                   GROUP_CONCAT(DISTINCT email) AS account_emails,
                   COUNT(DISTINCT email) AS account_count
            FROM activity GROUP BY identity_key
        ), latest AS (
            SELECT activity.*, ROW_NUMBER() OVER (PARTITION BY identity_key ORDER BY created_at DESC, row_id DESC) AS rank
            FROM activity
        )
        SELECT latest.email, latest.role, latest.visitor_id, latest.ip_address, latest.user_agent,
               summary.first_seen, summary.last_seen, summary.request_count, summary.login_count,
               summary.warning_count, summary.new_event_count, summary.danger_count, summary.account_emails,
               summary.account_count, latest.event AS last_event
        FROM latest JOIN summary ON summary.identity_key=latest.identity_key
        WHERE latest.rank=1
        ORDER BY summary.last_seen DESC LIMIT 100
    """).fetchall()
    con.close()
    return [dict(row) for row in rows]

@app.get("/api/admin/access-logs")
def admin_access_logs(request: Request):
    require_admin(request)
    try:
        page = max(1, int(request.query_params.get("page", "1")))
        limit = min(100, max(1, int(request.query_params.get("limit", "50"))))
    except ValueError:
        raise HTTPException(400, "Phân trang không hợp lệ")
    search = request.query_params.get("search", "").strip()[:200]
    clauses, values = [], []
    if search:
        clauses.append("(u.email LIKE ? OR l.ip_address LIKE ? OR l.path LIKE ? OR l.method LIKE ?)")
        values.extend([f"%{search}%"] * 4)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    con = db()
    total = con.execute(
        "SELECT COUNT(*) AS count FROM admin_access_logs l LEFT JOIN users u ON u.id=l.user_id" + where,
        values,
    ).fetchone()["count"]
    rows = con.execute(
        "SELECT l.*,u.email FROM admin_access_logs l "
        "LEFT JOIN users u ON u.id=l.user_id" + where + " ORDER BY l.id DESC LIMIT ? OFFSET ?",
        (*values, limit, (page - 1) * limit),
    ).fetchall()
    con.close()
    return {"page": page, "limit": limit, "total": total, "items": [dict(row) for row in rows]}

@app.get("/api/admin/stats")
def admin_stats(request: Request):
    require_admin(request)
    con = db()
    stats = {
        "users": con.execute("SELECT COUNT(*) c FROM users").fetchone()["c"],
        "waiting": con.execute("SELECT COUNT(*) c FROM jobs WHERE status='waiting'").fetchone()["c"],
        "running": con.execute("SELECT COUNT(*) c FROM jobs WHERE status='running'").fetchone()["c"],
        "done": con.execute("SELECT COUNT(*) c FROM jobs WHERE status='done'").fetchone()["c"],
        "pending_topups": con.execute("SELECT COUNT(*) c FROM topups WHERE status='pending' AND order_code IS NULL").fetchone()["c"],
        "pending_withdrawals": con.execute("SELECT COUNT(*) c FROM affiliate_withdrawals WHERE status='pending'").fetchone()["c"],
        "affiliate_rewards": round(float(con.execute("SELECT COALESCE(SUM(amount_credits),0) c FROM affiliate_rewards").fetchone()["c"] or 0), 2),
    }
    con.close()
    return stats

@app.get("/api/admin/overview")
def admin_overview(request: Request):
    require_admin(request)
    con = db()
    now = datetime.now(timezone.utc)
    ranges = {}
    for label, days in (("today", 1), ("seven_days", 7), ("thirty_days", 30)):
        since = (now - timedelta(days=days)).isoformat()
        ranges[label] = con.execute("SELECT COUNT(*) c FROM users WHERE created_at>=?", (since,)).fetchone()["c"]
    status_rows = con.execute("SELECT status,COUNT(*) c FROM jobs GROUP BY status").fetchall()
    tool_rows = con.execute("SELECT COALESCE(NULLIF(service,''), 'motion_studio') service,COUNT(*) c FROM jobs GROUP BY service ORDER BY c DESC").fetchall()
    revenue = con.execute("SELECT COALESCE(SUM(amount_vnd),0) total FROM topups WHERE status IN ('approved','paid')").fetchone()["total"]
    result = {
        "users_total": con.execute("SELECT COUNT(*) c FROM users WHERE role!='admin'").fetchone()["c"],
        "new_users": ranges,
        "credits_circulating": con.execute("SELECT COALESCE(SUM(credits),0) total FROM users WHERE role!='admin'").fetchone()["total"],
        "topup_revenue_vnd": revenue,
        "jobs_total": con.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"],
        "job_status": {row["status"]: row["c"] for row in status_rows},
        "top_tools": [dict(row) for row in tool_rows[:5]],
    }
    con.close()
    return result

@app.get("/api/admin/users")
def admin_users(request: Request):
    require_admin(request)
    con = db()
    q = (request.query_params.get("q") or "").strip()[:120]
    if q:
        like = f"%{q}%"
        rows = con.execute("SELECT id,email,name,credits,role,is_locked,created_at FROM users WHERE CAST(id AS TEXT)=? OR email LIKE ? OR name LIKE ? ORDER BY id DESC LIMIT 200", (q, like, like)).fetchall()
    else:
        rows = con.execute("SELECT id,email,name,credits,role,is_locked,created_at FROM users ORDER BY id DESC LIMIT 200").fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.get("/api/admin/users/{user_id}")
def admin_user_detail(user_id: int, request: Request):
    require_admin(request)
    con = db()
    user = con.execute("SELECT id,email,name,credits,role,is_locked,created_at FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        con.close(); raise HTTPException(404, "Không tìm thấy người dùng")
    ledger = con.execute("SELECT id,delta,reason,ref_type,ref_id,created_at FROM credit_ledger WHERE user_id=? ORDER BY id DESC LIMIT 100", (user_id,)).fetchall()
    jobs = con.execute("SELECT id,service,model,cost,status,progress,error,created_at,updated_at,input_json,output_path FROM jobs WHERE user_id=? ORDER BY id DESC LIMIT 100", (user_id,)).fetchall()
    con.close()
    return {"user": dict(user), "ledger": [dict(x) for x in ledger], "jobs": [dict(x) for x in jobs]}

@app.post("/api/admin/users/{user_id}/lock")
async def admin_lock_user(user_id: int, request: Request):
    require_admin(request)
    body = await request.json()
    locked = 1 if body.get("locked", True) else 0
    con = db()
    changed = con.execute("UPDATE users SET is_locked=? WHERE id=? AND role!='admin'", (locked, user_id)).rowcount
    con.commit(); con.close()
    if not changed: raise HTTPException(404, "Không thể khóa tài khoản này")
    return {"ok": True, "is_locked": bool(locked)}

@app.get("/api/admin/transactions")
def admin_transactions(request: Request):
    require_admin(request)
    con = db()
    rows = con.execute("""SELECT t.id,t.user_id,u.email,u.name,t.package,t.amount_vnd,t.credits,t.order_code,
        CASE WHEN t.order_code IS NOT NULL THEN 'PAYOS' ELSE 'MANUAL' END payment_method,
        t.status,t.created_at,t.reviewed_at,t.cancelled_at
        FROM topups t JOIN users u ON u.id=t.user_id ORDER BY t.id DESC LIMIT 300""").fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.get("/api/admin/tools")
def admin_tools(request: Request):
    require_admin(request)
    con = db(); rows = con.execute("SELECT * FROM admin_tools ORDER BY sort_order,service_key").fetchall(); con.close()
    return [dict(r) for r in rows]

@app.get("/api/tools")
def public_tools():
    con = db()
    rows = con.execute("SELECT service_key,name,description,thumbnail,badge,price_credits,is_free,cta_text,enabled,sort_order FROM admin_tools WHERE enabled=1 ORDER BY sort_order,service_key").fetchall()
    con.close()
    return [dict(row) for row in rows]

@app.put("/api/admin/tools/{service_key}")
async def update_admin_tool(service_key: str, request: Request):
    require_admin(request)
    body = await request.json()
    allowed = {"name","description","thumbnail","badge","price_credits","is_free","cta_text","enabled","sort_order"}
    updates = {key: body[key] for key in allowed if key in body}
    if not updates: raise HTTPException(400, "Không có thay đổi")
    updates["updated_at"] = now_iso()
    con = db()
    assignments = ",".join(f"{key}=?" for key in updates)
    changed = con.execute(f"UPDATE admin_tools SET {assignments} WHERE service_key=?", (*updates.values(), service_key)).rowcount
    con.commit(); row = con.execute("SELECT * FROM admin_tools WHERE service_key=?", (service_key,)).fetchone(); con.close()
    if not changed or not row: raise HTTPException(404, "Không tìm thấy công cụ")
    return {"ok": True, "tool": dict(row)}

@app.get("/api/admin/jobs")
def admin_jobs(request: Request):
    require_admin(request)
    con = db()
    rows = con.execute("""
        SELECT j.*,u.email FROM jobs j JOIN users u ON u.id=j.user_id ORDER BY j.id DESC LIMIT 200
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.get("/api/admin/topups")
def admin_topups(request: Request):
    require_admin(request)
    con = db()
    rows = con.execute("""
         SELECT t.*,u.email,u.name,
             CASE WHEN t.order_code IS NOT NULL THEN 'PAYOS' ELSE 'MANUAL' END payment_method
         FROM topups t JOIN users u ON u.id=t.user_id ORDER BY t.id DESC LIMIT 200
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.post("/api/admin/topups/{topup_id}/sync")
def sync_admin_topup(topup_id: int, request: Request):
    require_admin(request)
    con = db()
    row = con.execute("SELECT id,status,order_code FROM topups WHERE id=?", (topup_id,)).fetchone()
    con.close()
    if not row:
        raise HTTPException(404, "Không tìm thấy giao dịch")
    if row["status"] in {"approved", "paid", "completed"}:
        return {"ok": True, "status": row["status"], "settled": True}
    payment = payos_payment_status(row["order_code"]) if row["order_code"] else None
    status = payment["status"] if payment else None
    if payment and status == "PAID" and payment["amount"] == int(row["amount_vnd"]):
        approve_topup(topup_id, request, _internal=True, verified_amount=payment["amount"],
                      payment_reference=payment["reference"], payment_link_id=payment["payment_link_id"])
        return {"ok": True, "status": "paid", "settled": True}
    return {"ok": True, "status": row["status"], "payos_status": status,
            "payos_amount": payment["amount"] if payment else None, "settled": False}

@app.post("/api/admin/topups/{topup_id}/approve")
def approve_topup(topup_id: int, request: Request, _internal: bool = False,
                  verified_amount: int | None = None, payment_reference: str | None = None,
                  payment_link_id: str | None = None):
    if not _internal:
        require_admin(request)
    con = db()
    con.execute("BEGIN IMMEDIATE")
    t = con.execute("SELECT * FROM topups WHERE id=?", (topup_id,)).fetchone()
    if not t:
        con.rollback(); con.close()
        raise HTTPException(404, "Không tìm thấy yêu cầu")
    if t["status"] not in {"pending", "pending_payment"}:
        con.rollback(); con.close()
        raise HTTPException(409, "Yêu cầu đã xử lý")
    if t["order_code"]:
        if not _internal:
            con.rollback(); con.close()
            raise HTTPException(409, "PayOS được xử lý tự động, không thể duyệt thủ công")

    if _internal and (verified_amount is None or int(verified_amount) != int(t["amount_vnd"])):
        con.execute("UPDATE topups SET needs_review=1 WHERE id=?", (topup_id,))
        con.commit(); con.close()
        raise HTTPException(400, "Số tiền thanh toán không khớp")

    buyer = con.execute(
        "SELECT id,referred_by_user_id FROM users WHERE id=?", (t["user_id"],)
    ).fetchone()
    settings = affiliate_settings(con)
    buyer_bonus_rate = float(settings["buyer_bonus_percent"]) / 100
    prior_topup = con.execute(
        "SELECT 1 FROM topups WHERE user_id=? AND id<>? AND status IN ('approved','paid','completed') LIMIT 1",
        (t["user_id"], topup_id),
    ).fetchone()
    prior_buyer_bonus = con.execute(
        "SELECT 1 FROM affiliate_rewards WHERE user_id=? AND reward_type='buyer_bonus' LIMIT 1",
        (t["user_id"],),
    ).fetchone()
    # Buyer bonus is a separate Affiliate reward and is only created once, on first topup.
    buyer_bonus = int(round(t["credits"] * buyer_bonus_rate)) if (
        settings["enabled"] and buyer["referred_by_user_id"] and not prior_topup and not prior_buyer_bonus
    ) else 0

    # Mark approved first so tier calculations include this transaction.
    settlement_status = "paid" if _internal else "approved"
    con.execute("""UPDATE topups SET status=?,reviewed_at=?,paid_at=?,payment_reference=? ,
                   payment_link_id=COALESCE(?,payment_link_id),needs_review=0 WHERE id=?""",
                (settlement_status, now_iso(), now_iso(), payment_reference, payment_link_id, topup_id))
    con.execute("UPDATE users SET credits=credits+? WHERE id=?", (t["credits"], t["user_id"]))
    con.execute("""
        INSERT INTO credit_ledger(user_id,delta,reason,ref_type,ref_id,created_at)
        VALUES(?,?,?,?,?,?)
    """, (t["user_id"], t["credits"], f"Nạp gói {t['package']}", "topup", topup_id, now_iso()))

    if buyer_bonus:
        con.execute("""
            INSERT OR IGNORE INTO affiliate_rewards(
                user_id,source_user_id,topup_id,reward_type,amount_credits,rate,status,created_at
            ) VALUES(?,?,?,?,?,?,?,?)
        """, (
            t["user_id"], t["user_id"], topup_id, "buyer_bonus", buyer_bonus,
            buyer_bonus_rate, "pending", now_iso()
        ))

    direct_commission = 0.0
    direct_commission_vnd = 0
    override_commission = 0.0
    override_commission_vnd = 0
    if settings["enabled"] and buyer["referred_by_user_id"]:
        referrer_id = buyer["referred_by_user_id"]
        tier = affiliate_tier(con, referrer_id)
        direct_commission_vnd = affiliate_commission_vnd(t["amount_vnd"], tier["rate"])
        direct_commission = direct_commission_vnd
        con.execute("""
            INSERT OR IGNORE INTO affiliate_commissions(
                user_id,source_user_id,topup_id,commission_type,amount_vnd,rate,status,created_at
            ) VALUES(?,?,?,?,?,?,?,?)
        """, (
            referrer_id, t["user_id"], topup_id, "direct",
            direct_commission_vnd, tier["rate"], "pending", now_iso()
        ))

        # Gold partners receive 50% override on commission earned by their direct affiliate.
        parent = con.execute(
            "SELECT referred_by_user_id FROM users WHERE id=?", (referrer_id,)
        ).fetchone()
        if parent and parent["referred_by_user_id"]:
            parent_id = parent["referred_by_user_id"]
            parent_tier = affiliate_tier(con, parent_id)
            if parent_tier["key"] == "gold":
                override_rate = float(settings["parent_override_percent"]) / 100
                override_commission_vnd = int(round(direct_commission_vnd * override_rate))
                override_commission = override_commission_vnd
                con.execute("""
                    INSERT OR IGNORE INTO affiliate_commissions(
                        user_id,source_user_id,topup_id,commission_type,amount_vnd,rate,status,created_at
                    ) VALUES(?,?,?,?,?,?,?,?)
                """, (
                    parent_id, referrer_id, topup_id, "tier_override",
                    override_commission_vnd, float(settings["parent_override_percent"]) / 100, "pending", now_iso()
                ))

    con.commit()
    con.close()
    return {
        "ok": True,
        "buyer_bonus": buyer_bonus,
        "direct_commission": direct_commission_vnd,
        "direct_commission_vnd": direct_commission_vnd,
        "override_commission": override_commission,
        "override_commission_vnd": override_commission_vnd,
    }

@app.post("/api/admin/topups/{topup_id}/reject")
def reject_topup(topup_id: int, request: Request):
    require_admin(request)
    con = db()
    row = con.execute("SELECT status,order_code FROM topups WHERE id=?", (topup_id,)).fetchone()
    if row and row["order_code"]:
        con.close()
        raise HTTPException(409, "PayOS được xử lý tự động, không thể từ chối thủ công")
    con.execute("UPDATE topups SET status='rejected',reviewed_at=? WHERE id=? AND status='pending'", (now_iso(), topup_id))
    con.commit()
    con.close()
    return {"ok": True}

@app.post("/api/admin/users/{user_id}/credits")
async def admin_add_credits(user_id: int, request: Request):
    require_admin(request)
    body = await request.json()
    delta = int(body.get("delta", 0))
    reason = (body.get("reason") or "Admin điều chỉnh")[:200]
    if delta == 0 or abs(delta) > 1_000_000:
        raise HTTPException(400, "Số lượt không hợp lệ")
    con = db()
    con.execute("UPDATE users SET credits=MAX(0,credits+?) WHERE id=?", (delta, user_id))
    con.execute(
        "INSERT INTO credit_ledger(user_id,delta,reason,ref_type,created_at) VALUES(?,?,?,?,?)",
        (user_id, delta, reason, "admin", now_iso())
    )
    con.commit()
    con.close()
    return {"ok": True}


@app.get("/api/admin/affiliate/users")
def admin_affiliate_users(request: Request):
    require_admin(request)
    con = db()
    users = con.execute("""
        SELECT id,email,name,referral_code,referred_by_user_id,created_at
        FROM users WHERE role!='admin' ORDER BY id DESC LIMIT 300
    """).fetchall()
    result = []
    for row in users:
        tier = affiliate_tier(con, row["id"])
        totals = affiliate_totals(con, row["id"])
        refs = con.execute(
            "SELECT COUNT(*) c FROM users WHERE referred_by_user_id=?", (row["id"],)
        ).fetchone()["c"]
        referrer = None
        if row["referred_by_user_id"]:
            rr = con.execute("SELECT email,referral_code FROM users WHERE id=?", (row["referred_by_user_id"],)).fetchone()
            referrer = dict(rr) if rr else None
        result.append({
            **dict(row),
            "tier": tier["name"],
            "rate_percent": tier["rate_percent"],
            "sales_credits": tier["sales_credits"],
            "direct_referrals": refs,
            "total_rewards": totals["total_rewards"],
            "available": totals["money_due_vnd"],
            "money_pending_vnd": totals["money_pending_vnd"],
            "money_approved_vnd": totals["money_approved_vnd"],
            "money_paid_vnd": totals["money_paid_vnd"],
            "reward_pending_credits": totals["reward_pending_credits"],
            "reward_approved_credits": totals["reward_approved_credits"],
            "referrer": referrer,
        })
    con.close()
    return result

def affiliate_risk_network(ip: str) -> str:
    try:
        address = ipaddress.ip_address(ip)
        if address.version == 6:
            return str(ipaddress.ip_network(f"{address}/64", strict=False).network_address) + "/64"
        return str(ipaddress.ip_network(f"{address}/24", strict=False).network_address) + "/24"
    except ValueError:
        return ip or "unknown"

def affiliate_risk_device(user_agent: str) -> str:
    return " ".join((user_agent or "").lower().split())

def affiliate_risk_close_login(referrer_rows, referred_rows, minutes=15) -> bool:
    def parse(value):
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    referrer_times = [parse(row["created_at"]) for row in referrer_rows]
    referred_times = [parse(row["created_at"]) for row in referred_rows]
    return any(
        left and right and abs((left - right).total_seconds()) <= minutes * 60
        for left in referrer_times for right in referred_times
    )

def affiliate_risk_level(score: int) -> str:
    if score >= 100:
        return "Nghi ngờ cao"
    if score >= 60:
        return "Nghi ngờ"
    if score >= 30:
        return "Cần theo dõi"
    return "Bình thường"

@app.get("/api/admin/affiliate/risk-reports")
def admin_affiliate_risk_reports(request: Request):
    require_admin(request)
    search = request.query_params.get("search", "").strip().lower()[:200]
    level = request.query_params.get("level", "").strip().lower()[:30]
    con = db()
    users = con.execute("""
        SELECT child.id AS referred_id, child.email AS referred_email, child.created_at AS referred_created_at,
               parent.id AS referrer_id, parent.email AS referrer_email, parent.created_at AS referrer_created_at
        FROM users child JOIN users parent ON parent.id=child.referred_by_user_id
        WHERE child.role!='admin' ORDER BY child.id DESC LIMIT 500
    """).fetchall()
    activity_rows = con.execute("""
        SELECT user_id,visitor_id,ip_address,user_agent,created_at,event
        FROM security_logs WHERE user_id IS NOT NULL
        UNION ALL
        SELECT user_id,visitor_id,ip_address,user_agent,created_at,NULL AS event
        FROM admin_access_logs WHERE user_id IS NOT NULL
        ORDER BY created_at DESC
    """).fetchall()
    all_users = con.execute("SELECT id,email FROM users WHERE role!='admin'").fetchall()
    con.close()
    activity = {}
    for row in activity_rows:
        activity.setdefault(row["user_id"], []).append(dict(row))
    email_by_id = {row["id"]: row["email"] for row in all_users}
    visitor_accounts = {}
    for user_id, rows in activity.items():
        for row in rows:
            if row["visitor_id"]:
                visitor_accounts.setdefault(row["visitor_id"], set()).add(user_id)
    reports = []
    for pair in users:
        referrer = activity.get(pair["referrer_id"], [])
        referred = activity.get(pair["referred_id"], [])
        ref_visitor_ids = {row["visitor_id"] for row in referrer if row["visitor_id"]}
        child_visitor_ids = {row["visitor_id"] for row in referred if row["visitor_id"]}
        ref_ips = {row["ip_address"] for row in referrer if row["ip_address"]}
        child_ips = {row["ip_address"] for row in referred if row["ip_address"]}
        ref_networks = {affiliate_risk_network(ip) for ip in ref_ips}
        child_networks = {affiliate_risk_network(ip) for ip in child_ips}
        ref_devices = {affiliate_risk_device(row["user_agent"]) for row in referrer if row["user_agent"]}
        child_devices = {affiliate_risk_device(row["user_agent"]) for row in referred if row["user_agent"]}
        shared_visitors = ref_visitor_ids & child_visitor_ids
        shared_ips = ref_ips & child_ips
        shared_networks = ref_networks & child_networks
        shared_devices = ref_devices & child_devices
        close_login = affiliate_risk_close_login(referrer, referred)
        score = 0
        reasons = []
        if shared_visitors:
            account_count = max(len(visitor_accounts.get(visitor, set())) for visitor in shared_visitors)
            if account_count >= 3:
                score += 60
                reasons.append(f"Cùng visitor_id liên kết với {account_count} tài khoản và có quan hệ referrer/referred")
            else:
                score += 30
                reasons.append("Cùng visitor_id xuất hiện trên 2 tài khoản có quan hệ referrer/referred")
        elif shared_ips and shared_devices and close_login:
            score += 30
            reasons.append("Visitor khác nhau nhưng cùng IP, browser/device và đăng nhập trong 15 phút")
        elif shared_ips:
            reasons.append("Chỉ cùng IP; visitor và browser/device khác nhau nên không kết luận")
        if shared_devices and not shared_visitors:
            reasons.append("Cùng browser/User-Agent nhưng chưa đủ để kết luận")
        child_time = referred[0]["created_at"] if referred else pair["referred_created_at"]
        ref_time = referrer[0]["created_at"] if referrer else pair["referrer_created_at"]
        report_level = affiliate_risk_level(score)
        haystack = " ".join([pair["referrer_email"], pair["referred_email"], *ref_ips, *child_ips, *ref_visitor_ids, *child_visitor_ids]) .lower()
        if search and search not in haystack:
            continue
        if level and report_level.lower() != level:
            continue
        reports.append({
            "referrer": {"id": pair["referrer_id"], "email": pair["referrer_email"]},
            "referred": {"id": pair["referred_id"], "email": pair["referred_email"]},
            "risk_score": score, "level": report_level, "reasons": reasons or ["Không có tín hiệu rủi ro mạnh"],
            "visitor_ids": sorted(ref_visitor_ids | child_visitor_ids), "ips": sorted(ref_ips | child_ips),
            "networks": sorted(ref_networks | child_networks), "same_device": bool(shared_devices),
            "referrer_device": next(iter(ref_devices), ""), "referred_device": next(iter(child_devices), ""),
            "registered_at": child_time, "login_at": (referred[0]["created_at"] if referred else None),
            "other_accounts": sorted({email_by_id[user_id] for user_id, rows in activity.items() if any(visitor in {r["visitor_id"] for r in rows} for visitor in shared_visitors) if user_id not in {pair["referrer_id"], pair["referred_id"]}}),
        })
    return {"items": reports}

@app.get("/api/admin/affiliate/withdrawals")
def admin_affiliate_withdrawals(request: Request):
    require_admin(request)
    con = db()
    rows = con.execute("""
        SELECT w.*,u.email,u.name
        FROM affiliate_withdrawals w
        JOIN users u ON u.id=w.user_id
        ORDER BY w.id DESC LIMIT 300
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.get("/api/admin/affiliate/rewards")
def admin_affiliate_rewards(request: Request):
    require_admin(request)
    con = db()
    rows = con.execute("""
        SELECT r.*,u.email AS recipient_email,u.name AS recipient_name,
               src.email AS source_email,t.order_code,t.package
        FROM affiliate_rewards r
        JOIN users u ON u.id=r.user_id
        JOIN users src ON src.id=r.source_user_id
        JOIN topups t ON t.id=r.topup_id
        ORDER BY r.id DESC LIMIT 300
    """).fetchall()
    con.close()
    return [dict(row) for row in rows]

@app.get("/api/admin/affiliate/commissions")
def admin_affiliate_commissions(request: Request):
    require_admin(request)
    con = db()
    rows = con.execute("""
        SELECT c.*,u.email AS recipient_email,u.name AS recipient_name,
               src.email AS source_email,t.order_code,t.package,t.amount_vnd AS topup_amount_vnd
        FROM affiliate_commissions c
        JOIN users u ON u.id=c.user_id
        JOIN users src ON src.id=c.source_user_id
        JOIN topups t ON t.id=c.topup_id
        ORDER BY c.id DESC LIMIT 300
    """).fetchall()
    con.close()
    return [dict(row) for row in rows]

@app.get("/api/admin/affiliate/payouts")
def admin_affiliate_payouts(request: Request):
    require_admin(request)
    con = db()
    rows = con.execute("""
        SELECT c.user_id,u.email,u.name,
               SUM(c.amount_vnd) AS approved_vnd,
               COUNT(*) AS commission_count
        FROM affiliate_commissions c
        JOIN users u ON u.id=c.user_id
        WHERE c.status='approved'
        GROUP BY c.user_id,u.email,u.name
        ORDER BY approved_vnd DESC
    """).fetchall()
    con.close()
    return {"payout_date": next_affiliate_payout_date(), "items": [dict(row) for row in rows]}

def next_affiliate_payout_date(now=None):
    current = now or datetime.now(timezone.utc)
    if current.day < 25:
        return current.replace(day=25, hour=0, minute=0, second=0, microsecond=0).date().isoformat()
    year, month = current.year, current.month + 1
    if month == 13:
        year, month = year + 1, 1
    return current.replace(year=year, month=month, day=25, hour=0, minute=0, second=0, microsecond=0).date().isoformat()

@app.post("/api/admin/affiliate/rewards/{reward_id}/approve")
async def approve_affiliate_reward(reward_id: int, request: Request):
    require_admin(request)
    body = await request.json()
    note = (body.get("admin_note") or "")[:300]
    con = db()
    con.execute("BEGIN IMMEDIATE")
    reward = con.execute("SELECT * FROM affiliate_rewards WHERE id=?", (reward_id,)).fetchone()
    if not reward:
        con.rollback(); con.close(); raise HTTPException(404, "Không tìm thấy thưởng referral")
    if reward["status"] != "pending":
        con.rollback(); con.close(); raise HTTPException(409, "Thưởng referral đã được xử lý")
    if reward["reward_type"] == "buyer_bonus":
        con.execute("""
            INSERT OR IGNORE INTO affiliate_reward_credit_ledger(reward_id,user_id,delta,created_at)
            VALUES(?,?,?,?)
        """, (reward_id, reward["user_id"], reward["amount_credits"], now_iso()))
    con.execute("UPDATE affiliate_rewards SET status='approved',reviewed_at=?,admin_note=? WHERE id=?", (now_iso(), note, reward_id))
    con.commit(); con.close()
    return {"ok": True, "status": "approved", "amount_credits": reward["amount_credits"], "credited_to_service": False}

@app.post("/api/admin/affiliate/rewards/{reward_id}/reject")
async def reject_affiliate_reward(reward_id: int, request: Request):
    require_admin(request)
    body = await request.json()
    note = (body.get("admin_note") or "")[:300]
    con = db()
    changed = con.execute("UPDATE affiliate_rewards SET status='rejected',reviewed_at=?,admin_note=? WHERE id=? AND status='pending'", (now_iso(), note, reward_id)).rowcount
    con.commit(); con.close()
    if not changed: raise HTTPException(409, "Thưởng referral không còn pending")
    return {"ok": True, "status": "rejected"}

@app.get("/api/admin/affiliate/settings")
def admin_affiliate_settings(request: Request):
    require_admin(request)
    con = db()
    settings = affiliate_settings(con)
    con.close()
    return settings

@app.put("/api/admin/affiliate/settings")
async def update_admin_affiliate_settings(request: Request):
    require_admin(request)
    body = await request.json()
    try:
        values = {
            "enabled": 1 if body.get("enabled", True) else 0,
            "silver_rate_percent": float(body.get("silver_rate_percent")),
            "gold_rate_percent": float(body.get("gold_rate_percent")),
            "buyer_bonus_percent": float(body.get("buyer_bonus_percent")),
            "gold_threshold_credits": int(body.get("gold_threshold_credits")),
            "parent_override_percent": float(body.get("parent_override_percent")),
            "minimum_withdrawal_vnd": int(body.get("minimum_withdrawal_vnd", 50000)),
        }
    except (TypeError, ValueError):
        raise HTTPException(400, "Cấu hình hoa hồng không hợp lệ")
    if any(not 0 <= values[key] <= 100 for key in ("silver_rate_percent", "gold_rate_percent", "buyer_bonus_percent", "parent_override_percent")):
        raise HTTPException(400, "Tỷ lệ hoa hồng phải từ 0 đến 100%")
    if values["gold_threshold_credits"] < 1:
        raise HTTPException(400, "Mốc lên Vàng phải lớn hơn 0")
    if values["minimum_withdrawal_vnd"] < 1:
        raise HTTPException(400, "Mức rút tối thiểu phải lớn hơn 0")
    con = db()
    con.execute("""UPDATE affiliate_settings SET enabled=?,silver_rate_percent=?,gold_rate_percent=?,
        buyer_bonus_percent=?,gold_threshold_credits=?,parent_override_percent=?,minimum_withdrawal_vnd=?,updated_at=? WHERE id=1""",
        (*values.values(), now_iso()))
    con.commit()
    settings = affiliate_settings(con)
    con.close()
    return {"ok": True, "settings": settings}

@app.post("/api/admin/affiliate/withdrawals/{withdrawal_id}/paid")
async def admin_affiliate_withdrawal_paid(withdrawal_id: int, request: Request):
    actor = require_admin(request)
    body = await request.json()
    note = (body.get("admin_note") or "")[:300]
    con = db()
    w = con.execute("SELECT * FROM affiliate_withdrawals WHERE id=?", (withdrawal_id,)).fetchone()
    if not w:
        con.close(); raise HTTPException(404, "Không tìm thấy yêu cầu rút")
    if w["status"] != "approved":
        con.close(); raise HTTPException(409, "Yêu cầu đã được xử lý")
    con.execute(
        "UPDATE affiliate_withdrawals SET status='paid',paid_at=?,admin_note=? WHERE id=?",
        (now_iso(), note, withdrawal_id)
    )
    affiliate_audit(con, actor, w["user_id"], "withdrawal_paid", w["amount_vnd"], w["status"], "paid", request)
    con.commit(); con.close()
    return {"ok": True}

@app.post("/api/admin/affiliate/commissions/{commission_id}/paid")
async def admin_affiliate_commission_paid(commission_id: int, request: Request):
    actor = require_admin(request)
    body = await request.json()
    note = (body.get("admin_note") or "")[:300]
    con = db()
    con.execute("BEGIN IMMEDIATE")
    commission = con.execute("SELECT * FROM affiliate_commissions WHERE id=?", (commission_id,)).fetchone()
    if not commission:
        con.rollback(); con.close(); raise HTTPException(404, "Không tìm thấy hoa hồng tiền Affiliate")
    changed = con.execute(
        "UPDATE affiliate_commissions SET status='paid',paid_at=?,admin_note=? WHERE id=? AND status='approved'",
        (now_iso(), note, commission_id),
    ).rowcount
    if not changed:
        con.rollback(); con.close(); raise HTTPException(409, "Hoa hồng không còn ở trạng thái approved")
    affiliate_audit(con, actor, commission["user_id"], "commission_paid", commission["amount_vnd"], "approved", "paid", request)
    con.commit(); con.close()
    return {"ok": True, "status": "paid", "amount_vnd": commission["amount_vnd"]}

@app.post("/api/admin/affiliate/commissions/{commission_id}/approve")
async def admin_affiliate_commission_approve(commission_id: int, request: Request):
    actor = require_admin(request)
    body = await request.json()
    note = (body.get("admin_note") or "")[:300]
    con = db()
    con.execute("BEGIN IMMEDIATE")
    commission = con.execute("SELECT * FROM affiliate_commissions WHERE id=?", (commission_id,)).fetchone()
    if not commission:
        con.rollback(); con.close(); raise HTTPException(404, "Không tìm thấy hoa hồng tiền Affiliate")
    changed = con.execute(
        "UPDATE affiliate_commissions SET status='approved',reviewed_at=?,admin_note=? WHERE id=? AND status='pending'",
        (now_iso(), note, commission_id),
    ).rowcount
    if not changed:
        con.rollback(); con.close(); raise HTTPException(409, "Hoa hồng không còn pending")
    affiliate_audit(con, actor, commission["user_id"], "commission_approved", commission["amount_vnd"], "pending", "approved", request)
    con.commit(); con.close()
    return {"ok": True, "status": "approved", "amount_vnd": commission["amount_vnd"]}

@app.post("/api/admin/affiliate/withdrawals/{withdrawal_id}/approve")
async def admin_affiliate_withdrawal_approve(withdrawal_id: int, request: Request):
    actor = require_admin(request)
    body = await request.json()
    note = (body.get("admin_note") or "")[:300]
    con = db()
    con.execute("BEGIN IMMEDIATE")
    changed = con.execute("UPDATE affiliate_withdrawals SET status='approved',reviewed_at=?,admin_note=? WHERE id=? AND status='pending'", (now_iso(), note, withdrawal_id)).rowcount
    if not changed:
        con.rollback(); con.close(); raise HTTPException(409, "Yêu cầu không còn pending")
    w = con.execute("SELECT user_id,amount_vnd FROM affiliate_withdrawals WHERE id=?", (withdrawal_id,)).fetchone()
    affiliate_audit(con, actor, w["user_id"], "withdrawal_approved", w["amount_vnd"], "pending", "approved", request)
    con.commit(); con.close()
    return {"ok": True, "status": "approved"}

@app.post("/api/admin/affiliate/withdrawals/{withdrawal_id}/reject")
async def admin_affiliate_withdrawal_reject(withdrawal_id: int, request: Request):
    actor = require_admin(request)
    body = await request.json()
    note = (body.get("admin_note") or "")[:300]
    con = db()
    w = con.execute("SELECT * FROM affiliate_withdrawals WHERE id=?", (withdrawal_id,)).fetchone()
    if not w:
        con.close(); raise HTTPException(404, "Không tìm thấy yêu cầu rút")
    if w["status"] not in {"pending", "approved"}:
        con.close(); raise HTTPException(409, "Yêu cầu đã được xử lý")
    con.execute(
        "UPDATE affiliate_withdrawals SET status='rejected',reviewed_at=?,admin_note=? WHERE id=?",
        (now_iso(), note, withdrawal_id)
    )
    affiliate_audit(con, actor, w["user_id"], "withdrawal_rejected", w["amount_vnd"], w["status"], "rejected", request)
    con.commit(); con.close()
    return {"ok": True}


# ---------- WORKER ----------
def check_worker(auth: Optional[str]):
    if not auth or not hmac.compare_digest(auth, WORKER_TOKEN):
        raise HTTPException(401, "Worker token không hợp lệ")

@app.post("/api/worker/heartbeat")
async def worker_heartbeat(
    request: Request,
    x_worker_token: Optional[str] = Header(None),
    x_worker_id: Optional[str] = Header(None),
):
    check_worker(x_worker_token)
    body = await request.json()
    status = str(body.get("status") or "idle").lower()
    current_job_id = body.get("current_job_id")
    try:
        current_job_id = int(current_job_id) if current_job_id is not None else None
    except (TypeError, ValueError):
        current_job_id = None
    record_worker_heartbeat(x_worker_id or "default-worker", status, current_job_id)
    return {"ok": True, "state": worker_presence()["state"]}


@app.post("/api/worker/claim")
def worker_claim(
    x_worker_token: Optional[str] = Header(None),
    x_worker_id: Optional[str] = Header(None),
):
    check_worker(x_worker_token)
    worker_id = x_worker_id if isinstance(x_worker_id, str) else "default-worker"
    record_worker_heartbeat(worker_id, "idle")
    con = db()
    con.execute("BEGIN IMMEDIATE")
    row = con.execute("""SELECT * FROM jobs WHERE status='waiting' AND gpu_job_id IS NULL
                         AND service='motion_studio' ORDER BY priority DESC,id LIMIT 1""").fetchone()
    if not row:
        con.commit(); con.close()
        return {"job": None}
    con.execute("UPDATE jobs SET status='running',progress=1,claimed_at=?,updated_at=? WHERE id=?",
                (now_iso(), now_iso(), row["id"]))
    con.commit()
    row = con.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone()
    con.close()
    record_worker_heartbeat(worker_id, "busy", row["id"])
    d = dict(row)
    d["image_url"] = f"/api/worker/files/{row['id']}/image"
    d["motion_url"] = f"/api/worker/files/{row['id']}/motion"
    return {"job": d}

@app.get("/api/worker/files/{job_id}/{kind}")
def worker_file(job_id: int, kind: str, x_worker_token: Optional[str] = Header(None)):
    check_worker(x_worker_token)
    con = db()
    row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    con.close()
    if not row: raise HTTPException(404, "Không tìm thấy job")
    key = "image_path" if kind == "image" else "video_path"
    path = BASE / row[key]
    return FileResponse(path)

@app.post("/api/worker/jobs/{job_id}/progress")
async def worker_progress(
    job_id: int, request: Request,
    x_worker_token: Optional[str] = Header(None),
    x_worker_id: Optional[str] = Header(None),
):
    check_worker(x_worker_token)
    record_worker_heartbeat(x_worker_id or "default-worker", "busy", job_id)
    body = await request.json()
    progress = max(1, min(99, int(body.get("progress", 1))))
    con = db()
    con.execute("UPDATE jobs SET progress=?,updated_at=? WHERE id=? AND status='running'", (progress, now_iso(), job_id))
    con.commit(); con.close()
    return {"ok": True}

@app.post("/api/worker/jobs/{job_id}/complete")
async def worker_complete(
    job_id: int,
    output: UploadFile = File(...),
    x_worker_token: Optional[str] = Header(None),
    x_worker_id: Optional[str] = Header(None),
):
    check_worker(x_worker_token)
    ext = Path(output.filename or ".mp4").suffix.lower()
    if ext not in {".mp4",".mov",".webm"}:
        ext = ".mp4"
    con = db()
    job = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    con.close()
    if not job:
        raise HTTPException(404, "Không tìm thấy job")
    if job["status"] not in {"waiting", "running"}:
        raise HTTPException(409, "Job không ở trạng thái nhận kết quả")
    declared_size = output.headers.get("content-length")
    try:
        if declared_size is not None and int(declared_size) > WORKER_MAX_OUTPUT_BYTES:
            raise HTTPException(413, "File output vượt quá giới hạn cho phép")
    except ValueError:
        pass
    out = OUTPUTS / f"job_{job_id}{ext}"
    temporary = OUTPUTS / f".job_{job_id}{ext}.uploading"
    try:
        with temporary.open("wb") as destination:
            output_size = 0
            while True:
                chunk = await output.read(1024 * 1024)
                if not chunk:
                    break
                output_size += len(chunk)
                if output_size > WORKER_MAX_OUTPUT_BYTES:
                    raise HTTPException(413, "File output vượt quá giới hạn cho phép")
                destination.write(chunk)
        validation_error = validate_local_output(job, temporary)
        if validation_error:
            fail_job_once(job_id, validation_error)
            raise HTTPException(422, validation_error)
        temporary.replace(out)
    finally:
        temporary.unlink(missing_ok=True)
    con = db()
    con.execute(
        "UPDATE jobs SET output_path=?,status='done',progress=100,error=NULL,updated_at=? WHERE id=?",
        (str(out.relative_to(BASE)), now_iso(), job_id)
    )
    con.commit()
    completed = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    con.close()
    record_worker_heartbeat(x_worker_id or "default-worker", "idle")
    if completed:
        values = video_upscale_pipeline.start(sys.modules[__name__], dict(completed))
        video_upscale_pipeline.persist(sys.modules[__name__], job_id, values)
    return {"ok": True}


@app.post("/api/worker/jobs/{job_id}/fail")
async def worker_fail(
    job_id: int, request: Request,
    x_worker_token: Optional[str] = Header(None),
    x_worker_id: Optional[str] = Header(None),
):
    check_worker(x_worker_token)
    body = await request.json()
    error = (body.get("error") or "Render failed")[:1000]
    con = db()
    exists = con.execute("SELECT 1 FROM jobs WHERE id=?", (job_id,)).fetchone()
    con.close()
    if not exists:
        raise HTTPException(404, "Không tìm thấy job")
    changed = fail_job_once(job_id, error)
    record_worker_heartbeat(x_worker_id or "default-worker", "idle")
    return {"ok": True, "changed": changed}

from service_routes import router as service_router
app.include_router(service_router)

@app.get("/api/health")
def health():
    return {
        "ok": True, "time": now_iso(),
        "workers": {
            **{
                key: {"configured": adapter.config.configured}
                for key, adapter in service_adapters.items()
            },
            "video_upscale": {
                "enabled": video_upscale_adapter.video_config.enabled,
                "configured": video_upscale_adapter.video_config.configured,
            },
        },
    }


import threading

from mock_renderer import render_mock_fixture


_reconcile_stop = threading.Event()


def _job_reconcile_loop():
    while not _reconcile_stop.wait(JOB_RECONCILE_INTERVAL_SECONDS):
        try:
            from service_routes import refresh_job as refresh_service_job
            con = db()
            pending = con.execute(
                """SELECT id,user_id FROM jobs
                   WHERE service IS NOT NULL AND service!='motion_studio'
                     AND status IN ('waiting','running','upscaling')
                   ORDER BY id LIMIT 100"""
            ).fetchall()
            con.close()
            for row in pending:
                refresh_service_job(row["user_id"], row["id"])
            recover_stale_jobs()
        except Exception as error:
            print("[Job Reconciler Error]", error)


@app.on_event("startup")
def start_job_reconciler():
    thread = getattr(app.state, "job_reconciler_thread", None)
    if thread and thread.is_alive():
        return
    _reconcile_stop.clear()
    thread = threading.Thread(target=_job_reconcile_loop, daemon=True)
    app.state.job_reconciler_thread = thread
    thread.start()


@app.on_event("shutdown")
def stop_job_reconciler():
    _reconcile_stop.set()


def process_mock_job(job_id: int):
    """Process one queued job only when explicit mock mode is active."""
    if RENDER_MODE != "mock":
        return None
    con = db()
    try:
        con.execute("BEGIN IMMEDIATE")
        claimed = con.execute(
            """UPDATE jobs SET status='running',progress=30,worker_status='mock_preparing',updated_at=?
               WHERE id=? AND status='waiting' AND gpu_job_id IS NULL""",
            (now_iso(), job_id),
        )
        if claimed.rowcount != 1:
            con.commit()
            row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return dict(row) if row else None
        con.commit()
        row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    finally:
        con.close()
    if not row:
        return None
    try:
        service = row["service"] or "motion_studio"
        extension = ".png" if service in {"outfit_change", "background_change", "image_upscale"} else ".mp4"
        output = OUTPUTS / f"mock_job_{job_id}{extension}"
        con = db()
        con.execute(
            "UPDATE jobs SET progress=70,worker_status='mock_processing',updated_at=? WHERE id=? AND status='running'",
            (now_iso(), job_id),
        )
        con.commit()
        con.close()
        if not render_mock_fixture(service, job_id, output):
            raise RuntimeError("Mock renderer không tạo được output")
        validation_error = validate_local_output(row, output)
        if validation_error:
            raise RuntimeError(validation_error)
        con = db()
        con.execute(
            """UPDATE jobs SET status='done',progress=100,output_path=?,output_media_type=?,
               worker_status='mock_completed',error=NULL,updated_at=? WHERE id=? AND status='running'""",
            (
                str(output.relative_to(BASE)),
                "image/png" if extension == ".png" else "video/mp4",
                now_iso(), job_id,
            ),
        )
        con.commit()
        completed = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        con.close()
        return dict(completed) if completed else None
    except Exception as error:
        fail_job_once(job_id, str(error))
        con = db()
        failed = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        con.close()
        return dict(failed) if failed else None


def _auto_worker_loop():
    while True:
        try:
            time.sleep(1)
            con = db()
            row = con.execute(
                """SELECT id FROM jobs WHERE status='waiting' AND gpu_job_id IS NULL
                   ORDER BY priority DESC,id ASC LIMIT 1"""
            ).fetchone()
            con.close()
            if row:
                process_mock_job(row["id"])
        except Exception as error:
            print("[Mock Worker Loop Error]", error)


if RENDER_MODE == "mock":
    _worker_thread = threading.Thread(target=_auto_worker_loop, daemon=True)
    _worker_thread.start()
