"""
Web-Based ATM Card Request and Delivery System for Banks in Nigeria.

A lightweight Flask application implementing the modules described in
Chapter Three of the project write-up:

  1. User registration and authentication module
  2. ATM card request module
  3. Request tracking module
  4. Notification management module
  5. Administrative dashboard module
  6. Delivery coordination module
  7. Customer profile management module

Run with:  python app.py   (then open http://127.0.0.1:5000)
"""

import os
import secrets
from datetime import datetime, timezone
from functools import wraps

from flask import (Flask, abort, flash, redirect, render_template, request,
                   send_from_directory, session, url_for)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(16))
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "atm_card_system.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2 MB upload limit

db = SQLAlchemy(app)

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

REQUEST_TYPES = ["New Card", "Replacement Card", "Card Renewal"]
CARD_SCHEMES = ["Verve", "Visa", "Mastercard"]
DELIVERY_METHODS = ["Branch Pickup", "Home Delivery"]

# The card lifecycle used by the tracking module, in order.
STATUS_FLOW = ["Pending", "Approved", "In Production", "Dispatched", "Delivered"]
TERMINAL_STATUSES = ["Rejected"]
HOLD_STATUS = "On Hold"
ALL_STATUSES = STATUS_FLOW + TERMINAL_STATUSES + [HOLD_STATUS]


