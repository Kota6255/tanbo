"""
デモUI生成スクリプト
シミュレーションデータからインタラクティブHTMLデモを生成する。

出力: demo/index.html
実行: python demo/build_demo.py → ブラウザで demo/index.html を開く
"""

import json
import sys
import os
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simulation.simulate_season import (
    generate_daily_data, calc_season, determine_notifications, STAGES_KOSHI
)

OUTPUT = Path(__file__).parent / "index.html"


def main():
    transplant = date(2025, 6, 5)

    print("1. データ生成中...")
    raw = generate_daily_data(2025)
    results = calc_season(raw, transplant)
    notifications = determine_notifications(results, transplant)

    # 田植え以降のデータに絞る
    season = [r for r in results if r["date"] >= transplant - timedelta(days=3)]

    # JSON化
    chart_data = []
    for r in season:
        chart_data.append({
            "date": r["date"].isoformat(),
            "avg_temp": r["avg_temp"],
            "max_temp": r["max_temp"],
            "min_temp": r["min_temp"],
            "water_temp": r.get("water_temp"),
            "humidity": r.get("humidity"),
            "acc_temp": r["acc_temp"],
            "stage": r.get("stage_label", ""),
            "days": r.get("days", 0),
        })

    notif_data = []
    for n in notifications:
        notif_data.append({
            "date": n["date"].isoformat(),
            "type": n["type"],
            "level": n["level"],
            "title": n["title"],
            "detail": n["detail"],
            "acc_temp": n["acc_temp"],
        })

    stages_data = []
    for key, low, high, label, color in STAGES_KOSHI:
        stages_data.append({
            "key": key, "low": low, "high": high,
            "label": label, "color": color,
        })

    heading_date = None
    for r in results:
        if r["stage"] == "heading" and heading_date is None:
            heading_date = r["date"].isoformat()

    print("2. HTML生成中...")
    html = build_html(
        json.dumps(chart_data, ensure_ascii=False),
        json.dumps(notif_data, ensure_ascii=False),
        json.dumps(stages_data, ensure_ascii=False),
        transplant.isoformat(),
        heading_date or "",
    )

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"デモ生成完了: {OUTPUT}")
    print(f"ブラウザで開いてください: file:///{OUTPUT.as_posix()}")


