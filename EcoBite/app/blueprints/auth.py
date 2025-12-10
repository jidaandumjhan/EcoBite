from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash
import mariadb
from app.db import get_cursor, get_db

bp = Blueprint('auth', __name__)

ALLOWED_ROLES = {"user", "business", "admin"}

@bp.route("/get-started")
def get_started():
    """Get Started page - shows sign in/sign up options"""
    if "user_id" in session:
        return redirect(url_for("main.home"))
    return render_template("get_started.html")

@bp.route("/login", methods=["GET", "POST"])
def login(): 
    if "user_id" in session:
        return redirect(url_for("main.home"))
        
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        cur = get_cursor()
        if cur is None:
            return redirect(url_for("auth.login"))
        try:
            cur.execute("SELECT id,email,password_hash,role FROM users WHERE email=?", (email,))
            row = cur.fetchone()
            if not row or not check_password_hash(row[2], password):
                flash("Invalid email or password.","error")
                return redirect(url_for("auth.login"))
            session.update({"user_id": row[0], "email": row[1], "role": row[3]})
            flash("Welcome back!","success")
            return redirect(url_for("main.home"))
        except Exception as e:
            print(f"❌ Login error: {e}")
            flash("An error occurred. Please try again.","error")
            return redirect(url_for("auth.login"))
            
    return render_template("login.html")

@bp.post("/logout")
def logout():
    session.clear()
    flash("Logged out.","info")
    return redirect(url_for("main.landing"))

@bp.route("/signup", methods=["GET", "POST"])
def signup(): 
    if "user_id" in session:
        return redirect(url_for("main.home"))
        
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        role = (request.form.get("role","user") or "user").strip().lower()
        if role not in ALLOWED_ROLES: role = "user"
        
        if not email or not password:
            flash("Email and password are required.","error")
            return redirect(url_for("auth.signup"))
        
        pw_hash = generate_password_hash(password)
        conn = get_db()
        cur = get_cursor()
        if cur is None:
            flash("Database connection error. Please try again.","error")
            return redirect(url_for("auth.signup"))
        
        try:
            cur.execute("SELECT id FROM users WHERE email=?", (email,))
            if cur.fetchone():
                flash("Email already exists. Please use a different email or login instead.","error")
                return redirect(url_for("auth.signup"))
            
            cur.execute("INSERT INTO users (email,password_hash,role) VALUES (?,?,?)", (email,pw_hash,role))
            conn.commit()
            
            cur.execute("SELECT id,role FROM users WHERE email=?", (email,))
            u = cur.fetchone()
            session.update({"user_id":u[0],"email":email,"role":u[1]})
            flash("Account created!","success")
            return redirect(url_for("main.home"))
        except mariadb.IntegrityError as e:
            conn.rollback()
            error_msg = str(e).lower()
            if "duplicate" in error_msg and "email" in error_msg:
                flash("Email already exists. Please use a different email or login instead.","error")
            else:
                flash("An error occurred during registration. Please try again.","error")
                print(f"❌ Signup IntegrityError: {e}")
            return redirect(url_for("auth.signup"))
        except Exception as e:
            conn.rollback()
            print(f"❌ Signup error: {e}")
            flash("An error occurred. Please try again.","error")
            return redirect(url_for("auth.signup"))

    return render_template("signup.html")
