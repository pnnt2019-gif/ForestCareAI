import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import * as XLSX from "xlsx";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "/api";
const PREMIUM_CODE = import.meta.env.VITE_PREMIUM_CODE || "FORESTCARE-PREMIUM-2026";
const FREE_DAILY_LIMIT = 10;

function todayKey() {
  return new Date().toLocaleDateString("en-CA");
}

function usageStorageKey(email) {
  return `forestcare-daily-usage-${email}`;
}

function readDailyUsage(email) {
  const usage = JSON.parse(localStorage.getItem(usageStorageKey(email)) || "null");
  return usage?.date === todayKey() ? usage : { date: todayKey(), count: 0 };
}
const DISEASES = {
  "Gõ đỏ": [{ name: "Đốm đen", image: "/diseases/go-do-dom-den.jpg", scientific: "Stemphylium sp.", cause: "Do nấm Stemphylium sp. tấn công biểu bì lá.", symptoms: "Vết bệnh cục bộ trên lá, màu đen đặc trưng.", prevention: "Sử dụng chế phẩm chứa nấm đối kháng và phun ướt đều tán lá." }, { name: "Cháy lá sinh lý", image: "/diseases/go-do-chay-la-sinh-ly.jpg", scientific: "Yếu tố phi sinh học", cause: "Sốc nhiệt, gió hoặc muối.", symptoms: "Cháy mép lá, mô khô teo tóp, giòn, màu nâu hoặc vàng.", prevention: "Điều chỉnh vi khí hậu và che lưới." }],
  "Hồng lộc": [{ name: "Cháy lá sinh lý", image: "/diseases/hong-loc-chay-la-sinh-ly.jpg", scientific: "Yếu tố phi sinh học", cause: "Sốc nhiệt hoặc gió.", symptoms: "Mô lá khô lại, teo tóp, màu nâu hoặc xám.", prevention: "Điều chỉnh vi khí hậu, che lưới 50-70%." }],
  "Lát hoa": [{ name: "Đốm nâu", image: "/diseases/lat-hoa-dom-nau.jpg", scientific: "Curvularia sp.", cause: "Do nấm Curvularia sp. gây ra.", symptoms: "Vết tổn thương nâu sẫm, viền vàng.", prevention: "Đang cập nhật..." }],
  "Xà cừ": [{ name: "Đốm nâu", scientific: "Đang cập nhật...", cause: "Đang cập nhật...", symptoms: "Đang cập nhật...", prevention: "Đang cập nhật..." }]
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
  const [history, setHistory] = useState(() => JSON.parse(localStorage.getItem("forestcare-history") || "[]"));
  const [selectedHistory, setSelectedHistory] = useState([]);
  const [tree, setTree] = useState("Gõ đỏ");
  const [disease, setDisease] = useState(DISEASES["Gõ đỏ"][0].name);
  const [dailyUsage, setDailyUsage] = useState(() => readDailyUsage(account.email));
  const [premiumOpen, setPremiumOpen] = useState(false);
  const [premiumCode, setPremiumCode] = useState("");
  const [premiumError, setPremiumError] = useState("");

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
    localStorage.setItem("forestcare-history", JSON.stringify(next));
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
    localStorage.setItem("forestcare-history", JSON.stringify(next));
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

  const activatePremium = (event) => {
    event.preventDefault();
    if (premiumCode.trim() !== PREMIUM_CODE) {
      setPremiumError("Mã kích hoạt không đúng hoặc đã hết hiệu lực.");
      return;
    }
    onAccountChange({ ...account, premium: true });
    setPremiumCode("");
    setPremiumError("");
    setPremiumOpen(false);
  };

  const logout = () => {
    localStorage.removeItem("forestcare-account");
    window.location.reload();
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
            Chẩn đoán tình trạng lá
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
          <div className="qr-frame">
            <img src="/qr-fanpage.png" alt="Mã QR fanpage ForestCare" />
            <span>Quét mã để ghé thăm fanpage</span>
          </div>
          <a className="tiktok-link" href="https://www.tiktok.com/@forestcare.ai" target="_blank" rel="noreferrer">
            <span className="tiktok-mark">♪</span>
            <span><small>TikTok</small><strong>@forestcare.ai</strong></span>
            <span className="external-arrow">↗</span>
          </a>
        </div>

        <div className="account-panel">
          <div className="account-avatar">{account.email[0].toUpperCase()}</div>
          <div className="account-copy"><strong>{account.email}</strong><span className={account.premium ? "premium-text" : ""}>{account.premium ? "Premium account" : "Tài khoản miễn phí"}</span></div>
          {account.premium ? <span className="premium-badge">PRO</span> : <button className="upgrade-button" onClick={() => { setPremiumOpen(true); setPremiumError(""); }}>Nâng cấp</button>}
          <button className="logout-button" onClick={logout} title="Đăng xuất" aria-label="Đăng xuất">↪</button>
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

        {activePage === "history" && <HistoryPage history={history} selectedHistory={selectedHistory} onToggle={toggleHistory} onToggleAll={toggleAllHistory} onDeleteSelected={deleteSelectedHistory} onExport={exportSelectedHistory} onClear={() => { setHistory([]); setSelectedHistory([]); localStorage.removeItem("forestcare-history"); }} />}

      </main>

      {premiumOpen && <div className="modal-backdrop" role="presentation" onClick={() => setPremiumOpen(false)}>
        <form className="premium-modal" onSubmit={activatePremium} onClick={(event) => event.stopPropagation()}>
          <button type="button" className="modal-close" onClick={() => setPremiumOpen(false)} aria-label="Đóng">×</button>
          <span className="premium-kicker">FORESTCARE PREMIUM</span>
          <h2>Kích hoạt tài khoản Premium</h2>
          <p>Nhập mã kích hoạt để mở khóa trải nghiệm Premium trên tài khoản của bạn.</p>
          <label>Mã kích hoạt<input autoFocus value={premiumCode} onChange={(event) => { setPremiumCode(event.target.value.toUpperCase()); setPremiumError(""); }} placeholder="FORESTCARE-XXXX" /></label>
          {premiumError && <div className="premium-error">{premiumError}</div>}
          <button className="primary premium-submit" type="submit">Kích hoạt Premium</button>
        </form>
      </div>}

    </div>
  );
}

