import { useState, useMemo } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Area, AreaChart, ReferenceLine,
} from "recharts";

/* ═══════════════════════════════════════
   THEME — outdoor-friendly light palette
   ═══════════════════════════════════════ */
const T = {
  bg: "#f5f5f0",
  card: "#ffffff",
  cardAlt: "#fafaf7",
  border: "#e0ddd5",
  borderLight: "#ece9e1",
  text: "#1a1a1a",
  textSub: "#4a4a4a",
  textDim: "#7a7a72",
  textMuted: "#a8a8a0",
  accent: "#2563eb",
  green: "#16a34a",
  orange: "#d97706",
  red: "#dc2626",
  purple: "#7c3aed",
  navBg: "#ffffff",
  inputBg: "#f9f9f6",
  shadow: "0 1px 3px rgba(0,0,0,0.06)",
};
const font = "'DM Sans','Noto Sans JP',sans-serif";
const mono = "'JetBrains Mono',monospace";

/* ═══════════════════════════════════════
   MOCK SENSOR DATA
   ═══════════════════════════════════════ */
const genData = () => {
  const now = new Date(2026, 7, 15);
  const d = [];
  for (let i = 59; i >= 0; i--) {
    const dt = new Date(now); dt.setDate(dt.getDate() - i);
    const doy = Math.floor((dt - new Date(dt.getFullYear(), 0, 0)) / 864e5);
    const base = 22 + 8 * Math.sin((doy - 100) / 60);
    d.push({
      date: dt.toISOString().slice(0, 10),
      label: `${dt.getMonth() + 1}/${dt.getDate()}`,
      airTemp: +(base + (Math.random() - .5) * 4).toFixed(1),
      waterTemp: +(base - 1.5 + (Math.random() - .5) * 2).toFixed(1),
      soilTemp: +(base - 3 + (Math.random() - .5) * 1.5).toFixed(1),
      ph: +(5.8 + (Math.random() - .5) * .6).toFixed(2),
      waterLevel: +(5 + Math.sin(i / 7) * 3 + (Math.random() - .5) * 2).toFixed(1),
      humidity: +(70 + (Math.random() - .5) * 20).toFixed(0),
    });
  }
  return d;
};
const SENSOR = genData();

/* ═══════════════════════════════════════
   GROWTH STAGES
   ═══════════════════════════════════════ */
const STAGES = [
  { name: "育苗期", s: 0, e: .15, color: "#60a5fa", period: "4月下旬〜5月上旬", actions: "苗の生育管理\n水温15℃以上を維持", icon: "🌱",
    waterLevel: { min: 3, max: 5, label: "深水3〜5cm", method: "深水管理" },
    waterTemp: { warnLow: 15, warnHigh: 30, critLow: 12, critHigh: 35 },
    airTemp: { warnHigh: 33, critHigh: 35 } },
  { name: "活着〜分げつ期", s: .15, e: .45, color: "#2563eb", period: "5月中旬〜6月下旬", actions: "浅水管理で地温確保\n分げつ促進\n除草剤散布適期", icon: "🌿",
    waterLevel: { min: 2, max: 3, label: "浅水2〜3cm", method: "浅水管理" },
    waterTemp: { warnLow: 17, warnHigh: 28, critLow: 14, critHigh: 33 },
    airTemp: { warnHigh: 33, critHigh: 35 } },
  { name: "中干し期", s: .45, e: .55, color: "#d97706", period: "7月上旬〜中旬", actions: "落水して土壌を乾燥\n無効分げつ抑制\n根の活力回復", icon: "☀️",
    waterLevel: { min: 0, max: 0, label: "落水（0cm）", method: "中干し" },
    waterTemp: { warnLow: null, warnHigh: null, critLow: null, critHigh: null },
    airTemp: { warnHigh: 35, critHigh: 38 } },
  { name: "幼穂形成〜出穂期", s: .55, e: .75, color: "#ea580c", period: "7月下旬〜8月上旬", actions: "間断灌水（湛水2〜3cm⇔自然落水を2〜3日周期）\nいもち病・紋枯病警戒\n穂肥施用\n低温時は深水10cmで幼穂保護", icon: "🌾",
    waterLevel: { min: 0, max: 5, label: "間断灌水 0〜5cm", method: "間断灌水", alertBelow: 0, warnMsg: "水切れは穂の発育不良・不稔の原因。速やかに入水してください" },
    waterTemp: { warnLow: 17, warnHigh: 28, critLow: 15, critHigh: 30, lowMsg: "17℃以下で冷害リスク。深水10cm以上で幼穂を保護してください", highMsg: "28℃超で高温障害リスク。夕方以降に入水する間断灌水に切り替えてください" },
    airTemp: { warnHigh: 30, critHigh: 35, highMsg: "気温30℃超が継続すると高温障害リスク増大。掛け流し灌水で水温・地温を下げてください" } },
  { name: "登熟期", s: .75, e: .95, color: "#dc2626", period: "8月中旬〜9月中旬", actions: "間断灌水で根を維持\n高温時は夕方入水で水温低下\n日平均27℃超で白未熟粒リスク\n落水は出穂後30日頃", icon: "🍂",
    waterLevel: { min: 0, max: 3, label: "間断灌水 0〜3cm", method: "間断灌水", alertBelow: 0, warnMsg: "早期落水は品質低下の原因。出穂後30日頃まで水分を確保してください" },
    waterTemp: { warnLow: null, warnHigh: 26, critLow: null, critHigh: 30, highMsg: "水温が高い状態が続くと白未熟粒・胴割粒が増加。夕方入水の間断灌水で対応してください" },
    airTemp: { warnHigh: 27, critHigh: 35, highMsg: "日平均27℃超で白未熟粒発生が助長されます。間断灌水の間隔を狭めてください" } },
  { name: "収穫期", s: .95, e: 1, color: "#78716c", period: "9月下旬〜10月", actions: "積算温度1,000℃到達で収穫\n水分含量確認\n刈取5〜7日前に落水", icon: "🚜",
    waterLevel: { min: 0, max: 0, label: "落水", method: "落水" },
    waterTemp: { warnLow: null, warnHigh: null, critLow: null, critHigh: null },
    airTemp: { warnHigh: null, critHigh: null } },
];

const logistic = (x, a, b, c) => a / (1 + Math.exp(-b * (x - c)));

/* ═══════════════════════════════════════
   NAV ICONS
   ═══════════════════════════════════════ */
