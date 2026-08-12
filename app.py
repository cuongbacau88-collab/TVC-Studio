
import os, sqlite3, secrets, hashlib, hmac, mimetypes, shutil, time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, Request, Response, UploadFile, File, Form, HTTPException, Header
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
UPLOADS = DATA / "uploads"
OUTPUTS = DATA / "outputs"
DB_PATH = DATA / "motionhub.db"

UPLOADS.mkdir(parents=True, exist_ok=True)
OUTPUTS.mkdir(parents=True, exist_ok=True)

SESSION_DAYS = 30
MAX_IMAGE_MB = 25
MAX_VIDEO_MB = 300

WORKER_TOKEN = os.getenv("WORKER_TOKEN", "change-worker-token")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "cuongtv.bx92@gmail.com").lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Cuong123@")

app = FastAPI(title="TVC Studio AI Business V2.4")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
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
        credits INTEGER NOT NULL DEFAULT 30,
        role TEXT NOT NULL DEFAULT 'user',
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sessions(
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at TEXT NOT NULL
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
    CREATE TABLE IF NOT EXISTS affiliate_rewards(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        source_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        topup_id INTEGER NOT NULL REFERENCES topups(id) ON DELETE CASCADE,
        reward_type TEXT NOT NULL,
        amount_credits REAL NOT NULL,
        rate REAL NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(user_id, topup_id, reward_type)
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
    """)

    # Safe schema migration for databases created by older versions.
    cols = {r["name"] for r in con.execute("PRAGMA table_info(users)").fetchall()}
    if "referral_code" not in cols:
        con.execute("ALTER TABLE users ADD COLUMN referral_code TEXT")
    if "referred_by_user_id" not in cols:
        con.execute("ALTER TABLE users ADD COLUMN referred_by_user_id INTEGER")
    if "referred_at" not in cols:
        con.execute("ALTER TABLE users ADD COLUMN referred_at TEXT")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by_user_id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_affiliate_rewards_user ON affiliate_rewards(user_id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_affiliate_withdrawals_user ON affiliate_withdrawals(user_id)")

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

init_db()

def current_user(request: Request, required=True):
    token = request.cookies.get("mh_session")
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
    if not row and required:
        raise HTTPException(401, "Phiên đăng nhập đã hết hạn")
    return dict(row) if row else None

def require_admin(request: Request):
    u = current_user(request)
    if u["role"] != "admin":
        raise HTTPException(403, "Không có quyền admin")
    return u


AFFILIATE_VND_PER_CREDIT = 2500
AFFILIATE_GOLD_SALES_CREDITS = 1000
REFERRAL_BUYER_BONUS_RATE = 0.10

def affiliate_sales_credits(con, user_id: int):
    row = con.execute("""
        SELECT COALESCE(SUM(t.credits),0) AS total
        FROM topups t
        JOIN users child ON child.id=t.user_id
        WHERE child.referred_by_user_id=? AND t.status='approved'
    """, (user_id,)).fetchone()
    return float(row["total"] or 0)

def affiliate_tier(con, user_id: int):
    sales = affiliate_sales_credits(con, user_id)
    if sales >= AFFILIATE_GOLD_SALES_CREDITS:
        return {
            "key": "gold", "name": "Vàng", "rate": 0.15,
            "rate_percent": 15, "override_percent": 50,
            "sales_credits": sales, "next_sales_credits": None,
        }
    return {
        "key": "silver", "name": "Bạc", "rate": 0.10,
        "rate_percent": 10, "override_percent": 0,
        "sales_credits": sales, "next_sales_credits": AFFILIATE_GOLD_SALES_CREDITS,
    }

def affiliate_totals(con, user_id: int):
    reward = con.execute(
        "SELECT COALESCE(SUM(amount_credits),0) total FROM affiliate_rewards WHERE user_id=?",
        (user_id,)
    ).fetchone()["total"] or 0
    reserved = con.execute("""
        SELECT COALESCE(SUM(amount_credits),0) total
        FROM affiliate_withdrawals
        WHERE user_id=? AND status IN ('pending','paid')
    """, (user_id,)).fetchone()["total"] or 0
    paid = con.execute("""
        SELECT COALESCE(SUM(amount_credits),0) total
        FROM affiliate_withdrawals
        WHERE user_id=? AND status='paid'
    """, (user_id,)).fetchone()["total"] or 0
    return {
        "total_rewards": round(float(reward), 2),
        "available": round(max(0.0, float(reward) - float(reserved)), 2),
        "paid": round(float(paid), 2),
    }

def find_referrer_by_code(con, code: str):
    code = (code or "").strip().lower()
    if not code:
        return None
    return con.execute(
        "SELECT id,email,name,referral_code FROM users WHERE lower(referral_code)=?",
        (code,)
    ).fetchone()

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
    return size

@app.get("/")
def home():
    return FileResponse(BASE / "static" / "index.html")

@app.get("/app")
def app_page():
    return FileResponse(BASE / "static" / "app.html")

@app.get("/admin")
def admin_page():
    return FileResponse(BASE / "static" / "admin.html")

@app.post("/api/register")
async def register(request: Request):
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    name = (body.get("name") or "").strip()[:80]
    password = body.get("password") or ""
    referral_code = (body.get("referral_code") or "").strip().lower()

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
                email, name, hash_password(password), 30, "user", now_iso(),
                referrer["id"] if referrer else None,
                now_iso() if referrer else None
            )
        )
        uid = cur.lastrowid
        ensure_user_referral_code(con, uid)
        con.execute(
            "INSERT INTO credit_ledger(user_id,delta,reason,created_at) VALUES(?,?,?,?)",
            (uid, 30, "Tặng credits đăng ký", now_iso())
        )
        con.commit()
    except sqlite3.IntegrityError:
        con.close()
        raise HTTPException(409, "Email đã tồn tại")
    con.close()
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
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat()
    con.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)", (token, u["id"], expires))
    con.commit()
    con.close()
    response.set_cookie("mh_session", token, httponly=True, samesite="lax", secure=False, max_age=SESSION_DAYS*86400)
    return {"ok": True, "role": u["role"]}

@app.post("/api/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get("mh_session")
    if token:
        con = db()
        con.execute("DELETE FROM sessions WHERE token=?", (token,))
        con.commit()
        con.close()
    response.delete_cookie("mh_session")
    return {"ok": True}

@app.get("/api/me")
def me(request: Request):
    u = current_user(request)
    return {k: u.get(k) for k in ("id","email","name","credits","role","created_at","referral_code","referred_by_user_id")}

@app.get("/api/jobs")
def my_jobs(request: Request):
    u = current_user(request)
    con = db()
    rows = con.execute("""
        SELECT id,model,aspect_ratio,quality,prompt,cost,status,progress,error,created_at,updated_at,
               CASE WHEN output_path IS NOT NULL THEN 1 ELSE 0 END AS has_output
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
    quality: str = Form("720"),
    prompt: str = Form("")
):
    u = current_user(request)
    if aspect_ratio not in {"9:16","16:9","1:1"}:
        raise HTTPException(400, "Tỷ lệ không hợp lệ")
    if quality not in {"480","720"}:
        raise HTTPException(400, "Chất lượng không hợp lệ")
    cost = 10 if quality == "480" else 20

    con = db()
    fresh = con.execute("SELECT credits FROM users WHERE id=?", (u["id"],)).fetchone()
    if fresh["credits"] < cost:
        con.close()
        raise HTTPException(402, "Không đủ credits")

    cur = con.execute("""
        INSERT INTO jobs(user_id,model,aspect_ratio,quality,prompt,cost,image_path,video_path,status,progress,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
    """, (u["id"], model[:120], aspect_ratio, quality, prompt[:2000], cost, "", "", "uploading", 0, now_iso(), now_iso()))
    job_id = cur.lastrowid
    job_dir = UPLOADS / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)

    image_dest = job_dir / ("character" + Path(image.filename or ".png").suffix.lower())
    video_dest = job_dir / ("motion" + Path(motion.filename or ".mp4").suffix.lower())
    try:
        await save_upload(image, image_dest, {".png",".jpg",".jpeg",".webp"}, MAX_IMAGE_MB)
        await save_upload(motion, video_dest, {".mp4",".mov",".webm",".mkv"}, MAX_VIDEO_MB)
    except Exception:
        shutil.rmtree(job_dir, ignore_errors=True)
        con.execute("DELETE FROM jobs WHERE id=?", (job_id,))
        con.commit()
        con.close()
        raise

    con.execute("UPDATE users SET credits=credits-? WHERE id=?", (cost, u["id"]))
    con.execute(
        "INSERT INTO credit_ledger(user_id,delta,reason,ref_type,ref_id,created_at) VALUES(?,?,?,?,?,?)",
        (u["id"], -cost, f"Tạo job #{job_id}", "job", job_id, now_iso())
    )
    con.execute("""
        UPDATE jobs SET image_path=?,video_path=?,status='waiting',updated_at=? WHERE id=?
    """, (str(image_dest.relative_to(BASE)), str(video_dest.relative_to(BASE)), now_iso(), job_id))
    con.commit()
    con.close()
    return {"ok": True, "job_id": job_id, "cost": cost}

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
    if not row["output_path"]:
        raise HTTPException(404, "Job chưa có kết quả")
    path = BASE / row["output_path"]
    if not path.exists():
        raise HTTPException(404, "File kết quả không tồn tại")
    return FileResponse(path, filename=f"motionhub_job_{job_id}{path.suffix}")

