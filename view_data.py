"""データ可視化スクリプト

DBに投入されたすべてのデータを一覧表示する。
実行: python view_data.py
"""

import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))

from src.models.database import SessionLocal, init_db
from src.models.database import (
    Field, AmedasObservation, DailyWeather, SensorReading,
    GrowthStage, BlastRiskLog, Notification, PestAdvisory,
)


def main():
    db = SessionLocal()
    try:
        print_header()
        print_fields(db)
        print_daily_weather_summary(db)
        print_growth_stages(db)
        print_blast_risk(db)
        print_sensor_summary(db)
        print_pest_advisories(db)
        print_notifications(db)
        print_statistics(db)
    finally:
        db.close()


def print_header():
    print()
    print("=" * 80)
    print("  たんぼアドバイザー - データベース一覧")
    print("=" * 80)


def print_fields(db):
    print("\n" + "━" * 80)
    print("  【圃場マスタ】 fields テーブル")
    print("━" * 80)

    fields = db.query(Field).all()
    for f in fields:
        print(f"\n  ID: {f.id}")
        print(f"  圃場名:     {f.name}")
        print(f"  品種:       {f.variety}")
        print(f"  田植え日:   {f.transplant_date}")
        print(f"  緯度/経度:  {f.latitude}, {f.longitude}")
        print(f"  面積:       {f.area_m2} m² ({f.area_m2 / 10000:.2f} ha)" if f.area_m2 else "")
        print(f"  標高:       {f.elevation_m} m")
        print(f"  最寄アメダス: {f.nearest_amedas}")
        print(f"  LINE ID:    {f.line_user_id}")


def print_daily_weather_summary(db):
    print("\n" + "━" * 80)
    print("  【日別気象サマリ】 daily_weather テーブル（月別集計）")
    print("━" * 80)

    stations = db.query(DailyWeather.station_id).distinct().all()
    station_names = {"67511": "東広島", "67376": "三次", "67437": "広島"}

    for (station_id,) in stations:
        name = station_names.get(station_id, station_id)
        print(f"\n  ■ {name} ({station_id})")
        print(f"  {'月':>4}  {'日数':>4}  {'平均気温':>8}  {'最高気温':>8}  {'最低気温':>8}  {'降水量合計':>10}  {'平均湿度':>8}")
        print(f"  {'─' * 4}  {'─' * 4}  {'─' * 8}  {'─' * 8}  {'─' * 8}  {'─' * 10}  {'─' * 8}")

        for month in [6, 7, 8]:
            rows = db.query(DailyWeather).filter(
                DailyWeather.station_id == station_id,
                DailyWeather.date >= date(2026, month, 1),
                DailyWeather.date < date(2026, month + 1 if month < 12 else 1, 1),
            ).all()

            if rows:
                avg_temps = [r.avg_temp for r in rows if r.avg_temp is not None]
                max_temps = [r.max_temp for r in rows if r.max_temp is not None]
                min_temps = [r.min_temp for r in rows if r.min_temp is not None]
                precips = [r.total_precipitation for r in rows if r.total_precipitation is not None]
                humids = [r.avg_humidity for r in rows if r.avg_humidity is not None]

                avg_t = sum(avg_temps) / len(avg_temps) if avg_temps else 0
                max_t = max(max_temps) if max_temps else 0
                min_t = min(min_temps) if min_temps else 0
                total_p = sum(precips) if precips else 0
                avg_h = sum(humids) / len(humids) if humids else 0

                print(f"  {month:>4}月  {len(rows):>4}日  {avg_t:>7.1f}℃  {max_t:>7.1f}℃  {min_t:>7.1f}℃  {total_p:>9.1f}mm  {avg_h:>7.1f}%")


def print_growth_stages(db):
    print("\n" + "━" * 80)
    print("  【生育ステージ履歴】 growth_stages テーブル（主要ポイント）")
    print("━" * 80)

    fields = db.query(Field).all()
    stage_labels = {
        "tillering": "分げつ期",
        "max_tiller": "最高分げつ期",
        "midseason_drain": "中干し適期",
        "panicle_formation": "幼穂形成期",
        "booting": "穂ばらみ期",
        "heading": "出穂期",
        "grain_filling": "登熟期",
        "maturity": "成熟期",
    }

    for field in fields:
        print(f"\n  ■ {field.name}（{field.variety}）田植え: {field.transplant_date}")

        stages = db.query(GrowthStage).filter(
            GrowthStage.field_id == field.id
        ).order_by(GrowthStage.date).all()

        if not stages:
            print("    データなし")
            continue

        # ステージ切り替わりポイントを抽出
        print(f"    {'日付':>12}  {'日数':>4}  {'積算温度':>8}  {'ステージ'}")
        print(f"    {'─' * 12}  {'─' * 4}  {'─' * 8}  {'─' * 20}")

        prev_stage = None
        for gs in stages:
            if gs.estimated_stage != prev_stage:
                label = stage_labels.get(gs.estimated_stage, gs.estimated_stage)
                print(f"    {gs.date}  {gs.days_from_transplant:>4}日  {gs.accumulated_temp:>7.1f}℃日  → {label}")
                prev_stage = gs.estimated_stage

        # 最新の状態
        latest = stages[-1]
        label = stage_labels.get(latest.estimated_stage, latest.estimated_stage)
        print(f"    ─── 最新 ({latest.date}): {label}  積算温度 {latest.accumulated_temp:.1f}℃日  {latest.days_from_transplant}日目")