const Icons = {
  dashboard: <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>,
  input: <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>,
  analytics: <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/></svg>,
  gap: <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>,
};

/* ═══════════════════════════════════════
   REUSABLE COMPONENTS
   ═══════════════════════════════════════ */
function Expandable({ title, icon, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{ background: T.card, borderRadius: 12, border: `1px solid ${T.border}`, marginBottom: 10, boxShadow: T.shadow }}>
      <div onClick={() => setOpen(!open)} style={{ padding: "13px 16px", display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer", userSelect: "none" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {icon && <span style={{ fontSize: 16 }}>{icon}</span>}
          <span style={{ fontSize: 13.5, fontWeight: 600, color: T.text, fontFamily: font }}>{title}</span>
        </div>
        <span style={{ color: T.textMuted, fontSize: 11, transition: "transform .25s", transform: open ? "rotate(180deg)" : "rotate(0)", display: "inline-block" }}>▼</span>
      </div>
      <div style={{ maxHeight: open ? 2000 : 0, overflow: "hidden", transition: "max-height .4s ease" }}>
        <div style={{ padding: "0 16px 16px", borderTop: `1px solid ${T.borderLight}` }}>{children}</div>
      </div>
    </div>
  );
}

function Metric({ label, value, unit, status, small }) {
  const cols = { good: T.green, warn: T.orange, bad: T.red, neutral: T.accent };
  const c = cols[status] || T.accent;
  return (
    <div style={{ background: T.card, borderRadius: 8, border: `1px solid ${T.border}`, padding: small ? "8px 10px" : "12px 14px", flex: 1, minWidth: small ? 70 : 100, boxShadow: T.shadow }}>
      <div style={{ fontSize: 10, color: T.textDim, marginBottom: 3, fontFamily: font, letterSpacing: .3, textTransform: "uppercase" }}>{label}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 2 }}>
        <span style={{ fontSize: small ? 18 : 24, fontWeight: 700, color: c, fontFamily: mono }}>{value}</span>
        <span style={{ fontSize: 10, color: T.textDim }}>{unit}</span>
      </div>
    </div>
  );
}

