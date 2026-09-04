from flask import Blueprint, request, jsonify
import cv2
import numpy as np
import os
import pymysql
from datetime import datetime
from urllib.parse import urlparse

from services.yolo_service import YOLOService


diagnosis_bp = Blueprint(
    "diagnosis",
    __name__,
    url_prefix="/api"
)

yolo_service = YOLOService()

# Disease catalog
DISEASES_CATALOG = {
    "Gõ đỏ": [
        {"name": "Đốm đen", "image": "/diseases/go-do-dom-den.jpg", "scientific": "Stemphylium sp.", "cause": "Do nấm Stemphylium sp. tấn công biểu bì lá.", "symptoms": "Vết bệnh cục bộ trên lá, màu đen đặc trưng.", "prevention": "Sử dụng chế phẩm chứa nấm đối kháng và phun ướt đều tán lá."},
        {"name": "Cháy lá sinh lý", "image": "/diseases/go-do-chay-la-sinh-ly.jpg", "scientific": "Yếu tố phi sinh học", "cause": "Sốc nhiệt, gió hoặc muối.", "symptoms": "Cháy mép lá, mô khô teo tóp, giòn, màu nâu hoặc vàng.", "prevention": "Điều chỉnh vi khí hậu và che lưới."}
    ],
    "Hồng lộc": [
        {"name": "Cháy lá sinh lý", "image": "/diseases/hong-loc-chay-la-sinh-ly.jpg", "scientific": "Yếu tố phi sinh học", "cause": "Sốc nhiệt hoặc gió.", "symptoms": "Mô lá khô lại, teo tóp, màu nâu hoặc xám.", "prevention": "Điều chỉnh vi khí hậu, che lưới 50-70%."}
    ],
    "Lát hoa": [
        {"name": "Đốm nâu", "image": "/diseases/lat-hoa-dom-nau.jpg", "scientific": "Curvularia sp.", "cause": "Do nấm Curvularia sp. gây ra.", "symptoms": "Vết tổn thương nâu sẫm, viền vàng.", "prevention": "Đang cập nhật..."}
    ],
    "Xà cừ": [
        {"name": "Đốm nâu", "scientific": "Đang cập nhật...", "cause": "Đang cập nhật...", "symptoms": "Đang cập nhật...", "prevention": "Đang cập nhật..."}
    ]
}


def _is_mysql_connection(conn):
    return type(conn).__module__.startswith("pymysql")


def get_db_connection():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url.startswith(("mysql://", "mysql+pymysql://")) and not all(
        os.getenv(key) for key in ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME")
    ):
        raise RuntimeError(
            "MySQL configuration is required. Set DATABASE_URL or DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME in backend/.env."
        )

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


@diagnosis_bp.route("/diagnosis", methods=["POST"])
def diagnosis():
    email = request.form.get("email", "").strip()
    tree_name = request.form.get("tree", "").strip()
    
    if "image" not in request.files:
        return jsonify({
            "success": False,
            "message": "Chưa có ảnh"
        }), 400

    file = request.files["image"]
    image_bytes = file.read()
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if image is None:
        return jsonify({
            "success": False,
            "message": "Không thể đọc ảnh"
        }), 400

    result = yolo_service.diagnosis(image)
    
    # Save to MySQL if email is provided
    if email:
        try:
            conn = get_db_connection()
            if _is_mysql_connection(conn):
                cur = conn.cursor()
                cur.execute("SELECT id FROM users WHERE email = %s", (email,))
                user = cur.fetchone()
                if user:
                    user_id = user["id"]
                    is_healthy = result.get("is_healthy", False)
                    injury_percentage = result.get("damage", {}).get("injury_percentage") or result.get("damage", {}).get("percentage", 0)
                    symptoms_text = "" if is_healthy else (result.get("info", {}).get("symptoms", "").rstrip(".") + f" chiếm {injury_percentage}% trên tổng thể chiếc lá." if result.get("info", {}).get("symptoms") else "")
                    
                    cur.execute(
                        """INSERT INTO diagnosis_history 
                           (user_id, tree_name, disease_name, symptoms, severity_level, diagnosis_status, result_json, created_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            user_id,
                            result.get("tree_name", tree_name),
                            "" if is_healthy else result.get("disease", ""),
                            symptoms_text,
                            "" if is_healthy else result.get("damage", {}).get("level", ""),
                            "Không bệnh" if is_healthy else "Bị bệnh",
                            str(result),
                            datetime.now().isoformat()
                        )
                    )
                    conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error saving diagnosis to MySQL: {e}")

    return jsonify({
        "success": True,
        "result": result
    })


@diagnosis_bp.route("/history", methods=["GET"])
def get_history():
    email = request.args.get("email", "").strip()
    if not email:
        return jsonify({"success": False, "message": "Email required"}), 400
    
    try:
        conn = get_db_connection()
        if _is_mysql_connection(conn):
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            if not user:
                return jsonify({"success": False, "message": "User not found"}), 404
            
            cur.execute(
                "SELECT id, tree_name AS tree, disease_name AS disease, symptoms, severity_level AS level, diagnosis_status AS status, created_at AS date FROM diagnosis_history WHERE user_id = %s ORDER BY created_at DESC",
                (user["id"],)
            )
            history = cur.fetchall()
            conn.close()
            return jsonify({"success": True, "history": history})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@diagnosis_bp.route("/history", methods=["POST"])
def save_history():
    data = request.get_json() or {}
    email = data.get("email", "").strip()
    record = data.get("record", {})
    
    if not email or not record:
        return jsonify({"success": False, "message": "Email and record required"}), 400
    
    try:
        conn = get_db_connection()
        if _is_mysql_connection(conn):
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            if not user:
                return jsonify({"success": False, "message": "User not found"}), 404
            
            cur.execute(
                """INSERT INTO diagnosis_history 
                   (user_id, tree_name, disease_name, symptoms, severity_level, diagnosis_status, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    user["id"],
                    record.get("tree", ""),
                    record.get("disease", ""),
                    record.get("symptoms", ""),
                    record.get("level", ""),
                    record.get("status", ""),
                    datetime.now().isoformat()
                )
            )
            conn.commit()
            conn.close()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@diagnosis_bp.route("/history/<int:record_id>", methods=["DELETE"])
def delete_history(record_id):
    email = request.args.get("email", "").strip()
    if not email:
        return jsonify({"success": False, "message": "Email required"}), 400
    
    try:
        conn = get_db_connection()
        if _is_mysql_connection(conn):
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            if not user:
                return jsonify({"success": False, "message": "User not found"}), 404
            
            cur.execute(
                "DELETE FROM diagnosis_history WHERE id = %s AND user_id = %s",
                (record_id, user["id"])
            )
            conn.commit()
            conn.close()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@diagnosis_bp.route("/diseases", methods=["GET"])
def get_diseases():
    tree = request.args.get("tree", "").strip()
    if tree and tree in DISEASES_CATALOG:
        return jsonify({"success": True, "diseases": DISEASES_CATALOG[tree]})
    return jsonify({"success": True, "diseases": DISEASES_CATALOG})


@diagnosis_bp.route("/trees", methods=["GET"])
def get_trees():
    return jsonify({"success": True, "trees": list(DISEASES_CATALOG.keys())})
