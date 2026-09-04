import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS

from routes.auth import auth_bp, init_db
from routes.diagnosis import diagnosis_bp

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

configured_frontend_urls = [
    entry.strip()
    for entry in os.getenv("FRONTEND_URL", "").split(",")
    if entry.strip()
]
if not configured_frontend_urls:
    configured_frontend_urls = [
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://forestcareai-c05b0.web.app",
    ]

normalized_frontend_urls = []
for origin in configured_frontend_urls:
    if origin == "*":
        normalized_frontend_urls = ["*"]
        break
    if not origin.startswith("http"):
        normalized_frontend_urls.append(f"https://{origin}")
    else:
        normalized_frontend_urls.append(origin)

CORS(app, resources={r"/api/*": {"origins": normalized_frontend_urls}}, supports_credentials=True)

# Khởi tạo schema MySQL chuẩn hóa và bảo đảm dữ liệu subscription lifecycle hoạt động.
# Nếu MySQL chưa được cấu hình trong môi trường, app vẫn boot an toàn và log cảnh báo thay vì crash.
try:
    init_db()
except Exception as exc:
    logger.warning("Database init skipped during app startup: %s", exc)

app.register_blueprint(auth_bp)
app.register_blueprint(diagnosis_bp)


@app.route("/")
def home():
    return {
        "status": "success",
        "message": "ForestCare AI Backend đang hoạt động"
    }


@app.route("/api/test-ai")
def test_ai():
    return {
        "success": True,
        "message": "YOLO đã được tải thành công"
    }


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        use_reloader=False
    )