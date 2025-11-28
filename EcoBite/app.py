import os
import json
from datetime import datetime, timedelta
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
DB_USER = os.getenv("DB_USER", "ecobite")
DB_PASS = os.getenv("DB_PASS", "2312093")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "ecobite")

# Print database configuration for debugging
print(f"📊 Database Config: Host={DB_HOST}, Port={DB_PORT}, User={DB_USER}, Database={DB_NAME}")

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
    error_msg = str(e)
    print(f"❌ Database connection failed: {e}")
    if "Unknown database" in error_msg:
        print(f"💡 Tip: The database '{DB_NAME}' might not exist.")
        print(f"   Create it with: CREATE DATABASE `{DB_NAME}`;")
        print(f"   Or connect without specifying database and create it.")
    elif "Access denied" in error_msg:
        print(f"💡 Tip: Check your credentials - User: {DB_USER}, Password: {DB_PASS}")
    else:
        print(f"💡 Check if MariaDB is running on {DB_HOST}:{DB_PORT}")

# ------------------ Helpers --------------------
ALLOWED_ROLES = {"user", "business", "admin"}

def get_cursor():
    """Get database cursor, creating connection if needed"""
    global conn, cursor
    if cursor is None or conn is None:
        try:
            # First try to connect with the database
            conn = mariadb.connect(
                user=DB_USER, password=DB_PASS,
                host=DB_HOST, port=DB_PORT,
                database=DB_NAME
            )
            cursor = conn.cursor()
            print("✅ Connected to MariaDB!")
        except mariadb.Error as e:
            error_msg = str(e)
            print(f"❌ Database connection failed: {e}")
            
            # If database doesn't exist, try to create it
            if "Unknown database" in error_msg:
                try:
                    print(f"🔄 Attempting to create database '{DB_NAME}'...")
                    # Connect without database specified
                    temp_conn = mariadb.connect(
                        user=DB_USER, password=DB_PASS,
                        host=DB_HOST, port=DB_PORT
                    )
                    temp_cursor = temp_conn.cursor()
                    # Create database
                    temp_cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
                    temp_conn.commit()
                    temp_cursor.close()
                    temp_conn.close()
                    print(f"✅ Database '{DB_NAME}' created successfully!")
                    
                    # Now connect with the database
                    conn = mariadb.connect(
                        user=DB_USER, password=DB_PASS,
                        host=DB_HOST, port=DB_PORT,
                        database=DB_NAME
                    )
                    cursor = conn.cursor()
                    print("✅ Connected to MariaDB!")
                except mariadb.Error as create_error:
                    print(f"❌ Failed to create database: {create_error}")
                    # Only flash if we're in a request context
                    try:
                        from flask import has_request_context
                        if has_request_context():
                            flash("Database connection error. Please ensure MariaDB is running and the database exists.", "error")
                    except:
                        pass
                    return None
            else:
                # Only flash if we're in a request context
                try:
                    from flask import has_request_context
                    if has_request_context():
                        flash("Database connection error. Please check your database configuration.", "error")
                except:
                    pass
                return None
    return cursor

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
    cur = get_cursor()
    if cur is None:
        return stats
    try:
        # available
        q = """
            SELECT COUNT(*) FROM posts
            WHERE status='active' AND (expires_at IS NULL OR expires_at > NOW())
        """
        cur.execute(q + (" AND user_id=?" if user_id else ""), (user_id,) if user_id else ())
        stats["available"] = cur.fetchone()[0]
        # shared
        cur.execute("SELECT COUNT(*) FROM posts WHERE status='claimed'" + (" AND user_id=?" if user_id else ""), (user_id,) if user_id else ())
        stats["shared"] = cur.fetchone()[0]
        # total
        cur.execute("SELECT COUNT(*) FROM posts" + (" WHERE user_id=?" if user_id else ""), (user_id,) if user_id else ())
        stats["total"] = cur.fetchone()[0]
        stats["co2"] = co2_estimate(stats["shared"])
    except Exception as e:
        print("❌ Stats error:", e)
    return stats

# ------------------ Landing & Auth Routes ----------------
@app.get("/")
def landing():
    """Landing page - shown first to all visitors"""
    # If user is already logged in, redirect to home
    if "user_id" in session:
        return redirect(url_for("home"))
    return render_template("landing.html")

