import os
import json
from datetime import datetime
import mariadb
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash

# Optional: load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ------------------ Flask app ------------------
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecret")

# ------------------ Database -------------------
DB_USER = os.getenv("DB_USER", "EcoBite")
DB_PASS = os.getenv("DB_PASS", "2312093")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "EcoBite")

conn, cursor = None, None
try:
    conn = mariadb.connect(
        user=DB_USER, password=DB_PASS,
        host=DB_HOST, port=DB_PORT,
        database=DB_NAME
    )
    cursor = conn.cursor()
    print("✅ Connected to MariaDB!")
except mariadb.Error as e:
    print(f"❌ Database connection failed: {e}")

# ------------------ Helpers --------------------
ALLOWED_ROLES = {"user", "business", "admin"}

def require_login():
    if "user_id" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))
    return None

def dict_rows(rows, desc):
    cols = [d[0] for d in desc]
    return [dict(zip(cols, r)) for r in rows]

def co2_estimate(shared_count): return int(shared_count * 1.5)

def compute_stats(user_id=None):
    stats = {"available": 0, "shared": 0, "total": 0, "co2": 0}
    try:
        # available
        q = """
            SELECT COUNT(*) FROM posts
            WHERE status='active' AND (expires_at IS NULL OR expires_at > NOW())
        """
        cursor.execute(q + (" AND user_id=?" if user_id else ""), (user_id,) if user_id else ())
        stats["available"] = cursor.fetchone()[0]
        # shared
        cursor.execute("SELECT COUNT(*) FROM posts WHERE status='claimed'" + (" AND user_id=?" if user_id else ""), (user_id,) if user_id else ())
        stats["shared"] = cursor.fetchone()[0]
        # total
        cursor.execute("SELECT COUNT(*) FROM posts" + (" WHERE user_id=?" if user_id else ""), (user_id,) if user_id else ())
        stats["total"] = cursor.fetchone()[0]
        stats["co2"] = co2_estimate(stats["shared"])
    except Exception as e:
        print("❌ Stats error:", e)
    return stats

# ------------------ Auth Routes ----------------
@app.get("/login")
def login(): return render_template("login.html")

@app.post("/login")
def login_post():
    email = request.form.get("email","").strip().lower()
    password = request.form.get("password","")
    cursor.execute("SELECT id,email,password_hash,role FROM users WHERE email=?", (email,))
    row = cursor.fetchone()
    if not row or not check_password_hash(row[2], password):
        flash("Invalid email or password.","error")
        return redirect(url_for("login"))
    session.update({"user_id": row[0], "email": row[1], "role": row[3]})
    flash("Welcome back!","success")
    return redirect(url_for("home"))

@app.post("/logout")
def logout():
    session.clear(); flash("Logged out.","info")
    return redirect(url_for("login"))

@app.get("/signup")
def signup(): return render_template("signup.html")

@app.post("/signup")
def signup_post():
    email = request.form.get("email","").strip().lower()
    password = request.form.get("password","")
    role = (request.form.get("role","user") or "user").strip().lower()
    if role not in ALLOWED_ROLES: role = "user"
    pw_hash = generate_password_hash(password)
    try:
        cursor.execute("INSERT INTO users (email,password_hash,role) VALUES (?,?,?)", (email,pw_hash,role))
        conn.commit()
        cursor.execute("SELECT id,role FROM users WHERE email=?", (email,))
        u = cursor.fetchone()
        session.update({"user_id":u[0],"email":email,"role":u[1]})
        flash("Account created!","success")
        return redirect(url_for("home"))
    except mariadb.IntegrityError as e:
        flash("Email already exists.","error")
        print(e); return redirect(url_for("signup"))

# ------------------ Home / Feed ----------------
@app.get("/")
def home():
    if "user_id" not in session: return redirect(url_for("login"))
    try:
        cursor.execute("""
            SELECT p.id,p.description,p.category,p.quantity,p.status,p.location,
                   p.expires_at,u.email AS owner_email
            FROM posts p
            JOIN users u ON p.user_id=u.id
            WHERE p.status='active' AND (p.expires_at IS NULL OR p.expires_at > NOW())
            ORDER BY p.created_at DESC
        """)
        posts = dict_rows(cursor.fetchall(), cursor.description)
    except Exception as e:
        print("❌ Feed error:", e); posts=[]
    stats = compute_stats()
    return render_template("index.html", posts=posts, stats=stats, email=session["email"])

# ------------------ Create Post ----------------
@app.route("/create", methods=["GET","POST"])
def create():
    need = require_login(); 
    if need: return need
    if request.method == "POST":
        desc = request.form.get("description","").strip()
        category = request.form.get("category","Other")
        qty = request.form.get("qty","")
        expiry = request.form.get("expiry_time","0")
        location = request.form.get("location","").strip()
        diets = request.form.getlist("diet")
        dietary_json = json.dumps(diets) if diets else None
        if not desc or not expiry or not location:
            flash("All required fields must be filled.","error")
            return redirect(url_for("create"))
        try:
            cursor.execute("""
                INSERT INTO posts (user_id,description,category,quantity,dietary_json,location,expiry_minutes,status)
                VALUES (?,?,?,?,?,?,?,'active')
            """, (session["user_id"],desc,category,qty or None,dietary_json,location,int(expiry)))
            conn.commit()
            flash("Post shared successfully!","success")
            return redirect(url_for("home"))
        except Exception as e:
            print("❌ Post error:", e); conn.rollback()
            flash("Could not create post.","error")
            return redirect(url_for("create"))
    return render_template("create.html")

