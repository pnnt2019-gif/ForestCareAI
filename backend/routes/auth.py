import json
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from services.email_service import EmailService

try:
    import firebase_admin
    from firebase_admin import auth as firebase_auth
except ImportError:
    firebase_admin = None
    firebase_auth = None


logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api")
email_service = EmailService()
RESET_TOKENS = {}
OTP_CODES = {}


def _is_mysql_configured():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url.startswith(("mysql://", "mysql+pymysql://")):
        return True
    return all(os.getenv(key) for key in ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME"))


def _is_mysql_connection(conn):
    return type(conn).__module__.startswith("pymysql")


def db_fetch_one(conn, query, params=()):
    cursor = conn.cursor()
    cursor.execute(query, params)
    return cursor.fetchone()


def db_execute(conn, query, params=()):
    cursor = conn.cursor()
    cursor.execute(query, params)
    return cursor


def get_db_connection():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not _is_mysql_configured() and not database_url.startswith(("mysql://", "mysql+pymysql://")):
        raise RuntimeError(
            "MySQL configuration is required. Set DATABASE_URL or DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME in backend/.env."
        )

    if database_url.startswith(("mysql://", "mysql+pymysql://")):
        import pymysql

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

    import pymysql

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


def _table_exists(conn, table_name):
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES LIKE %s", (table_name,))
    return cursor.fetchone() is not None


def _column_exists(conn, table_name, column_name):
    cursor = conn.cursor()
    cursor.execute("SHOW COLUMNS FROM `%s`", (table_name,))
    fields = [row["Field"] for row in cursor.fetchall()]
    return column_name in fields


def _add_missing_columns(conn, table_name, columns):
    cursor = conn.cursor()
    cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
    existing = {row["Field"] for row in cursor.fetchall()}
    for column_name, column_sql in columns.items():
        if column_name not in existing:
            cursor.execute(f"ALTER TABLE `{table_name}` ADD COLUMN {column_name} {column_sql}")


def _ensure_schema(conn):
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(100) NOT NULL UNIQUE,
            email VARCHAR(255) NULL,
            phone VARCHAR(20) NULL,
            phone_verified TINYINT(1) NOT NULL DEFAULT 0,
            password_hash VARCHAR(255) NOT NULL,
            avatar_url VARCHAR(500) NULL,
            plan VARCHAR(50) NOT NULL DEFAULT 'free',
            premium TINYINT(1) NOT NULL DEFAULT 0,
            plan_expires_at TIMESTAMP NULL,
            status ENUM('active', 'disabled', 'banned') NOT NULL DEFAULT 'active',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_users_email (email),
            INDEX idx_users_phone (phone),
            INDEX idx_users_plan (plan),
            INDEX idx_users_status (status)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS subscriptions (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            user_id BIGINT NOT NULL,
            plan_name ENUM('free', 'premium', 'business', 'enterprise') NOT NULL DEFAULT 'free',
            status ENUM('active', 'expired', 'cancelled') NOT NULL DEFAULT 'active',
            started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NULL,
            activated_by_code VARCHAR(100) NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            CONSTRAINT fk_subscriptions_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE,
            INDEX idx_subscriptions_user_id (user_id),
            INDEX idx_subscriptions_plan (plan_name),
            INDEX idx_subscriptions_status (status),
            INDEX idx_subscriptions_expires_at (expires_at),
            INDEX idx_subscriptions_user_active (user_id, status, expires_at)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS activation_codes (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            code VARCHAR(100) NOT NULL UNIQUE,
            plan_name ENUM('premium', 'business') NOT NULL,
            valid_for_days INT NOT NULL DEFAULT 30,
            is_used TINYINT(1) NOT NULL DEFAULT 0,
            used_by_user_id BIGINT NULL,
            used_at TIMESTAMP NULL,
            created_by VARCHAR(100) NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NULL,
            status ENUM('active', 'used', 'expired', 'revoked') NOT NULL DEFAULT 'active',
            CONSTRAINT fk_activation_codes_user
                FOREIGN KEY (used_by_user_id) REFERENCES users(id)
                ON DELETE SET NULL,
            INDEX idx_activation_code_status (code, status),
            INDEX idx_activation_code_plan (plan_name, status),
            INDEX idx_activation_codes_used_by_user (used_by_user_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS diagnosis_history (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            user_id BIGINT NOT NULL,
            image_name VARCHAR(255) NULL,
            image_path VARCHAR(500) NULL,
            tree_name VARCHAR(255) NULL,
            disease_name VARCHAR(255) NULL,
            symptoms TEXT NULL,
            severity_level VARCHAR(100) NULL,
            diagnosis_status VARCHAR(100) NULL,
            result_json JSON NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_diagnosis_history_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE,
            INDEX idx_diagnosis_user_time (user_id, created_at DESC),
            INDEX idx_diagnosis_tree (tree_name),
            INDEX idx_diagnosis_status (diagnosis_status)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tree_species (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(255) NOT NULL UNIQUE,
            scientific_name VARCHAR(255) NULL,
            description TEXT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS diseases (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            species_id BIGINT NOT NULL,
            name VARCHAR(255) NOT NULL,
            scientific_name VARCHAR(255) NULL,
            cause TEXT NULL,
            symptoms TEXT NULL,
            prevention TEXT NULL,
            image_url VARCHAR(500) NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_diseases_species
                FOREIGN KEY (species_id) REFERENCES tree_species(id)
                ON DELETE CASCADE,
            INDEX idx_diseases_species_id (species_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS disease_references (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            disease_id BIGINT NOT NULL,
            title VARCHAR(255) NOT NULL,
            description TEXT NULL,
            url VARCHAR(500) NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_disease_references_disease
                FOREIGN KEY (disease_id) REFERENCES diseases(id)
                ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS premium_transactions (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            user_id BIGINT NOT NULL,
            subscription_id BIGINT NULL,
            plan_name ENUM('premium', 'business', 'enterprise') NOT NULL,
            amount DECIMAL(10,2) DEFAULT 0,
            payment_status ENUM('pending', 'success', 'failed') DEFAULT 'pending',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_premium_transactions_user
                FOREIGN KEY (user_id) REFERENCES users(id)
                ON DELETE CASCADE,
            CONSTRAINT fk_premium_transactions_subscription
                FOREIGN KEY (subscription_id) REFERENCES subscriptions(id)
                ON DELETE SET NULL
        )
        """
    )

    if _table_exists(conn, "users"):
        cursor.execute("SHOW COLUMNS FROM users")
        user_columns = {row["Field"] for row in cursor.fetchall()}

        if "phone" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN phone VARCHAR(20) NULL")

        if "phone_verified" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN phone_verified TINYINT(1) NOT NULL DEFAULT 0")

        if "password_hash" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NULL")

        if "avatar_url" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500) NULL")

        if "status" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN status ENUM('active', 'disabled', 'banned') NOT NULL DEFAULT 'active'")

        if "updated_at" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")

        if "email" in user_columns:
            cursor.execute("ALTER TABLE users MODIFY email VARCHAR(255) NULL")

        if "password" in user_columns:
            cursor.execute("ALTER TABLE users MODIFY password VARCHAR(255) NULL")

        cursor.execute("SELECT id, password FROM users WHERE password_hash IS NULL OR password_hash = ''")
        legacy_rows = cursor.fetchall()
        for legacy in legacy_rows:
            raw_password = legacy.get("password")
            if raw_password:
                cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (generate_password_hash(raw_password), legacy["id"]))

        cursor.execute("UPDATE users SET password_hash = password WHERE (password_hash IS NULL OR password_hash = '') AND password IS NOT NULL AND password != ''")

        cursor.execute("SELECT id, name, email FROM users WHERE email IS NULL OR email = ''")
        for row in cursor.fetchall():
            local_email = f"{row['name']}@forestcare.local"
            cursor.execute("UPDATE users SET email = %s WHERE id = %s", (local_email, row["id"]))

    if _table_exists(conn, "subscriptions"):
        columns = {
            "started_at": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "expires_at": "TIMESTAMP NULL",
            "activated_by_code": "VARCHAR(100) NULL",
            "updated_at": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
        }
        _add_missing_columns(conn, "subscriptions", columns)

    if _table_exists(conn, "activation_codes"):
        columns = {
            "valid_for_days": "INT NOT NULL DEFAULT 30",
            "is_used": "TINYINT(1) NOT NULL DEFAULT 0",
            "used_by_user_id": "BIGINT NULL",
            "used_at": "TIMESTAMP NULL",
            "created_by": "VARCHAR(100) NULL",
            "expires_at": "TIMESTAMP NULL",
            "status": "ENUM('active', 'used', 'expired', 'revoked') NOT NULL DEFAULT 'active'",
        }
        _add_missing_columns(conn, "activation_codes", columns)

    cursor.execute(
        """
        INSERT INTO users (name, email, password_hash, plan, premium, plan_expires_at)
        SELECT 'ForestCare Admin', 'admin@forestcare.ai', '$2b$12$examplehash', 'free', 0, NULL
        WHERE NOT EXISTS (SELECT 1 FROM users WHERE email = 'admin@forestcare.ai')
        """
    )

    cursor.execute(
        """
        INSERT INTO subscriptions (user_id, plan_name, status, started_at, expires_at)
        SELECT u.id, 'free', 'active', NOW(), NULL
        FROM users u
        WHERE u.email = 'admin@forestcare.ai'
        AND NOT EXISTS (
            SELECT 1 FROM subscriptions s
            WHERE s.user_id = u.id AND s.plan_name = 'free' AND s.status = 'active'
        )
        """
    )

    cursor.execute(
        """
        INSERT INTO activation_codes (code, plan_name, valid_for_days, is_used, created_by, expires_at, status)
        SELECT 'FORESTCARE-PREMIUM-2026', 'premium', 30, 0, 'system', DATE_ADD(NOW(), INTERVAL 365 DAY), 'active'
        WHERE NOT EXISTS (SELECT 1 FROM activation_codes WHERE code = 'FORESTCARE-PREMIUM-2026')
        """
    )


def _expire_old_subscriptions(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE subscriptions
        SET status = 'expired'
        WHERE status = 'active'
          AND expires_at IS NOT NULL
          AND expires_at <= NOW()
        """
    )


def _sync_user_plan_from_subscription(conn, user_id):
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT *
        FROM subscriptions
        WHERE user_id = %s AND status = 'active'
          AND (expires_at IS NULL OR expires_at > NOW())
        ORDER BY started_at DESC, id DESC
        LIMIT 1
        """,
        (user_id,),
    )
    active_subscription = cursor.fetchone()

    if active_subscription is None:
        cursor.execute(
            """
            SELECT id FROM subscriptions
            WHERE user_id = %s AND plan_name = 'free' AND status = 'active'
            LIMIT 1
            """,
            (user_id,),
        )
        if cursor.fetchone() is None:
            cursor.execute(
                "INSERT INTO subscriptions (user_id, plan_name, status, started_at, expires_at, activated_by_code) VALUES (%s, 'free', 'active', NOW(), NULL, NULL)",
                (user_id,),
            )
        plan_name = 'free'
        plan_expires_at = None
    else:
        plan_name = active_subscription["plan_name"]
        plan_expires_at = active_subscription.get("expires_at")

    premium_flag = plan_name in ("premium", "business", "enterprise")
    cursor.execute(
        "UPDATE users SET plan = %s, premium = %s, plan_expires_at = %s WHERE id = %s",
        (plan_name, int(premium_flag), plan_expires_at, user_id),
    )
    conn.commit()
    return {
        "plan": plan_name,
        "premium": premium_flag,
        "planExpiresAt": plan_expires_at,
    }


def _ensure_default_free_subscription(conn, user_id):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM subscriptions WHERE user_id = %s AND plan_name = 'free' AND status = 'active' ORDER BY started_at DESC LIMIT 1",
        (user_id,),
    )
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO subscriptions (user_id, plan_name, status, started_at, expires_at, activated_by_code) VALUES (%s, 'free', 'active', NOW(), NULL, NULL)",
            (user_id,),
        )


def _validate_activation_code(conn, code, plan_name):
    if not code or not plan_name:
        return None

    return db_fetch_one(
        conn,
        """
        SELECT *
        FROM activation_codes
        WHERE code = %s
          AND plan_name = %s
          AND status = 'active'
          AND is_used = 0
          AND (expires_at IS NULL OR expires_at > NOW())
        LIMIT 1
        """,
        (code.strip(), plan_name),
    )


def _get_user_by_email(conn, email):
    return db_fetch_one(
        conn,
        "SELECT * FROM users WHERE email = %s AND email IS NOT NULL AND email != ''",
        (email,),
    )


def _get_user_by_username(conn, username):
    return db_fetch_one(
        conn,
        "SELECT * FROM users WHERE name = %s",
        (username,),
    )


def _get_user_by_phone(conn, phone):
    normalized_phone = _normalize_phone(phone)
    if not normalized_phone:
        return None
    return db_fetch_one(
        conn,
        "SELECT * FROM users WHERE phone = %s",
        (normalized_phone,),
    )


def _normalize_phone(value):
    if value is None:
        return ""
    digits = re.sub(r"\D+", "", str(value).strip())
    if not digits:
        return ""
    if digits.startswith("84"):
        return "+" + digits
    if digits.startswith("0"):
        return "+84" + digits[1:]
    if digits.startswith("+"):
        return "+" + digits.lstrip("+")
    return "+" + digits


def _is_valid_phone(value):
    normalized = _normalize_phone(value)
    if not normalized:
        return False
    return bool(re.fullmatch(r"\+84\d{9,10}", normalized))


def _generate_otp():
    return str(secrets.randbelow(900000) + 100000)


def _store_otp(phone, purpose, ttl_minutes=5):
    normalized = _normalize_phone(phone)
    otp = _generate_otp()
    OTP_CODES[(normalized, purpose)] = {
        "otp": otp,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
    }
    return otp


def _consume_otp(phone, otp_value, purpose):
    normalized = _normalize_phone(phone)
    entry = OTP_CODES.get((normalized, purpose))
    if not entry:
        return False
    if datetime.now(timezone.utc) > entry["expires_at"]:
        OTP_CODES.pop((normalized, purpose), None)
        return False
    if str(otp_value).strip() != str(entry["otp"]).strip():
        return False
    OTP_CODES.pop((normalized, purpose), None)
    return True


def _normalize_user_row(row):
    if row is None:
        return None
    expires_at = row.get("plan_expires_at")
    if isinstance(expires_at, datetime):
        expires_at = expires_at.isoformat()
    password_hash = row.get("password_hash")
    if password_hash is None:
        password_hash = row.get("password")
    normalized_email = row.get("email") or row.get("name") or ""
    return {
        "id": row["id"],
        "name": row["name"],
        "email": normalized_email,
        "phone": row.get("phone") or "",
        "phoneVerified": bool(row.get("phone_verified") or row.get("phoneVerified") or 0),
        "username": row.get("name") or normalized_email,
        "plan": row.get("plan", "free"),
        "premium": bool(row.get("premium", 0)),
        "planExpiresAt": expires_at,
        "passwordHash": password_hash,
    }


def serialize_user(row):
    if row is None:
        return None
    normalized = _normalize_user_row(row)
    if normalized is None:
        return None
    return {
        "id": normalized["id"],
        "name": normalized["name"],
        "email": normalized["email"],
        "phone": normalized.get("phone") or "",
        "phoneVerified": bool(normalized.get("phoneVerified") or 0),
        "username": normalized.get("username") or normalized["name"],
        "plan": normalized["plan"],
        "premium": normalized["premium"],
        "planExpiresAt": normalized["planExpiresAt"],
    }


def init_db():
    try:
        conn = get_db_connection()
        _ensure_schema(conn)
        _expire_old_subscriptions(conn)
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.warning("MySQL initialization skipped: %s", exc)


def _is_valid_email(value):
    if not value:
        return False
    return "@" in value and "." in value.split("@")[-1]


def _load_firebase_service_account():
    json_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    json_value = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()

    if json_path:
        try:
            service_account_path = Path(json_path)
            if not service_account_path.is_absolute():
                service_account_path = Path(__file__).resolve().parent.parent / service_account_path
            with service_account_path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
            logger.warning("Firebase service account file could not be loaded: %s", exc)

    if json_value:
        try:
            return json.loads(json_value)
        except json.JSONDecodeError as exc:
            logger.warning("Firebase service account JSON could not be parsed: %s", exc)

    return None


def _initialize_firebase_admin():
    if firebase_admin is None:
        return None

    try:
        firebase_admin.get_app()
        return firebase_admin
    except ValueError:
        service_account = _load_firebase_service_account()
        project_id = os.getenv("FIREBASE_PROJECT_ID")
        try:
            if service_account:
                from firebase_admin import credentials

                cred = credentials.Certificate(service_account)
                firebase_admin.initialize_app(cred, {"projectId": project_id} if project_id else None)
                return firebase_admin

            if project_id:
                firebase_admin.initialize_app(options={"projectId": project_id})
                return firebase_admin
        except Exception as exc:
            logger.warning("Firebase Admin SDK initialization failed: %s", exc)
            return None

    return None


def verify_firebase_token(token):
    if not token or firebase_admin is None or firebase_auth is None:
        return None

    firebase_app = _initialize_firebase_admin()
    if firebase_app is None:
        return None

    try:
        return firebase_auth.verify_id_token(token)
    except Exception as exc:
        logger.warning("Firebase ID token verification failed: %s", exc)
        return None


def _build_reset_link(token):
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    return f"{frontend_url.rstrip('/')}/reset-password?token={token}"


@auth_bp.route("/auth/send-signup-otp", methods=["POST"])
def send_signup_otp():
    data = request.get_json(silent=True) or {}
    phone = _normalize_phone(data.get("phone") or "")
    if not _is_valid_phone(phone):
        return jsonify({"success": False, "message": "Số điện thoại không hợp lệ."}), 400

    conn = get_db_connection()
    if _get_user_by_phone(conn, phone):
        conn.close()
        return jsonify({"success": False, "message": "Số điện thoại này đã được sử dụng."}), 409

    otp = _store_otp(phone, "signup")
    conn.close()
    return jsonify({
        "success": True,
        "message": "Mã OTP đăng ký đã được gửi tới số điện thoại của bạn.",
        "otp": otp,
        "phone": phone,
    })


@auth_bp.route("/auth/request-reset-otp", methods=["POST"])
def request_reset_otp():
    data = request.get_json(silent=True) or {}
    phone = _normalize_phone(data.get("phone") or "")
    if not _is_valid_phone(phone):
        return jsonify({"success": False, "message": "Số điện thoại không hợp lệ."}), 400

    conn = get_db_connection()
    user_row = _get_user_by_phone(conn, phone)
    conn.close()
    if user_row is None:
        return jsonify({"success": False, "message": "Số điện thoại chưa được đăng ký."}), 404

    otp = _store_otp(phone, "reset")
    return jsonify({
        "success": True,
        "message": "Mã OTP đặt lại mật khẩu đã được gửi tới số điện thoại của bạn.",
        "otp": otp,
        "phone": phone,
    })


@auth_bp.route("/auth/verify-reset-otp", methods=["POST"])
def verify_reset_otp():
    data = request.get_json(silent=True) or {}
    phone = _normalize_phone(data.get("phone") or "")
    otp_value = (data.get("otp") or "").strip()
    new_password = (data.get("newPassword") or "").strip()
    firebase_token = (data.get("firebaseToken") or "").strip()

    if not _is_valid_phone(phone):
        return jsonify({"success": False, "message": "Số điện thoại không hợp lệ."}), 400
    if not otp_value:
        return jsonify({"success": False, "message": "Vui lòng nhập mã OTP."}), 400
    if len(new_password) < 6:
        return jsonify({"success": False, "message": "Mật khẩu mới tối thiểu 6 ký tự."}), 400

    if firebase_token:
        decoded_firebase = verify_firebase_token(firebase_token)
        if decoded_firebase is None:
            return jsonify({"success": False, "message": "Firebase token không hợp lệ hoặc đã hết hạn."}), 401
        firebase_phone = _normalize_phone(decoded_firebase.get("phone_number") or decoded_firebase.get("phone"))
        if firebase_phone and firebase_phone != phone:
            return jsonify({"success": False, "message": "Số điện thoại xác thực Firebase không khớp."}), 400
    elif not _consume_otp(phone, otp_value, "reset"):
        return jsonify({"success": False, "message": "Mã OTP không hợp lệ hoặc đã hết hạn."}), 400

    conn = get_db_connection()
    user_row = _get_user_by_phone(conn, phone)
    if user_row is None:
        conn.close()
        return jsonify({"success": False, "message": "Tài khoản không tồn tại."}), 404

    new_hash = generate_password_hash(new_password)
    db_execute(conn, "UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user_row["id"]))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Mật khẩu đã được đặt lại thành công bằng OTP.",
    })


@auth_bp.route("/auth/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    confirm_password = (data.get("confirmPassword") or "").strip()
    phone = _normalize_phone(data.get("phone") or "")
    otp_value = (data.get("otp") or "").strip()
    firebase_token = (data.get("firebaseToken") or "").strip()
    email = (data.get("email") or "").strip().lower()

    if not name or len(name) < 3:
        return jsonify({"success": False, "message": "Vui lòng nhập tên tài khoản ít nhất 3 ký tự."}), 400

    if len(password) < 6:
        return jsonify({"success": False, "message": "Mật khẩu tối thiểu 6 ký tự."}), 400

    if password != confirm_password:
        return jsonify({"success": False, "message": "Mật khẩu xác nhận không khớp."}), 400

    if firebase_token:
        decoded_firebase = verify_firebase_token(firebase_token)
        if decoded_firebase is None:
            return jsonify({"success": False, "message": "Firebase token không hợp lệ hoặc đã hết hạn."}), 401
        firebase_phone = _normalize_phone(decoded_firebase.get("phone_number") or decoded_firebase.get("phone"))
        if firebase_phone and phone and firebase_phone != phone:
            return jsonify({"success": False, "message": "Số điện thoại xác thực Firebase không khớp với số điện thoại đăng ký."}), 400
        if firebase_phone:
            phone = firebase_phone

    if phone and not _is_valid_phone(phone):
        return jsonify({"success": False, "message": "Số điện thoại không hợp lệ."}), 400

    if phone and not firebase_token and not _consume_otp(phone, otp_value, "signup"):
        return jsonify({"success": False, "message": "Mã OTP đăng ký không hợp lệ hoặc đã hết hạn."}), 400

    conn = get_db_connection()
    name_exists = _get_user_by_username(conn, name)
    if name_exists:
        conn.close()
        return jsonify({"success": False, "message": "Tên tài khoản này đã tồn tại trong hệ thống."}), 409

    if phone and _get_user_by_phone(conn, phone):
        conn.close()
        return jsonify({"success": False, "message": "Số điện thoại này đã được sử dụng."}), 409

    if not email:
        email = f"{name}@forestcare.local"
    password_hash = generate_password_hash(password)
    cursor = db_execute(
        conn,
        "INSERT INTO users (name, email, phone, phone_verified, password_hash, plan, premium, plan_expires_at) VALUES (%s, %s, %s, %s, %s, 'free', 0, NULL)",
        (name, email, phone or None, int(bool(phone)), password_hash),
    )
    user_id = cursor.lastrowid
    _ensure_default_free_subscription(conn, user_id)
    _sync_user_plan_from_subscription(conn, user_id)
    user_row = db_fetch_one(conn, "SELECT * FROM users WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "user": serialize_user(user_row)
    })


@auth_bp.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    identifier = (data.get("username") or data.get("email") or data.get("name") or "").strip()
    password = (data.get("password") or "").strip()
    firebase_token = (data.get("firebaseToken") or "").strip()

    if firebase_token:
        decoded_firebase = verify_firebase_token(firebase_token)
        if decoded_firebase is None:
            return jsonify({"success": False, "message": "Firebase token không hợp lệ hoặc đã hết hạn."}), 401

    if not identifier or (not password and not firebase_token):
        return jsonify({"success": False, "message": "Vui lòng nhập tên tài khoản và mật khẩu."}), 400

    conn = get_db_connection()
    _expire_old_subscriptions(conn)

    user_row = _get_user_by_username(conn, identifier)
    if user_row is None and "@" in identifier:
        user_row = _get_user_by_email(conn, identifier.lower())
    if user_row is None and (_is_valid_phone(identifier) or identifier.startswith("0") or identifier.startswith("+84")):
        user_row = _get_user_by_phone(conn, identifier)

    if user_row is None:
        conn.close()
        return jsonify({"success": False, "message": "Tên tài khoản hoặc mật khẩu không chính xác."}), 401

    password_hash = user_row.get("password_hash") or user_row.get("password")
    if not password_hash or not check_password_hash(password_hash, password):
        conn.close()
        return jsonify({"success": False, "message": "Tên tài khoản hoặc mật khẩu không chính xác."}), 401

    _ensure_default_free_subscription(conn, user_row["id"])
    _sync_user_plan_from_subscription(conn, user_row["id"])
    user_row = db_fetch_one(conn, "SELECT * FROM users WHERE id = %s", (user_row["id"],))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "user": serialize_user(user_row)
    })


@auth_bp.route("/auth/request-reset", methods=["POST"])
def request_reset():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify({"success": False, "message": "Vui lòng nhập email để gửi mã đặt lại mật khẩu."}), 400

    if not _is_valid_email(email):
        return jsonify({"success": False, "message": "Email không hợp lệ."}), 400

    conn = get_db_connection()
    user_row = db_fetch_one(conn, "SELECT * FROM users WHERE email = %s", (email,))
    conn.close()

    if user_row is None:
        return jsonify({"success": False, "message": "Email chưa được đăng ký trong hệ thống."}), 404

    if not user_row["email"]:
        return jsonify({"success": False, "message": "Tài khoản này chưa có email để gửi mã khôi phục. Hãy thêm email vào hồ sơ trước."}), 400

    token = secrets.token_urlsafe(32)
    reset_link = _build_reset_link(token)
    RESET_TOKENS[token] = {
        "email": email,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)
    }

    if not email_service.is_configured:
        if email_service.is_dev_reset_enabled:
            return jsonify({
                "success": True,
                "message": "Hệ thống email chưa được cấu hình. Link đặt lại mật khẩu đang chạy ở chế độ phát triển để bạn vẫn có thể test chức năng.",
                "resetLink": reset_link
            }), 200

        return jsonify({
            "success": False,
            "message": "Hệ thống email chưa được cấu hình. Vui lòng thiết lập SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD và SMTP_FROM trong file backend/.env để gửi email thật."
        }), 503

    try:
        email_service.send_reset_email(email, reset_link)
    except Exception as exc:
        return jsonify({
            "success": False,
            "message": str(exc)
        }), 500

    return jsonify({
        "success": True,
        "message": f"Yêu cầu đặt lại mật khẩu đã được gửi đến {email}. Vui lòng kiểm tra hộp thư điện tử."
    })


@auth_bp.route("/auth/activate-plan", methods=["POST"])
def activate_plan():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    code = (data.get("code") or "").strip()
    plan_name = (data.get("plan") or data.get("plan_name") or "").strip().lower()

    if not email or not code or not plan_name:
        return jsonify({"success": False, "message": "Email, mã kích hoạt và gói cần được cung cấp."}), 400

    if plan_name not in {"premium", "business"}:
        return jsonify({"success": False, "message": "Gói kích hoạt không hợp lệ."}), 400

    conn = get_db_connection()
    user_row = _get_user_by_email(conn, email)
    if user_row is None:
        conn.close()
        return jsonify({"success": False, "message": "Người dùng không tồn tại."}), 404

    code_row = _validate_activation_code(conn, code, plan_name)
    if code_row is None:
        conn.close()
        return jsonify({"success": False, "message": "Mã kích hoạt không hợp lệ hoặc đã được sử dụng."}), 400

    valid_for_days = int(code_row.get("valid_for_days") or 30)
    expires_at = datetime.now() + timedelta(days=valid_for_days)

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO subscriptions (user_id, plan_name, status, started_at, expires_at, activated_by_code)
        VALUES (%s, %s, 'active', NOW(), %s, %s)
        """,
        (user_row["id"], plan_name, expires_at, code),
    )

    cursor.execute(
        "UPDATE activation_codes SET is_used = 1, used_by_user_id = %s, used_at = NOW(), status = 'used' WHERE id = %s",
        (user_row["id"], code_row["id"]),
    )

    _sync_user_plan_from_subscription(conn, user_row["id"])
    user_row = db_fetch_one(conn, "SELECT * FROM users WHERE id = %s", (user_row["id"],))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Gói {plan_name} đã được kích hoạt thành công.",
        "user": serialize_user(user_row),
    })


@auth_bp.route("/auth/subscription", methods=["GET"])
def get_subscription():
    email = request.args.get("email", "").strip().lower()
    if not email:
        return jsonify({"success": False, "message": "Email là bắt buộc."}), 400

    conn = get_db_connection()
    user_row = _get_user_by_email(conn, email)
    if user_row is None:
        conn.close()
        return jsonify({"success": False, "message": "Người dùng không tồn tại."}), 404

    _expire_old_subscriptions(conn)
    active_subscription = db_fetch_one(
        conn,
        """
        SELECT *
        FROM subscriptions
        WHERE user_id = %s AND status = 'active'
          AND (expires_at IS NULL OR expires_at > NOW())
        ORDER BY started_at DESC, id DESC
        LIMIT 1
        """,
        (user_row["id"],),
    )
    conn.close()

    if active_subscription is None:
        return jsonify({
            "success": True,
            "subscription": {
                "plan": "free",
                "status": "active",
                "expiresAt": None,
            }
        })

    return jsonify({
        "success": True,
        "subscription": {
            "plan": active_subscription["plan_name"],
            "status": active_subscription["status"],
            "expiresAt": active_subscription.get("expires_at"),
        }
    })


@auth_bp.route("/auth/update-plan", methods=["POST"])
def update_plan():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    plan = (data.get("plan") or "free").strip() or "free"
    premium = bool(data.get("premium", plan != "free"))
    plan_expires_at = data.get("planExpiresAt")

    if not email:
        return jsonify({"success": False, "message": "Thiếu email người dùng."}), 400

    if plan not in {"free", "premium", "business", "enterprise"}:
        return jsonify({"success": False, "message": "Gói không hợp lệ."}), 400

    conn = get_db_connection()
    query = "SELECT * FROM users WHERE email = %s" if _is_mysql_connection(conn) else "SELECT * FROM users WHERE email = ?"
    user_row = db_fetch_one(conn, query, (email,))
    if user_row is None:
        conn.close()
        return jsonify({"success": False, "message": "Tài khoản không tồn tại."}), 404

    current_plan = (user_row.get("plan") or "free").strip().lower()
    current_expiry = user_row.get("plan_expires_at")
    if current_expiry is not None:
        try:
            if not isinstance(current_expiry, datetime):
                current_expiry = datetime.fromisoformat(str(current_expiry).replace("Z", "+00:00"))
        except ValueError:
            current_expiry = None

    if plan == "free" and current_plan in {"premium", "business"} and current_expiry is not None:
        if isinstance(current_expiry, datetime):
            if current_expiry.tzinfo is None:
                current_expiry = current_expiry.replace(tzinfo=timezone.utc)
            current_expiry = current_expiry.astimezone(timezone.utc)
            if current_expiry > datetime.now(timezone.utc):
                conn.close()
                return jsonify({
                    "success": False,
                    "message": f"Bạn không thể chuyển về gói Free trước khi hết thời hạn hiện tại. Hết hạn: {current_expiry.strftime('%d/%m/%Y %H:%M')}."
                }), 403

    if plan_expires_at:
        try:
            normalized_expiry = str(plan_expires_at).replace("Z", "+00:00")
            plan_expires_at = datetime.fromisoformat(normalized_expiry)
            if plan == "free":
                plan_expires_at = None
        except ValueError:
            plan_expires_at = None
    elif plan != "free":
        plan_expires_at = datetime.now(timezone.utc) + timedelta(days=30)

    update_query = "UPDATE users SET plan = %s, premium = %s, plan_expires_at = %s WHERE email = %s" if _is_mysql_connection(conn) else "UPDATE users SET plan = ?, premium = ?, plan_expires_at = ? WHERE email = ?"
    db_execute(conn, update_query, (plan, int(premium), plan_expires_at, email))
    conn.commit()
    updated_user = db_fetch_one(conn, query, (email,))
    conn.close()

    return jsonify({
        "success": True,
        "user": serialize_user(updated_user)
    })


@auth_bp.route("/auth/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    new_password = (data.get("newPassword") or "").strip()

    if not token or len(new_password) < 6:
        return jsonify({
            "success": False,
            "message": "Token không hợp lệ hoặc mật khẩu mới quá ngắn."
        }), 400

    reset_request = RESET_TOKENS.get(token)
    if not reset_request:
        return jsonify({
            "success": False,
            "message": "Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn."
        }), 400

    if datetime.now(timezone.utc) > reset_request["expires_at"]:
        RESET_TOKENS.pop(token, None)
        return jsonify({
            "success": False,
            "message": "Liên kết đặt lại mật khẩu đã hết hạn."
        }), 400

    email = reset_request["email"]
    conn = get_db_connection()
    query = "SELECT * FROM users WHERE email = %s" if _is_mysql_connection(conn) else "SELECT * FROM users WHERE email = ?"
    user_row = db_fetch_one(conn, query, (email,))
    if user_row is None:
        conn.close()
        RESET_TOKENS.pop(token, None)
        return jsonify({"success": False, "message": "Tài khoản không tồn tại."}), 404

    new_hash = generate_password_hash(new_password)
    update_query = "UPDATE users SET password_hash = %s WHERE email = %s" if _is_mysql_connection(conn) else "UPDATE users SET password_hash = ? WHERE email = ?"
    db_execute(conn, update_query, (new_hash, email))
    conn.commit()
    conn.close()
    RESET_TOKENS.pop(token, None)

    return jsonify({
        "success": True,
        "email": email,
        "message": "Mật khẩu đã được cập nhật thành công."
    })


@auth_bp.route("/auth/change-password", methods=["POST"])
def change_password():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or data.get("name") or data.get("email") or "").strip()
    old_password = (data.get("oldPassword") or "").strip()
    new_password = (data.get("newPassword") or "").strip()

    if not username or not old_password or not new_password:
        return jsonify({"success": False, "message": "Tên tài khoản, mật khẩu cũ và mật khẩu mới là bắt buộc."}), 400

    if len(new_password) < 6:
        return jsonify({"success": False, "message": "Mật khẩu mới tối thiểu 6 ký tự."}), 400

    conn = get_db_connection()
    user_row = _get_user_by_username(conn, username)
    if user_row is None and "@" in username:
        user_row = _get_user_by_email(conn, username.lower())
    if user_row is None:
        conn.close()
        return jsonify({"success": False, "message": "Tài khoản không tồn tại."}), 404

    current_hash = user_row.get("password_hash") or user_row.get("password")
    if not current_hash or not check_password_hash(current_hash, old_password):
        conn.close()
        return jsonify({"success": False, "message": "Mật khẩu cũ không chính xác."}), 401

    new_hash = generate_password_hash(new_password)
    db_execute(conn, "UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user_row["id"]))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Mật khẩu đã được cập nhật thành công."
    })


@auth_bp.route("/auth/update-phone", methods=["POST"])
def update_phone():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or data.get("email") or "").strip()
    phone = _normalize_phone(data.get("phone") or "")
    firebase_token = (data.get("firebaseToken") or "").strip()

    if not username or not phone or not firebase_token:
        return jsonify({"success": False, "message": "Tài khoản, số điện thoại và Firebase token là bắt buộc."}), 400

    decoded_firebase = verify_firebase_token(firebase_token)
    if decoded_firebase is None:
        return jsonify({"success": False, "message": "Firebase token không hợp lệ hoặc đã hết hạn."}), 401

    firebase_phone = _normalize_phone(decoded_firebase.get("phone_number") or decoded_firebase.get("phone"))
    if not firebase_phone or firebase_phone != phone:
        return jsonify({"success": False, "message": "Số điện thoại xác thực Firebase không khớp."}), 400

    conn = get_db_connection()
    user_row = _get_user_by_username(conn, username)
    if user_row is None and "@" in username:
        user_row = _get_user_by_email(conn, username.lower())
    if user_row is None:
        conn.close()
        return jsonify({"success": False, "message": "Tài khoản không tồn tại."}), 404
    existing_user = _get_user_by_phone(conn, phone)
    if existing_user and existing_user["id"] != user_row["id"]:
        conn.close()
        return jsonify({"success": False, "message": "Số điện thoại này đã được sử dụng."}), 409

    db_execute(conn, "UPDATE users SET phone = %s, phone_verified = 1 WHERE id = %s", (phone, user_row["id"]))
    conn.commit()
    user_row = db_fetch_one(conn, "SELECT * FROM users WHERE id = %s", (user_row["id"],))
    conn.close()
    return jsonify({"success": True, "message": "Số điện thoại đã được xác minh và cập nhật.", "user": serialize_user(user_row)})


@auth_bp.route("/migrate-history", methods=["POST"])
def migrate_history_endpoint():
    """Migrate history records from localStorage to MySQL"""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    history = data.get("history", [])
    
    if not email or not history:
        return jsonify({"success": False, "message": "Email and history required"}), 400
    
    try:
        conn = get_db_connection()
        if not _is_mysql_connection(conn):
            return jsonify({"success": False, "message": "MySQL mode is required for history migration."}), 400

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
                    (user_id, record.get("tree", ""), record.get("disease", ""), record.get("symptoms", ""), record.get("level", ""), record.get("status", ""), record.get("date", datetime.now(timezone.utc).isoformat()))
                )
                migrated += 1
            except Exception as e:
                print(f"Error migrating record: {e}")
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "migrated": migrated})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
