"""
たんぼアドバイザー 通知シミュレーション
========================================
東広島市の2025年気温データ（気候統計値ベース）を使い、
コシヒカリの田植え〜収穫までの全通知タイミングを可視化する。

出力:
  simulation/season_simulation.png  - 3パネルのシミュレーション図
  simulation/notification_log.txt   - 通知ログ一覧

実行: python simulation/simulate_season.py
"""

import math
import random
import sys
import os
from datetime import date, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

# 日本語フォント
try:
    import japanize_matplotlib
except ImportError:
    plt.rcParams["font.family"] = "MS Gothic"

random.seed(2025)

OUTPUT_DIR = Path(__file__).parent
PNG_PATH = OUTPUT_DIR / "season_simulation.png"
LOG_PATH = OUTPUT_DIR / "notification_log.txt"

# ============================================================
# 1. 東広島の気温データ生成（2025年 気候統計値ベース）
# ============================================================
# 東広島アメダス (標高227m) の月別平年値
CLIMATE_NORMALS = {
    #     avg   max   min  humidity
    4:  (12.5, 18.5,  7.0, 65),
    5:  (17.5, 23.5, 12.5, 68),
    6:  (21.5, 26.5, 17.5, 78),  # 梅雨
    7:  (25.8, 30.8, 22.0, 80),  # 梅雨明け〜盛夏
    8:  (26.8, 32.0, 23.0, 76),  # 盛夏
    9:  (22.5, 27.5, 18.5, 78),  # 秋雨
    10: (16.0, 22.0, 11.0, 72),
}


def generate_daily_data(year: int = 2025) -> list[dict]:
    """東広島の日別気象データを生成（4月〜10月）"""
    data = []
    start = date(year, 4, 1)
    end = date(year, 10, 15)

    d = start
    prev_avg = None
    while d <= end:
        m = d.month
        normals = CLIMATE_NORMALS.get(m, CLIMATE_NORMALS[6])
        avg_n, max_n, min_n, hum_n = normals

        # 月内の日変化（月初→月末で次月に近づく）
        day_frac = d.day / 30.0
        if m + 1 in CLIMATE_NORMALS:
            next_n = CLIMATE_NORMALS[m + 1]
            avg_base = avg_n + (next_n[0] - avg_n) * day_frac * 0.3
            max_base = max_n + (next_n[1] - max_n) * day_frac * 0.3
            min_base = min_n + (next_n[2] - min_n) * day_frac * 0.3
            hum_base = hum_n + (next_n[3] - hum_n) * day_frac * 0.3
        else:
            avg_base = avg_n
            max_base = max_n
            min_base = min_n
            hum_base = hum_n

        # 天気パターンによる変動
        doy = (d - date(year, 1, 1)).days

        # 田植え直後の寒の戻り (6/6〜6/9): 水温低下を再現
        if date(year, 6, 6) <= d <= date(year, 6, 9):
            avg_base -= random.uniform(4, 7)
            min_base -= random.uniform(5, 8)
            max_base -= random.uniform(2, 4)

        # 梅雨パターン (6/10〜7/15): 低温・高湿
        if date(year, 6, 10) <= d <= date(year, 7, 15):
            if random.random() < 0.55:  # 55%で雨
                avg_base -= random.uniform(1, 3)
                hum_base = min(100, hum_base + random.uniform(5, 15))

        # 盛夏の猛暑日 (7/20〜8/20): たまに35℃超
        if date(year, 7, 20) <= d <= date(year, 8, 20):
            if random.random() < 0.15:
                max_base += random.uniform(2, 5)
                min_base += random.uniform(1, 3)
                avg_base += random.uniform(1, 3)

        # 台風・秋雨 (8/25〜9/20): 急な低温
        if date(year, 8, 25) <= d <= date(year, 9, 20):
            if random.random() < 0.2:
                avg_base -= random.uniform(2, 5)
                hum_base = min(100, hum_base + 10)

        # 自己相関のあるノイズ（前日との連続性）
        noise = random.gauss(0, 1.5)
        if prev_avg is not None:
            # 前日からの変動を制限
            noise = noise * 0.6 + (prev_avg - avg_base) * 0.3

        avg_temp = round(avg_base + noise, 1)
        max_temp = round(avg_temp + (max_base - avg_base) + random.gauss(0, 1.0), 1)
        min_temp = round(avg_temp - (avg_base - min_base) + random.gauss(0, 0.8), 1)
        humidity = round(max(40, min(100, hum_base + random.gauss(0, 5))), 1)

        # 水温 = 最低気温寄り（夜間冷却の影響大）
        water_temp = round(min_temp + (avg_temp - min_temp) * 0.3 + random.gauss(0, 0.5), 1)

        data.append({
            "date": d,
            "avg_temp": avg_temp,
            "max_temp": max_temp,
            "min_temp": min_temp,
            "humidity": humidity,
            "water_temp": water_temp,
        })
        prev_avg = avg_temp
        d += timedelta(days=1)

    return data


