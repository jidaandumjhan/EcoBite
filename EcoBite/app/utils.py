from flask import session, flash, redirect, url_for
from app.db import get_cursor

def require_login():
    """
    Checks if user is logged in. 
    If not, it auto-logs in a default user (development mode behavior from original code)
    or redirects to login (if we were to strictly enforce it).
    
    Original behavior preserved: Auto-login student user if session missing.
    """
    if "user_id" not in session:
        # Preserving the original dev-friendly behavior found in the code
        session["user_id"] = 1
        session["email"] = "student@campus.edu"
        session["role"] = "user"
    return None

def dict_rows(rows, desc):
    """
    Converts DB rows to a list of dictionaries based on cursor description.
    """
    cols = [d[0] for d in desc]
    return [dict(zip(cols, r)) for r in rows]

def co2_estimate(shared_count):
    """Estimate CO2 saved.""" 
    return int(shared_count * 1.5)

def compute_stats(user_id=None):
    """
    Compute stats for homepage or profile.
    """
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