@app.get("/api/ledger")
def ledger(request: Request):
    u = current_user(request)
    con = db()
    rows = con.execute("SELECT * FROM credit_ledger WHERE user_id=? ORDER BY id DESC LIMIT 100", (u["id"],)).fetchall()
    con.close()
    return [dict(r) for r in rows]

PACKAGES = {
    "starter": (49_000, 50),
    "creator": (199_000, 250),
    "studio": (699_000, 1000),
}

@app.post("/api/topups")
async def request_topup(request: Request):
    u = current_user(request)
    body = await request.json()
    package = body.get("package")
    note = (body.get("note") or "")[:300]
    if package not in PACKAGES:
        raise HTTPException(400, "Gói không hợp lệ")
    amount, credits = PACKAGES[package]
    con = db()
    cur = con.execute("""
        INSERT INTO topups(user_id,package,amount_vnd,credits,note,status,created_at)
        VALUES(?,?,?,?,?,'pending',?)
    """, (u["id"], package, amount, credits, note, now_iso()))
    con.commit()
    tid = cur.lastrowid
    con.close()
    return {"ok": True, "topup_id": tid, "amount_vnd": amount, "credits": credits}

@app.get("/api/topups")
def my_topups(request: Request):
    u = current_user(request)
    con = db()
    rows = con.execute("SELECT * FROM topups WHERE user_id=? ORDER BY id DESC", (u["id"],)).fetchall()
    con.close()
    return [dict(r) for r in rows]


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
        JOIN topups t ON t.user_id=child.id AND t.status='approved'
        WHERE child.referred_by_user_id=?
    """, (u["id"],)).fetchone()["c"]
    tier = affiliate_tier(con, u["id"])
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
        "referral_link": f"{base_url}/app?ref={code}#affiliate",
        "direct_referrals": direct_count,
        "paying_referrals": paying_count,
        "tier": tier,
        "total_rewards": totals["total_rewards"],
        "available": totals["available"],
        "paid": totals["paid"],
        "available_vnd": int(round(totals["available"] * AFFILIATE_VND_PER_CREDIT)),
        "vnd_per_credit": AFFILIATE_VND_PER_CREDIT,
        "progress_percent": progress,
        "credits_to_gold": remaining,
        "referrer": dict(referrer) if referrer else None,
        "can_apply_code": not bool(user_row["referred_by_user_id"]),
        "buyer_bonus_percent": int(REFERRAL_BUYER_BONUS_RATE * 100),
    }

@app.post("/api/affiliate/apply-code")
async def affiliate_apply_code(request: Request):
    u = current_user(request)
    body = await request.json()
    code = (body.get("code") or "").strip().lower()
    if not code:
        raise HTTPException(400, "Hãy nhập mã giới thiệu")

    con = db()
    me_row = con.execute(
        "SELECT id,referred_by_user_id,referral_code FROM users WHERE id=?", (u["id"],)
    ).fetchone()
    if me_row["referred_by_user_id"]:
        con.close()
        raise HTTPException(409, "Tài khoản đã có người giới thiệu")
    referrer = find_referrer_by_code(con, code)
    if not referrer:
        con.close()
        raise HTTPException(404, "Mã giới thiệu không tồn tại")
    if referrer["id"] == u["id"]:
        con.close()
        raise HTTPException(400, "Không thể nhập mã của chính mình")

    con.execute(
        "UPDATE users SET referred_by_user_id=?,referred_at=? WHERE id=?",
        (referrer["id"], now_iso(), u["id"])
    )
    con.commit()
    con.close()
    return {"ok": True, "referrer_name": referrer["name"]}

@app.get("/api/affiliate/rewards")
def affiliate_rewards(request: Request):
    u = current_user(request)
    con = db()
    rows = con.execute("""
        SELECT r.*, src.name AS source_name, src.email AS source_email
        FROM affiliate_rewards r
        JOIN users src ON src.id=r.source_user_id
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