# ============================================================
# 2. 積算温度 & ステージ計算
# ============================================================
BASE_TEMP = 10.0

STAGES_KOSHI = [
    ("tillering",        0,    350, "分げつ期",     "#a8d8a8"),
    ("max_tiller",     350,    500, "最高分げつ期", "#7bc87b"),
    ("midseason_drain",500,    650, "中干し適期",   "#d4a84e"),
    ("panicle_form",   650,    800, "幼穂形成期",   "#e8c96e"),
    ("booting",        800,    950, "穂ばらみ期",   "#f0d890"),
    ("heading",        950,   1100, "出穂期",       "#f5a0a0"),
    ("grain_filling", 1100,   1600, "登熟期",       "#f0c0a0"),
    ("maturity",      1600,   2200, "成熟期",       "#c8a878"),
]


def calc_season(data: list[dict], transplant: date) -> list[dict]:
    """日ごとの積算温度と生育ステージを計算"""
    results = []
    acc = 0.0
    for row in data:
        d = row["date"]
        if d < transplant:
            results.append({**row, "acc_temp": 0, "eff_temp": 0, "stage": None,
                            "stage_label": "田植え前", "days": 0})
            continue

        days = (d - transplant).days
        eff = max(row["avg_temp"] - BASE_TEMP, 0)
        acc += eff

        stage_key = "tillering"
        stage_label = "分げつ期"
        for key, low, high, label, _ in STAGES_KOSHI:
            if low <= acc < high:
                stage_key = key
                stage_label = label
                break
            if acc >= high and key == "maturity":
                stage_key = key
                stage_label = label

        results.append({
            **row,
            "acc_temp": round(acc, 1),
            "eff_temp": round(eff, 1),
            "stage": stage_key,
            "stage_label": stage_label,
            "days": days,
        })
    return results