@app.get("/get-started")
def get_started():
    """Get Started page - shows sign in/sign up options"""
    # If user is already logged in, redirect to home
    if "user_id" in session:
        return redirect(url_for("home"))
    return render_template("get_started.html")

@app.get("/login")
def login(): 
    # If user is already logged in, redirect to home
    if "user_id" in session:
        return redirect(url_for("home"))
    return render_template("login.html")

@app.post("/login")
def login_post():
    email = request.form.get("email","").strip().lower()
    password = request.form.get("password","")
    cur = get_cursor()
    if cur is None:
        return redirect(url_for("login"))
    try:
        cur.execute("SELECT id,email,password_hash,role FROM users WHERE email=?", (email,))
        row = cur.fetchone()
        if not row or not check_password_hash(row[2], password):
            flash("Invalid email or password.","error")
            return redirect(url_for("login"))
        session.update({"user_id": row[0], "email": row[1], "role": row[3]})
        flash("Welcome back!","success")
        return redirect(url_for("home"))
    except Exception as e:
        print(f"❌ Login error: {e}")
        flash("An error occurred. Please try again.","error")
        return redirect(url_for("login"))

@app.post("/logout")
def logout():
    session.clear(); flash("Logged out.","info")
    return redirect(url_for("landing"))

@app.get("/signup")
def signup(): 
    # If user is already logged in, redirect to home
    if "user_id" in session:
        return redirect(url_for("home"))
    return render_template("signup.html")

@app.post("/signup")
def signup_post():
    email = request.form.get("email","").strip().lower()
    password = request.form.get("password","")
    role = (request.form.get("role","user") or "user").strip().lower()
    if role not in ALLOWED_ROLES: role = "user"
    
    # Validate input
    if not email or not password:
        flash("Email and password are required.","error")
        return redirect(url_for("signup"))
    
    pw_hash = generate_password_hash(password)
    cur = get_cursor()
    if cur is None:
        flash("Database connection error. Please try again.","error")
        return redirect(url_for("signup"))
    
    try:
        # Check if email already exists before attempting to insert
        cur.execute("SELECT id FROM users WHERE email=?", (email,))
        if cur.fetchone():
            flash("Email already exists. Please use a different email or login instead.","error")
            return redirect(url_for("signup"))
        
        # Insert new user
        cur.execute("INSERT INTO users (email,password_hash,role) VALUES (?,?,?)", (email,pw_hash,role))
        conn.commit()
        
        # Get the newly created user
        cur.execute("SELECT id,role FROM users WHERE email=?", (email,))
        u = cur.fetchone()
        session.update({"user_id":u[0],"email":email,"role":u[1]})
        flash("Account created!","success")
        return redirect(url_for("home"))
    except mariadb.IntegrityError as e:
        # Fallback error handling in case of race condition
        conn.rollback()
        error_msg = str(e).lower()
        if "duplicate" in error_msg and "email" in error_msg:
            flash("Email already exists. Please use a different email or login instead.","error")
        else:
            flash("An error occurred during registration. Please try again.","error")
            print(f"❌ Signup IntegrityError: {e}")
        return redirect(url_for("signup"))
    except Exception as e:
        conn.rollback()
        print(f"❌ Signup error: {e}")
        flash("An error occurred. Please try again.","error")
        return redirect(url_for("signup"))

