import os
import random
import uuid
from datetime import datetime
import qrcode
from flask import Flask, render_template, jsonify, request, make_response, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

ADMIN_PASSWORD = "qwerty"  # 🔒 Your admin password


# ───────────────────────────────
# DATABASE MODEL
# ───────────────────────────────
class Code(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(64), unique=True, index=True, nullable=False)
    code = db.Column(db.String(6), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ───────────────────────────────
# UTILITIES
# ───────────────────────────────
def init_db():
    with app.app_context():
        db.create_all()

def generate_unique_code():
    return f"{random.randint(0, 999999):06d}"


# ───────────────────────────────
# ROUTES
# ───────────────────────────────
@app.route("/")
def index():
    claim_url = url_for("claim", _external=True)
    import io, base64
    img = qrcode.make(claim_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    total = Code.query.count()
    return render_template("index.html", qr_data=img_b64, claim_url=claim_url, total=total)


@app.route("/claim")
def claim():
    """ให้รหัสกับผู้ใช้ โดยใช้ client_id จาก cookie"""
    client_id = request.cookies.get("client_id")
    new_cookie = None

    # ถ้ายังไม่มี client_id ใน cookie ให้สร้างใหม่
    if not client_id:
        client_id = uuid.uuid4().hex
        new_cookie = client_id

    # ตรวจว่ามีโค้ดอยู่แล้วหรือยัง
    existing = Code.query.filter_by(client_id=client_id).first()
    if existing:
        code = existing.code
    else:
        # พยายามสร้างโค้ดใหม่ (กันเลขซ้ำ)
        for _ in range(20):
            code = generate_unique_code()
            record = Code(client_id=client_id, code=code)
            db.session.add(record)
            try:
                db.session.commit()
                break
            except IntegrityError:
                db.session.rollback()
                continue

    # สร้าง response พร้อม set cookie ถ้ายังไม่มี
    resp = make_response(render_template("claim.html", code=code))
    if new_cookie:
        resp.set_cookie("client_id", new_cookie, max_age=60*60*24*365)
    return resp


@app.route("/api/total")
def api_total():
    """Return total number of users who received a code"""
    return jsonify({"total": Code.query.count()})


@app.route("/api/reset", methods=["POST"])
def reset_data():
    """Delete all data (requires password)"""
    data = request.get_json() or {}
    password = data.get("password")
    if password != ADMIN_PASSWORD:
        return jsonify({"ok": False, "error": "unauthorized"}), 403

    db.session.query(Code).delete()
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/admin")
def admin_page():
    """Admin page showing all codes"""
    codes = Code.query.order_by(Code.created_at.desc()).all()
    return render_template("admin.html", codes=codes)


@app.route("/api/random_winner", methods=["POST"])
def random_winner():
    """Pick a random winner (requires password)"""
    data = request.get_json() or {}
    password = data.get("password")
    if password != ADMIN_PASSWORD:
        return jsonify({"ok": False, "error": "unauthorized"}), 403

    codes = Code.query.all()
    if not codes:
        return jsonify({"ok": False, "error": "no_data"})
    winner = random.choice(codes)
    return jsonify({"ok": True, "code": winner.code})


# ───────────────────────────────
# MAIN ENTRY
# ───────────────────────────────
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