# ============================================================
# 3. 通知判定アルゴリズム（修正版）
# ============================================================
def determine_notifications(results: list[dict], transplant: date) -> list[dict]:
    """全通知イベントを判定して返す"""
    notifications = []
    state = {
        "establishment_warned": False,
        "drain_pre_notified": False,
        "drain_start_notified": False,
        "drain_started_date": None,
        "drain_end_notified": False,
        "blast_panicle_notified": False,
        "heading_notified": False,
        "heat_moderate_notified": False,
        "heat_high_notified": False,
        "drain_final_notified": False,
    }

    heading_date = None
    # 出穂日を先に特定
    for r in results:
        if r["stage"] == "heading" and heading_date is None:
            heading_date = r["date"]
            break

    for i, r in enumerate(results):
        d = r["date"]
        days = r.get("days", 0)
        stage = r.get("stage")
        acc = r.get("acc_temp", 0)

        if stage is None:
            continue

        # ─────────────────────────────────────────
        # (A) 活着期の水温チェック（田植え後1〜10日）
        # ─────────────────────────────────────────
        if 1 <= days <= 10 and not state["establishment_warned"]:
            wt = r.get("water_temp", 20)
            if wt < 15.0:
                notifications.append({
                    "date": d, "type": "water_temp",
                    "level": "warning",
                    "title": "活着注意：水温低下",
                    "detail": f"水温{wt:.1f}℃。15℃以下は活着遅延のおそれ。"
                             f"深水管理(5-7cm)で保温してください。",
                    "acc_temp": acc,
                })
                state["establishment_warned"] = True

        # ─────────────────────────────────────────
        # (B) 中干し事前通知（中干し適期の5日前）
        # ─────────────────────────────────────────
        if stage in ("tillering", "max_tiller") and not state["drain_pre_notified"]:
            drain_start = 500  # コシヒカリ中干し開始温度
            remaining = drain_start - acc
            if remaining > 0:
                # 直近5日の日平均有効積算温度
                recent = [results[j]["eff_temp"] for j in range(max(0, i-4), i+1)]
                daily_eff = sum(recent) / len(recent) if recent else 10
                days_to = remaining / max(daily_eff, 0.1)
                if days_to <= 7 and days_to > 0:
                    notifications.append({
                        "date": d, "type": "drain_pre",
                        "level": "info",
                        "title": f"中干し予告：あと約{int(days_to)}日",
                        "detail": f"積算温度{acc:.0f}℃日。500℃日で中干し適期。"
                                 f"水を少しずつ減らす準備を。",
                        "acc_temp": acc,
                    })
                    state["drain_pre_notified"] = True

        # ─────────────────────────────────────────
        # (C) 中干し開始通知
        # ─────────────────────────────────────────
        if stage == "midseason_drain" and not state["drain_start_notified"]:
            deadline = heading_date - timedelta(days=30) if heading_date else None
            deadline_str = deadline.strftime("%m/%d") if deadline else "不明"
            notifications.append({
                "date": d, "type": "drain_start",
                "level": "action",
                "title": "中干し開始",
                "detail": f"積算温度{acc:.0f}℃日。中干しを始めてください。"
                         f"期間7-10日。{deadline_str}までに完了。",
                "acc_temp": acc,
            })
            state["drain_start_notified"] = True
            state["drain_started_date"] = d

        # ─────────────────────────────────────────
        # (D) 中干し終了通知（開始から7-10日後）
        # ─────────────────────────────────────────
        if state["drain_started_date"] and not state["drain_end_notified"]:
            drain_days = (d - state["drain_started_date"]).days
            heading_deadline = heading_date - timedelta(days=25) if heading_date else None

            should_end = False
            reason = ""
            # 最低7日は中干しを続ける。10日経過 or 出穂25日前で終了
            if drain_days >= 10:
                should_end = True
                reason = f"中干し開始から{drain_days}日経過。十分に干せました"
            elif drain_days >= 7 and heading_deadline and d >= heading_deadline:
                should_end = True
                reason = f"中干し{drain_days}日目。出穂前に間に合わせるため終了"

            if should_end:
                notifications.append({
                    "date": d, "type": "drain_end",
                    "level": "action",
                    "title": "中干し終了→間断かんがい",
                    "detail": f"{reason}。水を入れて間断かんがいに切り替えてください。",
                    "acc_temp": acc,
                })
                state["drain_end_notified"] = True

        # ─────────────────────────────────────────
        # (E) 幼穂形成期のいもち病リスク（ステージ感度UP版）
        # ─────────────────────────────────────────
        if stage in ("panicle_form", "booting", "heading") and not state["blast_panicle_notified"]:
            # 過去72時間の高湿度連続時間を計算
            wetness_hours = 0
            for j in range(max(0, i-2), i+1):  # 3日分
                h = results[j].get("humidity", 60)
                t = results[j].get("avg_temp", 25)
                if 20 <= t <= 28 and h >= 85:  # 幼穂期は85%に閾値低下（通常90%）
                    wetness_hours += 24  # 1日=24時間とみなし
                elif 20 <= t <= 28 and h >= 80:
                    wetness_hours += 12

            # 幼穂形成期〜出穂期はリスク閾値を緩和
            threshold = 24  # 通常は連続10時間→日単位では厳しいので24時間相当
            if wetness_hours >= threshold:
                notifications.append({
                    "date": d, "type": "blast_risk",
                    "level": "warning",
                    "title": f"いもち病注意（{r['stage_label']}）",
                    "detail": f"穂いもち危険期。高湿度{wetness_hours:.0f}h連続。"
                             f"気温{r['avg_temp']:.1f}℃。予防散布を検討。",
                    "acc_temp": acc,
                })
                state["blast_panicle_notified"] = True

        # ─────────────────────────────────────────
        # (F) 出穂予測・出穂通知
        # ─────────────────────────────────────────
        if stage == "heading" and not state["heading_notified"]:
            notifications.append({
                "date": d, "type": "heading",
                "level": "info",
                "title": "出穂を確認",
                "detail": f"積算温度{acc:.0f}℃日。出穂期に入りました。"
                         f"今後20日間の高温に注意。穂いもち防除を。",
                "acc_temp": acc,
            })
            state["heading_notified"] = True

        # ─────────────────────────────────────────
        # (G) 登熟期の高温障害リスク（夜温考慮版）
        # ─────────────────────────────────────────
        if stage in ("heading", "grain_filling") and heading_date:
            days_post = (d - heading_date).days
            if 3 <= days_post <= 20:
                # 出穂後の全日のデータを集計
                post_rows = [results[j] for j in range(len(results))
                             if results[j]["date"] > heading_date
                             and results[j]["date"] <= d]
                if len(post_rows) >= 3:
                    avg_t = sum(r2["avg_temp"] for r2 in post_rows) / len(post_rows)
                    avg_min = sum(r2["min_temp"] for r2 in post_rows) / len(post_rows)

                    # moderate を先に判定
                    if avg_t >= 26.0 and not state["heat_moderate_notified"]:
                        notifications.append({
                            "date": d, "type": "heat_stress_mod",
                            "level": "info",
                            "title": "高温障害注意：やや高温",
                            "detail": f"出穂後{days_post}日。平均気温{avg_t:.1f}℃"
                                     f"(夜温{avg_min:.1f}℃)。水管理を注意深く。",
                            "acc_temp": acc,
                        })
                        state["heat_moderate_notified"] = True

                    if avg_t >= 27.0 and not state["heat_high_notified"]:
                        notifications.append({
                            "date": d, "type": "heat_stress",
                            "level": "warning",
                            "title": "高温障害リスク：高",
                            "detail": f"出穂後{days_post}日。平均気温{avg_t:.1f}℃"
                                     f"(夜温{avg_min:.1f}℃)。"
                                     f"掛け流しかんがい・夜間入水を。",
                            "acc_temp": acc,
                        })
                        state["heat_high_notified"] = True

        # ─────────────────────────────────────────
        # (H) 落水タイミング
        # ─────────────────────────────────────────
        if stage in ("grain_filling", "maturity") and heading_date and d > heading_date:
            # 出穂後の積算温度（収穫判定は日平均気温そのままの積算。農学標準）
            post_acc_raw = sum(
                results[j]["avg_temp"]
                for j in range(len(results))
                if results[j]["date"] > heading_date and results[j]["date"] <= d
            )
            # 収穫 = 出穂後の日平均気温積算≒1000℃日、落水 = 収穫の7-10日前
            remaining_to_harvest = max(1000 - post_acc_raw, 0)
            recent_avg = [results[j]["avg_temp"] for j in range(max(0,i-6), i+1)]
            daily_avg = sum(recent_avg)/len(recent_avg) if recent_avg else 22
            days_to_harvest = int(remaining_to_harvest / max(daily_avg, 1.0))
            post_acc = post_acc_raw  # 表示用

            if days_to_harvest <= 14 and not state["drain_final_notified"]:
                harvest_est = d + timedelta(days=days_to_harvest)
                drain_est = harvest_est - timedelta(days=10)
                notifications.append({
                    "date": d, "type": "final_drain",
                    "level": "action",
                    "title": "落水準備",
                    "detail": f"推定収穫{harvest_est.strftime('%m/%d')}。"
                             f"落水推奨{drain_est.strftime('%m/%d')}頃。"
                             f"出穂後積算{post_acc:.0f}℃日/1000℃日。",
                    "acc_temp": acc,
                })
                state["drain_final_notified"] = True

    return notifications


