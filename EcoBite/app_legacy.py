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
    # if "user_id" not in session:
    #     flash("Please log in first.", "warning")
    #     return redirect(url_for("login"))
    if "user_id" not in session:
        session["user_id"] = 1
        session["email"] = "student@campus.edu"
        session["role"] = "user"
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




# ------------------ API --------------------

@app.route("/api/food-posts", methods=["GET", "POST"])
def api_food_posts():
    cur = get_cursor()
    if not cur: return jsonify({"error": "Database error"}), 500

    if request.method == "POST":
        if "user_id" not in session: return jsonify({"error": "Unauthorized"}), 401
        
        # Handle both JSON and Form Data
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict() # Convert ImmutableMultiDict to dict
            print(f"DEBUG: Received data: {data}")

        
        # Extract fields
        title = data.get("title", "").strip()
        desc = data.get("description", "").strip()
        category = data.get("category", "Other")
        quantity = data.get("quantity") or data.get("qty", "")
        weight = data.get("estimated_weight_kg", 0)
        dietary = data.get("dietary_tags") or request.form.getlist("diet") or []
        location = data.get("location_text") or data.get("location", "").strip()
        pickup_start = data.get("pickup_window_start")
        pickup_end = data.get("pickup_window_end")
        expires_at = data.get("expires_at") or data.get("expiry_time")

        if not title or not desc or not location or not expires_at:
            missing = []
            if not title: missing.append("title")
            if not desc: missing.append("description")
            if not location: missing.append("location")
            if not expires_at: missing.append("expires_at")
            return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

        try:
            dietary_json = json.dumps(dietary)
            
            # Handle Image Upload
            image_file = request.files.get("image") or request.files.get("photo")
            image_url = None
            if image_file and image_file.filename:
                try:
                    ext = os.path.splitext(image_file.filename)[1].lower()
                    if ext in [".jpg", ".jpeg", ".png", ".webp"]:
                        filename = f"{session['user_id']}_{int(datetime.now().timestamp())}{ext}"
                        upload_path = os.path.join("static", "uploads", filename)
                        os.makedirs(os.path.dirname(upload_path), exist_ok=True)
                        image_file.save(upload_path)
                        image_url = f"/static/uploads/{filename}"
                except Exception as e:
                    print(f"❌ Image upload error: {e}")

            # Estimate weight if not provided
            if not weight:
                # Rough estimates in kg
                estimates = {
                    "Meals": 0.5, "Snacks": 0.2, "Beverages": 0.3,
                    "Baked Goods": 0.1, "Fruits": 0.2, "Other": 0.5
                }
                weight = float(quantity) * estimates.get(category, 0.5) if quantity and quantity.replace('.','',1).isdigit() else estimates.get(category, 0.5)

            # Insert
            cur.execute("""
                INSERT INTO posts (
                    user_id, title, description, category, quantity, 
                    estimated_weight_kg, dietary_json, location, 
                    pickup_window_start, pickup_window_end, expires_at, status, image_url, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, NOW())
            """, (
                session["user_id"], title, desc, category, quantity, 
                weight, dietary_json, location, pickup_start, pickup_end, expires_at, image_url
            ))
            conn.commit()
            
            post_id = cur.lastrowid
            
            # Fetch created post to return
            cur.execute("SELECT * FROM posts WHERE id=?", (post_id,))
            new_post = dict_rows(cur.fetchall(), cur.description)[0]
            return jsonify(new_post), 201
            
        except Exception as e:
            print(f"❌ API Create Post Error: {e}")
            conn.rollback()
            return jsonify({"error": str(e)}), 500

    # GET - List posts
    try:
        status_filter = request.args.get("status", "available")
        search = request.args.get("search", "").strip()
        cat_filter = request.args.get("type", "All Types")
        diet_filter = request.args.get("dietary", "")
        sort_order = request.args.get("sort", "newest")

        query = "SELECT p.*, u.email as owner_email FROM posts p JOIN users u ON p.user_id=u.id WHERE 1=1"
        params = []

        # Status filter
        if status_filter == "available":
            query += " AND p.status='active' AND (p.expires_at IS NULL OR p.expires_at > NOW())"
        elif status_filter == "claimed":
            query += " AND p.status='claimed'"
        elif status_filter == "expired":
            query += " AND (p.status='expired' OR p.expires_at <= NOW())"

        # Search
        if search:
            query += " AND (p.title LIKE ? OR p.description LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        # Category
        if cat_filter and cat_filter.lower() != "all types" and cat_filter.lower() != "all":
            query += " AND p.category = ?"
            params.append(cat_filter)

        # Dietary
        if diet_filter:
            query += " AND p.dietary_json LIKE ?"
            params.append(f"%{diet_filter}%")

        # Sort
        if sort_order == "endingSoon":
            query += " ORDER BY p.expires_at ASC"
        else: # newest
            query += " ORDER BY p.created_at DESC"

        cur.execute(query, tuple(params))
        posts = dict_rows(cur.fetchall(), cur.description)
        print(f"DEBUG: Returning {len(posts)} posts. First post image: {posts[0].get('image_url') if posts else 'None'}")
        return jsonify(posts)

    except Exception as e:
        print(f"❌ API List Posts Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.get("/api/food-posts/mine")
def api_my_posts():
    need = require_login()
    if need: return jsonify({"error": "Unauthorized"}), 401
    cur = get_cursor()
    if not cur: return jsonify({"error": "Database error"}), 500

    try:
        # Get posts
        cur.execute("""
            SELECT * FROM posts WHERE user_id=? ORDER BY created_at DESC
        """, (session["user_id"],))
        posts = dict_rows(cur.fetchall(), cur.description)

        # Aggregate claim info for each post
        for p in posts:
            cur.execute("""
                SELECT 
                    COUNT(CASE WHEN status='pending' THEN 1 END) as pending,
                    COUNT(CASE WHEN status='approved' THEN 1 END) as accepted,
                    COUNT(CASE WHEN status='rejected' THEN 1 END) as rejected
                FROM claims WHERE post_id=?
            """, (p['id'],))
            counts = dict_rows(cur.fetchall(), cur.description)[0]
            p['claims_summary'] = counts
            
        return jsonify(posts)
    except Exception as e:
        print(f"❌ API My Posts Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.get("/api/food-posts/<int:id>")
def api_get_post(id):
    cur = get_cursor()
    if not cur: return jsonify({"error": "Database error"}), 500
    try:
        cur.execute("SELECT p.*, u.email as owner_email FROM posts p JOIN users u ON p.user_id=u.id WHERE p.id=?", (id,))
        rows = cur.fetchall()
        if not rows: return jsonify({"error": "Post not found"}), 404
        post = dict_rows(rows, cur.description)[0]

        # If owner, include claims
        if "user_id" in session and session["user_id"] == post["user_id"]:
            cur.execute("""
                SELECT c.*, u.email as claimer_email 
                FROM claims c JOIN users u ON c.claimer_id=u.id 
                WHERE c.post_id=?
            """, (id,))
            post["claims"] = dict_rows(cur.fetchall(), cur.description)
        
        return jsonify(post)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.patch("/api/food-posts/<int:id>/status")
def api_update_post_status(id):
    need = require_login()
    if need: return jsonify({"error": "Unauthorized"}), 401
    cur = get_cursor()
    if not cur: return jsonify({"error": "Database error"}), 500
    
    data = request.get_json() or {}
    new_status = data.get("status")
    if not new_status: return jsonify({"error": "Status required"}), 400

    try:
        # Verify ownership
        cur.execute("SELECT user_id FROM posts WHERE id=?", (id,))
        row = cur.fetchone()
        if not row: return jsonify({"error": "Post not found"}), 404
        if row[0] != session["user_id"]: return jsonify({"error": "Forbidden"}), 403

        cur.execute("UPDATE posts SET status=? WHERE id=?", (new_status, id))
        conn.commit()
        return jsonify({"success": True, "status": new_status})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

@app.post("/api/food-posts/<int:id>/claims")
def api_create_claim(id):
    need = require_login()
    if need: return jsonify({"error": "Unauthorized"}), 401
    cur = get_cursor()
    if not cur: return jsonify({"error": "Database error"}), 500

    data = request.get_json() or {}
    req_qty = data.get("requested_quantity", "1")
    msg = data.get("message", "")

    try:
        # Validate post
        cur.execute("SELECT user_id, status, expires_at, quantity FROM posts WHERE id=?", (id,))
        row = cur.fetchone()
        if not row: return jsonify({"error": "Post not found"}), 404
        owner_id, status, expires_at, qty = row

        if owner_id == session["user_id"]: return jsonify({"error": "Cannot claim own post"}), 400
        if status != "active": return jsonify({"error": "Post not available"}), 400
        if expires_at and expires_at <= datetime.now(): return jsonify({"error": "Post expired"}), 400
        
        # Insert claim
        cur.execute("""
            INSERT INTO claims (post_id, claimer_id, message, requested_quantity, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', NOW())
        """, (id, session["user_id"], msg, req_qty))
        conn.commit()
        
        claim_id = cur.lastrowid
        cur.execute("SELECT * FROM claims WHERE id=?", (claim_id,))
        new_claim = dict_rows(cur.fetchall(), cur.description)[0]
        return jsonify(new_claim), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

@app.get("/api/claims/mine")
def api_my_claims():
    need = require_login()
    if need: return jsonify({"error": "Unauthorized"}), 401
    cur = get_cursor()
    if not cur: return jsonify({"error": "Database error"}), 500
    try:
        cur.execute("""
            SELECT c.*, p.title as post_title, p.location, p.expires_at, u.email as owner_email
            FROM claims c
            JOIN posts p ON c.post_id=p.id
            JOIN users u ON p.user_id=u.id
            WHERE c.claimer_id=?
            ORDER BY c.created_at DESC
        """, (session["user_id"],))
        claims = dict_rows(cur.fetchall(), cur.description)
        return jsonify(claims)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.get("/api/claims/for-my-posts")
def api_incoming_claims():
    need = require_login()
    if need: return jsonify({"error": "Unauthorized"}), 401
    cur = get_cursor()
    if not cur: return jsonify({"error": "Database error"}), 500
    try:
        cur.execute("""
            SELECT c.*, p.title as post_title, u.email as claimer_email, u.id as claimer_id
            FROM claims c
            JOIN posts p ON c.post_id=p.id
            JOIN users u ON c.claimer_id=u.id
            WHERE p.user_id=?
            ORDER BY c.created_at DESC
        """, (session["user_id"],))
        claims = dict_rows(cur.fetchall(), cur.description)
        return jsonify(claims)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.patch("/api/claims/<int:id>")
def api_update_claim(id):
    need = require_login()
    if need: return jsonify({"error": "Unauthorized"}), 401
    cur = get_cursor()
    if not cur: return jsonify({"error": "Database error"}), 500
    
    data = request.get_json() or {}
    action = data.get("status") # accepted or rejected
    if action not in ["accepted", "rejected"]: return jsonify({"error": "Invalid status"}), 400

    try:
        # Verify owner
        cur.execute("""
            SELECT c.post_id, p.user_id, c.requested_quantity, p.quantity
            FROM claims c JOIN posts p ON c.post_id=p.id
            WHERE c.id=?
        """, (id,))
        row = cur.fetchone()
        if not row: return jsonify({"error": "Claim not found"}), 404
        post_id, owner_id, req_qty, post_qty = row
        
        if owner_id != session["user_id"]: return jsonify({"error": "Forbidden"}), 403

        new_status = "approved" if action == "accepted" else "rejected"
        
        cur.execute("UPDATE claims SET status=?, decided_at=NOW() WHERE id=?", (new_status, id))
        
        if new_status == "approved":
            # Try to update quantity
            try:
                p_q = float(str(post_qty).split()[0]) 
                r_q = float(str(req_qty).split()[0])
                rem_q = max(0, p_q - r_q)
                
                if rem_q <= 0:
                    cur.execute("UPDATE posts SET status='claimed', quantity='0' WHERE id=?", (post_id,))
                else:
                    cur.execute("UPDATE posts SET quantity=? WHERE id=?", (str(rem_q), post_id))
            except:
                pass

        conn.commit()
        return jsonify({"success": True, "status": new_status})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

@app.patch("/api/claims/<int:id>/cancel")
def api_cancel_claim(id):
    need = require_login()
    if need: return jsonify({"error": "Unauthorized"}), 401
    cur = get_cursor()
    if not cur: return jsonify({"error": "Database error"}), 500

    try:
        cur.execute("SELECT claimer_id FROM claims WHERE id=?", (id,))
        row = cur.fetchone()
        if not row: return jsonify({"error": "Claim not found"}), 404
        if row[0] != session["user_id"]: return jsonify({"error": "Forbidden"}), 403

        cur.execute("UPDATE claims SET status='cancelled' WHERE id=?", (id,))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500


@app.get("/api/stats/global")
def api_stats_global():
    cur = get_cursor()
    if not cur: return jsonify({"error": "Database error"}), 500
    try:
        stats = {}
        
        # Available Now
        cur.execute("SELECT COUNT(*) FROM posts WHERE status='active' AND (expires_at IS NULL OR expires_at > NOW())")
        stats["available_now"] = cur.fetchone()[0]
        
        # Successfully Shared (claimed or completed)
        cur.execute("SELECT COUNT(*) FROM posts WHERE status IN ('claimed', 'completed')")
        stats["successfully_shared"] = cur.fetchone()[0]
        
        # Total Posts
        cur.execute("SELECT COUNT(*) FROM posts")
        stats["total_posts"] = cur.fetchone()[0]
        
        # Food Waste Prevented (kg)
        cur.execute("SELECT SUM(estimated_weight_kg) FROM posts WHERE status IN ('claimed', 'completed')")
        weight = cur.fetchone()[0]
        stats["food_waste_prevented_kg"] = float(weight) if weight else 0.0
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.get("/api/stats/me")
def api_stats_me():
    need = require_login()
    if need: return jsonify({"error": "Unauthorized"}), 401
    cur = get_cursor()
    if not cur: return jsonify({"error": "Database error"}), 500
    
    uid = session["user_id"]
    try:
        stats = {}
        
        # Posts Created
        cur.execute("SELECT COUNT(*) FROM posts WHERE user_id=?", (uid,))
        stats["posts_created"] = cur.fetchone()[0]
        
        # Posts Successfully Shared
        cur.execute("SELECT COUNT(*) FROM posts WHERE user_id=? AND status IN ('claimed', 'completed')", (uid,))
        stats["posts_shared"] = cur.fetchone()[0]
        
        # Total Weight Shared
        cur.execute("SELECT SUM(estimated_weight_kg) FROM posts WHERE user_id=? AND status IN ('claimed', 'completed')", (uid,))
        weight = cur.fetchone()[0]
        stats["weight_shared_kg"] = float(weight) if weight else 0.0
        
        # Claims Made
        cur.execute("SELECT COUNT(*) FROM claims WHERE claimer_id=?", (uid,))
        stats["claims_made"] = cur.fetchone()[0]
        
        # Claims Accepted
        cur.execute("SELECT COUNT(*) FROM claims WHERE claimer_id=? AND status='approved'", (uid,))
        stats["claims_accepted"] = cur.fetchone()[0]
        
        # Claims Rejected
        cur.execute("SELECT COUNT(*) FROM claims WHERE claimer_id=? AND status='rejected'", (uid,))
        stats["claims_rejected"] = cur.fetchone()[0]
        
        # Join Date
        cur.execute("SELECT created_at FROM users WHERE id=?", (uid,))
        row = cur.fetchone()
        stats["join_date"] = row[0] if row else None
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------ Main -----------------------
if __name__ == "__main__":
    app.run(debug=True)