def build_html(chart_json, notif_json, stages_json, transplant_date, heading_date):
    return f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>たんぼアドバイザー デモ</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  font-family: "Hiragino Kaku Gothic ProN","Meiryo","Yu Gothic",sans-serif;
  background: #f5f3ee;
  color: #333;
}}
.header {{
  background: linear-gradient(135deg, #2d7a3a 0%, #4a9a5a 100%);
  color: white;
  padding: 20px 24px;
  text-align: center;
}}
.header h1 {{ font-size: 22px; letter-spacing: 2px; }}
.header p {{ font-size: 13px; margin-top: 6px; opacity: 0.9; }}
.container {{ max-width: 1100px; margin: 0 auto; padding: 16px; }}
.info-bar {{
  display: flex; gap: 12px; flex-wrap: wrap;
  margin: 16px 0;
}}
.info-card {{
  background: white; border-radius: 10px; padding: 14px 18px;
  flex: 1; min-width: 180px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}}
.info-card .label {{ font-size: 11px; color: #888; }}
.info-card .value {{ font-size: 22px; font-weight: bold; margin-top: 4px; }}
.info-card .sub {{ font-size: 12px; color: #666; margin-top: 2px; }}
.chart-panel {{
  background: white; border-radius: 12px; padding: 20px;
  margin: 16px 0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}}
.chart-panel h2 {{
  font-size: 15px; color: #2d7a3a;
  border-left: 4px solid #2d7a3a;
  padding-left: 10px; margin-bottom: 14px;
}}
.chart-container {{ position: relative; height: 280px; }}
.timeline {{
  margin: 16px 0;
}}
.timeline h2 {{
  font-size: 15px; color: #2d7a3a;
  border-left: 4px solid #2d7a3a;
  padding-left: 10px; margin-bottom: 14px;
  background: white; border-radius: 12px 12px 0 0;
  padding: 16px 18px 10px 18px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}}
.notif-card {{
  background: white; border-radius: 10px; padding: 14px 18px;
  margin: 8px 0;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  border-left: 5px solid #ccc;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}}
.notif-card:hover {{
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.12);
}}
.notif-card.info    {{ border-left-color: #4488cc; }}
.notif-card.warning {{ border-left-color: #cc4444; }}
.notif-card.action  {{ border-left-color: #cc8800; }}
.notif-head {{
  display: flex; justify-content: space-between; align-items: center;
}}
.notif-date {{ font-size: 12px; color: #888; }}
.notif-badge {{
  font-size: 10px; padding: 2px 8px; border-radius: 10px;
  color: white; font-weight: bold;
}}
.notif-badge.info    {{ background: #4488cc; }}
.notif-badge.warning {{ background: #cc4444; }}
.notif-badge.action  {{ background: #cc8800; }}
.notif-title {{
  font-size: 15px; font-weight: bold; margin: 6px 0 4px;
}}
.notif-detail {{
  font-size: 13px; color: #555; line-height: 1.6;
}}
.notif-acc {{
  font-size: 11px; color: #999; margin-top: 4px;
}}
.line-preview {{
  background: #f8f8f0; border-radius: 12px; padding: 20px;
  margin: 16px 0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  max-width: 380px;
}}
.line-preview h2 {{
  font-size: 14px; color: #2d7a3a; margin-bottom: 12px;
}}
.line-bubble {{
  background: white; border-radius: 16px; padding: 16px;
  font-size: 14px; line-height: 1.8;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  white-space: pre-wrap;
  border: 1px solid #e8e8e0;
}}
.stage-bar {{
  display: flex; height: 30px; border-radius: 6px;
  overflow: hidden; margin: 16px 0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}}
.stage-seg {{
  display: flex; align-items: center; justify-content: center;
  font-size: 10px; color: #333; font-weight: bold;
  transition: flex 0.3s;
  white-space: nowrap; overflow: hidden;
}}
.stage-seg.active {{
  outline: 3px solid #333;
  outline-offset: -3px;
  z-index: 1;
}}
.footer {{
  text-align: center; padding: 24px; font-size: 12px; color: #999;
}}
</style>
</head>
<body>

<div class="header">
  <h1>たんぼアドバイザー</h1>
  <p>水稲農家向け 圃場モニタリング + 行動提案システム デモ</p>
</div>

<div class="container">

  <!-- 概要カード -->
  <div class="info-bar" id="infoBar"></div>

  <!-- 生育ステージバー -->
  <div class="chart-panel">
    <h2>生育ステージ進行</h2>
    <div class="stage-bar" id="stageBar"></div>
    <div id="stageDetail" style="font-size:13px;color:#666;margin-top:8px;"></div>
  </div>

  <!-- 気温チャート -->
  <div class="chart-panel">
    <h2>日別気温推移（東広島市 2025年）</h2>
    <div class="chart-container"><canvas id="tempChart"></canvas></div>
  </div>

  <!-- 積算温度チャート -->
  <div class="chart-panel">
    <h2>有効積算温度と通知ポイント</h2>
    <div class="chart-container"><canvas id="accChart"></canvas></div>
  </div>

  <!-- 通知タイムライン -->
  <div class="timeline">
    <h2>通知タイムライン（全 <span id="notifCount"></span> 件）</h2>
    <div id="notifList"></div>
  </div>

  <!-- LINE プレビュー -->
  <div style="display:flex;gap:16px;flex-wrap:wrap;">
    <div class="line-preview" style="flex:1;">
      <h2>LINE 通知プレビュー（クリックで切替）</h2>
      <div class="line-bubble" id="lineBubble">通知をクリックしてください</div>
    </div>
  </div>

</div>

<div class="footer">
  たんぼアドバイザー v1.0 シミュレーションデモ | 東広島市 2025年 コシヒカリ
</div>

<script>
const DATA = {chart_json};
const NOTIFS = {notif_json};
const STAGES = {stages_json};
const TRANSPLANT = "{transplant_date}";
const HEADING = "{heading_date}";

// 最新データ
const latest = DATA[DATA.length - 1];
const latestNotif = NOTIFS[NOTIFS.length - 1];

// 概要カード
document.getElementById("infoBar").innerHTML = `
  <div class="info-card">
    <div class="label">圃場</div>
    <div class="value">家の前の田</div>
    <div class="sub">コシヒカリ｜3,000m²</div>
  </div>
  <div class="info-card">
    <div class="label">田植えからの日数</div>
    <div class="value">${{latest.days}}日目</div>
    <div class="sub">田植え ${{TRANSPLANT}}</div>
  </div>
  <div class="info-card">
    <div class="label">有効積算温度</div>
    <div class="value">${{latest.acc_temp.toFixed(0)}} ℃日</div>
    <div class="sub">${{latest.stage}}</div>
  </div>
  <div class="info-card">
    <div class="label">今日の気温</div>
    <div class="value">${{latest.avg_temp}}℃</div>
    <div class="sub">最高${{latest.max_temp}}℃ / 最低${{latest.min_temp}}℃</div>
  </div>
`;

// 生育ステージバー
const maxAcc = Math.max(...DATA.map(d=>d.acc_temp));
const stageBar = document.getElementById("stageBar");
STAGES.forEach(s => {{
  const seg = document.createElement("div");
  seg.className = "stage-seg" + (latest.stage === s.label ? " active" : "");
  const width = (s.high - s.low) / Math.max(maxAcc, s.high) * 100;
  seg.style.flex = width;
  seg.style.background = s.color;
  seg.textContent = s.label;
  stageBar.appendChild(seg);
}});
document.getElementById("stageDetail").textContent =
  `現在: ${{latest.stage}}（${{latest.acc_temp.toFixed(0)}}℃日 / 田植え${{latest.days}}日目）`;

// 気温チャート
const tempCtx = document.getElementById("tempChart").getContext("2d");
new Chart(tempCtx, {{
  type: "line",
  data: {{
    labels: DATA.map(d=>d.date),
    datasets: [
      {{
        label: "日平均気温",
        data: DATA.map(d=>d.avg_temp),
        borderColor: "#333",
        borderWidth: 2,
        pointRadius: 0,
        fill: false,
      }},
      {{
        label: "最高気温",
        data: DATA.map(d=>d.max_temp),
        borderColor: "rgba(220,80,80,0.4)",
        borderWidth: 1,
        borderDash: [3,3],
        pointRadius: 0,
        fill: false,
      }},
      {{
        label: "最低気温",
        data: DATA.map(d=>d.min_temp),
        borderColor: "rgba(80,80,220,0.4)",
        borderWidth: 1,
        borderDash: [3,3],
        pointRadius: 0,
        fill: "-1",
        backgroundColor: "rgba(220,80,80,0.06)",
      }},
    ]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    scales: {{
      x: {{
        type: "time",
        time: {{ unit: "week", displayFormats: {{ week: "MM/dd" }} }},
      }},
      y: {{ title: {{ display: true, text: "℃" }} }}
    }},
    plugins: {{
      annotation: {{}},
    }}
  }}
}});

// 積算温度チャート
const accCtx = document.getElementById("accChart").getContext("2d");
const accChart = new Chart(accCtx, {{
  type: "line",
  data: {{
    labels: DATA.map(d=>d.date),
    datasets: [
      {{
        label: "有効積算温度",
        data: DATA.map(d=>d.acc_temp),
        borderColor: "#2d7a3a",
        borderWidth: 2.5,
        pointRadius: 0,
        fill: true,
        backgroundColor: "rgba(45,122,58,0.08)",
      }},
      // 通知ポイント
      {{
        label: "通知発火",
        data: NOTIFS.map(n => ({{ x: n.date, y: n.acc_temp }})),
        type: "scatter",
        pointRadius: 8,
        pointBackgroundColor: NOTIFS.map(n =>
          n.level === "warning" ? "#cc4444" :
          n.level === "action" ? "#cc8800" : "#4488cc"
        ),
        pointBorderColor: "white",
        pointBorderWidth: 2,
      }},
    ]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    scales: {{
      x: {{
        type: "time",
        time: {{ unit: "week", displayFormats: {{ week: "MM/dd" }} }},
      }},
      y: {{ title: {{ display: true, text: "℃日" }}, min: 0 }}
    }},
  }}
}});

// 通知タイムライン
document.getElementById("notifCount").textContent = NOTIFS.length;
const notifList = document.getElementById("notifList");
const levelLabels = {{ info: "情報", warning: "警告", action: "行動" }};
const levelIcons = {{ info: "\\ud83d\\udcd8", warning: "\\u26a0\\ufe0f", action: "\\ud83d\\udce2" }};

NOTIFS.forEach((n, idx) => {{
  const card = document.createElement("div");
  card.className = `notif-card ${{n.level}}`;
  card.innerHTML = `
    <div class="notif-head">
      <span class="notif-date">${{n.date}}</span>
      <span class="notif-badge ${{n.level}}">${{levelLabels[n.level]}}</span>
    </div>
    <div class="notif-title">${{levelIcons[n.level]}} ${{n.title}}</div>
    <div class="notif-detail">${{n.detail}}</div>
    <div class="notif-acc">積算温度: ${{n.acc_temp.toFixed(0)}}℃日</div>
  `;
  card.addEventListener("click", () => showLinePreview(n));
  notifList.appendChild(card);
}});

// LINE プレビュー
function showLinePreview(n) {{
  const lines = [];
  if (n.level === "warning") {{
    lines.push("\\u26a0\\ufe0f " + n.title);
  }} else if (n.level === "action") {{
    lines.push("\\ud83d\\udce2 " + n.title);
  }} else {{
    lines.push("\\ud83d\\udcd8 " + n.title);
  }}
  lines.push("");
  lines.push("\\ud83c\\udf3e 家の前の田（コシヒカリ）");
  lines.push("");
  lines.push(n.detail);
  lines.push("");
  lines.push("━━━━━━━━━━");
  lines.push(`積算温度: ${{n.acc_temp.toFixed(0)}}℃日`);
  lines.push(`${{n.date}}`);

  document.getElementById("lineBubble").textContent = lines.join("\\n");
}}

// 最初の通知をプレビュー
if (NOTIFS.length > 0) showLinePreview(NOTIFS[0]);
</script>
</body>
</html>'''


if __name__ == "__main__":
    main()
