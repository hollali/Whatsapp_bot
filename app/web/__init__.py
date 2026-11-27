from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.exceptions import BadRequest

from app.extensions import db
from app.models.user import User
from app.utils import email_field, password_field, string_field

web_bp = Blueprint("web", __name__)


@web_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("web.dashboard"))
    return render_template("index.html")


@web_bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=current_user)


@web_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid credentials", "danger")
        else:
            login_user(user, remember=bool(request.form.get("remember")))
            return redirect(url_for("web.dashboard"))
    return render_template("login.html")


@web_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = request.form.to_dict()
        try:
            email = email_field(data)
            password = password_field(data)
            name = string_field(data, "name", 120, required=False) or email.split("@")[0]
        except BadRequest as exc:
            flash(exc.description, "danger")
            return render_template("register.html")
        if User.query.filter_by(email=email).first():
            flash("Email already registered", "danger")
            return render_template("register.html")
        user = User(email=email, name=name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for("web.dashboard"))
    return render_template("register.html")


@web_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("web.index"))
