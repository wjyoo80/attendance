from flask import Flask, render_template, request, jsonify, session
import json
import os
import hashlib
import secrets
from datetime import datetime
from functools import wraps

app = Flask(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ── secret key ────────────────────────────────────────────────────────────────
# Flask 세션 서명용 키를 파일에 저장 (재시작해도 세션 유지)
SECRET_KEY_PATH = os.path.join(DATA_DIR, ".secret_key")

def _load_or_create_secret_key() -> str:
    if os.path.exists(SECRET_KEY_PATH):
        with open(SECRET_KEY_PATH) as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(SECRET_KEY_PATH, "w") as f:
        f.write(key)
    return key

app.secret_key = _load_or_create_secret_key()

# ── password store ────────────────────────────────────────────────────────────
# 저장 형식: {"user": {"hash": "...", "salt": "..."}, "admin": {...}}
PASSWORDS_PATH = os.path.join(DATA_DIR, ".passwords.json")

def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """PBKDF2-HMAC-SHA256으로 비밀번호를 해시합니다. (salt, hash) 반환."""
    if salt is None:
        salt = secrets.token_hex(32)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=260_000   # OWASP 2023 권장값
    )
    return salt, dk.hex()

def _load_passwords() -> dict:
    if os.path.exists(PASSWORDS_PATH):
        with open(PASSWORDS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}