# ------------------ Home / Feed ----------------
@app.get("/home")
def home():
    if "user_id" not in session: return redirect(url_for("login"))
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
        expiry_str = request.form.get("expiry_time","")
        location = request.form.get("location","").strip()
        diets = request.form.getlist("diet")
        dietary_json = json.dumps(diets) if diets else None
        
        if not desc or not expiry_str or not location:
            flash("All required fields must be filled.","error")
            return redirect(url_for("create"))
        
        try:
            # Parse datetime-local format (YYYY-MM-DDTHH:MM) - no timezone, treat as local
            if 'T' in expiry_str:
                expiry_dt = datetime.strptime(expiry_str, '%Y-%m-%dT%H:%M')
            else:
                # Fallback: assume minutes if numeric
                expiry_dt = datetime.now() + timedelta(minutes=int(expiry_str) if expiry_str.isdigit() else 60)
            
            now = datetime.now()
            # Calculate minutes until expiry
            delta = expiry_dt - now
            expiry_minutes = max(1, int(delta.total_seconds() / 60))
            
            # Calculate expires_at datetime
            cur = get_cursor()
            if cur is None:
                flash("Database connection error. Please try again.","error")
                return redirect(url_for("create"))
            cur.execute("""
                INSERT INTO posts (user_id,description,category,quantity,dietary_json,location,expiry_minutes,expires_at,status)
                VALUES (?,?,?,?,?,?,?,?,'active')
            """, (session["user_id"],desc,category,qty or None,dietary_json,location,expiry_minutes,expiry_dt))
            conn.commit()
            flash("Post shared successfully!","success")
            return redirect(url_for("home"))
        except ValueError as e:
            print("❌ Date parse error:", e)
            flash("Invalid date/time format.","error")
            return redirect(url_for("create"))
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
    cur = get_cursor()
    if cur is None:
        flash("Database connection error. Please try again.","error")
        return redirect(url_for("home"))
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
    cur = get_cursor()
    if cur is None:
        flash("Database connection error. Please try again.","error")
        return redirect(url_for("home"))
    try:
        # Prevent claiming own post
        cur.execute("SELECT user_id,status FROM posts WHERE id=?", (post_id,))
        row = cur.fetchone()
        if not row: flash("Post not found.","error"); return redirect(url_for("home"))
        if row[0]==session["user_id"]: flash("You cannot claim your own post.","error"); return redirect(url_for("home"))
        if row[1]!="active": flash("Post is not available.","error"); return redirect(url_for("home"))

        # Insert claim
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
        print("❌ Claim error:", e); conn.rollback()
        flash("Could not process claim.","error")
    return redirect(url_for("home"))

# ---- 2. Owner approves / rejects ----
@app.post("/claim/<int:claim_id>/<action>")
def update_claim_status(claim_id, action):
    need = require_login()
    if need: return need
    if action not in ("approve","reject"): return "Invalid action",400
    cur = get_cursor()
    if cur is None:
        flash("Database connection error. Please try again.","error")
        return redirect(url_for("myposts"))
    try:
        cur.execute("""
            SELECT c.post_id,p.user_id
            FROM claims c JOIN posts p ON c.post_id=p.id
            WHERE c.id=?
        """,(claim_id,))
        claim = cur.fetchone()
        if not claim: flash("Claim not found.","error"); return redirect(url_for("myposts"))
        post_id, owner_id = claim
        if owner_id != session["user_id"]:
            flash("You are not authorized.","error")
            return redirect(url_for("myposts"))
        new_status = "approved" if action=="approve" else "rejected"
        cur.execute("""
            UPDATE claims SET status=?, decided_at=NOW() WHERE id=?
        """,(new_status,claim_id))
        # If approved -> mark post as claimed
        if new_status=="approved":
            cur.execute("UPDATE posts SET status='claimed' WHERE id=?", (post_id,))
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
    cur = get_cursor()
    if cur is None:
        flash("Database connection error. Please try again.","error")
        return redirect(url_for("home"))
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

# ---- 4. Claims Received (requests on my posts) ----
@app.get("/claims")
def claims():
    need = require_login()
    if need: return need
    cur = get_cursor()
    if cur is None:
        flash("Database connection error. Please try again.","error")
        return redirect(url_for("home"))
    incoming = []
    try:
        cur.execute("""
            SELECT c.id, c.status, c.message, c.created_at,
                   p.description, u.email AS claimer_email
            FROM claims c
            JOIN posts p ON c.post_id = p.id
            JOIN users u ON c.claimer_id = u.id
            WHERE p.user_id = ?
            ORDER BY c.created_at DESC
        """,(session["user_id"],))
        incoming = dict_rows(cur.fetchall(), cur.description)
    except Exception as e:
        print("❌ Claims error:", e); incoming=[]
    return render_template("claims.html", claims=incoming)


# ------------------ Main -----------------------
if __name__ == "__main__":
    app.run(debug=True)
