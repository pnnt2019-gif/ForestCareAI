from flask import Blueprint, request, jsonify
import cv2
import numpy as np

from services.yolo_service import YOLOService


diagnosis_bp = Blueprint(
    "diagnosis",
    __name__,
    url_prefix="/api"
)

yolo_service = YOLOService()


@diagnosis_bp.route("/diagnosis", methods=["POST"])
def diagnosis():

    if "image" not in request.files:
        return jsonify({
            "success": False,
            "message": "Chưa có ảnh"
        }), 400

    file = request.files["image"]

    image_bytes = file.read()

    image_array = np.frombuffer(
        image_bytes,
        dtype=np.uint8
    )

    image = cv2.imdecode(
        image_array,
        cv2.IMREAD_COLOR
    )

    if image is None:
        return jsonify({
            "success": False,
            "message": "Không thể đọc ảnh"
        }), 400

    result = yolo_service.diagnosis(image)

    return jsonify({
        "success": True,
        "result": result
    })