# ============================================================
# 4. グラフ描画
# ============================================================
def draw_simulation(results, notifications, transplant, heading_date):
    """3パネルのシミュレーション図を作成"""

    # 田植え以降のデータに絞る
    season = [r for r in results if r["date"] >= transplant - timedelta(days=5)]
    dates = [r["date"] for r in season]
    avg_temps = [r["avg_temp"] for r in season]
    max_temps = [r["max_temp"] for r in season]
    min_temps = [r["min_temp"] for r in season]
    water_temps = [r.get("water_temp", None) for r in season]
    acc_temps = [r["acc_temp"] for r in season]

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(18, 14),
                                         gridspec_kw={"height_ratios": [3, 3, 2]},
                                         sharex=True)
    fig.suptitle("たんぼアドバイザー  通知タイミング シミュレーション\n"
                 "東広島市 2025年  品種：コシヒカリ  田植え：6月5日",
                 fontsize=16, fontweight="bold", y=0.98)

    # ── Panel 1: 気温推移 ──
    ax1.fill_between(dates, min_temps, max_temps, alpha=0.15, color="red", label="最高-最低気温")
    ax1.plot(dates, avg_temps, color="black", linewidth=1.5, label="日平均気温")
    ax1.plot(dates, max_temps, color="red", linewidth=0.7, alpha=0.5, linestyle="--")
    ax1.plot(dates, min_temps, color="blue", linewidth=0.7, alpha=0.5, linestyle="--")

    # 水温（田植え後15日間）
    wt_dates = [dates[i] for i in range(len(dates))
                if water_temps[i] is not None and dates[i] <= transplant + timedelta(days=15)]
    wt_vals = [water_temps[i] for i in range(len(dates))
               if water_temps[i] is not None and dates[i] <= transplant + timedelta(days=15)]
    if wt_dates:
        ax1.plot(wt_dates, wt_vals, color="cyan", linewidth=2.0, label="水温（活着期）",
                 marker=".", markersize=3)

    # 閾値ライン
    ax1.axhline(y=15, color="cyan", linewidth=0.8, linestyle=":", alpha=0.7, label="水温警戒15℃")
    ax1.axhline(y=27, color="orange", linewidth=0.8, linestyle=":", alpha=0.7, label="高温障害27℃")

    ax1.set_ylabel("気温 (℃)", fontsize=12)
    ax1.set_ylim(8, 40)
    ax1.legend(loc="upper left", fontsize=9, ncol=3)
    ax1.set_title("① 日別気温・水温", fontsize=13, loc="left")
    ax1.grid(axis="y", alpha=0.3)

    # ── Panel 2: 積算温度 + 生育ステージ ──
    # ステージ背景色
    for key, low, high, label, color in STAGES_KOSHI:
        ax2.axhspan(low, high, alpha=0.2, color=color)
        # ラベル
        mid_y = (low + high) / 2
        if mid_y < max(acc_temps) + 100:
            ax2.text(dates[-1] + timedelta(days=1), mid_y, f" {label}",
                     fontsize=8, va="center", color="#444")

    # 積算温度曲線
    ax2.plot(dates, acc_temps, color="#333", linewidth=2.5, label="有効積算温度")
    ax2.fill_between(dates, 0, acc_temps, alpha=0.08, color="green")

    # ステージ境界の水平線
    for key, low, high, label, color in STAGES_KOSHI:
        if low > 0:
            ax2.axhline(y=low, color="gray", linewidth=0.5, linestyle="--", alpha=0.5)

    # 通知マーカー
    marker_styles = {
        "water_temp":       ("v", "cyan",   12),
        "drain_pre":        ("D", "#88aa44", 10),
        "drain_start":      ("s", "#cc8800", 13),
        "drain_end":        ("s", "#44aa44", 13),
        "blast_risk":       ("^", "#cc3333", 13),
        "heading":          ("*", "#dd44dd", 16),
        "heat_stress":      ("P", "#ff6600", 13),
        "heat_stress_mod":  ("P", "#ffaa00", 11),
        "final_drain":      ("H", "#6666cc", 13),
    }

    for n in notifications:
        nd = n["date"]
        na = n["acc_temp"]
        mtype = n["type"]
        marker, color, size = marker_styles.get(mtype, ("o", "gray", 8))
        ax2.plot(nd, na, marker=marker, color=color, markersize=size,
                 markeredgecolor="white", markeredgewidth=0.8, zorder=5)

    ax2.set_ylabel("有効積算温度 (℃日)", fontsize=12)
    ax2.set_ylim(0, max(acc_temps) * 1.1)
    ax2.set_title("② 有効積算温度と生育ステージ推移", fontsize=13, loc="left")
    ax2.grid(axis="y", alpha=0.3)

    # ── Panel 3: 通知タイムライン ──
    type_order = [
        ("water_temp",      "活着期 水温"),
        ("drain_pre",       "中干し予告"),
        ("drain_start",     "中干し開始"),
        ("drain_end",       "中干し終了"),
        ("blast_risk",      "いもち病リスク"),
        ("heading",         "出穂確認"),
        ("heat_stress_mod", "高温注意(中)"),
        ("heat_stress",     "高温障害(高)"),
        ("final_drain",     "落水準備"),
    ]
    type_y = {t: i for i, (t, _) in enumerate(type_order)}
    type_labels = [label for _, label in type_order]

    level_colors = {
        "info": "#4488cc",
        "warning": "#cc4444",
        "action": "#cc8800",
    }

    for n in notifications:
        y = type_y.get(n["type"], 0)
        color = level_colors.get(n["level"], "gray")
        ax3.barh(y, 3, left=mdates.date2num(n["date"]) - 1.5,
                 height=0.6, color=color, alpha=0.85, edgecolor="white", linewidth=0.5)

        # 日付ラベル
        ax3.text(mdates.date2num(n["date"]), y + 0.4,
                 n["date"].strftime("%m/%d"), fontsize=7, ha="center", va="bottom",
                 color="#333")

    ax3.set_yticks(range(len(type_labels)))
    ax3.set_yticklabels(type_labels, fontsize=10)
    ax3.set_ylim(-0.5, len(type_labels) - 0.5)
    ax3.invert_yaxis()
    ax3.set_title("③ 通知タイムライン", fontsize=13, loc="left")
    ax3.grid(axis="x", alpha=0.3)

    # 凡例
    legend_elements = [
        mpatches.Patch(color="#4488cc", alpha=0.85, label="情報通知"),
        mpatches.Patch(color="#cc8800", alpha=0.85, label="行動指示"),
        mpatches.Patch(color="#cc4444", alpha=0.85, label="警告通知"),
    ]
    ax3.legend(handles=legend_elements, loc="lower right", fontsize=9, ncol=3)

    # X軸
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax3.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))  # 毎週月曜
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha="right", fontsize=9)

    # 田植え日の縦線
    for ax in (ax1, ax2, ax3):
        ax.axvline(x=transplant, color="green", linewidth=1.5, linestyle="-.", alpha=0.7)
    ax1.text(transplant, ax1.get_ylim()[1], " 田植え", fontsize=9, color="green", va="top")

    # 出穂日の縦線
    if heading_date:
        for ax in (ax1, ax2, ax3):
            ax.axvline(x=heading_date, color="purple", linewidth=1.5, linestyle="-.", alpha=0.7)
        ax1.text(heading_date, ax1.get_ylim()[1], " 出穂", fontsize=9, color="purple", va="top")

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(PNG_PATH, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"グラフ保存: {PNG_PATH}")
    plt.close()


