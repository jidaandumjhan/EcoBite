from flask import Blueprint, render_template, redirect, url_for, session, flash
from app.db import get_cursor
from app.utils import require_login, compute_stats, dict_rows

bp = Blueprint('main', __name__)

@bp.route("/")
def landing():
    """Landing page - shown first to all visitors"""
    if "user_id" in session:
        return redirect(url_for("main.home"))
    return render_template("landing.html")

@bp.route("/home")
def home():
    if "user_id" not in session: return redirect(url_for("auth.login"))
    cur = get_cursor()
    posts = []
    if cur:
        try:
            cur.execute("""
                SELECT p.id,p.description,p.category,p.quantity,p.status,p.location,
                       p.expires_at,u.email AS owner_email
                FROM posts p
                JOIN users u ON p.user_id=u.id
                WHERE p.status='active' AND (p.expires_at IS NULL OR p.expires_at > NOW())
                ORDER BY p.created_at DESC
            """)
            posts = dict_rows(cur.fetchall(), cur.description)
        except Exception as e:
            print("❌ Feed error:", e); posts=[]
    stats = compute_stats()
    return render_template("index.html", posts=posts, stats=stats, email=session.get("email"))

@bp.route("/profile")
def profile():
    need = require_login(); 
    if need: return need
    stats = compute_stats(session["user_id"])
    return render_template("profile.html", stats=stats)