def _save_passwords(data: dict) -> None:
    with open(PASSWORDS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def _init_default_passwords() -> None:
    """최초 실행 시 기본 비밀번호를 해시화하여 저장합니다."""
    store = _load_passwords()
    changed = False
    defaults = {"user": "1234", "admin": "admin1234"}
    for role, pw in defaults.items():
        if role not in store:
            salt, hashed = _hash_password(pw)
            store[role] = {"salt": salt, "hash": hashed}
            changed = True
    if changed:
        _save_passwords(store)

def verify_password(role: str, password: str) -> bool:
    store = _load_passwords()
    if role not in store:
        return False
    entry = store[role]
    _, hashed = _hash_password(password, salt=entry["salt"])
    return secrets.compare_digest(hashed, entry["hash"])

def change_password(role: str, new_password: str) -> None:
    store = _load_passwords()
    salt, hashed = _hash_password(new_password)
    store[role] = {"salt": salt, "hash": hashed}
    _save_passwords(store)

_init_default_passwords()

# ── helpers ──────────────────────────────────────────────────────────────────

def data_path(year: int) -> str:
    return os.path.join(DATA_DIR, f"{year}.json")

def load_year(year: int) -> dict:
    path = data_path(year)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    # default structure
    return {
        "year": year,
        "classes": {
            "중1": [], "중2": [], "중3": [],
            "고1": [], "고2": [], "고3": []
        },
        "attendance": {}
    }

def save_year(year: int, data: dict) -> None:
    with open(data_path(year), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_available_years() -> list[int]:
    years = []
    for fn in os.listdir(DATA_DIR):
        if fn.endswith(".json"):
            try:
                years.append(int(fn[:-5]))
            except ValueError:
                pass
    if not years:
        current = datetime.now().year
        # create default
        save_year(current, load_year(current))
        years = [current]
    return sorted(years, reverse=True)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            return jsonify({"error": "admin only"}), 403
        return f(*args, **kwargs)
    return decorated

# ── auth routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/login", methods=["POST"])
def login():
    body = request.get_json()
    pw = body.get("password", "")
    if verify_password("admin", pw):
        session["logged_in"] = True
        session["is_admin"] = True
        return jsonify({"role": "admin"})
    elif verify_password("user", pw):
        session["logged_in"] = True
        session["is_admin"] = False
        return jsonify({"role": "user"})
    return jsonify({"error": "wrong password"}), 401

@app.route("/api/change-password", methods=["POST"])
@login_required
@admin_required
def api_change_password():
    body = request.get_json()
    role = body.get("role")          # "user" | "admin"
    new_pw = body.get("password", "").strip()
    if role not in ("user", "admin"):
        return jsonify({"error": "invalid role"}), 400
    if len(new_pw) < 4:
        return jsonify({"error": "too short"}), 400
    change_password(role, new_pw)
    return jsonify({"ok": True})

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/api/me")
def me():
    if session.get("logged_in"):
        return jsonify({"logged_in": True, "is_admin": session.get("is_admin", False)})
    return jsonify({"logged_in": False, "is_admin": False})

# ── year / class routes ───────────────────────────────────────────────────────

@app.route("/api/years")
@login_required
def get_years():
    return jsonify(get_available_years())

@app.route("/api/years", methods=["POST"])
@login_required
@admin_required
def create_year():
    body = request.get_json()
    year = int(body["year"])
    if not os.path.exists(data_path(year)):
        save_year(year, load_year(year))
    return jsonify({"ok": True})

@app.route("/api/years/<int:year>")
@login_required
def get_year_data(year):
    return jsonify(load_year(year))

@app.route("/api/years/<int:year>/classes", methods=["POST"])
@login_required
@admin_required
def add_class(year):
    body = request.get_json()
    class_name = body["name"].strip()
    data = load_year(year)
    if class_name not in data["classes"]:
        data["classes"][class_name] = []
    save_year(year, data)
    return jsonify({"ok": True})

@app.route("/api/years/<int:year>/classes/<class_name>", methods=["DELETE"])
@login_required
@admin_required
def delete_class(year, class_name):
    data = load_year(year)
    data["classes"].pop(class_name, None)
    save_year(year, data)
    return jsonify({"ok": True})

@app.route("/api/years/<int:year>/classes/<class_name>/students", methods=["POST"])
@login_required
@admin_required
def add_student(year, class_name):
    body = request.get_json()
    name = body["name"].strip()
    data = load_year(year)
    if class_name in data["classes"] and name not in data["classes"][class_name]:
        data["classes"][class_name].append(name)
    save_year(year, data)
    return jsonify({"ok": True})

@app.route("/api/years/<int:year>/classes/<class_name>/students/<student_name>", methods=["DELETE"])
@login_required
@admin_required
def delete_student(year, class_name, student_name):
    data = load_year(year)
    if class_name in data["classes"]:
        try:
            data["classes"][class_name].remove(student_name)
        except ValueError:
            pass
    save_year(year, data)
    return jsonify({"ok": True})

# ── attendance routes ─────────────────────────────────────────────────────────

@app.route("/api/years/<int:year>/attendance", methods=["POST"])
@login_required
def save_attendance(year):
    body = request.get_json()
    date = body["date"]          # "2024-09-15"
    class_name = body["class_name"]
    present = body["present"]    # list of names

    data = load_year(year)
    if date not in data["attendance"]:
        data["attendance"][date] = {}
    data["attendance"][date][class_name] = present
    save_year(year, data)
    return jsonify({"ok": True})

@app.route("/api/years/<int:year>/attendance/<date>")
@login_required
def get_attendance_date(year, date):
    data = load_year(year)
    return jsonify(data["attendance"].get(date, {}))

@app.route("/api/years/<int:year>/attendance/<date>", methods=["DELETE"])
@login_required
@admin_required
def delete_attendance_date(year, date):
    data = load_year(year)

    if date in data["attendance"]:
        del data["attendance"][date]
        save_year(year, data)
        return jsonify({"ok": True})

    return jsonify({"error": "not found"}), 404

@app.route("/api/years/<int:year>/stats")
@login_required
def get_stats(year):
    data = load_year(year)
    classes = data["classes"]
    attendance = data["attendance"]

    # per-date total
    date_totals = {}
    for date, classes_att in sorted(attendance.items()):
        total_present = sum(len(v) for v in classes_att.values())
        total_enrolled = sum(len(classes.get(c, [])) for c in classes_att)
        date_totals[date] = {"present": total_present, "enrolled": total_enrolled}

    # per-class
    class_stats = {}
    for cls in classes:
        sessions = 0
        total_present = 0
        enrolled = len(classes[cls])
        for date_data in attendance.values():
            if cls in date_data:
                sessions += 1
                total_present += len(date_data[cls])
        class_stats[cls] = {
            "sessions": sessions,
            "total_present": total_present,
            "enrolled": enrolled,
            "rate": round(total_present / (sessions * enrolled) * 100, 1) if sessions and enrolled else 0
        }

    # per-student
    student_stats = {}
    for cls, students in classes.items():
        for student in students:
            sessions = 0
            present_count = 0
            for date_data in attendance.values():
                if cls in date_data:
                    sessions += 1
                    if student in date_data[cls]:
                        present_count += 1
            student_stats[f"{cls}::{student}"] = {
                "class": cls,
                "name": student,
                "sessions": sessions,
                "present": present_count,
                "rate": round(present_count / sessions * 100, 1) if sessions else 0
            }

    return jsonify({
        "date_totals": date_totals,
        "class_stats": class_stats,
        "student_stats": student_stats
    })

if __name__ == "__main__":
    app.run(debug=True, port=4989)
