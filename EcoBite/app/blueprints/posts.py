from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta
import json
from app.db import get_cursor, get_db
from app.utils import require_login, compute_stats, dict_rows

bp = Blueprint('posts', __name__)

@bp.route("/create", methods=["GET","POST"])
def create():
    need = require_login(); 
    if need: return need
    if request.method == "POST":
        desc = request.form.get("description","").strip()
        category = request.form.get("category","Other")
        qty = request.form.get("qty","")
        expiry_str = request.form.get("expiry_time","")
        location = request.form.get("location","").strip()
        diets = request.form.getlist("diet")
        dietary_json = json.dumps(diets) if diets else None
        
        if not desc or not expiry_str or not location:
            flash("All required fields must be filled.","error")
            return redirect(url_for("posts.create"))
        
        try:
            if 'T' in expiry_str:
                expiry_dt = datetime.strptime(expiry_str, '%Y-%m-%dT%H:%M')
            else:
                expiry_dt = datetime.now() + timedelta(minutes=int(expiry_str) if expiry_str.isdigit() else 60)
            
            now = datetime.now()
            delta = expiry_dt - now
            expiry_minutes = max(1, int(delta.total_seconds() / 60))
            
            conn = get_db()
            cur = get_cursor()
            if cur is None:
                flash("Database connection error. Please try again.","error")
                return redirect(url_for("posts.create"))
            cur.execute("""
                INSERT INTO posts (user_id,description,category,quantity,dietary_json,location,expiry_minutes,expires_at,status)
                VALUES (?,?,?,?,?,?,?,?,'active')
            """, (session["user_id"],desc,category,qty or None,dietary_json,location,expiry_minutes,expiry_dt))
            conn.commit()
            flash("Post shared successfully!","success")
            return redirect(url_for("main.home"))
        except ValueError as e:
            print("❌ Date parse error:", e)
            flash("Invalid date/time format.","error")
            return redirect(url_for("posts.create"))
        except Exception as e:
            conn.rollback()
            print("❌ Post error:", e)
            flash("Could not create post.","error")
            return redirect(url_for("posts.create"))
    return render_template("create.html")

@bp.route("/myposts")
def myposts():
    need = require_login(); 
    if need: return need
    cur = get_cursor()
    if cur is None:
        flash("Database connection error. Please try again.","error")
        return redirect(url_for("main.home"))
    posts = []
    try:
        cur.execute("""
            SELECT id,description,category,quantity,status,created_at
            FROM posts WHERE user_id=? ORDER BY created_at DESC
        """,(session["user_id"],))
        posts = dict_rows(cur.fetchall(), cur.description)
    except Exception as e:
        print("❌ MyPosts error:", e); posts=[]
    stats = compute_stats(session["user_id"])
    return render_template("myposts.html", posts=posts, stats=stats)
