import mariadb
from flask import g, current_app, flash

def get_db():
    """
    Connects to the database if not already connected for this request.
    Returns the connection object.
    """
    if 'db' not in g:
        try:
            g.db = mariadb.connect(
                user=current_app.config['DB_USER'],
                password=current_app.config['DB_PASS'],
                host=current_app.config['DB_HOST'],
                port=current_app.config['DB_PORT'],
                database=current_app.config['DB_NAME']
            )
        except mariadb.Error as e:
            # If the specific database connects fails, try to connect without DB to see if we can create it
            # This logic mimics the original app.py behavior but scoped properly.
            error_msg = str(e)
            if "Unknown database" in error_msg:
                try:
                    conn = mariadb.connect(
                        user=current_app.config['DB_USER'],
                        password=current_app.config['DB_PASS'],
                        host=current_app.config['DB_HOST'],
                        port=current_app.config['DB_PORT']
                    )
                    cursor = conn.cursor()
                    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{current_app.config['DB_NAME']}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
                    conn.commit()
                    cursor.close()
                    conn.close()
                    
                    # Retry connection
                    g.db = mariadb.connect(
                        user=current_app.config['DB_USER'],
                        password=current_app.config['DB_PASS'],
                        host=current_app.config['DB_HOST'],
                        port=current_app.config['DB_PORT'],
                        database=current_app.config['DB_NAME']
                    )
                except Exception as create_error:
                    print(f"❌ Database creation failed: {create_error}")
                    return None
            else:
                print(f"❌ Database connection failed: {e}")
                return None
                
    return g.db

def get_cursor():
    """
    Returns a cursor for the current request's database connection.
    Safe-guarding against connection errors.
    """
    db = get_db()
    if db:
        return db.cursor()
    return None

def close_db(e=None):
    """
    Closes the database connection at the end of the request.
    """
    db = g.pop('db', None)

    if db is not None:
        db.close()

def init_app(app):
    """
    Register database functions with the Flask app.
    """
    app.teardown_appcontext(close_db)
