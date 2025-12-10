from flask import Blueprint, jsonify, request, session, current_app
from datetime import datetime
import os
import json
from app.db import get_cursor, get_db
from app.utils import require_login, dict_rows

bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route("/food-posts", methods=["GET", "POST"])
def api_food_posts():
    cur = get_cursor()
    if not cur: return jsonify({"error": "Database error"}), 500

    if request.method == "POST":
        if "user_id" not in session: return jsonify({"error": "Unauthorized"}), 401
        
        # Handle both JSON and Form Data
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
        
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
                        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                        os.makedirs(os.path.dirname(upload_path), exist_ok=True)
                        image_file.save(upload_path)
                        image_url = f"/static/uploads/{filename}"
                except Exception as e:
                    print(f"❌ Image upload error: {e}")

            # Estimate weight if not provided
            if not weight:
                estimates = {
                    "Meals": 0.5, "Snacks": 0.2, "Beverages": 0.3,
                    "Baked Goods": 0.1, "Fruits": 0.2, "Other": 0.5
                }
                weight = float(quantity) * estimates.get(category, 0.5) if quantity and quantity.replace('.','',1).isdigit() else estimates.get(category, 0.5)

            conn = get_db()
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
            cur.execute("SELECT * FROM posts WHERE id=?", (post_id,))
            new_post = dict_rows(cur.fetchall(), cur.description)[0]
            return jsonify(new_post), 201
            
        except Exception as e:
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

        if status_filter == "available":
            query += " AND p.status='active' AND (p.expires_at IS NULL OR p.expires_at > NOW())"
        elif status_filter == "claimed":
            query += " AND p.status='claimed'"
        elif status_filter == "expired":
            query += " AND (p.status='expired' OR p.expires_at <= NOW())"

        if search:
            query += " AND (p.title LIKE ? OR p.description LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        if cat_filter and cat_filter.lower() != "all types" and cat_filter.lower() != "all":
            query += " AND p.category = ?"
            params.append(cat_filter)

        if diet_filter:
            query += " AND p.dietary_json LIKE ?"
            params.append(f"%{diet_filter}%")

        if sort_order == "endingSoon":
            query += " ORDER BY p.expires_at ASC"
        else: # newest
            query += " ORDER BY p.created_at DESC"

        cur.execute(query, tuple(params))
        posts = dict_rows(cur.fetchall(), cur.description)
        return jsonify(posts)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.get("/food-posts/mine")
def api_my_posts():
    need = require_login()
    if need: return jsonify({"error": "Unauthorized"}), 401
    cur = get_cursor()
    if not cur: return jsonify({"error": "Database error"}), 500

    try:
        cur.execute("""
            SELECT * FROM posts WHERE user_id=? ORDER BY created_at DESC
        """, (session["user_id"],))
        posts = dict_rows(cur.fetchall(), cur.description)

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
        return jsonify({"error": str(e)}), 500

@bp.get("/food-posts/<int:id>")
def api_get_post(id):
    cur = get_cursor()
    if not cur: return jsonify({"error": "Database error"}), 500
    try:
        cur.execute("SELECT p.*, u.email as owner_email FROM posts p JOIN users u ON p.user_id=u.id WHERE p.id=?", (id,))
        rows = cur.fetchall()
        if not rows: return jsonify({"error": "Post not found"}), 404
        post = dict_rows(rows, cur.description)[0]

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

@bp.patch("/food-posts/<int:id>/status")
def api_update_post_status(id):
    need = require_login()
    if need: return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    cur = get_cursor()
    if not cur: return jsonify({"error": "Database error"}), 500
    
    data = request.get_json() or {}
    new_status = data.get("status")
    if not new_status: return jsonify({"error": "Status required"}), 400

    try:
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

@bp.post("/food-posts/<int:id>/claims")
def api_create_claim(id):
    need = require_login()
    if need: return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    cur = get_cursor()
    if not cur: return jsonify({"error": "Database error"}), 500

    data = request.get_json() or {}
    req_qty = data.get("requested_quantity", "1")
    msg = data.get("message", "")

    try:
        cur.execute("SELECT user_id, status, expires_at, quantity FROM posts WHERE id=?", (id,))
        row = cur.fetchone()
        if not row: return jsonify({"error": "Post not found"}), 404
        owner_id, status, expires_at, qty = row

        if owner_id == session["user_id"]: return jsonify({"error": "Cannot claim own post"}), 400
        if status != "active": return jsonify({"error": "Post not available"}), 400
        if expires_at and expires_at <= datetime.now(): return jsonify({"error": "Post expired"}), 400
        
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

@bp.get("/claims/mine")
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

@bp.get("/claims/for-my-posts")
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

@bp.patch("/claims/<int:id>")
def api_update_claim(id):
    need = require_login()
    if need: return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    cur = get_cursor()
    if not cur: return jsonify({"error": "Database error"}), 500
    
    data = request.get_json() or {}
    action = data.get("status")
    if action not in ["accepted", "rejected"]: return jsonify({"error": "Invalid status"}), 400

    try:
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

@bp.patch("/claims/<int:id>/cancel")
def api_cancel_claim(id):
    need = require_login()
    if need: return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
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

@bp.get("/stats/global")
def api_stats_global():
    cur = get_cursor()
    if not cur: return jsonify({"error": "Database error"}), 500
    try:
        stats = {}
        cur.execute("SELECT COUNT(*) FROM posts WHERE status='active' AND (expires_at IS NULL OR expires_at > NOW())")
        stats["available_now"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM posts WHERE status IN ('claimed', 'completed')")
        stats["successfully_shared"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM posts")
        stats["total_posts"] = cur.fetchone()[0]
        cur.execute("SELECT SUM(estimated_weight_kg) FROM posts WHERE status IN ('claimed', 'completed')")
        weight = cur.fetchone()[0]
        stats["food_waste_prevented_kg"] = float(weight) if weight else 0.0
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.get("/stats/me")
def api_stats_me():
    need = require_login()
    if need: return jsonify({"error": "Unauthorized"}), 401
    cur = get_cursor()
    if not cur: return jsonify({"error": "Database error"}), 500
    
    uid = session["user_id"]
    try:
        stats = {}
        cur.execute("SELECT COUNT(*) FROM posts WHERE user_id=?", (uid,))
        stats["posts_created"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM posts WHERE user_id=? AND status IN ('claimed', 'completed')", (uid,))
        stats["posts_shared"] = cur.fetchone()[0]
        cur.execute("SELECT SUM(estimated_weight_kg) FROM posts WHERE user_id=? AND status IN ('claimed', 'completed')", (uid,))
        weight = cur.fetchone()[0]
        stats["weight_shared_kg"] = float(weight) if weight else 0.0
        cur.execute("SELECT COUNT(*) FROM claims WHERE claimer_id=?", (uid,))
        stats["claims_made"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM claims WHERE claimer_id=? AND status='approved'", (uid,))
        stats["claims_accepted"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM claims WHERE claimer_id=? AND status='rejected'", (uid,))
        stats["claims_rejected"] = cur.fetchone()[0]
        cur.execute("SELECT created_at FROM users WHERE id=?", (uid,))
        row = cur.fetchone()
        stats["join_date"] = row[0] if row else None
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
