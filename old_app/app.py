import os
import pathlib
import streamlit as st
import cv2
import numpy as np
import pandas as pd
import io
from datetime import datetime
from PIL import Image, ImageOps
from ultralytics import YOLO

# ==========================================
# 0. HACK FIX: LỖI TƯƠNG THÍCH WINDOWS -> LINUX CHO PYTORCH
# ==========================================
if os.name != 'nt':
    pathlib.WindowsPath = pathlib.PosixPath

# ==========================================
# 1. CẤU HÌNH GIAO DIỆN TRANG WEB
# ==========================================
st.set_page_config(
    page_title="ForestCare AI",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800;900&display=swap');
    html, body, [class*="css"], .stApp { font-family: 'Be Vietnam Pro', sans-serif; }
    :root {
        --fc-bg-soft: #f8fafc;
        --fc-bg-card: #ffffff;
        --fc-text-muted: #64748b;
        --fc-text-strong: #1e293b;
        --fc-border-soft: #e2e8f0;
        --fc-primary: #0d9488;
        --fc-primary-dark: #0f766e;
        --fc-primary-soft: rgba(13, 148, 136, 0.1);
        --fc-accent: #e11d48;
    }
    @media (prefers-color-scheme: dark) {
        :root {
            --fc-bg-soft: #1e293b;
            --fc-bg-card: #0f172a;
            --fc-text-muted: #94a3b8;
            --fc-text-strong: #f1f5f9;
            --fc-border-soft: #334155;
            --fc-primary: #2dd4bf;
            --fc-primary-dark: #5eead4;
            --fc-primary-soft: rgba(45, 212, 191, 0.12);
            --fc-accent: #fb7185;
        }
    }
    
    .block-container { padding-top: 2rem !important; padding-bottom: 1rem !important; }
    
    /* =======================================================
       TÙY CHỈNH CSS CHO MENU SIDEBAR (ĐÃ FIX LỖI CẮT CHỮ)
       ======================================================= */
    div[data-testid="stSidebar"] div[role="radiogroup"] {
        display: flex; flex-direction: column; gap: 6px; margin-top: 10px;
    }
    div[data-testid="stSidebar"] div[role="radiogroup"] label {
        background-color: transparent; padding: 10px 12px; border-radius: 8px; border: none;
        transition: all 0.2s ease; cursor: pointer; display: flex; align-items: center; width: 100%;
    }
    
    /* Ẩn dấu chấm tròn của radio button để tiết kiệm không gian và giống Menu thật */
    div[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {
        display: none !important;
    }
    
    /* Ép chữ tự động xuống dòng, không bị cắt xén (ellipsis) */
    div[data-testid="stSidebar"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
        white-space: normal !important; 
        overflow: visible !important;
        text-overflow: clip !important;
        font-weight: 600 !important; 
        font-size: 0.95rem !important; 
        color: var(--fc-text-strong);
        line-height: 1.4;
        margin: 0;
        transition: color 0.2s ease;
    }
    
    /* Hiệu ứng di chuột và khi được chọn */
    div[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        background-color: var(--fc-bg-soft);
    }
    div[data-testid="stSidebar"] div[role="radiogroup"] label:hover div[data-testid="stMarkdownContainer"] p {
        color: var(--fc-primary) !important;
    }
    div[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
        background-color: var(--fc-primary-soft); 
        border-left: 4px solid var(--fc-primary); 
        border-radius: 4px 8px 8px 4px;
    }
    div[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) div[data-testid="stMarkdownContainer"] p {
        color: var(--fc-primary-dark) !important;
    }
    
    /* Ẩn title mặc định của khối radio "Điều hướng" */
    div[data-testid="stSidebar"] .stRadio > label { display: none; } 
    /* ======================================================= */
    
    /* Logo / Tiêu đề Sidebar */
    .sidebar-logo {
        font-size: 2.2rem !important; margin: 0 0 20px 0 !important; padding: 0 !important; 
        color: var(--fc-primary) !important; font-weight: 900 !important; text-align: center; 
        line-height: 1.2 !important; letter-spacing: -0.02em;
    }

    h3 { font-size: 1.2rem !important; margin-top: 0 !important; color: var(--fc-primary-dark); }
    p { margin-bottom: 0.5rem !important; font-size: 0.95rem !important; }
    
    .info-card {
        background-color: var(--fc-bg-soft); border-left: 4px solid var(--fc-primary); padding: 12px 15px;
        border-radius: 6px; margin-bottom: 10px; font-size: 0.9rem; line-height: 1.4; color: var(--fc-text-strong);
        box-shadow: 0 1px 3px rgba(0,0,0,0.05); transition: box-shadow .2s ease, transform .2s ease;
    }
    .info-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.08); transform: translateY(-1px); }
    .warning-card { border-left-color: #f59e0b; background-color: rgba(245, 158, 11, 0.1); }
    .danger-card { border-left-color: #ef4444; background-color: rgba(239, 68, 68, 0.08); }
    .tip-card { border-left-color: var(--fc-primary); color: var(--fc-text-muted); font-size: 0.85rem; box-shadow: none; }
    
    img { max-height: 450px !important; max-width: 100% !important; width: auto !important; height: auto !important; object-fit: contain !important; border-radius: 8px; }
    div[data-testid="stImage"] { overflow: hidden; max-width: 100%; }
    div[data-testid="stImage"] img { display: block; margin: 0 auto; }
    
    .metric-value { font-size: 2.5rem; font-weight: 800; line-height: 1.1; background: none !important; }
    .metric-value.fc-level-0 { color: #16a34a; } .metric-value.fc-level-1 { color: #ca8a04; }
    .metric-value.fc-level-2 { color: #ea580c; } .metric-value.fc-level-3 { color: #dc2626; } .metric-value.fc-level-4 { color: #991b1b; }
    .metric-label { font-size: 0.9rem; color: var(--fc-text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em; }
    
    .fc-progress-track { width: 100%; height: 14px; background-color: var(--fc-border-soft); border-radius: 7px; overflow: hidden; margin: 6px 0 4px 0; }
    .fc-progress-fill { height: 100%; border-radius: 7px; transition: width 0.4s ease; }
    .fc-progress-fill.fc-level-0 { background-color: #22c55e; } .fc-progress-fill.fc-level-1 { background-color: #eab308; }
    .fc-progress-fill.fc-level-2 { background-color: #f97316; } .fc-progress-fill.fc-level-3 { background-color: #ef4444; } .fc-progress-fill.fc-level-4 { background-color: #991b1b; }
    
    .sidebar-title { font-size: 1rem; font-weight: 700; color: var(--fc-text-strong); margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }
    .sidebar-caption { color: var(--fc-text-muted); font-size: 0.85rem; margin-top: 8px; line-height: 1.4; text-align: center; }
    
    .kpi-card { display: flex; align-items: center; gap: 12px; }
    .kpi-icon { font-size: 1.8rem; line-height: 1; }
    
    button[kind="primary"], button[kind="primaryFormSubmit"] { background-color: var(--fc-primary) !important; border-color: var(--fc-primary) !important; }
    button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover { background-color: var(--fc-primary-dark) !important; border-color: var(--fc-primary-dark) !important; }
    button[kind="secondary"] {
        border-color: var(--fc-primary) !important; color: var(--fc-primary-dark) !important; background-color: transparent !important;
    }
    button[kind="secondary"]:hover { background-color: var(--fc-primary-soft) !important; color: var(--fc-primary-dark) !important; }

    /* Badge trạng thái hệ thống AI (sidebar) */
    .status-pill {
        display: inline-flex; align-items: center; gap: 6px; font-size: 0.8rem; font-weight: 600;
        padding: 5px 12px; border-radius: 999px; background-color: var(--fc-bg-soft); color: var(--fc-text-muted);
        margin: 0 auto;
    }
    .status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
    .status-dot.ok { background-color: #22c55e; box-shadow: 0 0 0 3px rgba(34,197,94,0.2); }
    .status-dot.err { background-color: #ef4444; box-shadow: 0 0 0 3px rgba(239,68,68,0.2); }
    .status-pill-wrap { display: flex; justify-content: center; margin-top: 10px; }

    /* Empty state tái sử dụng cho các tab chưa có ảnh/dữ liệu */
    .empty-state {
        border: 2px dashed var(--fc-border-soft); border-radius: 12px; padding: 36px 20px;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        text-align: center; background-color: var(--fc-bg-soft); margin-top: 8px;
    }
    .empty-state-icon { font-size: 2.5rem; margin-bottom: 10px; }
    .empty-state-text { color: var(--fc-text-muted); font-size: 0.95rem; }

    /* Đồng bộ radio ở khu vực nội dung chính (phương pháp đo) với phong cách menu sidebar */
    div[data-testid="stMain"] div[role="radiogroup"], section.main div[role="radiogroup"] {
        gap: 8px; flex-wrap: wrap;
    }
    div[data-testid="stMain"] div[role="radiogroup"] label, section.main div[role="radiogroup"] label {
        background-color: var(--fc-bg-soft); padding: 8px 16px; border-radius: 999px;
        border: 1px solid var(--fc-border-soft); transition: all 0.2s ease; cursor: pointer;
    }
    div[data-testid="stMain"] div[role="radiogroup"] label:hover, section.main div[role="radiogroup"] label:hover { border-color: var(--fc-primary); }
    div[data-testid="stMain"] div[role="radiogroup"] label:has(input:checked), section.main div[role="radiogroup"] label:has(input:checked) {
        background-color: var(--fc-primary-soft); border-color: var(--fc-primary);
    }
    div[data-testid="stMain"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p,
    section.main div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
        font-weight: 600 !important; color: var(--fc-text-strong);
    }
    div[data-testid="stMain"] div[role="radiogroup"] label:has(input:checked) div[data-testid="stMarkdownContainer"] p,
    section.main div[role="radiogroup"] label:has(input:checked) div[data-testid="stMarkdownContainer"] p {
        color: var(--fc-primary-dark) !important;
    }

    /* Khung bao bảng dữ liệu lịch sử */
    div[data-testid="stElementContainer"]:has(div[data-testid="stDataFrame"]) {
        border: 1px solid var(--fc-border-soft); border-radius: 10px; padding: 4px; background-color: var(--fc-bg-card);
    }

    /* Header trang cho từng tab ở khu vực nội dung chính */
    .page-header { margin-bottom: 4px; }
    .page-header h2 { margin: 0 !important; color: var(--fc-text-strong) !important; font-weight: 800 !important; }
    .page-subtitle { color: var(--fc-text-muted); font-size: 0.9rem; margin-bottom: 18px; }
</style>
""", unsafe_allow_html=True)

# Khởi tạo bộ nhớ tạm để lưu lịch sử và quản lý trạng thái luồng chẩn đoán
if "history" not in st.session_state: st.session_state.history = []
if "last_file_name" not in st.session_state: st.session_state.last_file_name = ""
if "diag_data" not in st.session_state: st.session_state.diag_data = None
if "diag_saved" not in st.session_state: st.session_state.diag_saved = False

# ==========================================
# 2. TẢI MÔ HÌNH & HÀM OPENCV HYBRID
# ==========================================
@st.cache_resource(show_spinner="Đang khởi tạo AI...")
def load_models():
    try:
        m_chuandoan = YOLO('model_chuandoan.pt')
        m_capbenh = YOLO('model_capbenh.pt')
        return m_chuandoan, m_capbenh
    except Exception as e:
        st.error(f"Lỗi tải mô hình: {e}")
        return None, None

model_chuandoan, model_capbenh = load_models()

def calculate_spots_cv2(image_cv, leaf_mask_binary, sensitivity=1.0):
    mask_8u = (leaf_mask_binary * 255).astype(np.uint8)
    
    contours, _ = cv2.findContours(mask_8u, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    solid_leaf_mask = np.zeros_like(mask_8u)
    if contours:
        largest_contour = max(contours, key=cv2.contourArea)
        cv2.drawContours(solid_leaf_mask, [largest_contour], -1, 255, thickness=cv2.FILLED)
    
    isolated_leaf = cv2.bitwise_and(image_cv, image_cv, mask=solid_leaf_mask)
    
    hsv_img = cv2.cvtColor(isolated_leaf, cv2.COLOR_BGR2HSV)
    s_channel = hsv_img[:, :, 1]
    v_channel = hsv_img[:, :, 2]
    
    dark_thresh = int(100 * sensitivity)
    _, dark_mask = cv2.threshold(v_channel, dark_thresh, 255, cv2.THRESH_BINARY_INV)
    
    lower_green = np.array([int(32 * (2-sensitivity)), 30, 30])
    upper_green = np.array([int(90 * sensitivity), 255, 255])
    green_mask = cv2.inRange(hsv_img, lower_green, upper_green)
    non_green_mask = cv2.bitwise_not(green_mask)
    
    disease_mask = cv2.bitwise_or(dark_mask, non_green_mask)
    
    _, high_v = cv2.threshold(v_channel, 230, 255, cv2.THRESH_BINARY)
    _, low_s = cv2.threshold(s_channel, 25, 255, cv2.THRESH_BINARY_INV)
    glare_mask = cv2.bitwise_and(high_v, low_s)
    no_glare_mask = cv2.bitwise_not(glare_mask)
    
    disease_mask = cv2.bitwise_and(disease_mask, no_glare_mask)
    disease_mask = cv2.bitwise_and(disease_mask, solid_leaf_mask)
    
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    disease_mask = cv2.morphologyEx(disease_mask, cv2.MORPH_OPEN, kernel, iterations=1)
    disease_mask = cv2.morphologyEx(disease_mask, cv2.MORPH_DILATE, kernel, iterations=1)
    
    leaf_pixels = cv2.countNonZero(solid_leaf_mask)
    disease_pixels = cv2.countNonZero(disease_mask)
    
    display_img = isolated_leaf.copy()
    overlay = display_img.copy()
    overlay[disease_mask > 0] = [0, 0, 255]
    cv2.addWeighted(overlay, 0.6, display_img, 0.4, 0, display_img)
    
    return leaf_pixels, disease_pixels, display_img, isolated_leaf

# ==========================================
# 3. DỮ LIỆU TỪ ĐIỂN BỆNH HẠI PHÂN TẦNG THEO CÂY
# ==========================================
healthy_base = {
    "name": "Lá khỏe mạnh", "scientific": "Khỏe mạnh", "order": "Không", "family": "Không",
    "cause": "Cây phát triển trong điều kiện môi trường thuận lợi.",
    "symptoms": "Bề mặt lá xanh tốt, nhẵn bóng, không có vết đốm hay hoại tử.",
    "prevention": "Tiếp tục duy trì chế độ chăm sóc, tưới tiêu và bón phân hợp lý.",
    "message": "Cây phát triển tốt. Không phát hiện nấm bệnh hay tổn thương.", "image": ""
}

DISEASE_DB = {
    "Gõ đỏ": {
        "Lá khỏe mạnh": healthy_base,
        "Đốm đen": {
            "name": "Đốm đen", "scientific": "<i>Stemphylium</i> sp.", "order": "Pleosporales", "family": "Pleosporaceae",
            "cause": "Do nấm <i>Stemphylium</i> sp. tấn công biểu bì lá.",
            "symptoms": "Vết bệnh cục bộ trên lá, màu đen đặc trưng.",
            "prevention": "- Sử dụng chế phẩm chứa nấm đối kháng Trichoderma harzianum.\n- Phun ướt đều tán lá.", "image": "dom_den.jpg"
        },
        "Cháy lá sinh lý": {
            "name": "Cháy lá sinh lý", "scientific": "Yếu tố phi sinh học", "order": "Không", "family": "Không",
            "cause": "Yếu tố phi sinh học: sốc nhiệt, gió, muối...",
            "symptoms": "Cháy mép lá, mô khô teo tóp, giòn, màu nâu/vàng.",
            "prevention": "- Điều chỉnh vi khí hậu.\n- Che lưới, phun phân bón lá hữu cơ.", "image": "chay_la_sinh_ly.jpg"
        }
    },
    "Hồng lộc": {
        "Lá khỏe mạnh": healthy_base,
        "Cháy lá sinh lý": {
            "name": "Cháy lá sinh lý", "scientific": "Yếu tố phi sinh học", "order": "Không", "family": "Không",
            "cause": "Yếu tố phi sinh học: sốc nhiệt, gió...",
            "symptoms": "Mô lá khô lại, teo tóp, màu nâu/xám.",
            "prevention": "- Điều chỉnh vi khí hậu.\n- Che lưới 50-70%.", "image": ""
        }
    },
    "Lát hoa": {
        "Lá khỏe mạnh": healthy_base,
        "Đốm nâu": {
            "name": "Đốm nâu", "scientific": "<i>Curvularia</i> sp.", "order": "Pleosporales", "family": "Pleosporaceae",
            "cause": "Do nấm <i>Curvularia</i> sp. gây ra.",
            "symptoms": "Vết tổn thương nâu sẫm, viền vàng.",
            "prevention": "Đang cập nhật...", "image": "lathoa_domnau.jpg"
        }
    },
    "Xà cừ": {
        "Lá khỏe mạnh": healthy_base,
        "Đốm nâu": {
            "name": "Đốm nâu", "scientific": "Đang cập nhật...", "order": "Đang cập nhật...", "family": "Đang cập nhật...",
            "cause": "Đang cập nhật...", "symptoms": "Đang cập nhật...", "prevention": "Đang cập nhật...", "image": "xacu_domnau.jpg"
        }
    }
}

def get_disease_info(pred_name):
    pred_lower = pred_name.lower()
    tree = "Gõ đỏ"
    if "hongloc" in pred_lower or "hồng lộc" in pred_lower: tree = "Hồng lộc"
    elif "lathoa" in pred_lower or "lát hoa" in pred_lower: tree = "Lát hoa"
    elif "xacu" in pred_lower or "xà cừ" in pred_lower: tree = "Xà cừ"
    
    is_healthy = "lakhoe" in pred_lower or "khoe" in pred_lower
    disease_name = "Lá khỏe mạnh"
    if not is_healthy:
        if "domden" in pred_lower or "đen" in pred_lower: disease_name = "Đốm đen"
        elif "domnau" in pred_lower or "nâu" in pred_lower: disease_name = "Đốm nâu"
        elif "chayla" in pred_lower or "cháy" in pred_lower: disease_name = "Cháy lá sinh lý"

    if disease_name in DISEASE_DB.get(tree, {}): info = DISEASE_DB[tree][disease_name]
    else: info = {"name": disease_name, "scientific": "...", "order": "...", "family": "...", "cause": "...", "symptoms": "...", "prevention": "...", "image": ""}
    return tree, info, is_healthy

def render_level_progress(infected_percentage: float, level: int):
    width = min(max(infected_percentage, 0), 100)
    st.markdown(f"""
    <div class="fc-progress-track"><div class="fc-progress-fill fc-level-{level}" style="width:{width}%;"></div></div>
    """, unsafe_allow_html=True)

def render_metric_value(infected_percentage: float, level: int):
    st.markdown(f"<div class='metric-label'>Mức độ bị hại</div><div class='metric-value fc-level-{level}'>{infected_percentage:.2f}%</div>", unsafe_allow_html=True)

def render_page_header(title: str, subtitle: str = ""):
    st.markdown(f"<div class='page-header'><h2>{title}</h2></div>", unsafe_allow_html=True)
    if subtitle:
        st.markdown(f"<div class='page-subtitle'>{subtitle}</div>", unsafe_allow_html=True)

def render_empty_state(icon: str, message: str):
    st.markdown(f"""
    <div class="empty-state">
        <div class="empty-state-icon">{icon}</div>
        <div class="empty-state-text">{message}</div>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 4. GIAO DIỆN CHÍNH & SIDEBAR
# ==========================================
TAB1, TAB2, TAB3, TAB4 = "🔍 Chẩn đoán bệnh hại", "📊 Tính toán mức độ bị hại", "📖 Thông tin về bệnh hại", "🗂️ Lịch sử chẩn đoán"

if "uploader_version" not in st.session_state: st.session_state.uploader_version = 0

image_pil = None
image_cv = None

# ---- CẤU TRÚC SIDEBAR MỚI TỐI GIẢN TẬP TRUNG ----
with st.sidebar:
    st.markdown("<h1 class='sidebar-logo'>🌿 ForestCare</h1>", unsafe_allow_html=True)
    
    # 4 TABS DẠNG MENU DỌC
    active_tab = st.radio("Điều hướng", [TAB1, TAB2, TAB3, TAB4], label_visibility="collapsed")
    
    st.divider()
    
    # KHU VỰC TẢI ẢNH GỌN GÀNG
    st.markdown("<div class='sidebar-title'>📸 Dữ liệu đầu vào</div>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Chọn ảnh", type=["jpg", "jpeg", "png"], label_visibility="collapsed", key=f"file_uploader_{st.session_state.uploader_version}")
    
    if uploaded_file is not None:
        current_file_name = uploaded_file.name
        if current_file_name != st.session_state.last_file_name:
            st.session_state.last_file_name = current_file_name
            st.session_state.diag_data = None
            st.session_state.diag_saved = False

        st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
        # Nút xóa ảnh gọn nhẹ (Đã loại bỏ khung xem trước ảnh theo yêu cầu)
        if st.button("🗑️ Hủy ảnh hiện tại", use_container_width=True):
            st.session_state.uploader_version += 1
            st.session_state.last_file_name = ""
            st.rerun()

    model_ok = model_chuandoan is not None and model_capbenh is not None
    dot_class = "ok" if model_ok else "err"
    status_text = "Hệ thống AI đang hoạt động" if model_ok else "Chưa tải được mô hình AI"
    st.markdown(f"""
    <div class='status-pill-wrap'>
        <div class='status-pill'><span class='status-dot {dot_class}'></span>{status_text}</div>
    </div>
    """, unsafe_allow_html=True)

# Lấy dữ liệu ảnh nếu có
if uploaded_file is not None:
    image_pil = ImageOps.exif_transpose(Image.open(uploaded_file))
    image_cv = cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)

# ---------------------------------------------------------
# MÀN 1: CHẨN ĐOÁN BỆNH HẠI
# ---------------------------------------------------------
if active_tab == TAB1:
    render_page_header(TAB1, "Nhận diện loại cây và bệnh hại từ ảnh lá bằng mô hình YOLO.")
    if image_cv is not None:
        if st.button("🚀 Thực hiện Chẩn đoán", type="primary", use_container_width=True):
            if model_chuandoan is not None:
                with st.spinner("Đang chẩn đoán..."):
                    res = model_chuandoan.predict(image_cv, conf=0.8)[0]
                    if len(res.boxes) > 0:
                        conf_values = res.boxes.conf.cpu().numpy()
                        best_idx = np.argmax(conf_values)
                        class_id = int(res.boxes.cls[best_idx].item())
                        pred_name = res.names[class_id].lower()
                        tree_name, info, is_healthy = get_disease_info(pred_name)
                        
                        st.session_state.diag_data = {
                            "res_plotted": cv2.cvtColor(res.plot(conf=True, line_width=2), cv2.COLOR_BGR2RGB),
                            "tree_name": tree_name, "info": info, "is_healthy": is_healthy,
                            "loai_benh_history": "Cháy lá sinh lý" if info['name'] == "Cháy lá sinh lý" else f"{info['name']} ({info.get('scientific', '')})",
                            "conf_display": f"{float(conf_values[best_idx])*100:.1f}".replace('.', ',')
                        }
                    else: st.session_state.diag_data = "NO_DETECT"

        if st.session_state.get("diag_data") == "NO_DETECT":
            st.warning("Mô hình không nhận diện được bệnh (Khỏe mạnh).")
        elif st.session_state.get("diag_data"):
            data = st.session_state.diag_data
            
            c1, c2, c3 = st.columns([1, 1, 1.5])
            with c1: st.image(image_pil, caption="Ảnh gốc", use_container_width=True)
            with c2: st.image(data["res_plotted"], caption="AI Nhận diện", use_container_width=True)
            with c3:
                st.markdown(f"### 🌳 Cây: {data['tree_name']}")
                st.markdown(f"### 🦠 Bệnh: {data['info']['name']}")
                st.markdown(f"<div style='color:var(--fc-accent); font-weight:bold; font-size: 1.1rem; margin-bottom: 12px;'>Độ tin cậy: {data['conf_display']}%</div>", unsafe_allow_html=True)
                
                if data['is_healthy']: 
                    st.success("Lá cây đang ở trạng thái khỏe mạnh.")
                else: 
                    if data['info'].get('order') != "Không" and data['info'].get('order') != "Đang cập nhật...":
                        st.markdown(f"**Danh pháp khoa học:** <i>{data['info']['scientific']}</i> | **Bộ:** {data['info']['order']} | **Họ:** {data['info']['family']}", unsafe_allow_html=True)
                    else:
                        st.markdown(f"**Danh pháp khoa học:** <i>{data['info']['scientific']}</i>", unsafe_allow_html=True)
                        
                    st.markdown(f"""
                    <div class="info-card danger-card"><b>🔴 Triệu chứng:</b><br>{data['info']['symptoms']}</div>
                    <div class="info-card warning-card"><b>🔬 Nguyên nhân:</b><br>{data['info']['cause']}</div>
                    <div class="info-card"><b>🛡️ Biện pháp phòng trừ:</b><br>{data['info']['prevention'].replace(chr(10), '<br>')}</div>
                    """, unsafe_allow_html=True)
            
            st.divider()
            st.markdown("### 💾 Đánh giá & Lưu kết quả")
            if not st.session_state.get("diag_saved", False):
                col_sel, col_btn = st.columns([2, 1])
                with col_sel:
                    if data['is_healthy']:
                        st.info("💡 Hệ thống nhận diện cây đang khỏe mạnh. Cấp bệnh tự động được gán là 0.")
                        user_cap_benh = "0"
                    else:
                        user_cap_benh = st.selectbox("📝 Đánh giá cấp bệnh bằng mắt thường (Mục trắc):", ["none", "1", "2", "3", "4"])
                with col_btn:
                    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                    if st.button("💾 Lưu vào Lịch sử", type="primary", use_container_width=True):
                        st.session_state.history.append({
                            "Chọn": True, "Ngày/ Tháng điều tra": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                            "Tên cây": data['tree_name'], "Tình Trạng cây": "Không bệnh" if data['is_healthy'] else "Bị Bệnh",
                            "Loại bệnh": "" if data['is_healthy'] else data['loai_benh_history'], 
                            "Mô tả biểu hiện": data['info'].get('symptoms', ''),
                            "Bộ phận cây": "Lá", "Cấp bệnh": user_cap_benh, "Phương pháp tính": "AI nhận diện" if data['is_healthy'] else "Mục trắc"
                        })
                        st.session_state.diag_saved = True; st.rerun()
            else: st.success("✅ Đã lưu kết quả chẩn đoán này vào Lịch sử thành công!")
    else:
        render_empty_state("📸", "Vui lòng tải ảnh lên ở thanh menu bên trái để bắt đầu Chẩn đoán.")

# ---------------------------------------------------------
# MÀN 2: TÍNH TOÁN MỨC ĐỘ BỊ HẠI & CẤP BỆNH
# ---------------------------------------------------------
elif active_tab == TAB2:
    render_page_header(TAB2, "Đo diện tích vùng tổn thương và phân cấp mức độ bị hại tự động.")
    if image_cv is not None:
        col_label, col_radio = st.columns([1.2, 2.8])
        with col_label:
            st.markdown("<div style='font-weight: 600; color: var(--fc-text-strong); margin-top: 8px;'>⚙️ Phương pháp đo:</div>", unsafe_allow_html=True)
        with col_radio:
            calc_method = st.radio("Chọn phương pháp:", options=["🧩 Segmentation", "🧮 Hybrid CV"], horizontal=True, label_visibility="collapsed")
        
        st.markdown("""
        <div class="info-card tip-card">
            💡 <b>Gợi ý:</b> Chọn <b>Hybrid CV</b> cho các vết bệnh có hình dạng phức tạp, và <b>Segmentation</b> cho các vết bệnh có hình dạng đơn giản.
        </div>
        """, unsafe_allow_html=True)
        
        sensitivity = 1.0

        if st.button("🚀 Bắt đầu tính toán", type="primary", use_container_width=True):
            if model_chuandoan is not None:
                with st.spinner("Đang xử lý hình ảnh và tính toán diện tích..."):
                    
                    res_cls = model_chuandoan.predict(image_cv, conf=0.8)[0]
                    is_healthy = True
                    
                    if len(res_cls.boxes) > 0:
                        conf_values = res_cls.boxes.conf.cpu().numpy()
                        best_idx = np.argmax(conf_values)
                        class_id = int(res_cls.boxes.cls[best_idx].item())
                        pred_name = res_cls.names[class_id]
                        _, _, is_healthy = get_disease_info(pred_name)
                    
                    if is_healthy:
                        st.success("✅ **Kết luận: Lá khỏe mạnh hoặc không nhận diện được bệnh (Cấp 0)**")
                        st.session_state.history.append({
                            "Chọn": True, "Ngày/ Tháng điều tra": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                            "Tên cây": "", "Tình Trạng cây": "Không bệnh", "Loại bệnh": "", 
                            "Mô tả biểu hiện": "", "Bộ phận cây": "Lá", "Cấp bệnh": "0", "Phương pháp tính": "AI nhận diện"
                        })
                    
                    elif "Segmentation" in calc_method:
                        if model_capbenh is not None:
                            res_seg = model_capbenh.predict(image_cv, conf=0.8)[0]
                            if len(res_seg.boxes) > 0 and hasattr(res_seg, 'masks') and res_seg.masks is not None:
                                c1, c2, c3 = st.columns([1, 1, 1.2])
                                with c1: st.image(image_pil, caption="Ảnh gốc", use_container_width=True)
                                
                                masks = res_seg.masks.data.cpu().numpy()
                                classes = res_seg.boxes.cls.cpu().numpy()
                                
                                h_orig, w_orig = image_cv.shape[:2]
                                total_leaf_mask_small = np.zeros(masks[0].shape, dtype=np.uint8)
                                disease_mask_small = np.zeros(masks[0].shape, dtype=np.uint8)

                                for i, cls_id in enumerate(classes):
                                    mask_binary = (masks[i] > 0.5).astype(np.uint8)
                                    total_leaf_mask_small = cv2.bitwise_or(total_leaf_mask_small, mask_binary)
                                    
                                    if "vet" in res_seg.names[int(cls_id)].lower():
                                        disease_mask_small = cv2.bitwise_or(disease_mask_small, mask_binary)

                                total_leaf_mask = cv2.resize(total_leaf_mask_small, (w_orig, h_orig), interpolation=cv2.INTER_NEAREST)
                                disease_mask = cv2.resize(disease_mask_small, (w_orig, h_orig), interpolation=cv2.INTER_NEAREST)

                                contours, _ = cv2.findContours(total_leaf_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                                solid_leaf_mask = np.zeros_like(total_leaf_mask)
                                if contours:
                                    largest_contour = max(contours, key=cv2.contourArea)
                                    cv2.drawContours(solid_leaf_mask, [largest_contour], -1, 1, thickness=cv2.FILLED)

                                disease_mask = cv2.bitwise_and(disease_mask, solid_leaf_mask)
                                
                                leaf_pixels = cv2.countNonZero(solid_leaf_mask)
                                disease_pixels = cv2.countNonZero(disease_mask)
                                infected_percentage = (disease_pixels / leaf_pixels) * 100 if leaf_pixels > 0 else 0
                                
                                with c2:
                                    res_plotted = image_cv.copy()
                                    overlay = res_plotted.copy()
                                    
                                    overlay[disease_mask > 0] = [0, 0, 255] 
                                    
                                    alpha = 0.45
                                    cv2.addWeighted(overlay, alpha, res_plotted, 1 - alpha, 0, res_plotted)
                                    
                                    contours_leaf, _ = cv2.findContours(solid_leaf_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                                    cv2.drawContours(res_plotted, contours_leaf, -1, (0, 255, 0), 3)
                                    
                                    st.image(cv2.cvtColor(res_plotted, cv2.COLOR_BGR2RGB), caption="Vùng bị hại (AI Segmentation)", use_container_width=True)

                                with c3:
                                    st.markdown("### Kết Quả Đo Lường")
                                    st.caption(f"📏 Tổng Pixel Lá thực tế: {leaf_pixels:,}")
                                    st.caption(f"📏 Tổng Pixel Vết Bệnh: {disease_pixels:,}")
                                    level = 0
                                    if infected_percentage > 0:
                                        if infected_percentage < 25: level = 1
                                        elif infected_percentage < 50: level = 2
                                        elif infected_percentage < 75: level = 3
                                        else: level = 4

                                    render_metric_value(infected_percentage, level)
                                    render_level_progress(infected_percentage, level)
                                    if level > 0: st.error(f"⚠️ **BỆNH CẤP {level}**")
                                    
                                    st.session_state.history.append({
                                        "Chọn": True, "Ngày/ Tháng điều tra": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                                        "Tên cây": "", "Tình Trạng cây": "Bị Bệnh", "Loại bệnh": "", "Mô tả biểu hiện": "",
                                        "Bộ phận cây": "Lá", "Cấp bệnh": str(level), "Phương pháp tính": "Segmentation AI"
                                    })
                            else:
                                st.warning("Hệ thống chưa trích xuất được vùng tổn thương (Mask) bằng AI.")
                    
                    elif "Hybrid" in calc_method:
                        if model_capbenh is not None:
                            res_seg = model_capbenh.predict(image_cv, conf=0.8)[0]
                            if len(res_seg.boxes) > 0 and hasattr(res_seg, 'masks') and res_seg.masks is not None:
                                masks = res_seg.masks.data.cpu().numpy()
                                classes = res_seg.boxes.cls.cpu().numpy()
                                
                                mask_combined_small = np.zeros(masks[0].shape, dtype=np.uint8)
                                for i in range(len(classes)):
                                    mask_binary = (masks[i] > 0.5).astype(np.uint8)
                                    mask_combined_small = cv2.bitwise_or(mask_combined_small, mask_binary)

                                h_orig, w_orig = image_cv.shape[:2]
                                mask_resized = cv2.resize(mask_combined_small, (w_orig, h_orig), interpolation=cv2.INTER_NEAREST)

                                leaf_px, disease_px, display_img, isolated_img = calculate_spots_cv2(image_cv, mask_resized, sensitivity)
                                
                                c1, c2, c3 = st.columns([1, 1, 1.2])
                                with c1:
                                    st.image(cv2.cvtColor(isolated_img, cv2.COLOR_BGR2RGB), caption="Bóc tách phông nền (AI Mask)", use_container_width=True)
                                with c2:
                                    st.image(cv2.cvtColor(display_img, cv2.COLOR_BGR2RGB), caption="Quét đốm bệnh (OpenCV)", use_container_width=True)
                                    
                                with c3:
                                    st.markdown("### Kết Quả Đo Lường")
                                    st.caption(f"📏 Tổng Pixel Lá thực tế: {leaf_px:,}")
                                    st.caption(f"📏 Tổng Pixel Vết Bệnh: {disease_px:,}")
                                    
                                    infected_percentage = (disease_px / leaf_px) * 100 if leaf_px > 0 else 0
                                    
                                    level, muc_do = 0, "Khỏe mạnh"
                                    if infected_percentage > 0:
                                        if infected_percentage < 25: level, muc_do = 1, "Hại nhẹ"
                                        elif infected_percentage < 50: level, muc_do = 2, "Hại vừa"
                                        elif infected_percentage < 75: level, muc_do = 3, "Hại nặng"
                                        else: level, muc_do = 4, "Hại rất nặng"

                                    render_metric_value(infected_percentage, level)
                                    render_level_progress(infected_percentage, level)
                                    
                                    if level > 0: st.error(f"⚠️ **Kết luận: BỆNH CẤP {level} ({muc_do})**")
                                    else: st.success("✅ **Kết luận: Chưa đến ngưỡng bị bệnh nặng (Cấp 0)**")
                                    
                                    st.session_state.history.append({
                                        "Chọn": True, "Ngày/ Tháng điều tra": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                                        "Tên cây": "", "Tình Trạng cây": "Bị Bệnh" if level > 0 else "Không bệnh", "Loại bệnh": "", 
                                        "Mô tả biểu hiện": "", "Bộ phận cây": "Lá", "Cấp bệnh": str(level), "Phương pháp tính": "Hybrid AI (CV2)"
                                    })
                            else:
                                st.warning("Hệ thống chưa trích xuất được hình dáng lá (Mask) bằng AI để chạy Hybrid.")
    else: render_empty_state("📸", "Vui lòng tải ảnh lên ở thanh menu bên trái để bắt đầu Tính toán.")

# ---------------------------------------------------------
# MÀN 3: THÔNG TIN VỀ BỆNH HẠI
# ---------------------------------------------------------
elif active_tab == TAB3:
    render_page_header(TAB3, "Tra cứu nguyên nhân, triệu chứng và biện pháp phòng trừ theo từng loại cây.")
    tree_options = list(DISEASE_DB.keys())
    selected_tree = st.selectbox("Chọn loại cây:", tree_options)
    
    st.divider()

    disease_options = [d for d in DISEASE_DB[selected_tree].keys() if d != "Lá khỏe mạnh"]
    
    if disease_options:
        selected_disease = st.selectbox("Chọn loại bệnh lý:", disease_options)
        d_info = DISEASE_DB[selected_tree][selected_disease]
        
        col_dict1, col_dict2 = st.columns([1, 1.2], gap="large")
        
        with col_dict1:
            if os.path.exists(d_info.get('image', '')) and d_info.get('image', ''):
                st.image(d_info['image'], caption=f"Hình ảnh thực tế: {d_info['name']}", use_container_width=True)
            else:
                st.markdown(f"""
                <div style="
                    height: 300px;
                    border: 2px dashed var(--fc-border-soft, #cbd5e1);
                    border-radius: 10px;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    background-color: var(--fc-bg-soft, #f8fafc);
                    text-align: center;
                    padding: 20px;
                ">
                    <div style="font-size: 2.5rem; margin-bottom: 8px;">🌿</div>
                    <div style="font-weight: 700; color: var(--fc-primary-dark); margin-bottom: 4px;">{d_info['name']}</div>
                    <div style="font-size: 0.8rem; color: var(--fc-text-muted, #64748b);">Ảnh minh họa đang được cập nhật</div>
                </div>
                """, unsafe_allow_html=True)
                
        with col_dict2:
            st.markdown(f"<h2 style='margin-top: 0; color: var(--fc-primary-dark);'>{d_info['name']}</h2>", unsafe_allow_html=True)
            
            if d_info.get('order') != "Không" and d_info.get('order') != "Đang cập nhật...":
                st.markdown(f"**Danh pháp khoa học:** <i>{d_info['scientific']}</i> | **Bộ:** {d_info['order']} | **Họ:** {d_info['family']}", unsafe_allow_html=True)
            else:
                st.markdown(f"**Danh pháp khoa học:** <i>{d_info['scientific']}</i>", unsafe_allow_html=True)
                
            st.markdown("---")
            st.markdown(f"""
            <div class="info-card warning-card"><b>🔬 Nguyên nhân:</b><br>{d_info['cause']}</div>
            <div class="info-card danger-card"><b>🔴 Triệu chứng:</b><br>{d_info['symptoms']}</div>
            <div class="info-card"><b>🛡️ Biện pháp phòng trừ:</b><br>{d_info['prevention'].replace(chr(10), '<br>')}</div>
            """, unsafe_allow_html=True)
    else: render_empty_state("📖", "Cơ sở dữ liệu cho loài cây này đang được cập nhật.")

# ---------------------------------------------------------
# MÀN 4: LỊCH SỬ CHẨN ĐOÁN
# ---------------------------------------------------------
elif active_tab == TAB4:
    render_page_header(TAB4, "Toàn bộ kết quả chẩn đoán đã lưu, có thể lọc, chỉnh sửa và xuất Excel.")
    if len(st.session_state.history) == 0: render_empty_state("🗂️", "Chưa có dữ liệu. Hãy thực hiện chẩn đoán ở Tab 1 hoặc 2 trước.")
    else:
        df_all = pd.DataFrame(st.session_state.history)
        
        if "Cấp bệnh" in df_all.columns:
            df_all["Cấp bệnh"] = df_all["Cấp bệnh"].astype(str)

        total_records = len(df_all)
        total_diseased = int((df_all["Tình Trạng cây"] == "Bị Bệnh").sum()) if "Tình Trạng cây" in df_all else 0
        most_common = df_all["Loại bệnh"].replace("", np.nan).mode()[0] if "Loại bệnh" in df_all and not df_all["Loại bệnh"].replace("", np.nan).mode().empty else "-"

        s1, s2, s3 = st.columns(3)
        with s1:
            st.markdown(f"""<div class='info-card kpi-card'><div class='kpi-icon'>🗂️</div><div>
                <div class='metric-label'>Tổng số bản ghi</div>
                <div style='font-size:1.6rem;font-weight:800;color:var(--fc-text-strong);'>{total_records}</div></div></div>""", unsafe_allow_html=True)
        with s2:
            st.markdown(f"""<div class='info-card danger-card kpi-card'><div class='kpi-icon'>🦠</div><div>
                <div class='metric-label'>Số lượt bị bệnh</div>
                <div style='font-size:1.6rem;font-weight:800;color:var(--fc-text-strong);'>{total_diseased}</div></div></div>""", unsafe_allow_html=True)
        with s3:
            st.markdown(f"""<div class='info-card warning-card kpi-card'><div class='kpi-icon'>📌</div><div>
                <div class='metric-label'>Bệnh phổ biến nhất</div>
                <div style='font-size:1.15rem;font-weight:800;color:var(--fc-text-strong);'>{most_common}</div></div></div>""", unsafe_allow_html=True)

        disease_filter_options = ["Tất cả"] + sorted([d for d in df_all["Loại bệnh"].dropna().unique().tolist() if d != ""]) if "Loại bệnh" in df_all else ["Tất cả"]
        selected_filter = st.selectbox("🔎 Lọc theo loại bệnh:", disease_filter_options)

        df_history = df_all if selected_filter == "Tất cả" else df_all[df_all["Loại bệnh"] == selected_filter]
        
        # Bảng dữ liệu mở khóa toàn bộ để chỉnh sửa tự do
        edited_df = st.data_editor(
            df_history,
            column_config={
                "Chọn": st.column_config.CheckboxColumn("Chọn xuất", default=True),
                "Cấp bệnh": st.column_config.SelectboxColumn("Cấp bệnh", options=["none", "0", "1", "2", "3", "4"])
            },
            hide_index=True,
            use_container_width=True
        )

        if "Cấp bệnh" in edited_df.columns:
            edited_df["Cấp bệnh"] = edited_df["Cấp bệnh"].astype(str)

        df_all.update(edited_df)
        st.session_state.history = df_all.to_dict('records')
        
        df_export = edited_df[edited_df.get("Chọn", pd.Series([True]*len(edited_df), index=edited_df.index)) == True]
        if not df_export.empty:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df_export.to_excel(writer, index=False)
            st.download_button("📥 Tải Excel", buffer.getvalue(), f"ForestCare_Export_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx", type="primary")

        st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
        col_del_sel, col_del_all = st.columns(2)
        with col_del_sel:
            n_selected = len(df_export)
            if st.button(f"🗑️ Xóa mục đã chọn ({n_selected})", use_container_width=True, disabled=n_selected == 0):
                st.session_state.history = df_all.drop(index=df_export.index).to_dict('records')
                st.rerun()
        with col_del_all:
            if st.button("🗑️ Xóa toàn bộ Lịch Sử", use_container_width=True):
                st.session_state.history = []
                st.rerun()