# ============================================================
# 5. 通知ログ出力
# ============================================================
def write_notification_log(notifications):
    level_icons = {"info": "📘", "warning": "⚠️", "action": "📢"}
    lines = [
        "=" * 70,
        "  たんぼアドバイザー 通知シミュレーション結果",
        "  東広島市 2025年  コシヒカリ  田植え 6/5",
        "=" * 70,
        "",
    ]
    for n in notifications:
        icon = level_icons.get(n["level"], "")
        lines.append(f"  {n['date']}  {icon} [{n['level'].upper():>7}]  {n['title']}")
        lines.append(f"              積算温度 {n['acc_temp']:.0f}℃日")
        lines.append(f"              {n['detail']}")
        lines.append("")

    lines.append(f"  合計: {len(notifications)} 件の通知")
    text = "\n".join(lines)

    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"通知ログ保存: {LOG_PATH}")
    return text


# ============================================================
# main
# ============================================================
def main():
    transplant = date(2025, 6, 5)

    print("1. 気象データ生成中...")
    raw_data = generate_daily_data(2025)
    print(f"   {len(raw_data)}日分のデータ生成完了")

    print("2. 積算温度・生育ステージ計算中...")
    results = calc_season(raw_data, transplant)

    # 出穂日を特定
    heading_date = None
    for r in results:
        if r["stage"] == "heading" and heading_date is None:
            heading_date = r["date"]

    print(f"   出穂予測日: {heading_date}")

    print("3. 通知判定中...")
    notifications = determine_notifications(results, transplant)
    print(f"   {len(notifications)}件の通知を検出")

    print("4. グラフ描画中...")
    draw_simulation(results, notifications, transplant, heading_date)

    print("5. 通知ログ出力中...")
    log_text = write_notification_log(notifications)
    print()
    print(log_text)


if __name__ == "__main__":
    main()