/* ─── Threshold-aware Metric Card ─── */
function ThresholdMetric({ label, value, unit, stage, sensorKey }) {
  let status = "good";
  let rangeLabel = null;
  if (sensorKey === "airTemp" && stage.airTemp) {
    const t = stage.airTemp;
    if (t.critHigh !== null && value >= t.critHigh) status = "bad";
    else if (t.warnHigh !== null && value >= t.warnHigh) status = "warn";
    if (t.warnHigh) rangeLabel = `推奨: 〜${t.warnHigh}℃`;
  } else if (sensorKey === "waterTemp" && stage.waterTemp) {
    const t = stage.waterTemp;
    if ((t.critLow !== null && value <= t.critLow) || (t.critHigh !== null && value >= t.critHigh)) status = "bad";
    else if ((t.warnLow !== null && value <= t.warnLow) || (t.warnHigh !== null && value >= t.warnHigh)) status = "warn";
    if (t.warnLow && t.warnHigh) rangeLabel = `推奨: ${t.warnLow}〜${t.warnHigh}℃`;
    else if (t.warnHigh) rangeLabel = `推奨: 〜${t.warnHigh}℃`;
  } else if (sensorKey === "waterLevel" && stage.waterLevel) {
    const w = stage.waterLevel;
    if (w.alertBelow !== undefined && value <= w.alertBelow) status = "bad";
    else if (w.min !== null && value < w.min && stage.name !== "中干し期" && stage.name !== "収穫期") status = "warn";
    else if (w.max !== null && value > w.max + 3) status = "warn";
    rangeLabel = stage.waterLevel.label;
  }
  const statusColors = { good: T.green, warn: T.orange, bad: T.red, neutral: T.accent };
  const col = statusColors[status];
  return (
    <div style={{
      background: T.card, borderRadius: 8, padding: "12px 14px", flex: 1, minWidth: 100, boxShadow: T.shadow,
      border: status === "bad" ? `2px solid ${T.red}` : status === "warn" ? `2px solid ${T.orange}60` : `1px solid ${T.border}`,
    }}>
      <div style={{ fontSize: 10, color: T.textDim, marginBottom: 3, fontFamily: font, letterSpacing: .3, textTransform: "uppercase" }}>{label}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 2 }}>
        <span style={{ fontSize: 24, fontWeight: 700, color: col, fontFamily: mono }}>{value}</span>
        <span style={{ fontSize: 10, color: T.textDim }}>{unit}</span>
      </div>
      {rangeLabel && (
        <div style={{ fontSize: 9, color: status === "bad" ? T.red : status === "warn" ? T.orange : T.textMuted, marginTop: 3, fontFamily: font }}>
          {rangeLabel}
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════
   COMMON PESTICIDE LIST
   ═══════════════════════════════════════ */
const PESTICIDES = {
  blast: [
    { name: "トリシクラゾール粒剤", category: "殺菌剤", timing: "予防" },
    { name: "イソチアニル粒剤", category: "殺菌剤", timing: "予防" },
    { name: "カスガマイシン液剤", category: "殺菌剤", timing: "治療" },
    { name: "フェリムゾン・フサライド粉剤DL", category: "殺菌剤", timing: "予防+治療" },
  ],
  sheath: [
    { name: "バリダマイシン液剤", category: "殺菌剤", timing: "予防+治療" },
    { name: "チフルザミド粒剤", category: "殺菌剤", timing: "予防" },
    { name: "ペンシクロン水和剤", category: "殺菌剤", timing: "治療" },
  ],
};

/* ══════════════════════════════════════════════
   PAGE 1: DASHBOARD
   ══════════════════════════════════════════════ */
function DashboardPage({ corrections, setCorrections, sprayLogs, setSprayLogs, setPage }) {
  const currentDVI = 0.62;
  const currentStage = STAGES.find(s => currentDVI >= s.s && currentDVI < s.e) || STAGES[3];
  const accTemp = 1842;
  const daysFromTransplant = 85;
  const latest = SENSOR[SENSOR.length - 1];

  // disease risk calc
  const blastRisk = latest.airTemp >= 25 && latest.airTemp <= 30 && latest.humidity >= 80 ? "high" : latest.humidity >= 70 ? "mid" : "low";
  const sheathRisk = latest.waterTemp >= 28 ? "high" : latest.waterTemp >= 25 ? "mid" : "low";
  const blastHandled = sprayLogs.some(l => l.disease === "blast" && daysSince(l.date) < 14);
  const sheathHandled = sprayLogs.some(l => l.disease === "sheath" && daysSince(l.date) < 14);

  // panicle model
  const modelPanicle = logistic(accTemp, 22.5, 0.005, 1600);

  // inline n=3 input for panicle
  const [p1, setP1] = useState("");
  const [p2, setP2] = useState("");
  const [p3, setP3] = useState("");
  const pVals = [p1, p2, p3].filter(v => v !== "").map(Number);
  const pAvg = pVals.length > 0 ? (pVals.reduce((a, b) => a + b, 0) / pVals.length) : null;

  const handlePanicleSave = () => {
    if (pAvg !== null) {
      setCorrections(prev => ({ ...prev, panicleLength: +pAvg.toFixed(1), date: new Date().toISOString().slice(0, 10) }));
    }
  };

  const deviation = corrections.panicleLength !== null ? (corrections.panicleLength - modelPanicle).toFixed(1) : null;

  // spray recording
  const [sprayOpen, setSprayOpen] = useState(null); // "blast" | "sheath" | null
  const [selectedPesticide, setSelectedPesticide] = useState(null);
  const [sprayAmount, setSprayAmount] = useState("");
  const [sprayArea, setSprayArea] = useState("");

  const handleSprayRecord = (disease) => {
    if (!selectedPesticide) return;
    const log = {
      id: Date.now(),
      date: new Date().toISOString().slice(0, 10),
      disease,
      pesticide: selectedPesticide.name,
      category: selectedPesticide.category,
      timing: selectedPesticide.timing,
      amount: sprayAmount || "—",
      area: sprayArea || "—",
    };
    setSprayLogs(prev => [log, ...prev]);
    setSprayOpen(null);
    setSelectedPesticide(null);
    setSprayAmount("");
    setSprayArea("");
  };

  const inputSm = {
    background: T.inputBg, border: `1px solid ${T.border}`, borderRadius: 6,
    padding: "8px 10px", color: T.text, fontSize: 14, fontFamily: mono,
    width: "100%", boxSizing: "border-box", outline: "none",
  };

  return (
    <div>
      {/* ─── Growth stage header ─── */}
      <div style={{ background: T.card, borderRadius: 12, border: `1px solid ${T.border}`, padding: 16, marginBottom: 10, boxShadow: T.shadow }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
          <span style={{ fontSize: 32 }}>{currentStage.icon}</span>
          <div>
            <div style={{ fontSize: 10, color: T.textDim, letterSpacing: 1, textTransform: "uppercase", fontFamily: font }}>現在の生育ステージ</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: T.text, fontFamily: font }}>{currentStage.name}</div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {[
            { label: "移植後", val: daysFromTransplant, unit: "日目", c: T.accent },
            { label: "積算温度", val: accTemp, unit: "℃", c: T.orange },
            { label: "DVI", val: currentDVI.toFixed(2), unit: "", c: T.green },
          ].map((t, i) => (
            <div key={i} style={{ background: T.cardAlt, borderRadius: 6, padding: "5px 10px", fontSize: 12, color: T.textDim, fontFamily: font }}>
              {t.label} <span style={{ color: t.c, fontWeight: 700 }}>{t.val}</span>{t.unit}
            </div>
          ))}
        </div>
        {/* progress bar */}
        <div style={{ marginTop: 12 }}>
          <div style={{ display: "flex", height: 24, borderRadius: 6, overflow: "hidden" }}>
            {STAGES.map((s, i) => {
              const w = (s.e - s.s) * 100;
              const cur = currentDVI >= s.s && currentDVI < s.e;
              return (
                <div key={i} style={{
                  width: `${w}%`, background: currentDVI >= s.e ? s.color : cur ? `${s.color}dd` : `${s.color}18`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 9, color: currentDVI >= s.s ? "#fff" : T.textMuted, fontWeight: cur ? 700 : 400,
                  borderRight: i < STAGES.length - 1 ? `1px solid ${T.bg}` : "none",
                }}>{w > 8 && s.icon}</div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ─── Current stage details with threshold alerts ─── */}
      <Expandable title="推奨アクション" icon="📋" defaultOpen={true}>
        <div style={{ marginTop: 10, fontSize: 12.5, color: T.textSub, lineHeight: 1.8, fontFamily: font }}>
          <div style={{ color: T.text, fontWeight: 600, marginBottom: 4 }}>{currentStage.name}（{currentStage.period}）</div>
          <div style={{ fontSize: 11, color: T.textDim, marginBottom: 6 }}>水管理: {currentStage.waterLevel.label}（{currentStage.waterLevel.method}）</div>
          {currentStage.actions.split("\n").map((a, i) => (
            <div key={i} style={{ display: "flex", gap: 6, marginBottom: 3 }}>
              <span style={{ color: currentStage.color, flexShrink: 0 }}>→</span><span>{a}</span>
            </div>
          ))}
          {/* Dynamic threshold alerts */}
          {(() => {
            const alerts = [];
            const wl = currentStage.waterLevel;
            const wt = currentStage.waterTemp;
            const at = currentStage.airTemp;
            // Water level alerts
            if (wl.alertBelow !== undefined && latest.waterLevel <= wl.alertBelow && wl.warnMsg) {
              alerts.push({ msg: wl.warnMsg, level: "crit" });
            } else if (wl.min !== null && latest.waterLevel < wl.min && currentStage.name !== "中干し期") {
              alerts.push({ msg: `水位${latest.waterLevel}cmは推奨下限${wl.min}cm未満です。入水を検討してください。`, level: "warn" });
            } else if (wl.max !== null && latest.waterLevel > wl.max + 3) {
              alerts.push({ msg: `水位${latest.waterLevel}cmは推奨上限${wl.max}cmを大きく超えています。排水を検討してください。`, level: "warn" });
            }
            // Water temp alerts
            if (wt.critLow !== null && latest.waterTemp <= wt.critLow) {
              alerts.push({ msg: wt.lowMsg || `水温${latest.waterTemp}℃は危険低温域（${wt.critLow}℃以下）です。深水管理で保温してください。`, level: "crit" });
            } else if (wt.warnLow !== null && latest.waterTemp <= wt.warnLow) {
              alerts.push({ msg: wt.lowMsg || `水温${latest.waterTemp}℃は注意域（${wt.warnLow}℃以下）です。水温の推移に注意してください。`, level: "warn" });
            }
            if (wt.critHigh !== null && latest.waterTemp >= wt.critHigh) {
              alerts.push({ msg: wt.highMsg || `水温${latest.waterTemp}℃は危険高温域（${wt.critHigh}℃以上）です。掛け流し灌水で対応してください。`, level: "crit" });
            } else if (wt.warnHigh !== null && latest.waterTemp >= wt.warnHigh) {
              alerts.push({ msg: wt.highMsg || `水温${latest.waterTemp}℃は注意域（${wt.warnHigh}℃以上）です。高温障害に注意してください。`, level: "warn" });
            }
            // Air temp alerts
            if (at.critHigh !== null && latest.airTemp >= at.critHigh) {
              alerts.push({ msg: at.highMsg || `気温${latest.airTemp}℃は危険域（${at.critHigh}℃以上）です。`, level: "crit" });
            } else if (at.warnHigh !== null && latest.airTemp >= at.warnHigh) {
              alerts.push({ msg: at.highMsg || `気温${latest.airTemp}℃は注意域です。高温障害対策を検討してください。`, level: "warn" });
            }
            if (alerts.length === 0) return null;
            return (
              <div style={{ marginTop: 10 }}>
                {alerts.map((a, i) => (
                  <div key={i} style={{
                    background: a.level === "crit" ? `${T.red}10` : `${T.orange}10`,
                    border: `1px solid ${a.level === "crit" ? T.red + "30" : T.orange + "30"}`,
                    borderRadius: 6, padding: 10, marginBottom: 6,
                  }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: a.level === "crit" ? T.red : T.orange, lineHeight: 1.6, fontFamily: font }}>
                      {a.level === "crit" ? "🔴" : "🟡"} {a.msg}
                    </div>
                  </div>
                ))}
              </div>
            );
          })()}
        </div>
      </Expandable>

      {/* ─── Quick metrics with threshold coloring ─── */}
      <div style={{ display: "flex", gap: 6, marginBottom: 10, flexWrap: "wrap" }}>
        <ThresholdMetric label="気温" value={latest.airTemp} unit="℃" stage={currentStage} sensorKey="airTemp" />
        <ThresholdMetric label="水温" value={latest.waterTemp} unit="℃" stage={currentStage} sensorKey="waterTemp" />
        <ThresholdMetric label="水位" value={latest.waterLevel} unit="cm" stage={currentStage} sensorKey="waterLevel" />
      </div>
      <div style={{ display: "flex", gap: 6, marginBottom: 10, flexWrap: "wrap" }}>
        <Metric label="湿度" value={latest.humidity} unit="%" status={latest.humidity > 85 ? "warn" : "good"} small />
        <Metric label="地温" value={latest.soilTemp} unit="℃" status="good" small />
        <Metric label="pH" value={latest.ph} unit="" status={latest.ph < 5.5 || latest.ph > 6.5 ? "warn" : "good"} small />
      </div>

      {/* ─── Disease Risk + Spray Action ─── */}
      <div style={{ background: T.card, borderRadius: 12, border: `1px solid ${T.border}`, padding: 16, marginBottom: 10, boxShadow: T.shadow }}>
        <div style={{ fontSize: 13.5, fontWeight: 600, color: T.text, marginBottom: 12, fontFamily: font }}>⚠️ 病害リスク評価</div>

        {[
          { key: "blast", name: "いもち病", risk: blastRisk, handled: blastHandled,
            detail: `気温${latest.airTemp}℃ / 湿度${latest.humidity}%。25〜30℃ かつ 多湿で発生リスク増大。`,
            pesticides: PESTICIDES.blast },
          { key: "sheath", name: "紋枯病", risk: sheathRisk, handled: sheathHandled,
            detail: `水温${latest.waterTemp}℃。28℃以上で菌核が活発化。`,
            pesticides: PESTICIDES.sheath },
        ].map(d => {
          const riskLabel = { high: "高", mid: "中", low: "低" };
          const riskCol = { high: T.red, mid: T.orange, low: T.green };
          const isOpen = sprayOpen === d.key;
          return (
            <div key={d.key} style={{ background: T.cardAlt, borderRadius: 8, padding: 12, marginBottom: 8, border: `1px solid ${T.borderLight}` }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: T.text, fontFamily: font }}>{d.name}</span>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  {d.handled && (
                    <span style={{ fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 10, background: `${T.green}15`, color: T.green }}>対応済み</span>
                  )}
                  <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 10px", borderRadius: 10, background: `${riskCol[d.risk]}12`, color: riskCol[d.risk] }}>
                    リスク: {riskLabel[d.risk]}
                  </span>
                </div>
              </div>
              <div style={{ fontSize: 11.5, color: T.textDim, lineHeight: 1.7, fontFamily: font, marginBottom: 6 }}>{d.detail}</div>

              {d.risk !== "low" && !d.handled && (
                <div style={{ background: `${T.orange}08`, border: `1px solid ${T.orange}22`, borderRadius: 6, padding: 10, marginBottom: 6 }}>
                  <div style={{ fontSize: 12, color: T.orange, fontWeight: 600, marginBottom: 2, fontFamily: font }}>
                    🧴 農薬散布の検討をおすすめします
                  </div>
                  <div style={{ fontSize: 11, color: T.textDim, lineHeight: 1.6, fontFamily: font }}>
                    {d.risk === "high" ? "リスクが高い状態です。早めの防除が収量低下を防ぎます。" : "注意レベルです。今後の天候次第で防除を検討してください。"}
                  </div>
                </div>
              )}

              {!d.handled && (
                <button onClick={() => { setSprayOpen(isOpen ? null : d.key); setSelectedPesticide(null); }}
                  style={{
                    width: "100%", padding: 9, background: isOpen ? T.cardAlt : T.accent, color: isOpen ? T.accent : "#fff",
                    border: isOpen ? `1px solid ${T.accent}` : "none", borderRadius: 8, fontSize: 12.5, fontWeight: 600,
                    cursor: "pointer", fontFamily: font, marginTop: 4,
                  }}>
                  {isOpen ? "閉じる" : "散布を記録する"}
                </button>
              )}

              {isOpen && (
                <div style={{ marginTop: 10, padding: 12, background: T.bg, borderRadius: 8, border: `1px solid ${T.border}` }}>
                  <div style={{ fontSize: 11, color: T.textDim, marginBottom: 8, fontFamily: font }}>使用農薬を選択</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 10 }}>
                    {d.pesticides.map((p, i) => (
                      <div key={i} onClick={() => setSelectedPesticide(p)}
                        style={{
                          padding: "8px 10px", borderRadius: 6, cursor: "pointer", fontSize: 12, fontFamily: font,
                          background: selectedPesticide?.name === p.name ? `${T.accent}12` : T.card,
                          border: `1px solid ${selectedPesticide?.name === p.name ? T.accent : T.border}`,
                          color: T.text, display: "flex", justifyContent: "space-between", alignItems: "center",
                        }}>
                        <span>{p.name}</span>
                        <span style={{ fontSize: 10, color: T.textMuted }}>{p.timing}</span>
                      </div>
                    ))}
                  </div>
                  <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 10, color: T.textDim, marginBottom: 3 }}>使用量</div>
                      <input placeholder="例: 3kg/10a" value={sprayAmount} onChange={e => setSprayAmount(e.target.value)} style={inputSm} />
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 10, color: T.textDim, marginBottom: 3 }}>散布面積</div>
                      <input placeholder="例: 30a" value={sprayArea} onChange={e => setSprayArea(e.target.value)} style={inputSm} />
                    </div>
                  </div>
                  <button onClick={() => handleSprayRecord(d.key)}
                    style={{
                      width: "100%", padding: 10, background: selectedPesticide ? T.green : T.textMuted,
                      color: "#fff", border: "none", borderRadius: 8, fontSize: 13, fontWeight: 600,
                      cursor: selectedPesticide ? "pointer" : "default", fontFamily: font,
                    }}>
                    記録してGAPに反映する ✓
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* ─── Panicle Length Model (bottom) ─── */}
      <div style={{ background: T.card, borderRadius: 12, border: `1px solid ${T.border}`, padding: 16, marginBottom: 10, boxShadow: T.shadow }}>
        <div style={{ fontSize: 13.5, fontWeight: 600, color: T.text, marginBottom: 10, fontFamily: font }}>📏 穂長予測モデル</div>

        <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
          <Metric label="モデル予測" value={modelPanicle.toFixed(1)} unit="cm" status="neutral" small />
          {corrections.panicleLength !== null && (
            <>
              <Metric label="実測平均" value={corrections.panicleLength} unit="cm" status="good" small />
              <Metric label="乖離" value={`${deviation > 0 ? "+" : ""}${deviation}`} unit="cm" status={Math.abs(deviation) > 2 ? "warn" : "good"} small />
            </>
          )}
        </div>

        <div style={{ fontSize: 11.5, color: T.textDim, lineHeight: 1.7, fontFamily: font, marginBottom: 12 }}>
          ロジスティックモデル y = a/(1+e^(-b(x-c))) による予測値と実測値にズレがあれば、下に3本の穂長を入力してください。平均値でモデルを補正します。
        </div>

        {/* Inline n=3 input */}
        <div style={{ background: T.cardAlt, borderRadius: 8, padding: 12, border: `1px solid ${T.borderLight}` }}>
          <div style={{ fontSize: 11, color: T.textDim, marginBottom: 8, fontFamily: font }}>穂長 n=3 (cm)</div>
          <div style={{ display: "flex", gap: 6, marginBottom: 6 }}>
            {[
              { val: p1, set: setP1 },
              { val: p2, set: setP2 },
              { val: p3, set: setP3 },
            ].map((f, i) => (
              <div key={i} style={{ flex: 1 }}>
                <div style={{ fontSize: 9, color: T.textMuted, marginBottom: 2, textAlign: "center" }}>#{i + 1}</div>
                <input type="number" step="0.1" placeholder="—" value={f.val} onChange={e => f.set(e.target.value)}
                  style={inputSm} />
              </div>
            ))}
            <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "flex-end" }}>
              <div style={{ fontSize: 9, color: T.textMuted, marginBottom: 2, textAlign: "center" }}>平均</div>
              <div style={{
                ...inputSm, background: pAvg !== null ? `${T.accent}08` : T.inputBg,
                border: `1px solid ${pAvg !== null ? T.accent + "44" : T.border}`,
                textAlign: "center", color: pAvg !== null ? T.accent : T.textMuted, fontWeight: 600,
              }}>
                {pAvg !== null ? pAvg.toFixed(1) : "—"}
              </div>
            </div>
          </div>
          <button onClick={handlePanicleSave}
            style={{
              width: "100%", padding: 9, marginTop: 4,
              background: pAvg !== null ? T.accent : `${T.textMuted}44`,
              color: pAvg !== null ? "#fff" : T.textMuted,
              border: "none", borderRadius: 8, fontSize: 12.5, fontWeight: 600,
              cursor: pAvg !== null ? "pointer" : "default", fontFamily: font,
            }}>
            モデルに反映する
          </button>
        </div>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════
   PAGE 2: DATA INPUT
   ══════════════════════════════════════════════ */
function DataInputPage({ corrections, setCorrections }) {
  const [form, setForm] = useState({
    tiller1: "", tiller2: "", tiller3: "",
    height1: "", height2: "", height3: "",
    leafColor: "", notes: "",
  });
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    const nc = { ...corrections };
    const tillers = [form.tiller1, form.tiller2, form.tiller3].filter(v => v !== "").map(Number);
    if (tillers.length > 0) nc.tillerCount = +(tillers.reduce((a, b) => a + b, 0) / tillers.length).toFixed(1);
    const heights = [form.height1, form.height2, form.height3].filter(v => v !== "").map(Number);
    if (heights.length > 0) nc.plantHeight = +(heights.reduce((a, b) => a + b, 0) / heights.length).toFixed(1);
    if (form.leafColor) nc.leafColor = form.leafColor;
    if (form.notes) nc.notes = form.notes;
    nc.date = new Date().toISOString().slice(0, 10);
    setCorrections(nc);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  const inputSt = {
    background: T.inputBg, border: `1px solid ${T.border}`, borderRadius: 6,
    padding: "10px 12px", color: T.text, fontSize: 14, fontFamily: mono,
    width: "100%", boxSizing: "border-box", outline: "none",
  };

  const InputRow = ({ label, fields, unit }) => (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 12, color: T.textDim, marginBottom: 6, fontFamily: font }}>{label} <span style={{ color: T.textMuted }}>({unit})</span></div>
      <div style={{ display: "flex", gap: 6 }}>
        {fields.map((f, i) => (
          <div key={i} style={{ flex: 1 }}>
            <div style={{ fontSize: 9, color: T.textMuted, marginBottom: 2, textAlign: "center" }}>#{i + 1}</div>
            <input type="number" step="0.1" placeholder="—" value={form[f]} onChange={e => setForm({ ...form, [f]: e.target.value })} style={inputSt} />
          </div>
        ))}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "flex-end" }}>
          <div style={{ fontSize: 9, color: T.textMuted, marginBottom: 2, textAlign: "center" }}>平均</div>
          <div style={{ ...inputSt, background: `${T.accent}06`, border: `1px solid ${T.accent}22`, textAlign: "center", color: T.accent, fontWeight: 600 }}>
            {(() => { const v = fields.map(f => form[f]).filter(v => v !== "").map(Number); return v.length > 0 ? (v.reduce((a, b) => a + b, 0) / v.length).toFixed(1) : "—"; })()}
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div>
      <div style={{ fontSize: 12.5, color: T.textDim, marginBottom: 14, lineHeight: 1.7, fontFamily: font }}>
        圃場の実測データを入力してモデル予測を補正します。穂長はダッシュボード下部から直接入力できます。
      </div>

      <div style={{ background: T.card, borderRadius: 12, border: `1px solid ${T.border}`, padding: 16, marginBottom: 10, boxShadow: T.shadow }}>
        <div style={{ fontSize: 13.5, fontWeight: 600, color: T.text, marginBottom: 12, fontFamily: font }}>🌾 生育計測値</div>
        <InputRow label="茎数（分げつ数）" fields={["tiller1", "tiller2", "tiller3"]} unit="本/株" />
        <InputRow label="草丈" fields={["height1", "height2", "height3"]} unit="cm" />
      </div>

      <div style={{ background: T.card, borderRadius: 12, border: `1px solid ${T.border}`, padding: 16, marginBottom: 10, boxShadow: T.shadow }}>
        <div style={{ fontSize: 13.5, fontWeight: 600, color: T.text, marginBottom: 12, fontFamily: font }}>🍃 定性観察</div>
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, color: T.textDim, marginBottom: 6, fontFamily: font }}>葉色（カラースケール値）</div>
          <div style={{ display: "flex", gap: 5 }}>
            {[3, 3.5, 4, 4.5, 5, 5.5, 6].map(v => (
              <div key={v} onClick={() => setForm({ ...form, leafColor: String(v) })}
                style={{
                  flex: 1, height: 34, borderRadius: 6,
                  background: `hsl(${100 + (v - 3) * 15}, ${50 + (v - 3) * 5}%, ${45 - (v - 3) * 4}%)`,
                  cursor: "pointer", border: form.leafColor === String(v) ? `2.5px solid ${T.text}` : `1px solid ${T.border}`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 10, color: "#fff", fontWeight: form.leafColor === String(v) ? 700 : 400,
                }}>{v}</div>
            ))}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 12, color: T.textDim, marginBottom: 6, fontFamily: font }}>メモ</div>
          <textarea placeholder="観察所見を自由記述..." value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })}
            rows={3} style={{ ...inputSt, resize: "vertical", fontFamily: font }} />
        </div>
      </div>

      {corrections.date && (
        <div style={{ background: `${T.green}08`, borderRadius: 10, border: `1px solid ${T.green}22`, padding: 12, marginBottom: 10 }}>
          <div style={{ fontSize: 11, color: T.green, fontWeight: 600, marginBottom: 4, fontFamily: font }}>前回入力 ({corrections.date})</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {corrections.panicleLength !== null && <Metric label="穂長" value={corrections.panicleLength} unit="cm" status="good" small />}
            {corrections.tillerCount !== null && <Metric label="茎数" value={corrections.tillerCount} unit="本" status="good" small />}
            {corrections.plantHeight !== null && <Metric label="草丈" value={corrections.plantHeight} unit="cm" status="good" small />}
          </div>
        </div>
      )}

      <button onClick={handleSave}
        style={{
          width: "100%", padding: 13, background: saved ? T.green : T.accent, color: "#fff",
          border: "none", borderRadius: 10, fontSize: 14, fontWeight: 700, cursor: "pointer", fontFamily: font,
          transition: "background .3s",
        }}>
        {saved ? "✓ 保存しました" : "実測データを保存"}
      </button>
    </div>
  );
}

