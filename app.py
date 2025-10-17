import os
import random
import uuid
from datetime import datetime
import qrcode
from flask import Flask, render_template, request, jsonify, make_response, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError

# ───────────────────────────────
# INITIAL SETUP
# ───────────────────────────────
app = Flask(__name__)
app.config["SECRET_KEY"] = "secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


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
    """สุ่มเลข 6 หลัก ไม่ซ้ำ"""
    return f"{random.randint(0, 999999):06d}"


@app.before_request
def assign_cookie():
    """กำหนด client_id ให้แต่ละคนผ่านคุกกี้"""
    if request.endpoint == "static":
        return
    if not request.cookies.get("client_id"):
        client_id = uuid.uuid4().hex
        resp = make_response()
        resp.set_cookie("client_id", client_id, max_age=60 * 60 * 24 * 365)
        request._new_cookie_resp = resp


@app.after_request
def attach_cookie(response):
    cookie_resp = getattr(request, "_new_cookie_resp", None)
    if cookie_resp is not None:
        for header, value in cookie_resp.headers:
            if header.lower() == "set-cookie":
                response.headers.add(header, value)
    return response


# ───────────────────────────────
# ROUTES
# ───────────────────────────────
@app.route("/")
def index():
    """หน้าเว็บหลัก แสดง QR ให้สแกน"""
    # URL ที่ QR จะพาไป
    claim_url = url_for("claim", _external=True)
    # สร้าง QR code แล้วแปลงเป็น base64
    import io, base64
    img = qrcode.make(claim_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return render_template("index.html", qr_data=img_b64, claim_url=claim_url)


@app.route("/claim")
def claim():
    """หน้าเมื่อสแกน QR"""
    client_id = request.cookies.get("client_id")
    if not client_id:
        client_id = uuid.uuid4().hex

    # ถ้ามีอยู่แล้ว → ใช้เลขเดิม
    existing = Code.query.filter_by(client_id=client_id).first()
    if existing:
        code = existing.code
    else:
        # สุ่มเลขใหม่ ไม่ให้ซ้ำ
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

    return render_template("claim.html", code=code)


# ───────────────────────────────
# MAIN
# ───────────────────────────────
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