@app.post("/api/affiliate/withdrawals")
async def affiliate_request_withdrawal(request: Request):
    u = current_user(request)
    body = await request.json()
    try:
        amount = round(float(body.get("amount_credits", 0)), 2)
    except Exception:
        raise HTTPException(400, "Số credits không hợp lệ")
    method = (body.get("method") or "").strip()[:50]
    account = (body.get("account") or "").strip()[:200]
    note = (body.get("note") or "").strip()[:300]

    if amount < 10:
        raise HTTPException(400, "Tối thiểu 10 credits cho mỗi lần rút")
    if not method or not account:
        raise HTTPException(400, "Hãy nhập phương thức và thông tin nhận tiền")

    con = db()
    totals = affiliate_totals(con, u["id"])
    if amount > totals["available"] + 1e-9:
        con.close()
        raise HTTPException(400, "Số dư affiliate không đủ")

    amount_vnd = int(round(amount * AFFILIATE_VND_PER_CREDIT))
    cur = con.execute("""
        INSERT INTO affiliate_withdrawals(
            user_id,amount_credits,amount_vnd,method,account,note,status,created_at
        ) VALUES(?,?,?,?,?,?,'pending',?)
    """, (u["id"], amount, amount_vnd, method, account, note, now_iso()))
    con.commit()
    wid = cur.lastrowid
    con.close()
    return {"ok": True, "withdrawal_id": wid, "amount_vnd": amount_vnd}


