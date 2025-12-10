from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.db import get_cursor, get_db
from app.utils import require_login, dict_rows
import mariadb

bp = Blueprint('claims', __name__)

@bp.post("/claim/<int:post_id>")
def claim_post(post_id):
    need = require_login()
    if need: return need
    message = request.form.get("message","").strip()
    conn = get_db()
    cur = get_cursor()
    if cur is None:
        flash("Database connection error. Please try again.","error")
        return redirect(url_for("main.home"))
    try:
        cur.execute("SELECT user_id,status FROM posts WHERE id=?", (post_id,))
        row = cur.fetchone()
        if not row: flash("Post not found.","error"); return redirect(url_for("main.home"))
        if row[0]==session["user_id"]: flash("You cannot claim your own post.","error"); return redirect(url_for("main.home"))
        if row[1]!="active": flash("Post is not available.","error"); return redirect(url_for("main.home"))

        cur.execute("""
            INSERT INTO claims (post_id, claimer_id, message)
            VALUES (?, ?, ?)
        """,(post_id, session["user_id"], message or None))
        conn.commit()
        flash("Request sent to owner!","success")
    except mariadb.IntegrityError:
        conn.rollback()
        flash("You already requested this item.","warning")
    except Exception as e:
        conn.rollback()
        print("❌ Claim error:", e)
        flash("Could not process claim.","error")
    return redirect(url_for("main.home"))

@bp.post("/claim/<int:claim_id>/<action>")
def update_claim_status(claim_id, action):
    need = require_login()
    if need: return need
    if action not in ("approve","reject"): return "Invalid action",400
    conn = get_db()
    cur = get_cursor()
    if cur is None:
        flash("Database connection error. Please try again.","error")
        return redirect(url_for("posts.myposts"))
    try:
        cur.execute("""
            SELECT c.post_id,p.user_id
            FROM claims c JOIN posts p ON c.post_id=p.id
            WHERE c.id=?
        """,(claim_id,))
        claim = cur.fetchone()
        if not claim: flash("Claim not found.","error"); return redirect(url_for("posts.myposts"))
        post_id, owner_id = claim
        if owner_id != session["user_id"]:
            flash("You are not authorized.","error")
            return redirect(url_for("posts.myposts"))
        new_status = "approved" if action=="approve" else "rejected"
        cur.execute("""
            UPDATE claims SET status=?, decided_at=NOW() WHERE id=?
        """,(new_status,claim_id))
        
        if new_status=="approved":
            cur.execute("UPDATE posts SET status='claimed' WHERE id=?", (post_id,))
        conn.commit()
        flash(f"Claim {new_status}.","success")
    except Exception as e:
        conn.rollback()
        print("❌ Approve/Reject error:", e)
        flash("Action failed.","error")
    return redirect(url_for("posts.myposts"))

@bp.get("/requests")
def requests_page():
    need = require_login()
    if need: return need
    cur = get_cursor()
    if cur is None:
        flash("Database connection error. Please try again.","error")
        return redirect(url_for("main.home"))
    claims = []
    try:
        cur.execute("""
            SELECT c.id, c.status, c.message, c.created_at,
                   p.description, p.category, p.location, u.email AS owner_email
            FROM claims c
            JOIN posts p ON c.post_id = p.id
            JOIN users u ON p.user_id = u.id
            WHERE c.claimer_id = ?
            ORDER BY c.created_at DESC
        """,(session["user_id"],))
        claims = dict_rows(cur.fetchall(), cur.description)
    except Exception as e:
        print("❌ Requests error:", e); claims=[]
    return render_template("requests.html", claims=claims)