def print_blast_risk(db):
    print("\n" + "━" * 80)
    print("  【いもち病リスク判定ログ】 blast_risk_log テーブル")
    print("━" * 80)

    fields = db.query(Field).all()
    risk_icons = {"low": "🟢", "moderate": "🟡", "high": "🔴"}

    for field in fields:
        print(f"\n  ■ {field.name}（{field.variety}）")
        print(f"    {'日時':>20}  {'リスク':>6}  {'湿潤時間':>8}  {'平均気温':>8}  {'通知'}")
        print(f"    {'─' * 20}  {'─' * 6}  {'─' * 8}  {'─' * 8}  {'─' * 4}")

        logs = db.query(BlastRiskLog).filter(
            BlastRiskLog.field_id == field.id
        ).order_by(BlastRiskLog.assessed_at).all()

        for log in logs:
            icon = risk_icons.get(log.risk_level, "?")
            notif = "済" if log.notified else "-"
            print(f"    {log.assessed_at[:16]:>20}  {icon} {log.risk_level:<6}  {log.leaf_wetness_hours:>6.1f}h  {log.avg_temp:>7.1f}℃  {notif}")


def print_sensor_summary(db):
    print("\n" + "━" * 80)
    print("  【ESP32センサーデータ】 sensor_readings テーブル（日別サマリ）")
    print("━" * 80)

    fields = db.query(Field).all()
    for field in fields:
        readings = db.query(SensorReading).filter(
            SensorReading.field_id == field.id
        ).all()

        if not readings:
            continue

        print(f"\n  ■ {field.name}  総データ数: {len(readings)}件")

        # 週ごとにサマリ
        from collections import defaultdict
        weekly = defaultdict(list)
        for r in readings:
            # ISO weekの取得
            d = r.recorded_at[:10]
            weekly[d[:7]].append(r)  # 月ごと

        print(f"    {'月':>8}  {'件数':>6}  {'平均気温':>8}  {'平均湿度':>8}  {'平均水温':>8}  {'平均水位':>8}")
        print(f"    {'─' * 8}  {'─' * 6}  {'─' * 8}  {'─' * 8}  {'─' * 8}  {'─' * 8}")

        for month_key in sorted(weekly.keys()):
            rlist = weekly[month_key]
            temps = [r.air_temp for r in rlist if r.air_temp]
            humids = [r.humidity for r in rlist if r.humidity]
            wtemps = [r.water_temp for r in rlist if r.water_temp]
            wlevels = [r.water_level for r in rlist if r.water_level]

            avg_t = sum(temps) / len(temps) if temps else 0
            avg_h = sum(humids) / len(humids) if humids else 0
            avg_wt = sum(wtemps) / len(wtemps) if wtemps else 0
            avg_wl = sum(wlevels) / len(wlevels) if wlevels else 0

            print(f"    {month_key:>8}  {len(rlist):>6}  {avg_t:>7.1f}℃  {avg_h:>7.1f}%  {avg_wt:>7.1f}℃  {avg_wl:>6.1f}cm")


def print_pest_advisories(db):
    print("\n" + "━" * 80)
    print("  【病害虫予察情報】 pest_advisories テーブル")
    print("━" * 80)

    advisories = db.query(PestAdvisory).order_by(PestAdvisory.date).all()
    for a in advisories:
        level_icon = {"警報": "🔴", "注意報": "🟡", "技術情報": "🔵"}.get(a.advisory_level, "⚪")
        print(f"\n  {a.date}  {level_icon} [{a.advisory_level}] {a.pest_name}")
        print(f"  対象: {a.region}")
        print(f"  内容: {a.message}")


def print_notifications(db):
    print("\n" + "━" * 80)
    print("  【LINE通知ログ】 notifications テーブル")
    print("━" * 80)

    notifs = db.query(Notification).order_by(Notification.sent_at).all()
    type_labels = {
        "daily_advice": "📬 毎朝通知",
        "blast_alert": "⚠️ いもち警報",
        "drain_reminder": "📢 中干し通知",
        "heat_stress_alert": "🌡️ 高温警報",
    }

    for n in notifs:
        label = type_labels.get(n.notification_type, n.notification_type)
        status = "✅ 配信済" if n.delivered else "❌ 失敗"
        print(f"\n  {label}  圃場ID:{n.field_id}  {status}")
        # メッセージの最初の2行だけ表示
        msg_lines = (n.message or "").split("\n")[:2]
        for line in msg_lines:
            print(f"    {line}")
        if len((n.message or "").split("\n")) > 2:
            print(f"    ...")


def print_statistics(db):
    print("\n" + "━" * 80)
    print("  【統計サマリ】")
    print("━" * 80)

    counts = {
        "圃場": db.query(Field).count(),
        "アメダス観測": db.query(AmedasObservation).count(),
        "日別気象": db.query(DailyWeather).count(),
        "センサーデータ": db.query(SensorReading).count(),
        "生育ステージ": db.query(GrowthStage).count(),
        "いもち病リスク": db.query(BlastRiskLog).count(),
        "予察情報": db.query(PestAdvisory).count(),
        "通知ログ": db.query(Notification).count(),
    }

    print()
    total = 0
    for name, count in counts.items():
        print(f"  {name:<16} {count:>8} 件")
        total += count
    print(f"  {'─' * 28}")
    print(f"  {'合計':<16} {total:>8} 件")
    print()


if __name__ == "__main__":
    main()
