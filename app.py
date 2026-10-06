import os
import re
import secrets
import time
from functools import wraps

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from extensions import db
from models import Link, User

CATEGORIES = ["Meetings", "YouTube", "Study", "Work", "News", "Tools", "Social", "Other"]
CAT_COLORS = {
    "Meetings": "#3b82f6", "YouTube": "#ef4444", "Study": "#10b981", "Work": "#f59e0b",
    "News": "#06b6d4", "Tools": "#8b5cf6", "Social": "#ec4899", "Other": "#6b7280",
}
CAT_ICONS = {
    "Meetings": "bi-camera-video", "YouTube": "bi-youtube", "Study": "bi-book",
    "Work": "bi-briefcase", "News": "bi-newspaper", "Tools": "bi-wrench",
    "Social": "bi-people", "Other": "bi-three-dots",
}
MAX_FAILS, LOCK_SECS = 5, 300
_fails = {}                # ip -> (count, first_fail_time)


def normalize_url(url):
    """Return a safe http(s) URL, or None if it is not acceptable."""
    url = url.strip()
    if not url:
        return None
    low = url.lower()
    if low.startswith(("http://", "https://")):
        return url
    if "://" in low or low.startswith(("javascript:", "data:", "vbscript:", "file:")):
        return None
    return "https://" + url


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key-in-production")
    # SQLite by default. For PostgreSQL set DATABASE_URL, e.g.
    #   postgresql://user:password@localhost:5432/beamer
    db_url = os.environ.get("DATABASE_URL", "sqlite:///beamer_team.db")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    db.init_app(app)
    with app.app_context():
        db.create_all()
        seed()

    # ── helpers ─────────────────────────────────────────────────────────────
    def csrf_token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        return session["csrf"]

    app.jinja_env.globals["csrf_token"] = csrf_token

    def can_edit(link):
        """Admin can manage every link; a member only their own."""
        return bool(g.user) and (g.user.is_admin or link.created_by == g.user.id)

    @app.context_processor
    def inject():
        return dict(CAT_COLORS=CAT_COLORS, CAT_ICONS=CAT_ICONS, categories=CATEGORIES,
                    can_edit=can_edit)

    @app.before_request
    def load_user():
        g.user = None
        uid = session.get("uid")
        if uid:
            u = db.session.get(User, uid)
            if u and u.active:
                g.user = u
            else:
                session.pop("uid", None)
        if request.method == "POST":
            sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
            if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
                abort(400, "Session expired. Please go back, refresh and try again.")

    @app.after_request
    def headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        if g.get("user"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    def login_required(f):
        @wraps(f)
        def wrapper(*a, **kw):
            if not g.user:
                return redirect(url_for("login"))
            return f(*a, **kw)
        return wrapper

    def admin_required(f):
        @wraps(f)
        @login_required
        def wrapper(*a, **kw):
            if not g.user.is_admin:
                abort(403)
            return f(*a, **kw)
        return wrapper

    def all_links():
        """Every link is visible to everyone in the team (no private links)."""
        return Link.query

    def read_link_form():
        title = request.form.get("title", "").strip()
        url = normalize_url(request.form.get("url", ""))
        category = request.form.get("category", "Other")
        note = request.form.get("note", "").strip()[:300]
        if category not in CATEGORIES:
            category = "Other"
        errors = []
        if not title:
            errors.append("Title is required.")
        if not url:
            errors.append("Enter a valid http/https URL.")
        return dict(title=title, url=url, category=category, note=note or None), errors

    def members_list():
        return User.query.filter_by(role="member").order_by(User.emp_id).all()

    # ── auth ────────────────────────────────────────────────────────────────
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.user:
            return redirect(url_for("index"))
        if request.method == "POST":
            ip = request.remote_addr or "?"
            count, first = _fails.get(ip, (0, 0))
            if count >= MAX_FAILS and time.time() - first < LOCK_SECS:
                flash("Too many attempts. Try again in a few minutes.", "danger")
                return render_template("login.html"), 429
            emp = request.form.get("emp_id", "").strip().upper()
            pw = request.form.get("password", "")
            user = User.query.filter_by(emp_id=emp).first()
            if user and user.active and user.check_password(pw):
                _fails.pop(ip, None)
                session.clear()
                session["uid"] = user.id
                session["csrf"] = secrets.token_hex(16)
                return redirect(url_for("index"))
            if count == 0 or time.time() - first >= LOCK_SECS:
                _fails[ip] = (1, time.time())
            else:
                _fails[ip] = (count + 1, first)
            flash("Invalid employee ID or password.", "danger")
        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/password", methods=["GET", "POST"])
    @login_required
    def change_password():
        if request.method == "POST":
            cur = request.form.get("current", "")
            new = request.form.get("new", "")
            if not g.user.check_password(cur):
                flash("Current password is wrong.", "danger")
            elif len(new) < 6:
                flash("New password must be at least 6 characters.", "danger")
            elif new != request.form.get("confirm", ""):
                flash("New passwords do not match.", "danger")
            else:
                g.user.set_password(new)
                db.session.commit()
                flash("Password updated.", "success")
                return redirect(url_for("index"))
        return render_template("password.html", page="password")

    # ── dashboard ───────────────────────────────────────────────────────────
    @app.route("/")
    @login_required
    def index():
        cat = request.args.get("category", "")
        q = request.args.get("q", "").strip()
        only_fav = request.args.get("fav") == "1"
        by = request.args.get("by", "")
        by_id = g.user.id if by == "me" else (int(by) if by.isdigit() else None)

        base = all_links()
        counts = {c: base.filter(Link.category == c).count() for c in CATEGORIES}
        total = base.count()
        mine_count = base.filter(Link.created_by == g.user.id).count()
        fav_count = base.filter(Link.fav_by.any(User.id == g.user.id)).count()

        query = base.options(joinedload(Link.creator))
        if cat in CATEGORIES:
            query = query.filter(Link.category == cat)
        else:
            cat = ""
        if by_id is not None:
            query = query.filter(Link.created_by == by_id)
        if only_fav:
            query = query.filter(Link.fav_by.any(User.id == g.user.id))
        if q:
            like = f"%{q}%"
            query = query.filter(or_(Link.title.ilike(like), Link.url.ilike(like), Link.note.ilike(like)))

        links = query.order_by(Link.created_at.desc()).all()
        fav_ids = {l.id for l in g.user.favs}
        stats = None
        if g.user.is_admin:
            stats = dict(links=total, members=User.query.filter_by(role="member").count(),
                         active=User.query.filter_by(role="member", active=True).count())
        everyone = User.query.order_by(User.role, User.name).all()
        return render_template("index.html", links=links, counts=counts, total=total,
                               mine_count=mine_count, fav_count=fav_count, fav_ids=fav_ids,
                               selected=cat, q=q, only_fav=only_fav, by=by, by_id=by_id,
                               everyone=everyone, stats=stats, page="links")

    @app.route("/fav/<int:link_id>", methods=["POST"])
    @login_required
    def toggle_fav(link_id):
        link = db.get_or_404(Link, link_id)
        if link in g.user.favs:
            g.user.favs.remove(link)
            state = False
        else:
            g.user.favs.append(link)
            state = True
        db.session.commit()
        return jsonify(fav=state)

    # ── links (admin + members) ─────────────────────────────────────────────
    @app.route("/add", methods=["GET", "POST"])
    @login_required
    def add_link():
        if request.method == "POST":
            data, errors = read_link_form()
            if errors:
                for e in errors:
                    flash(e, "danger")
                return render_template("link_form.html", link=None, form=request.form, page="add")
            link = Link(title=data["title"], url=data["url"], category=data["category"],
                        note=data["note"], share_all=True, created_by=g.user.id)
            db.session.add(link)
            db.session.commit()
            flash(f'"{link.title}" added. Everyone in the team can see it now.', "success")
            return redirect(url_for("index"))
        return render_template("link_form.html", link=None, form={}, page="add")

    def editable_link_or_403(link_id):
        link = db.get_or_404(Link, link_id)
        if not can_edit(link):
            abort(403)
        return link

    @app.route("/edit/<int:link_id>", methods=["GET", "POST"])
    @login_required
    def edit_link(link_id):
        link = editable_link_or_403(link_id)
        if request.method == "POST":
            data, errors = read_link_form()
            if errors:
                for e in errors:
                    flash(e, "danger")
                return render_template("link_form.html", link=link, form=request.form, page="add")
            link.title, link.url, link.category = data["title"], data["url"], data["category"]
            link.note = data["note"]
            db.session.commit()
            flash(f'"{link.title}" updated.', "success")
            return redirect(url_for("index"))
        return render_template("link_form.html", link=link, form={}, page="add")

    @app.route("/delete/<int:link_id>", methods=["POST"])
    @login_required
    def delete_link(link_id):
        link = editable_link_or_403(link_id)
        title = link.title
        link.fav_by = []
        db.session.delete(link)
        db.session.commit()
        flash(f'"{title}" deleted.', "info")
        return redirect(url_for("index"))

    # ── team (admin) ────────────────────────────────────────────────────────
    @app.route("/team")
    @admin_required
    def team():
        rows = (db.session.query(Link.created_by, func.count(Link.id))
                .group_by(Link.created_by).all())
        link_counts = {uid: n for uid, n in rows}
        return render_template("team.html", members=members_list(), link_counts=link_counts,
                               page="team")

    EMP_RE = re.compile(r"[A-Z0-9_-]{2,30}")

    @app.route("/team/add", methods=["POST"])
    @admin_required
    def team_add():
        emp = request.form.get("emp_id", "").strip().upper()
        name = request.form.get("name", "").strip()
        pw = request.form.get("password", "")
        if not EMP_RE.fullmatch(emp):
            flash("Employee ID: 2-30 letters, numbers, - or _ only.", "danger")
        elif not name:
            flash("Name is required.", "danger")
        elif len(pw) < 6:
            flash("Password must be at least 6 characters.", "danger")
        elif User.query.filter_by(emp_id=emp).first():
            flash("That employee ID already exists.", "danger")
        else:
            u = User(emp_id=emp, name=name[:100], role="member")
            u.set_password(pw)
            db.session.add(u)
            db.session.commit()
            flash(f"{name} ({emp}) added.", "success")
        return redirect(url_for("team"))

    def get_member(uid):
        u = db.get_or_404(User, uid)
        if u.role != "member":
            abort(403)
        return u

    @app.route("/team/<int:uid>/edit", methods=["POST"])
    @admin_required
    def team_edit(uid):
        u = get_member(uid)
        emp = request.form.get("emp_id", "").strip().upper()
        name = request.form.get("name", "").strip()
        clash = User.query.filter(User.emp_id == emp, User.id != u.id).first()
        if not EMP_RE.fullmatch(emp):
            flash("Employee ID: 2-30 letters, numbers, - or _ only.", "danger")
        elif not name:
            flash("Name is required.", "danger")
        elif clash:
            flash("That employee ID already exists.", "danger")
        else:
            u.name, u.emp_id = name[:100], emp
            db.session.commit()
            flash(f"{u.name} ({u.emp_id}) updated.", "success")
        return redirect(url_for("team"))

    @app.route("/team/<int:uid>/reset", methods=["POST"])
    @admin_required
    def team_reset(uid):
        u = get_member(uid)
        pw = request.form.get("password", "")
        if len(pw) < 6:
            flash("Password must be at least 6 characters.", "danger")
        else:
            u.set_password(pw)
            db.session.commit()
            flash(f"Password reset for {u.name}.", "success")
        return redirect(url_for("team"))

    @app.route("/team/<int:uid>/toggle", methods=["POST"])
    @admin_required
    def team_toggle(uid):
        u = get_member(uid)
        u.active = not u.active
        db.session.commit()
        flash(f"{u.name} is now {'active' if u.active else 'deactivated'}.", "info")
        return redirect(url_for("team"))

    @app.route("/team/<int:uid>/delete", methods=["POST"])
    @admin_required
    def team_delete(uid):
        u = get_member(uid)
        u.favs = []
        # keep the member's links for the team; they just lose their "added by" owner
        Link.query.filter(Link.created_by == u.id).update({Link.created_by: None})
        name = u.name
        db.session.delete(u)
        db.session.commit()
        flash(f"{name} removed.", "info")
        return redirect(url_for("team"))

    @app.errorhandler(403)
    def forbidden(_):
        return render_template("error.html", code=403, msg="You don't have access to this page."), 403

    @app.errorhandler(404)
    def not_found(_):
        return render_template("error.html", code=404, msg="Page not found."), 404

    @app.errorhandler(400)
    def bad(e):
        return render_template("error.html", code=400, msg=getattr(e, "description", "Bad request.")), 400

    return app


def seed():
    """First run only: create the leader, 4 members and a few sample links."""
    if User.query.first():
        return
    admin = User(emp_id="EMP001", name="Team Leader", role="admin")
    admin.set_password("admin123")
    db.session.add(admin)
    for i in range(1, 5):
        m = User(emp_id=f"EMP10{i}", name=f"Member {i}", role="member")
        m.set_password("member123")
        db.session.add(m)
    db.session.flush()
    first_member = User.query.filter_by(emp_id="EMP101").first()
    for title, url, cat, note in [
        ("Daily Standup", "https://meet.google.com", "Meetings", "Every day 10:00 AM"),
        ("Python Docs", "https://docs.python.org/3/", "Study", "Official reference"),
        ("Team Drive", "https://drive.google.com", "Work", "Shared project files"),
    ]:
        db.session.add(Link(title=title, url=url, category=cat, note=note,
                            share_all=True, created_by=admin.id))
    db.session.add(Link(title="Team Wiki", url="https://example.com/wiki", category="Work",
                        note="Added by a team member", share_all=True,
                        created_by=first_member.id))
    db.session.commit()


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
