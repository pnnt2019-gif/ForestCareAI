import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import * as XLSX from "xlsx";
import { RecaptchaVerifier, signInWithPhoneNumber, signOut } from "firebase/auth";
import { firebaseAuth, isFirebaseConfigured } from "./firebase";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "/api";
const FREE_DAILY_LIMIT = 10;
const PLAN_OPTIONS = [
  { key: "free", name: "Free", price: "0đ", status: "Đang sử dụng", badge: "Gói hiện tại", description: "Dùng thử cơ bản", highlight: false },
  { key: "premium", name: "Premium", price: "299k/tháng", status: "Phổ biến nhất", badge: "Đề xuất", description: "Tối ưu cho cá nhân", highlight: true },
  { key: "business", name: "Business", price: "599k/tháng", status: "Cho doanh nghiệp", badge: "Nâng cấp", description: "Tăng hiệu quả làm việc", highlight: false },
  { key: "enterprise", name: "Enterprise", price: "Liên hệ", status: "Tùy chỉnh", badge: "Liên hệ", description: "Giải pháp theo yêu cầu", highlight: false }
];

function todayKey() {
  return new Date().toLocaleDateString("en-CA");
}

function formatPlanExpiry(value) {
  if (!value) return "Chưa có thời hạn";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Chưa có thời hạn";
  return date.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function formatScientificText(value) {
  if (!value || typeof value !== "string") return "";
  return value.replace(/(\b[A-Z][a-z]+\s+(?:[a-z]+|sp\.|spp\.|var\.[A-Za-z0-9-]+))/g, "<i>$1</i>");
}

function usageStorageKey(email) {
  return `forestcare-daily-usage-${email}`;
}

function readDailyUsage(email) {
  const usage = JSON.parse(localStorage.getItem(usageStorageKey(email)) || "null");
  return usage?.date === todayKey() ? usage : { date: todayKey(), count: 0 };
}
const DISEASES = {
  "Gõ đỏ": [
    {
      name: "Đốm đen",
      image: "/diseases/go-do-dom-den.jpg",
      scientific: "Stemphylium sp.",
      order: "Pleosporales",
      family: "Pleosporaceae",
      cause: "Do nấm Stemphylium sp. gây ra.",
      symptoms: "Các vết bệnh cục bộ trên lá có màu đen đặc trưng.",
      prevention: "- Sử dụng chế phẩm nấm đối kháng Trichoderma harzianum.\n- Phun ướt đều tán lá."
    },
    {
      name: "Cháy lá sinh lý",
      image: "/diseases/go-do-chay-la-sinh-ly.jpg",
      scientific: "Yếu tố phi sinh học",
      order: "Sinh lý",
      family: "Phi sinh học",
      cause: "Do các yếu tố phi sinh học như sốc nhiệt, gió, muối,... gây ra.",
      symptoms: "Cháy mép lá, mô khô teo tóp, giòn và chuyển màu nâu/vàng.",
      prevention: "- Điều chỉnh vi khí hậu.\n- Sử dụng lưới che phù hợp."
    }
  ],
  "Hồng lộc": [
    {
      name: "Cháy lá sinh lý",
      image: "/diseases/hong-loc-chay-la-sinh-ly.jpg",
      scientific: "Yếu tố phi sinh học",
      order: "Sinh lý",
      family: "Phi sinh học",
      cause: "Do các yếu tố phi sinh học như sốc nhiệt, gió,... gây ra.",
      symptoms: "Mô lá khô, teo tóp và chuyển màu nâu/xám.",
      prevention: "- Điều chỉnh vi khí hậu.\n- Sử dụng lưới che 50–70%."
    }
  ],
  "Lát hoa": [
    {
      name: "Đốm nâu",
      image: "/diseases/lat-hoa-dom-nau.jpg",
      scientific: "Curvularia sp.",
      order: "Pleosporales",
      family: "Pleosporaceae",
      cause: "Do nấm Curvularia sp. gây ra.",
      symptoms: "Các vết tổn thương màu nâu sẫm, có thể kèm viền vàng.",
      prevention: "- Vệ sinh vườn.\n- Loại bỏ lá bệnh.\n- Quản lý độ ẩm."
    }
  ],
  "Xà cừ": [
    {
      name: "Đốm nâu",
      scientific: "Curvularia sp.",
      order: "Pleosporales",
      family: "Pleosporaceae",
      cause: "Do nấm Curvularia sp. gây ra.",
      symptoms: "Các vết bệnh đốm nâu trên lá.",
      prevention: "- Vệ sinh vườn.\n- Giảm độ ẩm.\n- Phòng trừ sớm."
    }
  ]
};

function App() {
  const [account, setAccount] = useState(() => JSON.parse(localStorage.getItem("forestcare-account") || "null"));

  if (!account) {
    return <LoginPage onLogin={(nextAccount) => {
      localStorage.setItem("forestcare-account", JSON.stringify(nextAccount));
      setAccount(nextAccount);
    }} />;
  }

  return <AppShell account={account} onAccountChange={(nextAccount) => {
    localStorage.setItem("forestcare-account", JSON.stringify(nextAccount));
    setAccount(nextAccount);
  }} />;
}

function AppShell({ account, onAccountChange }) {
  const [activePage, setActivePage] = useState("diagnosis");
  const [menuOpen, setMenuOpen] = useState(true);
  const [selectedFile, setSelectedFile] = useState(null);
  const [diagnosis, setDiagnosis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const historyStorageKey = `forestcare-history-${account.email || "default"}`;
  const [history, setHistory] = useState(() => JSON.parse(localStorage.getItem(historyStorageKey) || "[]"));
  const [selectedHistory, setSelectedHistory] = useState([]);
  const [tree, setTree] = useState("Gõ đỏ");
  const [disease, setDisease] = useState(DISEASES["Gõ đỏ"][0].name);
  const [dailyUsage, setDailyUsage] = useState(() => readDailyUsage(account.email));

  useEffect(() => {
    const nextHistory = JSON.parse(localStorage.getItem(historyStorageKey) || "[]");
    setHistory(nextHistory);
    setSelectedHistory([]);
  }, [historyStorageKey]);
  const [premiumOpen, setPremiumOpen] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState(account.plan || "free");
  const [activationCode, setActivationCode] = useState("");
  const [premiumError, setPremiumError] = useState("");
  const [accountInfoOpen, setAccountInfoOpen] = useState(false);
  const [profilePhone, setProfilePhone] = useState(account.phone || "+84");
  const [profileOtp, setProfileOtp] = useState("");
  const [profileMessage, setProfileMessage] = useState("");
  const [profileLoading, setProfileLoading] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [oldPassword, setOldPassword] = useState("");

  const hasActivePaidPlan = ["premium", "business"].includes(account.plan || "free") && account.planExpiresAt && new Date(account.planExpiresAt) > new Date();
  const activePlanLabel = account.plan === "business" ? "Business" : account.plan === "premium" ? "Premium" : "Free";

  useEffect(() => {
    setSelectedPlan(account.plan || "free");
  }, [account.plan]);
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [passwordMessage, setPasswordMessage] = useState("");
  const [passwordLoading, setPasswordLoading] = useState(false);

  const previewUrl = useMemo(
    () => selectedFile ? URL.createObjectURL(selectedFile) : "",
    [selectedFile]
  );

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    setSelectedFile(file || null);
    setDiagnosis(null);
    setError("");
  };

  const handleDiagnosis = async () => {
    if (!selectedFile) {
      setError("Vui lòng chọn ảnh lá cây trước khi chẩn đoán.");
      return;
    }
    if (!account.premium && dailyUsage.count >= FREE_DAILY_LIMIT) {
      setError("Bạn đã sử dụng hết 10 lượt chẩn đoán miễn phí hôm nay. Hãy kích hoạt Premium để tiếp tục không giới hạn.");
      return;
    }
    const formData = new FormData();
    formData.append("image", selectedFile);
    setLoading(true);
    setError("");
    try {
      const response = await axios.post(`${API_URL}/diagnosis`, formData);
      const result = response.data.result;
      setDiagnosis(result);
      if (!account.premium) {
        const nextUsage = { date: todayKey(), count: dailyUsage.count + 1 };
        setDailyUsage(nextUsage);
        localStorage.setItem(usageStorageKey(account.email), JSON.stringify(nextUsage));
      }
      const injuryPercentage = result.damage?.injury_percentage ?? result.damage?.percentage ?? 0;
      const symptomText = result.info?.symptoms ? `${result.info.symptoms.replace(/\.$/, "")} chiếm ${injuryPercentage}% trên tổng thể chiếc lá.` : "-";
      saveHistory({ tree: result.tree_name || "", status: result.is_healthy ? "Không bệnh" : "Bị bệnh", disease: result.disease || "", symptoms: symptomText, level: result.damage?.level ?? 0, method: "AI chẩn đoán" });
    } catch (requestError) {
      setError(requestError.response?.data?.message || "Không thể kết nối đến hệ thống AI.");
    } finally {
      setLoading(false);
    }
  };

  const resetImage = () => {
    setSelectedFile(null);
    setDiagnosis(null);
    setError("");
  };

  const saveHistory = (record) => {
    const next = [{ ...record, id: Date.now(), date: new Date().toLocaleString("vi-VN") }, ...history];
    setHistory(next);
    localStorage.setItem(historyStorageKey, JSON.stringify(next));
  };

  const toggleHistory = (id) => {
    setSelectedHistory((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  };

  const toggleAllHistory = () => {
    setSelectedHistory(selectedHistory.length === history.length ? [] : history.map((item) => item.id));
  };

  const deleteSelectedHistory = () => {
    const next = history.filter((item) => !selectedHistory.includes(item.id));
    setHistory(next);
    setSelectedHistory([]);
    localStorage.setItem(historyStorageKey, JSON.stringify(next));
  };

  const exportSelectedHistory = () => {
    const rows = history.filter((item) => selectedHistory.includes(item.id)).map((item) => ({
      "Ngày / Thời gian": item.date,
      "Tên cây": item.tree || "-",
      "Tình trạng cây": item.status,
      "Loại bệnh": item.disease || "-",
      "Triệu chứng": item.symptoms || "-",
      "Cấp bệnh": item.level,
      "Phương pháp": "AI chẩn đoán"
    }));
    const workbook = XLSX.utils.book_new();
    const worksheet = XLSX.utils.json_to_sheet(rows);
    worksheet["!cols"] = [{ wch: 22 }, { wch: 18 }, { wch: 18 }, { wch: 24 }, { wch: 55 }, { wch: 12 }, { wch: 34 }];
    XLSX.utils.book_append_sheet(workbook, worksheet, "Lịch sử chẩn đoán");
    XLSX.writeFile(workbook, `forestcare-history-${new Date().toISOString().slice(0, 10)}.xlsx`);
  };

  const handlePlanSelect = async (planKey) => {
    if (planKey === "enterprise") {
      window.open("https://zalo.me/0366146305", "_blank", "noopener,noreferrer");
      setPremiumOpen(false);
      return;
    }

    if (planKey === "free") {
      const currentExpiry = account.planExpiresAt ? new Date(account.planExpiresAt) : null;
      if (["premium", "business"].includes(account.plan || "free") && currentExpiry && currentExpiry > new Date()) {
        setSelectedPlan(planKey);
        setPremiumError(`Bạn không thể xuống Free trước khi hết hạn gói hiện tại. Hết hạn: ${formatPlanExpiry(account.planExpiresAt)}.`);
        return;
      }

      try {
        await axios.post(`${API_URL}/auth/update-plan`, {
          email: account.email,
          plan: "free",
          premium: false,
          planExpiresAt: null,
        });
      } catch (error) {
        console.error("Update free plan failed", error);
      }

      onAccountChange({
        ...account,
        plan: "free",
        premium: false,
        planExpiresAt: null,
      });
      setActivationCode("");
      setPremiumError("");
      setPremiumOpen(false);
      return;
    }

    if (!activationCode.trim()) {
      setSelectedPlan(planKey);
      setPremiumError("Vui lòng nhập mã kích hoạt để nâng cấp lên gói Premium/Business.");
      return;
    }

    try {
      const response = await axios.post(`${API_URL}/auth/activate-plan`, {
        email: account.email,
        code: activationCode.trim(),
        plan: planKey,
      });

      if (!response.data?.success) {
        setSelectedPlan(planKey);
        setPremiumError(response.data?.message || "Mã kích hoạt không hợp lệ.");
        return;
      }

      const nextPlan = planKey;
      onAccountChange({
        ...account,
        plan: nextPlan,
        premium: true,
        planExpiresAt: response.data?.user?.planExpiresAt || new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
      });
      setActivationCode("");
      setPremiumError("");
      setSelectedPlan(nextPlan);
      setPremiumOpen(false);
    } catch (error) {
      setSelectedPlan(planKey);
      setPremiumError(error.response?.data?.message || "Mã kích hoạt không hợp lệ hoặc đã hết hạn.");
    }
  };

  const logout = () => {
    setAccountMenuOpen(false);
    localStorage.removeItem("forestcare-account");
    window.location.reload();
  };

  const updatePhoneDigits = (value, setter) => {
    let digits = value.replace(/\D/g, "");
    if (digits.startsWith("84")) digits = digits.slice(2);
    if (digits.startsWith("0")) digits = digits.slice(1);
    setter(`+84${digits.slice(0, 9)}`);
  };

  const handleChangePassword = async (event) => {
    event.preventDefault();
    setPasswordMessage("");

    if (!oldPassword || !newPassword || !confirmNewPassword) {
      setPasswordMessage("Vui lòng nhập đầy đủ mật khẩu cũ, mật khẩu mới và xác nhận.");
      return;
    }
    if (newPassword.length < 6) {
      setPasswordMessage("Mật khẩu mới tối thiểu 6 ký tự.");
      return;
    }
    if (newPassword !== confirmNewPassword) {
      setPasswordMessage("Mật khẩu mới và xác nhận không khớp.");
      return;
    }

    setPasswordLoading(true);
    try {
      const username = account.username || account.email;
      const response = await axios.post(`${API_URL}/auth/change-password`, {
        username,
        oldPassword,
        newPassword,
      });

      if (!response.data?.success) {
        setPasswordMessage(response.data?.message || "Không thể đổi mật khẩu.");
        return;
      }

      setPasswordMessage("✅ Đổi mật khẩu thành công.");
      setOldPassword("");
      setNewPassword("");
      setConfirmNewPassword("");
      setTimeout(() => setAccountInfoOpen(false), 900);
    } catch (error) {
      setPasswordMessage(error.response?.data?.message || "Không thể đổi mật khẩu lúc này.");
    } finally {
      setPasswordLoading(false);
    }
  };

  const sendProfilePhoneOtp = async () => {
    const digits = profilePhone.replace(/^\+84/, "");
    if (digits.length !== 9) {
      setProfileMessage("Vui lòng nhập đủ 9 chữ số điện thoại.");
      return;
    }
    setProfileLoading(true);
    try {
      if (!firebaseAuth || !isFirebaseConfigured) throw new Error("Firebase chưa được cấu hình.");
      if (!window.recaptchaVerifier) {
        window.recaptchaVerifier = new RecaptchaVerifier(firebaseAuth, "firebase-recaptcha-container", { size: "invisible", callback: () => {}, defaultCountry: "VN" });
      }
      window.confirmationResult = await signInWithPhoneNumber(firebaseAuth, `+84${digits}`, window.recaptchaVerifier);
      setProfileMessage("✅ Mã OTP Firebase đã được gửi.");
    } catch (error) {
      setProfileMessage(error.message || "Không thể gửi mã OTP.");
    } finally {
      setProfileLoading(false);
    }
  };

  const verifyProfilePhone = async (event) => {
    event.preventDefault();
    if (!window.confirmationResult || !profileOtp.trim()) {
      setProfileMessage("Vui lòng gửi OTP và nhập mã xác thực.");
      return;
    }
    setProfileLoading(true);
    try {
      const credential = await window.confirmationResult.confirm(profileOtp.trim());
      const firebaseToken = await credential.user.getIdToken();
      const response = await axios.post(`${API_URL}/auth/update-phone`, {
        username: account.username || account.email,
        phone: profilePhone,
        firebaseToken,
      });
      if (!response.data?.success) throw new Error(response.data?.message || "Không thể cập nhật số điện thoại.");
      const nextUser = response.data.user;
      onAccountChange({ ...account, phone: nextUser.phone, phoneVerified: nextUser.phoneVerified });
      setProfileMessage("✅ Số điện thoại đã được xác minh.");
      setProfileOtp("");
    } catch (error) {
      setProfileMessage(error.response?.data?.message || error.message || "Không thể xác minh số điện thoại.");
    } finally {
      setProfileLoading(false);
    }
  };

  return (
    <div className={`app ${menuOpen ? "menu-open" : "menu-closed"}`}>

      <aside className={`sidebar ${menuOpen ? "" : "sidebar-collapsed"}`}>

        <div className="logo">
          <img src="/logo.png" alt="ForestCare AI" />
        </div>

        <nav>

          <button
            className={activePage === "diagnosis" ? "active" : ""}
            onClick={() => setActivePage("diagnosis")}
          >
            Chẩn đoán
          </button>

          <button
            className={activePage === "disease" ? "active" : ""}
            onClick={() => setActivePage("disease")}
          >
            Thông tin bệnh hại
          </button>

          <button
            className={activePage === "history" ? "active" : ""}
            onClick={() => setActivePage("history")}
          >
            Lịch sử chẩn đoán
          </button>

        </nav>

        <div className="social-links">
          <div className="social-heading">Kết nối với ForestCare</div>
          <a className="qr-frame qr-frame-link" href="https://www.facebook.com/people/ForestCare-AI/61593786680677/?mibextid=wwXIfr" target="_blank" rel="noreferrer" aria-label="Mở Facebook ForestCare AI">
            <img src="/qr-fanpage.png" alt="Mã QR fanpage ForestCare" />
            <span>Quét mã để ghé thăm fanpage</span>
          </a>
          <a className="tiktok-link" href="https://www.tiktok.com/@forestcare.ai" target="_blank" rel="noreferrer">
            <span className="tiktok-mark">♪</span>
            <span><small>TikTok</small><strong>@forestcare.ai</strong></span>
            <span className="external-arrow">↗</span>
          </a>
        </div>

        <div className="account-panel">
          <button
            type="button"
            className={`account-badge ${accountMenuOpen ? "account-badge-open" : ""}`}
            onClick={() => setAccountMenuOpen((open) => !open)}
            aria-expanded={accountMenuOpen}
          >
            <div className="account-avatar">{(account.username || account.email || "U")[0].toUpperCase()}</div>
            <div className="account-copy">
              <strong>{account.username || account.email}</strong>
              <span className={account.premium ? "premium-text" : ""}>{account.premium ? (account.plan === "business" ? "Business account" : account.plan === "premium" ? "Premium account" : "Gói cao cấp") : "Tài khoản miễn phí"}</span>
            </div>
            <span className={`premium-badge ${account.plan === "business" ? "premium-badge-business" : account.plan === "premium" ? "premium-badge-premium" : "premium-badge-free"}`}>
              {account.premium ? (account.plan === "business" ? "BUSINESS" : "PREMIUM") : "FREE"}
            </span>
          </button>

          {accountMenuOpen && (
            <div className="account-menu">
              <button type="button" className="account-menu-item primary" onClick={() => { setSelectedPlan(account.plan || "premium"); setPremiumOpen(true); setPremiumError(""); setAccountMenuOpen(false); }}>
                Nâng cấp
              </button>
              <button type="button" className="account-menu-item secondary" onClick={() => { setAccountInfoOpen(true); setAccountMenuOpen(false); setProfileMessage(""); }}>
                Thông tin
              </button>
              <button type="button" className="account-menu-item danger" onClick={logout}>
                Đăng xuất
              </button>
            </div>
          )}
        </div>

      </aside>

      <main className="main">

        <header>
          <div className="topbar">
            <button
              className="menu-toggle"
              onClick={() => setMenuOpen((isOpen) => !isOpen)}
              aria-label={menuOpen ? "Ẩn thanh menu" : "Hiện thanh menu"}
              title={menuOpen ? "Ẩn thanh menu" : "Hiện thanh menu"}
            >
              {menuOpen ? "‹" : "☰"}
            </button>
            <div><h1>ForestCare AI</h1>
          <p>
            Hệ thống hỗ trợ nhận diện và đánh giá bệnh hại cây xanh
          </p>
            </div>
          </div>
        </header>

        {activePage === "diagnosis" && <DiagnosisPage
          diagnosis={diagnosis}
          error={error}
          loading={loading}
          onDiagnose={handleDiagnosis}
          onFileChange={handleFileChange}
          onReset={resetImage}
          previewUrl={previewUrl}
          selectedFile={selectedFile}
          account={account}
          dailyUsage={dailyUsage}
        />}

        {activePage === "disease" && <DiseasePage tree={tree} disease={disease} onTreeChange={(value) => { setTree(value); setDisease(DISEASES[value][0].name); }} onDiseaseChange={setDisease} />}

        {activePage === "history" && <HistoryPage history={history} selectedHistory={selectedHistory} onToggle={toggleHistory} onToggleAll={toggleAllHistory} onDeleteSelected={deleteSelectedHistory} onExport={exportSelectedHistory} onClear={() => { setHistory([]); setSelectedHistory([]); localStorage.removeItem(historyStorageKey); }} />}

      </main>

      {premiumOpen && <div className="modal-backdrop" role="presentation" onClick={() => setPremiumOpen(false)}>
        <div className="premium-modal plan-modal" onClick={(event) => event.stopPropagation()}>
          <button type="button" className="modal-close" onClick={() => setPremiumOpen(false)} aria-label="Đóng">×</button>
          <div className="plan-modal-header">
            <h2>Các gói ForestCare AI</h2>
            <div className="plan-current-summary">
              <span className="plan-current-label">Gói hiện tại</span>
              <div className="plan-current-value">
                <strong>{activePlanLabel}</strong>
                {account.plan !== "free" && account.planExpiresAt && (
                  <span>Hết hạn {formatPlanExpiry(account.planExpiresAt)}</span>
                )}
              </div>
            </div>
          </div>
          <div className="plan-list">
            {PLAN_OPTIONS.map((plan) => {
              const isCurrent = account.plan === plan.key || (plan.key === "free" && account.plan !== "premium" && account.plan !== "business");
              const isSelected = selectedPlan === plan.key;
              const isFreeLocked = plan.key === "free" && ["premium", "business"].includes(account.plan || "free") && account.planExpiresAt && new Date(account.planExpiresAt) > new Date();
              const actionLabel = plan.key === "free"
                ? isFreeLocked ? "Khóa đến hết hạn" : "Đang sử dụng"
                : plan.key === "enterprise"
                  ? "Liên hệ"
                  : isCurrent
                    ? "Đang sử dụng"
                    : "Nâng cấp";
              return (
                <div key={plan.key} className={`plan-card ${plan.highlight ? "plan-card-highlight" : ""} ${isCurrent ? "plan-card-current" : ""} ${isSelected ? "plan-card-selected" : ""}`}>
                  {plan.highlight && <span className="plan-badge plan-badge-recommended">Đề xuất</span>}
                  {isCurrent && <span className="plan-badge plan-badge-active">Đang dùng</span>}
                  <div className="plan-header">
                    <span className="plan-name">{plan.name}</span>
                    <span className="plan-price">{plan.price}</span>
                  </div>
                  <div className="plan-status">{plan.status}</div>
                  <p className="plan-description">{plan.description}</p>
                  <button
                    type="button"
                    className={`plan-action ${plan.key === "free" ? "plan-action-current" : plan.key === "enterprise" ? "plan-action-contact" : isSelected ? "plan-action-selected" : "plan-action-idle"}`}
                    onClick={() => {
                      if (plan.key === "enterprise") {
                        window.open("https://zalo.me/0366146305", "_blank", "noopener,noreferrer");
                        setPremiumOpen(false);
                        return;
                      }

                      if (plan.key === "free") {
                        if (isFreeLocked) {
                          setSelectedPlan(plan.key);
                          setPremiumError(`Bạn đang ở gói ${activePlanLabel}. Chỉ có thể xuống Free sau khi hết hạn ${formatPlanExpiry(account.planExpiresAt)}.`);
                          return;
                        }
                        handlePlanSelect(plan.key);
                        return;
                      }

                      setSelectedPlan(plan.key);
                      setPremiumError("");
                      setActivationCode("");
                    }}
                    aria-label={plan.key === "free" ? "Gói Free đang được sử dụng" : `Chọn gói ${plan.name}`}
                    disabled={isFreeLocked && plan.key === "free"}
                  >
                    {actionLabel}
                  </button>
                </div>
              );
            })}
          </div>
          {(selectedPlan === "premium" || selectedPlan === "business") && (
            <div className="activation-panel">
              <button type="button" className="activation-close" onClick={() => { setSelectedPlan("free"); setActivationCode(""); setPremiumError(""); }} aria-label="Đóng panel nhập mã">×</button>
              <div className="activation-header">
                <span className="activation-pill">{selectedPlan === "premium" ? "Premium" : "Business"}</span>
              </div>
              <label>
                Mã kích hoạt
                <input
                  type="text"
                  value={activationCode}
                  onChange={(event) => setActivationCode(event.target.value)}
                  placeholder="Nhập mã code kích hoạt"
                />
              </label>
              <button type="button" className="primary premium-submit" onClick={() => handlePlanSelect(selectedPlan)}>
                Xác nhận kích hoạt
              </button>
              {premiumError && <div className="premium-error">{premiumError}</div>}
            </div>
          )}
        </div>
      </div>}

      {accountInfoOpen && <div className="modal-backdrop" role="presentation" onClick={() => setAccountInfoOpen(false)}>
        <div className="premium-modal plan-modal" onClick={(event) => event.stopPropagation()}>
          <button type="button" className="modal-close" onClick={() => setAccountInfoOpen(false)} aria-label="Đóng">×</button>
          <div className="plan-modal-header">
            <span className="premium-kicker">ForestCare AI</span>
            <h2>Thông tin tài khoản</h2>
          </div>
          <div id="firebase-recaptcha-container" />
          <div className="account-info-grid">
            <div><span>Tên tài khoản</span><strong>{account.username || account.email}</strong></div>
            <div><span>Gói đang sử dụng</span><strong>{activePlanLabel}</strong></div>
            <div><span>Số điện thoại</span><strong>{account.phone || "Chưa bổ sung"}</strong></div>
            <div><span>Trạng thái SĐT</span><strong>{account.phoneVerified ? "Đã xác minh" : "Chưa xác minh"}</strong></div>
          </div>
          <div className="profile-section">
            <div className="profile-section-heading"><strong>Bổ sung số điện thoại</strong><span>Nhận OTP để xác minh</span></div>
            <form onSubmit={verifyProfilePhone} className="profile-phone-form">
              <div className="phone-input">
                <span>+84</span>
                <input type="tel" value={profilePhone.replace(/^\+84/, "")} onChange={(event) => updatePhoneDigits(event.target.value, setProfilePhone)} placeholder="Nhập 9 chữ số còn lại" />
              </div>
              <div className="otp-row">
                <input type="text" value={profileOtp} onChange={(event) => setProfileOtp(event.target.value)} placeholder="Mã xác thực" />
                <button type="button" className="secondary" onClick={sendProfilePhoneOtp} disabled={profileLoading}>Gửi OTP</button>
              </div>
              <button className="primary" type="submit" disabled={profileLoading}>{profileLoading ? "Đang xác minh..." : "Xác nhận số điện thoại"}</button>
            </form>
            {profileMessage && <div className={`auth-message ${profileMessage.startsWith("✅") ? "success" : "error"}`}>{profileMessage}</div>}
          </div>
          <div className="profile-section">
            <div className="profile-section-heading"><strong>Đổi mật khẩu</strong><span>Cập nhật bảo mật tài khoản</span></div>
          <form onSubmit={handleChangePassword} className="profile-password-form">
            <label>
              Mật khẩu cũ
              <input type="password" value={oldPassword} onChange={(event) => setOldPassword(event.target.value)} placeholder="Nhập mật khẩu cũ" />
            </label>
            <label>
              Mật khẩu mới
              <input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} placeholder="Tối thiểu 6 ký tự" />
            </label>
            <label>
              Xác nhận mật khẩu mới
              <input type="password" value={confirmNewPassword} onChange={(event) => setConfirmNewPassword(event.target.value)} placeholder="Nhập lại mật khẩu mới" />
            </label>
            <button className="primary" type="submit" disabled={passwordLoading}>{passwordLoading ? "Đang cập nhật..." : "Cập nhật mật khẩu"}</button>
          </form>
          </div>
          {passwordMessage && <div className={`auth-message ${passwordMessage.startsWith("✅") ? "success" : "error"}`}>{passwordMessage}</div>}
        </div>
      </div>}

    </div>
  );
}

function LoginPage({ onLogin }) {
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [phone, setPhone] = useState("+84");
  const [otp, setOtp] = useState("");
  const [resetPhone, setResetPhone] = useState("+84");
  const [resetOtp, setResetOtp] = useState("");
  const [resetPassword, setResetPassword] = useState("");
  const [resetConfirmPassword, setResetConfirmPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [authLoading, setAuthLoading] = useState(false);

  const normalizePhoneForFirebase = (value) => {
    const digits = (value || "").replace(/\D/g, "");
    if (!digits) return "";
    if (digits.startsWith("84")) return `+${digits}`;
    if (digits.startsWith("0")) return `+84${digits.slice(1)}`;
    return `+${digits}`;
  };

  const updatePhoneDigits = (value, setter) => {
    let digits = value.replace(/\D/g, "");
    if (digits.startsWith("84")) digits = digits.slice(2);
    if (digits.startsWith("0")) digits = digits.slice(1);
    setter(`+84${digits.slice(0, 9)}`);
  };

  const sendFirebasePhoneOtp = async (phoneNumber) => {
    if (!firebaseAuth || !isFirebaseConfigured) {
      return null;
    }

    if (!window.recaptchaVerifier) {
      window.recaptchaVerifier = new RecaptchaVerifier(firebaseAuth, "firebase-recaptcha-container", {
        size: "invisible",
        callback: () => {},
        defaultCountry: "VN",
      });
    }

    const normalizedPhone = normalizePhoneForFirebase(phoneNumber);
    const confirmation = await signInWithPhoneNumber(firebaseAuth, normalizedPhone, window.recaptchaVerifier);
    window.confirmationResult = confirmation;
    return confirmation;
  };

  const sendSignupOtp = async () => {
    const normalizedPhone = phone.trim();
    if (normalizedPhone.replace(/^\+84/, "").length !== 9) {
      setLoginError("Vui lòng nhập số điện thoại để nhận OTP.");
      return;
    }

    setAuthLoading(true);
    try {
      if (isFirebaseConfigured && firebaseAuth) {
        await sendFirebasePhoneOtp(normalizedPhone);
        setLoginError("✅ Mã OTP Firebase đã được gửi đến số điện thoại của bạn.");
        return;
      }

      const response = await axios.post(`${API_URL}/auth/send-signup-otp`, { phone: normalizedPhone });
      if (!response.data?.success) {
        setLoginError(response.data?.message || "Không thể gửi mã OTP.");
        return;
      }
      setLoginError("✅ Mã OTP đã được gửi đến số điện thoại của bạn.");
    } catch (error) {
      setLoginError(error.response?.data?.message || error.message || "Không thể gửi mã OTP.");
    } finally {
      setAuthLoading(false);
    }
  };

  const sendResetOtp = async () => {
    const normalizedPhone = resetPhone.trim();
    if (normalizedPhone.replace(/^\+84/, "").length !== 9) {
      setLoginError("Vui lòng nhập số điện thoại để xác thực reset mật khẩu.");
      return;
    }

    setAuthLoading(true);
    try {
      if (isFirebaseConfigured && firebaseAuth) {
        await sendFirebasePhoneOtp(normalizedPhone);
        setLoginError("✅ Mã OTP Firebase đã được gửi để đặt lại mật khẩu.");
        return;
      }

      const response = await axios.post(`${API_URL}/auth/request-reset-otp`, { phone: normalizedPhone });
      if (!response.data?.success) {
        setLoginError(response.data?.message || "Không thể gửi OTP đặt lại mật khẩu.");
        return;
      }
      setLoginError("✅ Mã OTP đặt lại mật khẩu đã được gửi.");
    } catch (error) {
      setLoginError(error.response?.data?.message || error.message || "Không thể gửi mã OTP đặt lại mật khẩu.");
    } finally {
      setAuthLoading(false);
    }
  };

  const submitAuth = async (event) => {
    event.preventDefault();
    setLoginError("");

    const trimmedUsername = username.trim();
    if (mode !== "reset") {
      if (!trimmedUsername || trimmedUsername.length < 3) {
        setLoginError("Tên tài khoản tối thiểu 3 ký tự.");
        return;
      }

      if (password.length < 6) {
        setLoginError("Mật khẩu tối thiểu 6 ký tự.");
        return;
      }
    }

    if (mode === "signup") {
      const hasPhone = phone.replace(/^\+84/, "").trim().length > 0;
      if (hasPhone && !otp.trim()) {
        setLoginError("Vui lòng nhập mã OTP đã nhận qua số điện thoại.");
        return;
      }
      if (password !== confirmPassword) {
        setLoginError("Mật khẩu xác nhận không khớp.");
        return;
      }
    }

    if (mode === "reset") {
      if (!resetPhone.trim()) {
        setLoginError("Vui lòng nhập số điện thoại để xác thực reset mật khẩu.");
        return;
      }
      if (!resetOtp.trim()) {
        setLoginError("Vui lòng nhập mã OTP để đặt lại mật khẩu.");
        return;
      }
      if (resetPassword.length < 6) {
        setLoginError("Mật khẩu mới tối thiểu 6 ký tự.");
        return;
      }
      if (resetPassword !== resetConfirmPassword) {
        setLoginError("Mật khẩu mới và xác nhận không khớp.");
        return;
      }
    }

    setAuthLoading(true);

    try {
      let firebaseToken = "";
      if ((mode === "signup" || mode === "reset") && isFirebaseConfigured && firebaseAuth && window.confirmationResult && (mode === "reset" ? resetOtp : otp).trim()) {
        const firebaseCredential = await window.confirmationResult.confirm((mode === "reset" ? resetOtp : otp).trim());
        firebaseToken = await firebaseCredential.user.getIdToken();
      }

      const endpoint = mode === "signup" ? `${API_URL}/auth/signup` : mode === "reset" ? `${API_URL}/auth/verify-reset-otp` : `${API_URL}/auth/login`;
      const payload = mode === "signup"
        ? { username: trimmedUsername, password, confirmPassword, phone: phone.replace(/^\+84$/, "") ? normalizePhoneForFirebase(phone) : "", otp, firebaseToken }
        : mode === "reset"
          ? { phone: normalizePhoneForFirebase(resetPhone), otp: resetOtp, newPassword: resetPassword, firebaseToken }
          : { username: trimmedUsername, password };

      const response = await axios.post(endpoint, payload);
      const result = response.data;

      if (!result?.success) {
        setLoginError(result?.message || "Xử lý đăng nhập thất bại.");
        return;
      }

      if (mode === "reset") {
        setMode("login");
        setLoginError("✅ Đặt lại mật khẩu thành công. Vui lòng đăng nhập lại.");
        setResetPhone("+84");
        setResetOtp("");
        setResetPassword("");
        setResetConfirmPassword("");
        setPassword("");
        setUsername("");
        setAuthLoading(false);
        return;
      }

      const userPayload = result.user || { username: trimmedUsername, email: trimmedUsername, premium: false, plan: "free" };
      onLogin({
        id: userPayload.id,
        name: userPayload.name || username.trim(),
        username: userPayload.username || userPayload.name || trimmedUsername,
        email: userPayload.email || userPayload.username || trimmedUsername,
        plan: userPayload.plan || "free",
        premium: Boolean(userPayload.premium),
        planExpiresAt: userPayload.planExpiresAt || null,
        phone: userPayload.phone || "",
        phoneVerified: Boolean(userPayload.phoneVerified),
      });
    } catch (error) {
      const backendMessage = error.response?.data?.message || error.message || "Không kết nối được đến máy chủ.";
      setLoginError(backendMessage || "Thao tác không thành công. Vui lòng thử lại.");
    } finally {
      setAuthLoading(false);
    }
  };

  const title = mode === "signup" ? "Tạo tài khoản mới" : mode === "reset" ? "Đặt lại mật khẩu" : "Chào mừng trở lại";
  const subtitle = mode === "signup"
    ? "Đăng ký bằng số điện thoại, OTP và mật khẩu."
    : mode === "reset"
      ? "Nhập số điện thoại để nhận OTP và đổi mật khẩu mới."
      : "Đăng nhập bằng tên tài khoản và mật khẩu.";

  return (
    <main className="auth-page">
      <div className="auth-layout">
        <section className="auth-panel">
          <div className="auth-logo"><img src="/logo.png" alt="ForestCare AI" /></div>
          <div className="auth-panel-header">
            <span className="auth-kicker">Tài khoản của bạn</span>
            <span className="auth-secure"><span aria-hidden="true">●</span> Kết nối bảo mật</span>
          </div>

        <div className="auth-toggle">
          <button
            type="button"
            className={mode === "login" ? "primary" : "secondary"}
            onClick={() => setMode("login")}
          >
            Đăng nhập
          </button>
          <button
            type="button"
            className={mode === "signup" ? "primary" : "secondary"}
            onClick={() => setMode("signup")}
          >
            Tạo tài khoản
          </button>
        </div>

        <h1>{title}</h1>
        <p className="auth-subtitle">{subtitle}</p>

        <div id="firebase-recaptcha-container" />

        {mode !== "reset" && (
          <form onSubmit={submitAuth}>
            <label>
              Tên tài khoản
              <input type="text" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Nhập tên tài khoản" />
            </label>

            {mode === "signup" && (
              <>
                <label>
                  Số điện thoại
                  <div className="phone-input">
                    <span>+84</span>
                    <input type="tel" value={phone.replace(/^\+84/, "")} onChange={(event) => updatePhoneDigits(event.target.value, setPhone)} placeholder="Nhập 9 chữ số còn lại" />
                  </div>
                </label>
                <div className="otp-row">
                  <input type="text" value={otp} onChange={(event) => setOtp(event.target.value)} placeholder="Mã xác thực" />
                  <button type="button" className="secondary" onClick={sendSignupOtp} disabled={authLoading}>Gửi OTP</button>
                </div>
              </>
            )}

            <label>
              Mật khẩu
              <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Tối thiểu 6 ký tự" />
            </label>

            {mode === "signup" && (
              <label>
                Xác nhận mật khẩu
                <input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} placeholder="Nhập lại mật khẩu" />
              </label>
            )}

            {loginError && <div className={`auth-message ${loginError.startsWith("✅") ? "success" : "error"}`} aria-live="polite">{loginError}</div>}

            <button className="primary auth-submit" type="submit" disabled={authLoading}>
              {authLoading ? (mode === "signup" ? "Đang tạo tài khoản..." : "Đang đăng nhập...") : (mode === "signup" ? "Tạo tài khoản" : "Đăng nhập")}
            </button>
          </form>
        )}

        {mode === "reset" && (
          <form onSubmit={submitAuth}>
            <label>
              Số điện thoại
              <div className="phone-input">
                <span>+84</span>
                <input type="tel" value={resetPhone.replace(/^\+84/, "")} onChange={(event) => updatePhoneDigits(event.target.value, setResetPhone)} placeholder="Nhập 9 chữ số còn lại" />
              </div>
            </label>
            <div className="otp-row">
              <input type="text" value={resetOtp} onChange={(event) => setResetOtp(event.target.value)} placeholder="Mã xác thực" />
              <button type="button" className="secondary" onClick={sendResetOtp} disabled={authLoading}>Gửi OTP</button>
            </div>
            <label>
              Mật khẩu mới
              <input type="password" value={resetPassword} onChange={(event) => setResetPassword(event.target.value)} placeholder="Tối thiểu 6 ký tự" />
            </label>
            <label>
              Xác nhận mật khẩu mới
              <input type="password" value={resetConfirmPassword} onChange={(event) => setResetConfirmPassword(event.target.value)} placeholder="Nhập lại mật khẩu mới" />
            </label>

            {loginError && <div className={`auth-message ${loginError.startsWith("✅") ? "success" : "error"}`} aria-live="polite">{loginError}</div>}

            <button className="primary auth-submit" type="submit" disabled={authLoading}>
              {authLoading ? "Đang cập nhật mật khẩu..." : "Đặt lại mật khẩu"}
            </button>
          </form>
        )}

        {mode !== "reset" && (
          <div className="auth-secondary-action">
            <button type="button" className="secondary" onClick={() => setMode("reset")}>Quên mật khẩu?</button>
          </div>
        )}

        {mode === "reset" && (
          <div className="auth-secondary-action reset-back">
            <button type="button" className="secondary" onClick={() => setMode("login")}>Quay lại đăng nhập</button>
          </div>
        )}

        <small>
          {mode === "signup"
            ? "Mã OTP sẽ được gửi qua SĐT để xác minh tài khoản mới."
            : mode === "reset"
              ? "Đặt lại mật khẩu bằng OTP trên SĐT của bạn."
              : "Tên tài khoản và mật khẩu được lưu trên thiết bị này."}
        </small>
        </section>
      </div>
    </main>
  );
}

function DiseasePage({ tree, disease, onTreeChange, onDiseaseChange }) {
  const info = DISEASES[tree].find((item) => item.name === disease) || DISEASES[tree][0];
  const isPhysiological = info.scientific === "Yếu tố phi sinh học";
  return (
    <section>
      <div className="page-heading">
        <span className="eyebrow">FIELD GUIDE</span>
        <h2>📖 Thông tin bệnh hại</h2>
        <p>Tra cứu nguyên nhân, triệu chứng và biện pháp phòng trừ theo từng loại cây.</p>
      </div>

      <div className="card filters">
        <label>
          Loài cây
          <select value={tree} onChange={(event) => onTreeChange(event.target.value)}>
            {Object.keys(DISEASES).map((item) => <option key={item}>{item}</option>)}
          </select>
        </label>
        <label>
          Loại bệnh
          <select value={disease} onChange={(event) => onDiseaseChange(event.target.value)}>
            {DISEASES[tree].map((item) => <option key={item.name}>{item.name}</option>)}
          </select>
        </label>
      </div>

      <div className="disease-detail">
        <div className="disease-visual">
          {info.image ? <img src={info.image} alt={info.name} /> : <><span>🌿</span><strong>{info.name}</strong><small>Ảnh minh họa đang được cập nhật</small></>}
        </div>

        <div className="disease-content">
          <div className="disease-header">
            <div className="disease-identity">
              <span className="eyebrow disease-species">{tree.toUpperCase()}</span>
              <h3>{info.name}</h3>
            </div>
            {isPhysiological ? <span className="disease-tag disease-tag-soft">Sinh lý</span> : <span className="disease-tag disease-tag-strong">Nấm bệnh</span>}
          </div>

          <div className="taxonomy-row">
            {isPhysiological ? (
              <span className="taxonomy-item">
                <span className="taxonomy-label">Danh pháp</span>
                <span className="taxonomy-value scientific-value" dangerouslySetInnerHTML={{ __html: formatScientificText(info.scientific) }} />
              </span>
            ) : (
              <>
                <span className="taxonomy-item">
                  <span className="taxonomy-label">Danh pháp</span>
                  <span className="taxonomy-value scientific-value" dangerouslySetInnerHTML={{ __html: formatScientificText(info.scientific) }} />
                </span>
                {info.order && <><span className="taxonomy-divider">•</span><span className="taxonomy-item"><span className="taxonomy-label">Bộ</span><span className="taxonomy-value">{info.order}</span></span></>}
                {info.family && <><span className="taxonomy-divider">•</span><span className="taxonomy-item"><span className="taxonomy-label">Họ</span><span className="taxonomy-value">{info.family}</span></span></>}
              </>
            )}
          </div>

          <InfoBlock title="Nguyên nhân" icon="🔬" tone="gold" value={info.cause} />
          <InfoBlock title="Triệu chứng" icon="🔴" tone="rose" value={info.symptoms} />
          <InfoBlock title="Biện pháp phòng trừ" icon="🛡️" tone="green" value={info.prevention.replace(/^-\s*/gm, "")} />
        </div>
      </div>
    </section>
  );
}

function HistoryPage({ history, selectedHistory, onToggle, onToggleAll, onDeleteSelected, onExport, onClear }) {
  const diseased = history.filter((item) => item.status === "Bị bệnh").length;
  const allSelected = history.length > 0 && selectedHistory.length === history.length;
  return <section><div className="page-heading history-heading"><div><span className="eyebrow">FIELD RECORDS</span><h2>🗂️ Lịch sử chẩn đoán</h2><p>Các kết quả đã lưu trên thiết bị này.</p></div>{history.length > 0 && <button className="secondary" onClick={onClear}>Xóa tất cả</button>}</div><div className="kpis"><div><span>🗂️</span><strong>{history.length}</strong><small>Tổng bản ghi</small></div><div><span>🦠</span><strong>{diseased}</strong><small>Lượt bị bệnh</small></div><div><span>📌</span><strong>{history.find((item) => item.disease)?.disease || "-"}</strong><small>Phổ biến nhất</small></div></div>{history.length === 0 ? <div className="empty-state"><span>🗂️</span><p>Chưa có dữ liệu. Hãy thực hiện chẩn đoán hoặc tính mức độ trước.</p></div> : <><div className="history-actions"><label><input type="checkbox" checked={allSelected} onChange={onToggleAll} /> Chọn tất cả</label><span>{selectedHistory.length} mục đã chọn</span><div><button className="secondary" onClick={onExport} disabled={!selectedHistory.length}>📥 Xuất Excel</button><button className="danger-button" onClick={onDeleteSelected} disabled={!selectedHistory.length}>🗑️ Xóa mục chọn</button></div></div><div className="history-table"><div className="table-head"><span>Chọn</span><span>Thời gian</span><span>Cây</span><span>Tình trạng</span><span>Tên bệnh</span><span>Triệu chứng</span><span>Cấp</span><span>Phương pháp</span></div>{history.map((item) => <div className="table-row" key={item.id}><span><input type="checkbox" checked={selectedHistory.includes(item.id)} onChange={() => onToggle(item.id)} /></span><span>{item.date}</span><span>{item.tree || "-"}</span><span className={item.status === "Bị bệnh" ? "text-danger" : "text-good"}>{item.status}</span><span>{item.disease || "-"}</span><span>{item.symptoms || "-"}</span><span className="level-badge">{item.level}</span><span>AI chẩn đoán</span></div>)}</div></>}</section>;
}

function DiagnosisPage({ diagnosis, error, loading, onDiagnose, onFileChange, onReset, previewUrl, selectedFile, account, dailyUsage }) {
  return (
    <section>
      <div className="page-heading diagnosis-heading">
        <div><span className="eyebrow">AI ANALYSIS</span><h2>🔍 Chẩn đoán tình trạng lá</h2></div>
        <p>Nhận diện tình trạng lá, triệu chứng và tự động tính mức độ bị hại.</p>
        <div className={account.premium ? "usage-badge premium-usage" : "usage-badge"}>{account.premium ? "✦ Premium · Không giới hạn lượt chẩn đoán" : `Tài khoản Free · Còn ${Math.max(FREE_DAILY_LIMIT - dailyUsage.count, 0)}/${FREE_DAILY_LIMIT} lượt hôm nay`}</div>
      </div>
      <div className="card upload-card diagnosis-upload">
        <div className="upload-copy"><span className="upload-icon">📸</span><div><strong>Dữ liệu đầu vào</strong><span>JPG, JPEG hoặc PNG</span></div></div>
        <label className="file-picker">{selectedFile ? selectedFile.name : "Chọn ảnh lá cây"}<input type="file" accept="image/jpeg,image/png" onChange={onFileChange} /></label>
        <div className="action-row">
          <button className="primary" onClick={onDiagnose} disabled={loading}>{loading ? "⏳ Đang chẩn đoán..." : "🚀 Thực hiện chẩn đoán"}</button>
          {selectedFile && <button className="secondary" onClick={onReset}>🗑️ Hủy ảnh</button>}
        </div>
      </div>
      {error && <div className="notice error">{error}</div>}
      {diagnosis?.detected === false && <div className="notice healthy">✅ {diagnosis.message}</div>}
      {diagnosis?.detected && <DiagnosisResult diagnosis={diagnosis} previewUrl={previewUrl} />}
      {!diagnosis && !error && <div className="empty-state"><span>🌿</span><p>Chọn ảnh lá cây để bắt đầu phân tích.</p></div>}
    </section>
  );
}

function DiagnosisResult({ diagnosis, previewUrl }) {
  const { info } = diagnosis;
  const damage = diagnosis.damage;
  return (
    <div className="result-area diagnosis-results">
      <div className="image-grid">
        <figure><img src={previewUrl} alt="Ảnh gốc" /><figcaption>Ảnh gốc</figcaption></figure>
        <figure><img src={damage?.annotated_image || diagnosis.annotated_image} alt="Ảnh AI nhận diện" /><figcaption>AI nhận diện + vùng tổn thương</figcaption></figure>
      </div>
      <div className="result-summary diagnosis-summary">
        <div className="result-title"><span className="eyebrow">KẾT QUẢ CHẨN ĐOÁN</span><h3>🌳 {diagnosis.tree_name}</h3><h4>🦠 {diagnosis.disease}</h4><strong className="confidence">Độ tin cậy: {diagnosis.confidence}%</strong></div>
        {damage && <div className="measurement-box"><div className="measurement-card metric-total"><span>Tổng thể chiếc lá</span><strong>{damage.total_leaf_pixels.toLocaleString("vi-VN")} pixel</strong></div><div className="measurement-card metric-damage"><span>Vùng tổn thương</span><strong>{damage.injury_pixels.toLocaleString("vi-VN")} pixel</strong></div><div className="measurement-card metric-percent"><span>Mức độ bị hại</span><strong>{damage.injury_percentage}%</strong></div><div className={damage.level ? "measurement-level danger-level" : "measurement-level healthy-level"}>Cấp bệnh: {damage.level}</div></div>}
        {diagnosis.is_healthy ? <div className="notice healthy">Lá cây đang ở trạng thái khỏe mạnh.</div> : <>
          <InfoBlock title="Triệu chứng" icon="" value={`${info.symptoms.replace(/\.$/, "")} chiếm ${damage?.injury_percentage ?? 0}% trên tổng thể chiếc lá.`} />
          <InfoBlock title="Nguyên nhân" icon="" value={info.cause} />
          <InfoBlock title="Biện pháp phòng trừ" icon="" value={info.prevention} />
        </>}
      </div>
    </div>
  );
}

function InfoBlock({ title, value, icon = "•", tone = "default" }) {
  return <div className={`info-block info-block-${tone}`}>
    <div className="info-block-head">
      <span className="info-block-icon">{icon}</span>
      <strong>{title}</strong>
    </div>
    <p dangerouslySetInnerHTML={{ __html: formatScientificText(value) }} />
  </div>;
}

export default App;