/* ══════════════════════════════════════════════
   PAGE 3: ANALYTICS
   ══════════════════════════════════════════════ */
function AnalyticsPage() {
  const [period, setPeriod] = useState("7d");
  const [metric, setMetric] = useState("airTemp");

  const days = { "3d": 3, "7d": 7, "30d": 30 };
  const filtered = SENSOR.slice(-days[period]);

  const mList = [
    { key: "airTemp", label: "気温", unit: "℃", color: "#dc2626", domain: [10, 40] },
    { key: "waterTemp", label: "水温", unit: "℃", color: "#2563eb", domain: [10, 35] },
    { key: "soilTemp", label: "地温", unit: "℃", color: "#d97706", domain: [10, 35] },
    { key: "ph", label: "pH", unit: "", color: "#7c3aed", domain: [4.5, 7.5] },
    { key: "waterLevel", label: "水位", unit: "cm", color: "#16a34a", domain: [0, 15] },
    { key: "humidity", label: "湿度", unit: "%", color: "#64748b", domain: [40, 100] },
  ];
  const cur = mList.find(m => m.key === metric);

  const stats = useMemo(() => {
    const v = filtered.map(d => d[metric]);
    return { avg: (v.reduce((a, b) => a + b, 0) / v.length).toFixed(1), max: Math.max(...v).toFixed(1), min: Math.min(...v).toFixed(1) };
  }, [filtered, metric]);

  return (
    <div>
      {/* Period banners */}
      <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
        {[{ k: "3d", l: "3日間" }, { k: "7d", l: "1週間" }, { k: "30d", l: "1ヶ月" }].map(p => (
          <div key={p.k} onClick={() => setPeriod(p.k)}
            style={{
              flex: 1, padding: "10px 0", textAlign: "center", borderRadius: 8,
              fontSize: 13, fontWeight: period === p.k ? 700 : 500, cursor: "pointer", fontFamily: font,
              background: period === p.k ? T.accent : T.card, color: period === p.k ? "#fff" : T.textDim,
              border: `1px solid ${period === p.k ? T.accent : T.border}`, transition: "all .2s", boxShadow: T.shadow,
            }}>{p.l}</div>
        ))}
      </div>

      {/* Metric selector */}
      <div style={{ display: "flex", gap: 5, marginBottom: 14, flexWrap: "wrap" }}>
        {mList.map(m => (
          <div key={m.key} onClick={() => setMetric(m.key)}
            style={{
              padding: "6px 12px", borderRadius: 18, fontSize: 12, fontWeight: metric === m.key ? 700 : 500,
              cursor: "pointer", fontFamily: font,
              background: metric === m.key ? `${m.color}12` : T.card,
              color: metric === m.key ? m.color : T.textDim,
              border: `1px solid ${metric === m.key ? m.color + "44" : T.border}`, transition: "all .2s",
            }}>{m.label}</div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
        <Metric label="平均" value={stats.avg} unit={cur.unit} status="neutral" small />
        <Metric label="最高" value={stats.max} unit={cur.unit} status="warn" small />
        <Metric label="最低" value={stats.min} unit={cur.unit} status="good" small />
      </div>

      <div style={{ background: T.card, borderRadius: 12, border: `1px solid ${T.border}`, padding: "14px 6px 6px 0", boxShadow: T.shadow }}>
        <div style={{ paddingLeft: 14, marginBottom: 6 }}>
          <span style={{ fontSize: 13.5, fontWeight: 600, color: cur.color, fontFamily: font }}>{cur.label}</span>
          <span style={{ fontSize: 11, color: T.textDim, marginLeft: 6 }}>{cur.unit && `(${cur.unit})`}</span>
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={filtered} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <defs>
              <linearGradient id={`g-${metric}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={cur.color} stopOpacity={0.2} />
                <stop offset="95%" stopColor={cur.color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={T.borderLight} />
            <XAxis dataKey="label" tick={{ fill: T.textMuted, fontSize: 10 }} axisLine={{ stroke: T.border }} tickLine={false} />
            <YAxis domain={cur.domain} tick={{ fill: T.textMuted, fontSize: 10 }} axisLine={false} tickLine={false} width={32} />
            <Tooltip contentStyle={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 8, fontSize: 12, color: T.text }} />
            {metric === "ph" && <ReferenceLine y={5.5} stroke={T.orange} strokeDasharray="4 4" />}
            {metric === "ph" && <ReferenceLine y={6.5} stroke={T.orange} strokeDasharray="4 4" />}
            <Area type="monotone" dataKey={metric} stroke={cur.color} fill={`url(#g-${metric})`} strokeWidth={2} dot={false} activeDot={{ r: 4, fill: cur.color }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <Expandable title="複合グラフ（気温・水温・地温）" icon="📊">
        <div style={{ marginTop: 6 }}>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={filtered} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={T.borderLight} />
              <XAxis dataKey="label" tick={{ fill: T.textMuted, fontSize: 10 }} axisLine={{ stroke: T.border }} tickLine={false} />
              <YAxis domain={[10, 40]} tick={{ fill: T.textMuted, fontSize: 10 }} axisLine={false} tickLine={false} width={32} />
              <Tooltip contentStyle={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 8, fontSize: 12 }} />
              <Line type="monotone" dataKey="airTemp" stroke="#dc2626" strokeWidth={1.5} dot={false} name="気温" />
              <Line type="monotone" dataKey="waterTemp" stroke="#2563eb" strokeWidth={1.5} dot={false} name="水温" />
              <Line type="monotone" dataKey="soilTemp" stroke="#d97706" strokeWidth={1.5} dot={false} name="地温" />
            </LineChart>
          </ResponsiveContainer>
          <div style={{ display: "flex", justifyContent: "center", gap: 14, marginTop: 6 }}>
            {[{ l: "気温", c: "#dc2626" }, { l: "水温", c: "#2563eb" }, { l: "地温", c: "#d97706" }].map(x => (
              <div key={x.l} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: T.textSub }}>
                <div style={{ width: 8, height: 8, borderRadius: 2, background: x.c }} />{x.l}
              </div>
            ))}
          </div>
        </div>
      </Expandable>
    </div>
  );
}

/* ══════════════════════════════════════════════
   PAGE 4: GAP
   ══════════════════════════════════════════════ */
function GAPPage({ sprayLogs, corrections }) {
  const totalArea = sprayLogs.reduce((a, l) => {
    const n = parseFloat(l.area);
    return a + (isNaN(n) ? 0 : n);
  }, 0);

  return (
    <div>
      <div style={{ fontSize: 12.5, color: T.textDim, marginBottom: 14, lineHeight: 1.7, fontFamily: font }}>
        ダッシュボードで記録した農薬散布データが自動的にGAP認証項目として蓄積されます。
      </div>

      {/* Summary */}
      <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
        <Metric label="散布回数" value={sprayLogs.length} unit="回" status="neutral" />
        <Metric label="記録開始" value={sprayLogs.length > 0 ? sprayLogs[sprayLogs.length - 1].date.slice(5) : "—"} unit="" status="neutral" />
      </div>

      {/* Records */}
      <div style={{ background: T.card, borderRadius: 12, border: `1px solid ${T.border}`, padding: 16, marginBottom: 10, boxShadow: T.shadow }}>
        <div style={{ fontSize: 13.5, fontWeight: 600, color: T.text, marginBottom: 12, fontFamily: font }}>📋 防除記録一覧</div>

        {sprayLogs.length === 0 ? (
          <div style={{ textAlign: "center", padding: 30, color: T.textMuted, fontSize: 13, fontFamily: font }}>
            まだ防除記録がありません。<br />ダッシュボードの病害リスク欄から農薬散布を記録してください。
          </div>
        ) : (
          sprayLogs.map((log, i) => (
            <div key={log.id} style={{
              padding: 12, marginBottom: 6, background: T.cardAlt, borderRadius: 8,
              border: `1px solid ${T.borderLight}`,
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: T.text, fontFamily: font }}>{log.pesticide}</span>
                <span style={{ fontSize: 10, color: T.textMuted, fontFamily: mono }}>{log.date}</span>
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {[
                  { l: "対象", v: log.disease === "blast" ? "いもち病" : "紋枯病" },
                  { l: "分類", v: log.category },
                  { l: "使用量", v: log.amount },
                  { l: "面積", v: log.area },
                  { l: "区分", v: log.timing },
                ].map((t, j) => (
                  <div key={j} style={{ fontSize: 11, color: T.textDim, fontFamily: font }}>
                    <span style={{ color: T.textMuted }}>{t.l}: </span>{t.v}
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>

      {/* GAP checklist */}
      <div style={{ background: T.card, borderRadius: 12, border: `1px solid ${T.border}`, padding: 16, boxShadow: T.shadow }}>
        <div style={{ fontSize: 13.5, fontWeight: 600, color: T.text, marginBottom: 12, fontFamily: font }}>✅ GAP認証チェック項目</div>
        {[
          { item: "農薬使用の記録", done: sprayLogs.length > 0, detail: "使用日、農薬名、使用量、対象病害が記録されていること" },
          { item: "散布面積の記録", done: sprayLogs.some(l => l.area !== "—"), detail: "散布対象面積が記録されていること" },
          { item: "農薬カテゴリの記録", done: sprayLogs.length > 0, detail: "殺菌剤・殺虫剤等の分類が記録されていること" },
          { item: "生育観察データ", done: corrections.date !== null, detail: "草丈・茎数・穂長等の生育計測値が記録されていること" },
          { item: "葉色診断", done: corrections.leafColor !== null, detail: "カラースケールによる葉色値が記録されていること" },
        ].map((c, i) => (
          <div key={i} style={{
            display: "flex", alignItems: "flex-start", gap: 10, padding: "10px 0",
            borderBottom: i < 4 ? `1px solid ${T.borderLight}` : "none",
          }}>
            <div style={{
              width: 22, height: 22, borderRadius: 6, flexShrink: 0, marginTop: 1,
              background: c.done ? T.green : T.bg,
              border: `1.5px solid ${c.done ? T.green : T.border}`,
              display: "flex", alignItems: "center", justifyContent: "center",
              color: "#fff", fontSize: 12, fontWeight: 700,
            }}>
              {c.done && "✓"}
            </div>
            <div>
              <div style={{ fontSize: 12.5, fontWeight: 600, color: c.done ? T.text : T.textDim, fontFamily: font }}>{c.item}</div>
              <div style={{ fontSize: 11, color: T.textMuted, lineHeight: 1.5, fontFamily: font }}>{c.detail}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════
   UTILITY
   ═══════════════════════════════════════ */
function daysSince(dateStr) {
  return Math.floor((new Date() - new Date(dateStr)) / 864e5);
}

/* ══════════════════════════════════════════════
   MAIN APP
   ══════════════════════════════════════════════ */
export default function App() {
  const [page, setPage] = useState("dashboard");
  const [corrections, setCorrections] = useState({
    panicleLength: null, tillerCount: null, plantHeight: null,
    leafColor: null, notes: null, date: null,
  });
  const [sprayLogs, setSprayLogs] = useState([]);

  const pages = [
    { key: "dashboard", label: "ダッシュボード", icon: Icons.dashboard },
    { key: "input", label: "データ入力", icon: Icons.input },
    { key: "analytics", label: "データ解析", icon: Icons.analytics },
    { key: "gap", label: "GAP認証", icon: Icons.gap },
  ];
  const titles = { dashboard: "圃場モニタリング", input: "実測データ入力", analytics: "データ解析", gap: "GAP認証記録" };

  return (
    <div style={{ background: T.bg, minHeight: "100vh", maxWidth: 480, margin: "0 auto", fontFamily: font, display: "flex", flexDirection: "column" }}>
      <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Noto+Sans+JP:wght@400;500;600;700&display=swap" rel="stylesheet" />

      {/* Top bar */}
      <div style={{
        padding: "14px 16px 10px", borderBottom: `1px solid ${T.border}`,
        position: "sticky", top: 0, background: `${T.bg}ee`, zIndex: 10,
        backdropFilter: "blur(8px)", WebkitBackdropFilter: "blur(8px)",
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <div style={{ fontSize: 9.5, color: T.green, letterSpacing: 2, textTransform: "uppercase", fontWeight: 700 }}>AgriDX Monitor</div>
            <div style={{ fontSize: 17, fontWeight: 700, color: T.text }}>{titles[page]}</div>
          </div>
          <div style={{ fontSize: 11, color: T.textDim, textAlign: "right", fontFamily: font }}>
            <div>東広島市 西条</div>
            <div style={{ fontFamily: mono, fontSize: 10, color: T.textMuted }}>2026.08.15</div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, padding: 14, paddingBottom: 76, overflowY: "auto" }}>
        {page === "dashboard" && <DashboardPage corrections={corrections} setCorrections={setCorrections} sprayLogs={sprayLogs} setSprayLogs={setSprayLogs} setPage={setPage} />}
        {page === "input" && <DataInputPage corrections={corrections} setCorrections={setCorrections} />}
        {page === "analytics" && <AnalyticsPage />}
        {page === "gap" && <GAPPage sprayLogs={sprayLogs} corrections={corrections} />}
      </div>

      {/* Bottom nav */}
      <div style={{
        position: "fixed", bottom: 0, left: "50%", transform: "translateX(-50%)",
        width: "100%", maxWidth: 480, background: T.navBg,
        borderTop: `1px solid ${T.border}`, display: "flex", zIndex: 20,
        boxShadow: "0 -2px 10px rgba(0,0,0,0.04)",
      }}>
        {pages.map(p => {
          const active = page === p.key;
          const hasNotif = p.key === "gap" && sprayLogs.length > 0;
          return (
            <div key={p.key} onClick={() => setPage(p.key)}
              style={{
                flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 2,
                padding: "9px 0 11px", cursor: "pointer",
                color: active ? T.accent : T.textMuted, transition: "color .2s", position: "relative",
              }}>
              {active && <div style={{ position: "absolute", top: 0, left: "20%", right: "20%", height: 2.5, background: T.accent, borderRadius: "0 0 2px 2px" }} />}
              <div style={{ position: "relative" }}>
                {p.icon}
                {hasNotif && !active && (
                  <div style={{
                    position: "absolute", top: -2, right: -6, width: 8, height: 8,
                    borderRadius: 4, background: T.red, border: `1.5px solid ${T.navBg}`,
                  }} />
                )}
              </div>
              <span style={{ fontSize: 9.5, fontWeight: active ? 700 : 500, fontFamily: font }}>{p.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
