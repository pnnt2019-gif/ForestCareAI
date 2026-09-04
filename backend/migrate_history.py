#!/usr/bin/env python
"""
Migration script to move diagnosis history from localStorage to MySQL.
Users can export their localStorage data and this script will import it.

Usage:
    python migrate_history.py --email user@example.com --data-file exported_history.json
"""

import os
import sys
import json
import pymysql
from datetime import datetime
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url.startswith(("mysql://", "mysql+pymysql://")):
        parsed = urlparse(database_url)
        conn = pymysql.connect(
            host=parsed.hostname or os.getenv("DB_HOST", "localhost"),
            port=parsed.port or int(os.getenv("DB_PORT", "3306")),
            user=parsed.username or os.getenv("DB_USER", "forestcare"),
            password=parsed.password or os.getenv("DB_PASSWORD", "Forestcare@123"),
            database=parsed.path.lstrip("/") or os.getenv("DB_NAME", "forestcare_db"),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
        return conn
    
    if any(os.getenv(key) for key in ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME")):
        conn = pymysql.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER", "forestcare"),
            password=os.getenv("DB_PASSWORD", "Forestcare@123"),
            database=os.getenv("DB_NAME", "forestcare_db"),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
        return conn
    
    raise RuntimeError("MySQL configuration not found in environment variables.")


def migrate_history(email, data_file=None, history_data=None):
    """
    Migrate diagnosis history to MySQL.
    
    Args:
        email: User email address
        data_file: Path to JSON file with history data
        history_data: Direct list of history records
    """
    
    if data_file:
        with open(data_file, 'r', encoding='utf-8') as f:
            history_data = json.load(f)
    
    if not history_data:
        print("No history data to migrate.")
        return False
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get user ID
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        if not user:
            print(f"User with email {email} not found.")
            return False
        
        user_id = user["id"]
        migrated_count = 0
        
        # Insert each history record
        for record in history_data:
            try:
                cur.execute(
                    """INSERT INTO diagnosis_history 
                       (user_id, tree_name, disease_name, symptoms, severity_level, diagnosis_status, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        user_id,
                        record.get("tree", ""),
                        record.get("disease", ""),
                        record.get("symptoms", ""),
                        record.get("level", ""),
                        record.get("status", ""),
                        record.get("date", datetime.now().isoformat())
                    )
                )
                migrated_count += 1
            except Exception as e:
                print(f"Error migrating record {record}: {e}")
        
        conn.commit()
        conn.close()
        
        print(f"Successfully migrated {migrated_count} records to MySQL for {email}")
        return True
    
    except Exception as e:
        print(f"Error during migration: {e}")
        return False


def create_migration_endpoint():
    """
    Create a migration endpoint for the Flask app.
    This is used to migrate data when the user logs in.
    """
    return """
@auth_bp.route("/migrate-history", methods=["POST"])
def migrate_history_endpoint():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    history = data.get("history", [])
    
    if not email or not history:
        return jsonify({"success": False, "message": "Email and history required"}), 400
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Verify user exists
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        user_id = user["id"]
        migrated = 0
        
        for record in history:
            try:
                cur.execute(
                    "INSERT INTO diagnosis_history (user_id, tree_name, disease_name, symptoms, severity_level, diagnosis_status, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (user_id, record.get("tree", ""), record.get("disease", ""), record.get("symptoms", ""), record.get("level", ""), record.get("status", ""), record.get("date", datetime.now().isoformat()))
                )
                migrated += 1
            except:
                pass
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "migrated": migrated})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
"""


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate diagnosis history from localStorage to MySQL")
    parser.add_argument("--email", required=True, help="User email address")
    parser.add_argument("--data-file", help="Path to JSON file with history data")
    
    args = parser.parse_args()
    
    if not args.data_file and len(sys.argv) == 3:
        # Try to read from stdin if no file specified
        print("Paste history JSON data (Ctrl+D when done):")
        data = json.load(sys.stdin)
        success = migrate_history(args.email, history_data=data)
    else:
        success = migrate_history(args.email, data_file=args.data_file)
    
    sys.exit(0 if success else 1)
