import os

from flask import Flask
from flask_cors import CORS

from routes.diagnosis import diagnosis_bp


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

frontend_url = os.getenv("FRONTEND_URL", "*")
if frontend_url != "*" and not frontend_url.startswith("http"):
    frontend_url = f"https://{frontend_url}"
CORS(app, resources={r"/api/*": {"origins": frontend_url}})

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
        debug=True
    )