def utcnow():
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    account_number = db.Column(db.String(10), unique=True, nullable=False)
    address = db.Column(db.String(255), default="")
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), default="customer")  # customer | admin
    created_at = db.Column(db.DateTime, default=utcnow)

    requests = db.relationship("CardRequest", backref="customer", lazy=True)
    notifications = db.relationship("Notification", backref="user", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class CardRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    request_type = db.Column(db.String(30), nullable=False)
    card_scheme = db.Column(db.String(20), nullable=False)
    delivery_method = db.Column(db.String(20), nullable=False)
    delivery_address = db.Column(db.String(255), default="")
    reason = db.Column(db.String(255), default="")
    document_filename = db.Column(db.String(255))
    status = db.Column(db.String(20), default="Pending")
    admin_note = db.Column(db.String(255), default="")
    delivery_agent = db.Column(db.String(120), default="")
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    updates = db.relationship("StatusUpdate", backref="card_request", lazy=True,
                              order_by="StatusUpdate.created_at")

    @property
    def progress_index(self):
        """Position of the current status within the normal flow (-1 if off-flow)."""
        return STATUS_FLOW.index(self.status) if self.status in STATUS_FLOW else -1


class StatusUpdate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("card_request.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    note = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=utcnow)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    channel = db.Column(db.String(10), default="in-app")  # in-app | email | sms
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)


class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    actor = db.Column(db.String(120), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def current_user():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Please log in to continue.", "error")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user or user.role != "admin":
            flash("Administrator access required.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def log_activity(actor, action):
    db.session.add(ActivityLog(actor=actor, action=action))


def notify(user, message):
    """Notification module: records an in-app alert and a simulated email.

    A production deployment would hand the message to an SMS/email gateway
    here; the prototype stores both so the flow can be demonstrated.
    """
    db.session.add(Notification(user_id=user.id, message=message, channel="in-app"))
    db.session.add(Notification(user_id=user.id, message=message, channel="email"))
    app.logger.info("EMAIL to %s: %s", user.email, message)


def generate_reference():
    while True:
        ref = "ATM-" + secrets.token_hex(3).upper()
        if not CardRequest.query.filter_by(reference=ref).first():
            return ref


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def record_status(card_request, status, note=""):
    card_request.status = status
    db.session.add(StatusUpdate(request_id=card_request.id, status=status, note=note))
    notify(card_request.customer,
           f"Your request {card_request.reference} is now '{status}'."
           + (f" Note: {note}" if note else ""))


@app.context_processor
def inject_globals():
    user = current_user()
    unread = 0
    if user:
        unread = Notification.query.filter_by(
            user_id=user.id, is_read=False, channel="in-app").count()
    return dict(current_user=user, unread_count=unread, STATUS_FLOW=STATUS_FLOW)


# --------------------------------------------------------------------------
# Public routes
# --------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        form = request.form
        errors = []
        if not form.get("full_name", "").strip():
            errors.append("Full name is required.")
        if not form.get("email", "").strip():
            errors.append("Email is required.")
        account_number = form.get("account_number", "").strip()
        if not (account_number.isdigit() and len(account_number) == 10):
            errors.append("Account number must be exactly 10 digits (NUBAN format).")
        if len(form.get("password", "")) < 6:
            errors.append("Password must be at least 6 characters.")
        if form.get("password") != form.get("confirm_password"):
            errors.append("Passwords do not match.")
        if User.query.filter_by(email=form.get("email", "").strip().lower()).first():
            errors.append("An account with this email already exists.")
        if User.query.filter_by(account_number=account_number).first():
            errors.append("An account with this account number already exists.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("register.html", form=form), 400

        user = User(
            full_name=form["full_name"].strip(),
            email=form["email"].strip().lower(),
            phone=form.get("phone", "").strip(),
            account_number=account_number,
            address=form.get("address", "").strip(),
        )
        user.set_password(form["password"])
        db.session.add(user)
        db.session.flush()
        notify(user, "Welcome! Your profile has been created successfully.")
        log_activity(user.email, "Registered a new customer account")
        db.session.commit()
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html", form={})


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(request.form.get("password", "")):
            session["user_id"] = user.id
            log_activity(user.email, "Logged in")
            db.session.commit()
            flash(f"Welcome back, {user.full_name}.", "success")
            target = request.args.get("next")
            if user.role == "admin":
                return redirect(target or url_for("admin_dashboard"))
            return redirect(target or url_for("dashboard"))
        flash("Invalid email or password.", "error")
        return render_template("login.html"), 401
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/track", methods=["GET", "POST"])
def track():
    """Public tracking: anyone with a reference code can view request progress."""
    card_request = None
    searched = False
    if request.method == "POST":
        searched = True
        ref = request.form.get("reference", "").strip().upper()
        card_request = CardRequest.query.filter_by(reference=ref).first()
    return render_template("track.html", card_request=card_request, searched=searched)


# --------------------------------------------------------------------------
# Customer routes
# --------------------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    if user.role == "admin":
        return redirect(url_for("admin_dashboard"))
    requests_ = (CardRequest.query.filter_by(user_id=user.id)
                 .order_by(CardRequest.created_at.desc()).all())
    return render_template("dashboard.html", requests=requests_)


@app.route("/requests/new", methods=["GET", "POST"])
@login_required
def new_request():
    user = current_user()
    if request.method == "POST":
        form = request.form
        errors = []
        if form.get("request_type") not in REQUEST_TYPES:
            errors.append("Please choose a valid request type.")
        if form.get("card_scheme") not in CARD_SCHEMES:
            errors.append("Please choose a valid card scheme.")
        if form.get("delivery_method") not in DELIVERY_METHODS:
            errors.append("Please choose a valid delivery method.")
        if (form.get("delivery_method") == "Home Delivery"
                and not form.get("delivery_address", "").strip()):
            errors.append("A delivery address is required for home delivery.")

        document_filename = None
        upload = request.files.get("document")
        if upload and upload.filename:
            if allowed_file(upload.filename):
                document_filename = (secrets.token_hex(4) + "_"
                                     + secure_filename(upload.filename))
            else:
                errors.append("Document must be a PNG, JPG, JPEG or PDF file.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("request_new.html", form=form,
                                   request_types=REQUEST_TYPES,
                                   card_schemes=CARD_SCHEMES,
                                   delivery_methods=DELIVERY_METHODS), 400

        if document_filename:
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            upload.save(os.path.join(app.config["UPLOAD_FOLDER"], document_filename))

        card_request = CardRequest(
            reference=generate_reference(),
            user_id=user.id,
            request_type=form["request_type"],
            card_scheme=form["card_scheme"],
            delivery_method=form["delivery_method"],
            delivery_address=form.get("delivery_address", "").strip() or user.address,
            reason=form.get("reason", "").strip(),
            document_filename=document_filename,
        )
        db.session.add(card_request)
        db.session.flush()
        record_status(card_request, "Pending", "Request submitted and awaiting review.")
        log_activity(user.email, f"Submitted card request {card_request.reference}")
        db.session.commit()
        flash(f"Request submitted. Your tracking reference is {card_request.reference}.",
              "success")
        return redirect(url_for("request_detail", request_id=card_request.id))
    return render_template("request_new.html", form={},
                           request_types=REQUEST_TYPES,
                           card_schemes=CARD_SCHEMES,
                           delivery_methods=DELIVERY_METHODS)


@app.route("/requests/<int:request_id>")
@login_required
def request_detail(request_id):
    user = current_user()
    card_request = db.session.get(CardRequest, request_id) or abort(404)
    if user.role != "admin" and card_request.user_id != user.id:
        abort(403)
    return render_template("request_detail.html", card_request=card_request)


@app.route("/notifications")
@login_required
def notifications():
    user = current_user()
    items = (Notification.query.filter_by(user_id=user.id, channel="in-app")
             .order_by(Notification.created_at.desc()).all())
    for n in items:
        n.is_read = True
    db.session.commit()
    return render_template("notifications.html", notifications=items)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user()
    if request.method == "POST":
        user.full_name = request.form.get("full_name", user.full_name).strip()
        user.phone = request.form.get("phone", user.phone).strip()
        user.address = request.form.get("address", user.address).strip()
        new_password = request.form.get("new_password", "")
        if new_password:
            if len(new_password) < 6:
                flash("New password must be at least 6 characters.", "error")
                return render_template("profile.html"), 400
            user.set_password(new_password)
            flash("Password updated.", "success")
        log_activity(user.email, "Updated profile information")
        db.session.commit()
        flash("Profile saved.", "success")
        return redirect(url_for("profile"))
    return render_template("profile.html")


@app.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    user = current_user()
    card_request = CardRequest.query.filter_by(document_filename=filename).first()
    if not card_request:
        abort(404)
    if user.role != "admin" and card_request.user_id != user.id:
        abort(403)
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# --------------------------------------------------------------------------
# Admin routes
# --------------------------------------------------------------------------

@app.route("/admin")
@admin_required
def admin_dashboard():
    counts = {status: CardRequest.query.filter_by(status=status).count()
              for status in ALL_STATUSES}
    total = CardRequest.query.count()
    customers = User.query.filter_by(role="customer").count()
    recent = (CardRequest.query.order_by(CardRequest.created_at.desc())
              .limit(8).all())
    return render_template("admin/dashboard.html", counts=counts, total=total,
                           customers=customers, recent=recent)


@app.route("/admin/requests")
@admin_required
def admin_requests():
    status = request.args.get("status", "")
    query = CardRequest.query
    if status:
        query = query.filter_by(status=status)
    requests_ = query.order_by(CardRequest.created_at.desc()).all()
    return render_template("admin/requests.html", requests=requests_,
                           statuses=ALL_STATUSES, active_status=status)


@app.route("/admin/requests/<int:request_id>", methods=["GET", "POST"])
@admin_required
def admin_request_detail(request_id):
    admin = current_user()
    card_request = db.session.get(CardRequest, request_id) or abort(404)
    if request.method == "POST":
        action = request.form.get("action")
        note = request.form.get("note", "").strip()
        if action == "approve" and card_request.status in ("Pending", "On Hold"):
            record_status(card_request, "Approved", note or "Request verified and approved.")
        elif action == "reject" and card_request.status in ("Pending", "On Hold"):
            record_status(card_request, "Rejected", note or "Request rejected.")
        elif action == "hold" and card_request.status == "Pending":
            record_status(card_request, "On Hold", note or "Request placed on hold.")
        elif action == "advance" and card_request.status in STATUS_FLOW[1:-1]:
            next_status = STATUS_FLOW[card_request.progress_index + 1]
            if next_status == "Dispatched":
                agent = request.form.get("delivery_agent", "").strip()
                if not agent:
                    flash("Assign a delivery agent before dispatching the card.", "error")
                    return render_template("admin/request_detail.html",
                                           card_request=card_request), 400
                card_request.delivery_agent = agent
                note = note or f"Card dispatched via {agent}."
            record_status(card_request, next_status, note)
        else:
            flash("That action is not valid for the current status.", "error")
            return render_template("admin/request_detail.html",
                                   card_request=card_request), 400
        if note:
            card_request.admin_note = note
        log_activity(admin.email,
                     f"{action.title()} on request {card_request.reference} "
                     f"(now {card_request.status})")
        db.session.commit()
        flash(f"Request {card_request.reference} updated to '{card_request.status}'.",
              "success")
        return redirect(url_for("admin_request_detail", request_id=request_id))
    return render_template("admin/request_detail.html", card_request=card_request)


@app.route("/admin/customers")
@admin_required
def admin_customers():
    q = request.args.get("q", "").strip()
    query = User.query.filter_by(role="customer")
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(User.full_name.ilike(like),
                                    User.email.ilike(like),
                                    User.account_number.ilike(like)))
    customers = query.order_by(User.created_at.desc()).all()
    return render_template("admin/customers.html", customers=customers, q=q)


@app.route("/admin/logs")
@admin_required
def admin_logs():
    logs = (ActivityLog.query.order_by(ActivityLog.created_at.desc())
            .limit(200).all())
    return render_template("admin/logs.html", logs=logs)


# --------------------------------------------------------------------------
# Database bootstrap and demo data
# --------------------------------------------------------------------------

def create_default_admin():
    if not User.query.filter_by(role="admin").first():
        admin = User(full_name="Bank Administrator",
                     email="admin@bank.com",
                     phone="08000000000",
                     account_number="0000000000",
                     role="admin")
        admin.set_password(os.environ.get("ADMIN_PASSWORD", "admin123"))
        db.session.add(admin)
        db.session.commit()


def init_db():
    db.create_all()
    create_default_admin()


@app.cli.command("seed")
def seed():
    """Populate the database with demonstration data (flask seed)."""
    init_db()
    if User.query.filter_by(email="ada@example.com").first():
        print("Demo data already present.")
        return
    demo_users = [
        ("Ada Obi", "ada@example.com", "08031112222", "0123456789",
         "12 Allen Avenue, Ikeja, Lagos"),
        ("Chidi Eze", "chidi@example.com", "08033334444", "0987654321",
         "45 Aba Road, Port Harcourt"),
        ("Fatima Bello", "fatima@example.com", "08055556666", "0111222333",
         "7 Zoo Road, Kano"),
    ]
    users = []
    for name, email, phone, acct, addr in demo_users:
        u = User(full_name=name, email=email, phone=phone,
                 account_number=acct, address=addr)
        u.set_password("password")
        db.session.add(u)
        users.append(u)
    db.session.flush()

    specs = [
        (users[0], "New Card", "Verve", "Home Delivery", "Pending"),
        (users[0], "Replacement Card", "Mastercard", "Branch Pickup", "Approved"),
        (users[1], "Card Renewal", "Visa", "Home Delivery", "Dispatched"),
        (users[2], "New Card", "Mastercard", "Home Delivery", "Delivered"),
    ]
    for user, rtype, scheme, method, final_status in specs:
        cr = CardRequest(reference=generate_reference(), user_id=user.id,
                         request_type=rtype, card_scheme=scheme,
                         delivery_method=method, delivery_address=user.address)
        db.session.add(cr)
        db.session.flush()
        for status in STATUS_FLOW[:STATUS_FLOW.index(final_status) + 1]:
            if status == "Dispatched":
                cr.delivery_agent = "Swift Couriers NG"
            record_status(cr, status)
    db.session.commit()
    print("Seeded 3 demo customers (password: password) and 4 card requests.")


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True)
