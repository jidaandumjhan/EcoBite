
import mariadb
import os
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER", "ecobite")
DB_PASS = os.getenv("DB_PASS", "2312093")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "ecobite")

def migrate():
    try:
        conn = mariadb.connect(
            user=DB_USER, password=DB_PASS,
            host=DB_HOST, port=DB_PORT,
            database=DB_NAME
        )
        cursor = conn.cursor()
        
        # Add columns to posts
        print("Migrating posts table...")
        try:
            cursor.execute("ALTER TABLE posts ADD COLUMN title VARCHAR(255) DEFAULT NULL")
            print("Added title to posts")
        except mariadb.Error as e:
            if "Duplicate column" in str(e): print("title already exists")
            else: print(f"Error adding title: {e}")

        try:
            cursor.execute("ALTER TABLE posts ADD COLUMN estimated_weight_kg FLOAT DEFAULT 0")
            print("Added estimated_weight_kg to posts")
        except mariadb.Error as e:
            if "Duplicate column" in str(e): print("estimated_weight_kg already exists")
            else: print(f"Error adding estimated_weight_kg: {e}")

        try:
            cursor.execute("ALTER TABLE posts ADD COLUMN pickup_window_start DATETIME DEFAULT NULL")
            print("Added pickup_window_start to posts")
        except mariadb.Error as e:
            if "Duplicate column" in str(e): print("pickup_window_start already exists")
            else: print(f"Error adding pickup_window_start: {e}")

        try:
            cursor.execute("ALTER TABLE posts ADD COLUMN pickup_window_end DATETIME DEFAULT NULL")
            print("Added pickup_window_end to posts")
        except mariadb.Error as e:
            if "Duplicate column" in str(e): print("pickup_window_end already exists")
            else: print(f"Error adding pickup_window_end: {e}")

        # Add columns to claims
        print("Migrating claims table...")
        try:
            cursor.execute("ALTER TABLE claims ADD COLUMN requested_quantity VARCHAR(255) DEFAULT NULL")
            print("Added requested_quantity to claims")
        except mariadb.Error as e:
            if "Duplicate column" in str(e): print("requested_quantity already exists")
            else: print(f"Error adding requested_quantity: {e}")

        conn.commit()
        conn.close()
        print("Migration complete!")
        
    except mariadb.Error as e:
        print(f"Connection Error: {e}")

if __name__ == "__main__":
    migrate()
