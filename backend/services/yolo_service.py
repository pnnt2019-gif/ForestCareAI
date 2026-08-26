import base64
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


class YOLOService:

    def __init__(self):
        model_dir = Path(__file__).resolve().parents[1] / "models"
        print("Đang tải model chẩn đoán...")
        self.model_chuandoan = YOLO(
            str(model_dir / "model_chuandoan.pt")
        )
        print("✅ Đã tải model segmentation/chẩn đoán thành công!")

    def diagnosis(self, image):
        result = self.model_chuandoan.predict(image, conf=0.8, verbose=False)[0]

        if len(result.boxes) == 0:
            return {
                "detected": False,
                "message": "Mô hình không nhận diện được bệnh (Khỏe mạnh)."
            }

        confidence_values = result.boxes.conf.cpu().numpy()
        best_index = int(confidence_values.argmax())
        class_id = int(result.boxes.cls[best_index].item())
        prediction_name = result.names[class_id]
        tree_name, info, is_healthy = self._get_disease_info(prediction_name)
        damage_result = self.damage(image)

        plotted = result.plot(conf=True, line_width=2)
        success, encoded_image = cv2.imencode(".jpg", plotted)

        return {
            "detected": True,
            "tree_name": tree_name,
            "disease": info["name"],
            "is_healthy": is_healthy,
            "confidence": round(float(confidence_values[best_index]) * 100, 1),
            "info": info,
            "damage": damage_result if damage_result.get("success") else None,
            "annotated_image": (
                f"data:image/jpeg;base64,{base64.b64encode(encoded_image).decode()}"
                if success else None
            )
        }

    @staticmethod
    def _get_disease_info(prediction_name):
        prediction = prediction_name.lower()
        tree_name = "Gõ đỏ"
        if "hongloc" in prediction or "hồng lộc" in prediction:
            tree_name = "Hồng lộc"
        elif "lathoa" in prediction or "lát hoa" in prediction:
            tree_name = "Lát hoa"
        elif "xacu" in prediction or "xà cừ" in prediction:
            tree_name = "Xà cừ"

        disease_name = "Lá khỏe mạnh"
        is_healthy = "lakhoe" in prediction or "khoe" in prediction
        if not is_healthy:
            if "domden" in prediction or "đen" in prediction:
                disease_name = "Đốm đen"
            elif "domnau" in prediction or "nâu" in prediction:
                disease_name = "Đốm nâu"
            elif "chayla" in prediction or "cháy" in prediction:
                disease_name = "Cháy lá sinh lý"

        healthy_info = {
            "name": "Lá khỏe mạnh",
            "scientific": "Khỏe mạnh",
            "order": "Không",
            "family": "Không",
            "cause": "Cây phát triển trong điều kiện môi trường thuận lợi.",
            "symptoms": "Bề mặt lá xanh tốt, không có vết đốm hay hoại tử.",
            "prevention": "Tiếp tục duy trì chế độ chăm sóc, tưới tiêu và bón phân hợp lý."
        }
        disease_info = {
            "Đốm đen": {
                "scientific": "Stemphylium sp.",
                "cause": "Do nấm Stemphylium sp. tấn công biểu bì lá.",
                "symptoms": "Vết bệnh cục bộ trên lá, màu đen đặc trưng.",
                "prevention": "Sử dụng chế phẩm chứa nấm đối kháng và phun ướt đều tán lá."
            },
            "Đốm nâu": {
                "scientific": "Curvularia sp.",
                "cause": "Do nấm Curvularia sp. gây ra.",
                "symptoms": "Vết tổn thương nâu sẫm, viền vàng.",
                "prevention": "Đang cập nhật..."
            },
            "Cháy lá sinh lý": {
                "scientific": "Yếu tố phi sinh học",
                "cause": "Do sốc nhiệt, gió hoặc nồng độ muối không phù hợp.",
                "symptoms": "Cháy mép lá, mô khô teo tóp, giòn, màu nâu hoặc vàng.",
                "prevention": "Điều chỉnh vi khí hậu, che lưới và phun phân bón lá hữu cơ."
            }
        }
        info = healthy_info if is_healthy else {
            "name": disease_name,
            "order": "Đang cập nhật...",
            "family": "Đang cập nhật...",
            **disease_info.get(disease_name, {
                "scientific": "Đang cập nhật...",
                "cause": "Đang cập nhật...",
                "symptoms": "Đang cập nhật...",
                "prevention": "Đang cập nhật..."
            })
        }
        return tree_name, info, is_healthy

    def test(self):
        return {
            "model_chuandoan": str(
                self.model_chuandoan.model
            )
        }

    def damage(self, image):
        # First isolate the whole leaf with the diagnosis model, then scan
        # only that mask with Hybrid CV2 for disease spots.
        result = self.model_chuandoan.predict(image, conf=0.8, verbose=False)[0]
        if result.masks is None or len(result.masks) == 0:
            return {"success": False, "message": "Mô hình segmentation chưa nhận diện được chiếc lá."}

        height, width = image.shape[:2]
        solid_leaf = np.zeros((height, width), dtype=np.uint8)
        for mask in result.masks.data.cpu().numpy():
            resized_mask = cv2.resize((mask > 0.5).astype(np.uint8), (width, height), interpolation=cv2.INTER_NEAREST)
            solid_leaf = cv2.bitwise_or(solid_leaf, resized_mask)

        contours, _ = cv2.findContours(solid_leaf, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            solid_leaf = np.zeros_like(solid_leaf)
            cv2.drawContours(solid_leaf, [max(contours, key=cv2.contourArea)], -1, 1, cv2.FILLED)

        isolated_leaf = cv2.bitwise_and(image, image, mask=solid_leaf * 255)
        hsv = cv2.cvtColor(isolated_leaf, cv2.COLOR_BGR2HSV)
        saturation = hsv[:, :, 1]
        value = hsv[:, :, 2]

        dark_mask = cv2.inRange(value, 0, 100)
        green_mask = cv2.inRange(hsv, np.array([28, 30, 30]), np.array([90, 255, 255]))
        non_green_mask = cv2.bitwise_not(green_mask)
        disease_mask = cv2.bitwise_or(dark_mask, non_green_mask)

        high_value = cv2.inRange(value, 230, 255)
        low_saturation = cv2.inRange(saturation, 0, 25)
        glare_mask = cv2.bitwise_and(high_value, low_saturation)
        disease_mask = cv2.bitwise_and(disease_mask, cv2.bitwise_not(glare_mask))
        disease_mask = cv2.bitwise_and(disease_mask, solid_leaf * 255)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        disease_mask = cv2.morphologyEx(disease_mask, cv2.MORPH_OPEN, kernel, iterations=1)
        disease_mask = cv2.morphologyEx(disease_mask, cv2.MORPH_DILATE, kernel, iterations=1)

        leaf_pixels = cv2.countNonZero(solid_leaf)
        disease_pixels = cv2.countNonZero(disease_mask)
        percentage = disease_pixels / leaf_pixels * 100 if leaf_pixels else 0
        level = 0 if percentage == 0 else min(4, int(percentage // 25) + 1)
        overlay = image.copy()
        overlay[disease_mask > 0] = (0, 0, 255)
        cv2.addWeighted(overlay, 0.45, image, 0.55, 0, overlay)
        leaf_contours, _ = cv2.findContours(solid_leaf, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, leaf_contours, -1, (0, 200, 70), 4)
        success, encoded = cv2.imencode(".jpg", overlay)
        return {
            "success": True, "percentage": round(percentage, 2), "level": level,
            "method": "Segmentation (model_chuandoan) + Hybrid AI (CV2)",
            "total_leaf_pixels": leaf_pixels, "injury_pixels": disease_pixels,
            "injury_percentage": round(percentage, 2),
            "annotated_image": f"data:image/jpeg;base64,{base64.b64encode(encoded).decode()}" if success else None
        }