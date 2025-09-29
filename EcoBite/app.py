import mariadb
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecret"  # ⚠️ replace with env var in production

# ---------- Database Connection ----------
try:
    conn = mariadb.connect(
        user="EcoBite",
        password="2312093",
        host="127.0.0.1",
        port=3306,
        database="EcoBite"   # make sure DB name matches HeidiSQL exactly
    )
    cursor = conn.cursor()
    print("✅ Connected to MariaDB!")
except mariadb.Error as e:
    print(f"❌ Error connecting to MariaDB: {e}")


# ---------- Routes ----------

@app.get("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Fetch posts from DB
    cursor.execute(
        "SELECT id, description, expiry_minutes, status, created_at "
        "FROM posts ORDER BY created_at DESC"
    )
    rows = cursor.fetchall()

    # Convert to list of dicts (since cursor returns tuples)
    columns = [desc[0] for desc in cursor.description]
    posts = [dict(zip(columns, row)) for row in rows]

    return render_template(
        "index.html",
        email=session.get("email"),
        role=session.get("role"),
        posts=posts
    )


# ---------- Signup ----------
@app.get("/signup")
def signup():
    return render_template("signup.html")


@app.post("/signup")
def signup_post():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password")
    role = request.form.get("role")

    if not email or not password:
        flash("Email and password are required.", "error")
        return redirect(url_for("signup"))

    pw_hash = generate_password_hash(password)

    try:
        cursor.execute(
            "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
            (email, pw_hash, role)
        )
        conn.commit()
    except mariadb.Error as e:
        flash("Email already registered.", "error")
        print(f"❌ Signup error: {e}")
        return redirect(url_for("signup"))

    # Fetch new user
    cursor.execute("SELECT id, role FROM users WHERE email=?", (email,))
    row = cursor.fetchone()
    if row:
        user_id, user_role = row
    else:
        flash("Signup failed.", "error")
        return redirect(url_for("signup"))

    # Save session
    session["user_id"] = user_id
    session["email"] = email
    session["role"] = user_role

    flash("Account created successfully!", "success")
    return redirect(url_for("home"))


# ---------- Login ----------
@app.get("/login")
def login():
    return render_template("login.html")


@app.post("/login")
def login_post():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password")

    cursor.execute("SELECT id, email, password_hash, role FROM users WHERE email=?", (email,))
    row = cursor.fetchone()

    if not row:
        flash("Invalid email or password.", "error")
        return redirect(url_for("login"))

    user_id, user_email, password_hash, role = row

    if not check_password_hash(password_hash, password):
        flash("Invalid email or password.", "error")
        return redirect(url_for("login"))

    # Save session
    session["user_id"] = user_id
    session["email"] = user_email
    session["role"] = role

    flash("Logged in!", "success")
    return redirect(url_for("home"))


# ---------- Logout ----------
@app.post("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))


# ---------- Create Post ----------
@app.route("/create", methods=["GET", "POST"])
def create():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        description = request.form.get("description", "").strip()
        expiry_minutes = request.form.get("expiry_time")

        if not description or not expiry_minutes:
            flash("Description and expiry time are required.", "error")
            return redirect(url_for("create"))

        try:
            cursor.execute(
                """
                INSERT INTO posts (user_id, description, expiry_minutes, status)
                VALUES (?, ?, ?, 'active')
                """,
                (session["user_id"], description, int(expiry_minutes))
            )
            conn.commit()
            flash("Post created successfully!", "success")
            return redirect(url_for("home"))
        except Exception as e:
            conn.rollback()
            print("❌ Create post error:", e)
            flash("Could not create post.", "error")
            return redirect(url_for("create"))

    return render_template("create.html")


# ---------- Run ----------
if __name__ == "__main__":
    app.run(debug=True)