# ------------------ My Posts -------------------
@app.get("/myposts")
def myposts():
    need = require_login(); 
    if need: return need
    try:
        cursor.execute("""
            SELECT id,description,category,quantity,status,created_at
            FROM posts WHERE user_id=? ORDER BY created_at DESC
        """,(session["user_id"],))
        posts = dict_rows(cursor.fetchall(), cursor.description)
    except Exception as e:
        print("❌ MyPosts error:", e); posts=[]
    stats = compute_stats(session["user_id"])
    return render_template("myposts.html", posts=posts, stats=stats)

# ------------------ Profile --------------------
@app.get("/profile")
def profile():
    need = require_login(); 
    if need: return need
    stats = compute_stats(session["user_id"])
    return render_template("profile.html", stats=stats)

# =====================================================
# CLAIM SYSTEM (Request / Approve / Reject / MyClaims)
# =====================================================

# ---- 1. Claim a post ----
@app.post("/claim/<int:post_id>")
def claim_post(post_id):
    need = require_login()
    if need: return need
    message = request.form.get("message","").strip()
    try:
        # Prevent claiming own post
        cursor.execute("SELECT user_id,status FROM posts WHERE id=?", (post_id,))
        row = cursor.fetchone()
        if not row: flash("Post not found.","error"); return redirect(url_for("home"))
        if row[0]==session["user_id"]: flash("You cannot claim your own post.","error"); return redirect(url_for("home"))
        if row[1]!="active": flash("Post is not available.","error"); return redirect(url_for("home"))

        # Insert claim
        cursor.execute("""
            INSERT INTO claims (post_id, claimer_id, message)
            VALUES (?, ?, ?)
        """,(post_id, session["user_id"], message or None))
        conn.commit()
        flash("Request sent to owner!","success")
    except mariadb.IntegrityError:
        flash("You already requested this item.","warning")
    except Exception as e:
        print("❌ Claim error:", e); conn.rollback()
        flash("Could not process claim.","error")
    return redirect(url_for("home"))

# ---- 2. Owner approves / rejects ----
@app.post("/claim/<int:claim_id>/<action>")
def update_claim_status(claim_id, action):
    need = require_login()
    if need: return need
    if action not in ("approve","reject"): return "Invalid action",400
    try:
        cursor.execute("""
            SELECT c.post_id,p.user_id
            FROM claims c JOIN posts p ON c.post_id=p.id
            WHERE c.id=?
        """,(claim_id,))
        claim = cursor.fetchone()
        if not claim: flash("Claim not found.","error"); return redirect(url_for("myposts"))
        post_id, owner_id = claim
        if owner_id != session["user_id"]:
            flash("You are not authorized.","error")
            return redirect(url_for("myposts"))
        new_status = "approved" if action=="approve" else "rejected"
        cursor.execute("""
            UPDATE claims SET status=?, decided_at=NOW() WHERE id=?
        """,(new_status,claim_id))
        # If approved -> mark post as claimed
        if new_status=="approved":
            cursor.execute("UPDATE posts SET status='claimed' WHERE id=?", (post_id,))
        conn.commit()
        flash(f"Claim {new_status}.","success")
    except Exception as e:
        print("❌ Approve/Reject error:", e); conn.rollback()
        flash("Action failed.","error")
    return redirect(url_for("myposts"))

# ---- 3. My Requests (claims made by me) ----
@app.get("/requests")
def requests_page():
    need = require_login()
    if need: return need
    try:
        cursor.execute("""
            SELECT c.id, c.status, c.message, c.created_at,
                   p.description, p.category, p.location, u.email AS owner_email
            FROM claims c
            JOIN posts p ON c.post_id = p.id
            JOIN users u ON p.user_id = u.id
            WHERE c.claimer_id = ?
            ORDER BY c.created_at DESC
        """,(session["user_id"],))
        claims = dict_rows(cursor.fetchall(), cursor.description)
    except Exception as e:
        print("❌ Requests error:", e); claims=[]
    return render_template("requests.html", claims=claims)

# ---- 4. Claims Received (requests on my posts) ----
@app.get("/claims")
def claims():
    need = require_login()
    if need: return need
    try:
        cursor.execute("""
            SELECT c.id, c.status, c.message, c.created_at,
                   p.description, u.email AS claimer_email
            FROM claims c
            JOIN posts p ON c.post_id = p.id
            JOIN users u ON c.claimer_id = u.id
            WHERE p.user_id = ?
            ORDER BY c.created_at DESC
        """,(session["user_id"],))
        incoming = dict_rows(cursor.fetchall(), cursor.description)
    except Exception as e:
        print("❌ Claims error:", e); incoming=[]
    return render_template("claims.html", claims=incoming)


# ------------------ Main -----------------------
if __name__ == "__main__":
    app.run(debug=True)