function LoginPage({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");

  const submitLogin = (event) => {
    event.preventDefault();
    if (!email.trim() || password.length < 6) {
      setLoginError("Vui lòng nhập email và mật khẩu tối thiểu 6 ký tự.");
      return;
    }
    onLogin({ email: email.trim().toLowerCase(), premium: false });
  };

  return <main className="auth-page"><div className="auth-panel"><img src="/logo.png" alt="ForestCare AI" /><span className="eyebrow">FORESTCARE AI</span><h1>Chào mừng trở lại</h1><p>Đăng nhập để tiếp tục theo dõi sức khỏe cây xanh.</p><form onSubmit={submitLogin}><label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" /></label><label>Mật khẩu<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Tối thiểu 6 ký tự" /></label>{loginError && <div className="premium-error">{loginError}</div>}<button className="primary auth-submit" type="submit">Đăng nhập</button></form><small>Phiên đăng nhập được lưu trên thiết bị này.</small></div></main>;
}

function DiseasePage({ tree, disease, onTreeChange, onDiseaseChange }) {
  const info = DISEASES[tree].find((item) => item.name === disease) || DISEASES[tree][0];
  return <section><div className="page-heading"><span className="eyebrow">FIELD GUIDE</span><h2>📖 Thông tin bệnh hại</h2><p>Tra cứu nguyên nhân, triệu chứng và biện pháp phòng trừ theo từng loại cây.</p></div><div className="card filters"><label>Loài cây<select value={tree} onChange={(event) => onTreeChange(event.target.value)}>{Object.keys(DISEASES).map((item) => <option key={item}>{item}</option>)}</select></label><label>Loại bệnh<select value={disease} onChange={(event) => onDiseaseChange(event.target.value)}>{DISEASES[tree].map((item) => <option key={item.name}>{item.name}</option>)}</select></label></div><div className="disease-detail"><div className="disease-visual">{info.image ? <img src={info.image} alt={info.name} /> : <><span>🌿</span><strong>{info.name}</strong><small>Ảnh minh họa đang được cập nhật</small></>}</div><div><span className="eyebrow">{tree.toUpperCase()}</span><h3>{info.name}</h3><p className="scientific"><i>{info.scientific}</i></p><InfoBlock title="🔬 Nguyên nhân" value={info.cause} /><InfoBlock title="🔴 Triệu chứng" value={info.symptoms} /><InfoBlock title="🛡️ Biện pháp phòng trừ" value={info.prevention} /></div></div></section>;
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
        {damage && <div className="measurement-box"><div><span>Tổng thể chiếc lá</span><strong>{damage.total_leaf_pixels.toLocaleString("vi-VN")} pixel</strong></div><div><span>Vùng tổn thương</span><strong>{damage.injury_pixels.toLocaleString("vi-VN")} pixel</strong></div><div><span>Mức độ bị hại</span><strong>{damage.injury_percentage}%</strong></div><div className={damage.level ? "measurement-level danger-level" : "measurement-level healthy-level"}>Cấp bệnh: {damage.level}</div></div>}
        {diagnosis.is_healthy ? <div className="notice healthy">Lá cây đang ở trạng thái khỏe mạnh.</div> : <>
          <InfoBlock title="🔴 Triệu chứng" value={`${info.symptoms.replace(/\.$/, "")} chiếm ${damage?.injury_percentage ?? 0}% trên tổng thể chiếc lá.`} />
          <InfoBlock title="🔬 Nguyên nhân" value={info.cause} />
          <InfoBlock title="🛡️ Biện pháp phòng trừ" value={info.prevention} />
        </>}
      </div>
    </div>
  );
}

function InfoBlock({ title, value }) {
  return <div className="info-block"><strong>{title}</strong><p>{value}</p></div>;
}

export default App;