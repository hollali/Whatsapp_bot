from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

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
    from flask import request, flash
    from app.models.user import User
    from flask_login import login_user
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("web.dashboard"))
        flash("Invalid credentials", "danger")
    return render_template("login.html")


@web_bp.route("/register", methods=["GET", "POST"])
def register():
    from flask import request, flash
    from app.models.user import User
    from app.extensions import db
    from flask_login import login_user
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        name = request.form.get("name")
        if User.query.filter_by(email=email).first():
            flash("Email already registered", "danger")
            return render_template("register.html")
        u = User(email=email, name=name)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        login_user(u)
        return redirect(url_for("web.dashboard"))
    return render_template("register.html")


@web_bp.route("/logout")
@login_required
def logout():
    from flask_login import logout_user
    logout_user()
    return redirect(url_for("web.index"))
