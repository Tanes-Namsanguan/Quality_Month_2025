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
    """Initialize the SQLite database."""
    with app.app_context():
        db.create_all()


def generate_unique_code():
    """Generate a unique 6-digit code."""
    return f"{random.randint(0, 999999):06d}"


@app.before_request
def assign_cookie():
    """Assign a unique client_id cookie to each visitor."""
    if request.endpoint == "static":
        return
    if not request.cookies.get("client_id"):
        client_id = uuid.uuid4().hex
        resp = make_response()
        resp.set_cookie("client_id", client_id, max_age=60 * 60 * 24 * 365)  # 1 year
        request._new_cookie_resp = resp


@app.after_request
def attach_cookie(response):
    """Attach the client_id cookie to the response if newly created."""
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
    """Main page showing a QR code to scan."""
    claim_url = url_for("claim", _external=True)

    # Generate QR code for the claim URL
    import io, base64
    img = qrcode.make(claim_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return render_template("index.html", qr_data=img_b64, claim_url=claim_url)


@app.route("/claim")
def claim():
    """Page shown after scanning the QR code."""
    client_id = request.cookies.get("client_id")
    new_cookie = False

    # If the user doesn't have a client_id yet, create one
    if not client_id:
        client_id = uuid.uuid4().hex
        new_cookie = True

    # Check if the user already has a code
    existing = Code.query.filter_by(client_id=client_id).first()

    if existing:
        code = existing.code
    else:
        # Generate a new unique code if not exists
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

    # Prepare the response with the code
    resp = make_response(render_template("claim.html", code=code))

    # If the client_id was newly created, set the cookie
    if new_cookie:
        resp.set_cookie("client_id", client_id, max_age=60 * 60 * 24 * 365)

    return resp

@app.route("/reset", methods=["POST"])
def reset():
    """Delete all data from the database (admin only with password)."""
    data = request.get_json()
    password = data.get("password") if data else None

    if password != "quality_month_2025":
        return jsonify({"status": "error", "message": "Unauthorized: incorrect password."}), 403

    try:
        db.session.query(Code).delete()
        db.session.commit()
        return jsonify({"status": "ok", "message": "All data cleared."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


# ───────────────────────────────
# MAIN ENTRY POINT
# ───────────────────────────────
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