# ---------- ADMIN ----------
@app.get("/api/admin/stats")
def admin_stats(request: Request):
    require_admin(request)
    con = db()
    stats = {
        "users": con.execute("SELECT COUNT(*) c FROM users").fetchone()["c"],
        "waiting": con.execute("SELECT COUNT(*) c FROM jobs WHERE status='waiting'").fetchone()["c"],
        "running": con.execute("SELECT COUNT(*) c FROM jobs WHERE status='running'").fetchone()["c"],
        "done": con.execute("SELECT COUNT(*) c FROM jobs WHERE status='done'").fetchone()["c"],
        "pending_topups": con.execute("SELECT COUNT(*) c FROM topups WHERE status='pending'").fetchone()["c"],
        "pending_withdrawals": con.execute("SELECT COUNT(*) c FROM affiliate_withdrawals WHERE status='pending'").fetchone()["c"],
        "affiliate_rewards": round(float(con.execute("SELECT COALESCE(SUM(amount_credits),0) c FROM affiliate_rewards").fetchone()["c"] or 0), 2),
    }
    con.close()
    return stats

@app.get("/api/admin/users")
def admin_users(request: Request):
    require_admin(request)
    con = db()
    rows = con.execute("SELECT id,email,name,credits,role,created_at FROM users ORDER BY id DESC LIMIT 200").fetchall()
    con.close()
    return [dict(r) for r in rows]

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
        SELECT t.*,u.email,u.name FROM topups t JOIN users u ON u.id=t.user_id ORDER BY t.id DESC LIMIT 200
    """).fetchall()
    con.close()
    return [dict(r) for r in rows]

@app.post("/api/admin/topups/{topup_id}/approve")
def approve_topup(topup_id: int, request: Request):
    require_admin(request)
    con = db()
    con.execute("BEGIN IMMEDIATE")
    t = con.execute("SELECT * FROM topups WHERE id=?", (topup_id,)).fetchone()
    if not t:
        con.rollback(); con.close()
        raise HTTPException(404, "Không tìm thấy yêu cầu")
    if t["status"] != "pending":
        con.rollback(); con.close()
        raise HTTPException(409, "Yêu cầu đã xử lý")

    buyer = con.execute(
        "SELECT id,referred_by_user_id FROM users WHERE id=?", (t["user_id"],)
    ).fetchone()
    buyer_bonus = int(round(t["credits"] * REFERRAL_BUYER_BONUS_RATE)) if buyer["referred_by_user_id"] else 0

    # Mark approved first so tier calculations include this transaction.
    con.execute("UPDATE topups SET status='approved',reviewed_at=? WHERE id=?", (now_iso(), topup_id))
    con.execute(
        "UPDATE users SET credits=credits+? WHERE id=?",
        (t["credits"] + buyer_bonus, t["user_id"])
    )
    con.execute("""
        INSERT INTO credit_ledger(user_id,delta,reason,ref_type,ref_id,created_at)
        VALUES(?,?,?,?,?,?)
    """, (t["user_id"], t["credits"], f"Nạp gói {t['package']}", "topup", topup_id, now_iso()))

    if buyer_bonus:
        con.execute("""
            INSERT INTO credit_ledger(user_id,delta,reason,ref_type,ref_id,created_at)
            VALUES(?,?,?,?,?,?)
        """, (
            t["user_id"], buyer_bonus,
            f"Thưởng +{int(REFERRAL_BUYER_BONUS_RATE*100)}% từ mã giới thiệu",
            "referral_bonus", topup_id, now_iso()
        ))

    direct_commission = 0.0
    override_commission = 0.0
    if buyer["referred_by_user_id"]:
        referrer_id = buyer["referred_by_user_id"]
        tier = affiliate_tier(con, referrer_id)
        direct_commission = round(t["credits"] * tier["rate"], 2)
        con.execute("""
            INSERT OR IGNORE INTO affiliate_rewards(
                user_id,source_user_id,topup_id,reward_type,amount_credits,rate,created_at
            ) VALUES(?,?,?,?,?,?,?)
        """, (
            referrer_id, t["user_id"], topup_id, "direct",
            direct_commission, tier["rate"], now_iso()
        ))

        # Gold partners receive 50% override on commission earned by their direct affiliate.
        parent = con.execute(
            "SELECT referred_by_user_id FROM users WHERE id=?", (referrer_id,)
        ).fetchone()
        if parent and parent["referred_by_user_id"]:
            parent_id = parent["referred_by_user_id"]
            parent_tier = affiliate_tier(con, parent_id)
            if parent_tier["key"] == "gold":
                override_commission = round(direct_commission * 0.50, 2)
                con.execute("""
                    INSERT OR IGNORE INTO affiliate_rewards(
                        user_id,source_user_id,topup_id,reward_type,amount_credits,rate,created_at
                    ) VALUES(?,?,?,?,?,?,?)
                """, (
                    parent_id, referrer_id, topup_id, "tier_override",
                    override_commission, 0.50, now_iso()
                ))

    con.commit()
    con.close()
    return {
        "ok": True,
        "buyer_bonus": buyer_bonus,
        "direct_commission": direct_commission,
        "override_commission": override_commission,
    }

@app.post("/api/admin/topups/{topup_id}/reject")
def reject_topup(topup_id: int, request: Request):
    require_admin(request)
    con = db()
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
        raise HTTPException(400, "Số credits không hợp lệ")
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
            "available": totals["available"],
            "referrer": referrer,
        })
    con.close()
    return result

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

@app.post("/api/admin/affiliate/withdrawals/{withdrawal_id}/paid")
async def admin_affiliate_withdrawal_paid(withdrawal_id: int, request: Request):
    require_admin(request)
    body = await request.json()
    note = (body.get("admin_note") or "")[:300]
    con = db()
    w = con.execute("SELECT * FROM affiliate_withdrawals WHERE id=?", (withdrawal_id,)).fetchone()
    if not w:
        con.close(); raise HTTPException(404, "Không tìm thấy yêu cầu rút")
    if w["status"] != "pending":
        con.close(); raise HTTPException(409, "Yêu cầu đã được xử lý")
    con.execute(
        "UPDATE affiliate_withdrawals SET status='paid',reviewed_at=?,admin_note=? WHERE id=?",
        (now_iso(), note, withdrawal_id)
    )
    con.commit(); con.close()
    return {"ok": True}

@app.post("/api/admin/affiliate/withdrawals/{withdrawal_id}/reject")
async def admin_affiliate_withdrawal_reject(withdrawal_id: int, request: Request):
    require_admin(request)
    body = await request.json()
    note = (body.get("admin_note") or "")[:300]
    con = db()
    w = con.execute("SELECT * FROM affiliate_withdrawals WHERE id=?", (withdrawal_id,)).fetchone()
    if not w:
        con.close(); raise HTTPException(404, "Không tìm thấy yêu cầu rút")
    if w["status"] != "pending":
        con.close(); raise HTTPException(409, "Yêu cầu đã được xử lý")
    con.execute(
        "UPDATE affiliate_withdrawals SET status='rejected',reviewed_at=?,admin_note=? WHERE id=?",
        (now_iso(), note, withdrawal_id)
    )
    con.commit(); con.close()
    return {"ok": True}


# ---------- WORKER ----------
def check_worker(auth: Optional[str]):
    if not auth or not hmac.compare_digest(auth, WORKER_TOKEN):
        raise HTTPException(401, "Worker token không hợp lệ")

@app.post("/api/worker/claim")
def worker_claim(x_worker_token: Optional[str] = Header(None)):
    check_worker(x_worker_token)
    con = db()
    con.execute("BEGIN IMMEDIATE")
    row = con.execute("SELECT * FROM jobs WHERE status='waiting' ORDER BY id LIMIT 1").fetchone()
    if not row:
        con.commit(); con.close()
        return {"job": None}
    con.execute("UPDATE jobs SET status='running',progress=1,claimed_at=?,updated_at=? WHERE id=?",
                (now_iso(), now_iso(), row["id"]))
    con.commit()
    row = con.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone()
    con.close()
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
async def worker_progress(job_id: int, request: Request, x_worker_token: Optional[str] = Header(None)):
    check_worker(x_worker_token)
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
    x_worker_token: Optional[str] = Header(None)
):
    check_worker(x_worker_token)
    ext = Path(output.filename or ".mp4").suffix.lower()
    if ext not in {".mp4",".mov",".webm"}:
        ext = ".mp4"
    out = OUTPUTS / f"job_{job_id}{ext}"
    with out.open("wb") as f:
        while True:
            chunk = await output.read(1024*1024)
            if not chunk: break
            f.write(chunk)
    con = db()
    con.execute("UPDATE jobs SET output_path=?,status='done',progress=100,error=NULL,updated_at=? WHERE id=?",
                (str(out.relative_to(BASE)), now_iso(), job_id))
    con.commit(); con.close()
    return {"ok": True}

@app.post("/api/worker/jobs/{job_id}/fail")
async def worker_fail(job_id: int, request: Request, x_worker_token: Optional[str] = Header(None)):
    check_worker(x_worker_token)
    body = await request.json()
    error = (body.get("error") or "Render failed")[:1000]
    con = db()
    job = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        con.close(); raise HTTPException(404, "Không tìm thấy job")
    if job["status"] not in {"failed","done"}:
        con.execute("UPDATE users SET credits=credits+? WHERE id=?", (job["cost"], job["user_id"]))
        con.execute("""
            INSERT INTO credit_ledger(user_id,delta,reason,ref_type,ref_id,created_at)
            VALUES(?,?,?,?,?,?)
        """, (job["user_id"], job["cost"], f"Hoàn credits job lỗi #{job_id}", "job_refund", job_id, now_iso()))
    con.execute("UPDATE jobs SET status='failed',error=?,updated_at=? WHERE id=?", (error, now_iso(), job_id))
    con.commit(); con.close()
    return {"ok": True}

@app.get("/api/health")
def health():
    return {"ok": True, "time": now_iso()}
