
import mariadb
import os
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER", "ecobite")
DB_PASS = os.getenv("DB_PASS", "2312093")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "ecobite")

try:
    conn = mariadb.connect(
        user=DB_USER, password=DB_PASS,
        host=DB_HOST, port=DB_PORT,
        database=DB_NAME
    )
    cursor = conn.cursor()
    
    print("--- Posts Table ---")
    cursor.execute("DESCRIBE posts")
    for row in cursor.fetchall():
        print(row)
        
    print("\n--- Claims Table ---")
    cursor.execute("DESCRIBE claims")
    for row in cursor.fetchall():
        print(row)
        
except mariadb.Error as e:
    print(f"Error: {e}")
