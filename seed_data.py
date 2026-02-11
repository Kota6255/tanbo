"""サンプルデータ投入スクリプト

DBを初期化し、デモ用データを投入する。
実行: python seed_data.py
"""

import sys
import os
import random
from datetime import date, datetime, timedelta, timezone

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(__file__))

from src.models.database import (
    Base, engine, SessionLocal, init_db,
    Field, AmedasObservation, DailyWeather, SensorReading,
    GrowthStage, BlastRiskLog, Notification, PestAdvisory,
)

JST = timezone(timedelta(hours=9))
random.seed(42)


def main():
    print("=" * 60)
    print("  たんぼアドバイザー - サンプルデータ投入")
    print("=" * 60)

    # DB初期化
    print("\n[1/7] データベースを初期化中...")
    Base.metadata.drop_all(engine)
    init_db()
    print("  OK: テーブル作成完了")

    db = SessionLocal()
    try:
        # 圃場マスタ
        print("\n[2/7] 圃場マスタを登録中...")
        fields = _seed_fields(db)
        print(f"  OK: {len(fields)}件の圃場を登録")

        # アメダス観測データ（6/1〜8/31の3ヶ月分を1時間間隔で生成）
        print("\n[3/7] アメダス観測データを生成中（6月〜8月）...")
        obs_count = _seed_amedas_observations(db)
        print(f"  OK: {obs_count}件の観測データを投入")

        # 日別気象サマリ
        print("\n[4/7] 日別気象サマリを計算中...")
        daily_count = _seed_daily_weather(db)
        print(f"  OK: {daily_count}件の日別サマリを作成")

        # センサーデータ
        print("\n[5/7] ESP32センサーデータを生成中...")
        sensor_count = _seed_sensor_readings(db, fields[0])
        print(f"  OK: {sensor_count}件のセンサーデータを投入")

        # 生育ステージ
        print("\n[6/7] 生育ステージ履歴を計算中...")
        stage_count = _seed_growth_stages(db, fields)
        print(f"  OK: {stage_count}件の生育ステージ記録を作成")

        # いもち病リスク・予察情報・通知ログ
        print("\n[7/7] いもち病リスク・通知ログを生成中...")
        blast_count = _seed_blast_risk_and_notifications(db, fields)
        print(f"  OK: リスクログ{blast_count}件、予察情報・通知ログを投入")

        db.commit()
        print("\n" + "=" * 60)
        print("  データ投入完了！")
        print("  DBファイル: tanbo.db")
        print("  可視化:     python view_data.py")
        print("=" * 60)

    finally:
        db.close()


def _seed_fields(db) -> list:
    """圃場マスタ投入"""
    fields_data = [
        Field(
            name="家の前の田",
            latitude=34.4269, longitude=132.7433,
            area_m2=3000.0, variety="コシヒカリ",
            transplant_date=date(2026, 6, 5),
            nearest_amedas="67511", elevation_m=230.0,
            line_user_id="U_demo_user_001",
        ),
        Field(
            name="山の奥の田",
            latitude=34.8028, longitude=132.8539,
            area_m2=5000.0, variety="ヒノヒカリ",
            transplant_date=date(2026, 6, 12),
            nearest_amedas="67376", elevation_m=170.0,
            line_user_id="U_demo_user_001",
        ),
        Field(
            name="駅前の田",
            latitude=34.3981, longitude=132.4594,
            area_m2=2000.0, variety="あきろまん",
            transplant_date=date(2026, 6, 8),
            nearest_amedas="67437", elevation_m=35.0,
            line_user_id="U_demo_user_002",
        ),
    ]
    for f in fields_data:
        db.add(f)
    db.flush()
    return fields_data


def _seed_amedas_observations(db) -> int:
    """アメダス観測データ（6/1〜8/31、1時間間隔）"""
    stations = ["67511", "67376", "67437"]  # 東広島, 三次, 広島
    start = datetime(2026, 6, 1, 0, 0, 0, tzinfo=JST)
    end = datetime(2026, 8, 31, 23, 0, 0, tzinfo=JST)
    count = 0

    for station in stations:
        t = start
        while t <= end:
            hour = t.hour
            day_of_year = t.timetuple().tm_yday

            # 月による基準気温
            month = t.month
            if month == 6:
                base = 22.0
            elif month == 7:
                base = 26.0
            else:
                base = 28.0

            # 日変動（sin波）+ ランダム揺らぎ
            daily_variation = 5.0 * (
                -1.0 + 2.0 * max(0, min(1, (hour - 5) / 9))
                if hour < 14
                else 1.0 - (hour - 14) / 10
            )
            temp = base + daily_variation + random.gauss(0, 1.0)
            humidity = max(40, min(100, 75 - daily_variation * 3 + random.gauss(0, 5)))
            precip = max(0, random.gauss(-0.5, 0.3)) if random.random() < 0.15 else 0.0
            wind = max(0, random.gauss(2.0, 1.0))
            sunshine = max(0, min(1.0, 0.7 + random.gauss(0, 0.2))) if 6 <= hour <= 18 else 0

            obs = AmedasObservation(
                station_id=station,
                observed_at=t.isoformat(),
                air_temp=round(temp, 1),
                humidity=round(humidity, 1),
                precipitation_1h=round(precip, 1),
                wind_speed=round(wind, 1),
                sunshine_1h=round(sunshine, 2),
                pressure=round(1013.0 + random.gauss(0, 2), 1),
            )
            db.add(obs)
            count += 1
            t += timedelta(hours=1)

        # バッチコミット（メモリ節約）
        if count % 5000 == 0:
            db.flush()

    db.flush()
    return count


def _seed_daily_weather(db) -> int:
    """日別気象サマリ（観測データから集計）"""
    stations = ["67511", "67376", "67437"]
    start = date(2026, 6, 1)
    end = date(2026, 8, 31)
    count = 0

    for station in stations:
        d = start
        while d <= end:
            day_start = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=JST).isoformat()
            day_end = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=JST).isoformat()

            rows = db.query(AmedasObservation).filter(
                AmedasObservation.station_id == station,
                AmedasObservation.observed_at >= day_start,
                AmedasObservation.observed_at <= day_end,
            ).all()

            if rows:
                temps = [r.air_temp for r in rows if r.air_temp is not None]
                humids = [r.humidity for r in rows if r.humidity is not None]
                precips = [r.precipitation_1h for r in rows if r.precipitation_1h is not None]
                sunshines = [r.sunshine_1h for r in rows if r.sunshine_1h is not None]

                if temps:
                    dw = DailyWeather(
                        station_id=station,
                        date=d,
                        avg_temp=round(sum(temps) / len(temps), 1),
                        max_temp=round(max(temps), 1),
                        min_temp=round(min(temps), 1),
                        total_precipitation=round(sum(precips), 1),
                        avg_humidity=round(sum(humids) / len(humids), 1) if humids else None,
                        total_sunshine=round(sum(sunshines), 2) if sunshines else None,
                    )
                    db.add(dw)
                    count += 1

            d += timedelta(days=1)

    db.flush()
    return count


def _seed_sensor_readings(db, field) -> int:
    """ESP32センサーデータ（30分間隔、6/5〜7/31）"""
    start = datetime(2026, 6, 5, 6, 0, 0, tzinfo=JST)
    end = datetime(2026, 7, 31, 18, 0, 0, tzinfo=JST)
    count = 0
    t = start

    while t <= end:
        hour = t.hour
        month = t.month
        base_temp = 22.0 if month == 6 else 26.0
        daily_var = 4.0 * (-1.0 + 2.0 * max(0, min(1, (hour - 5) / 9)) if hour < 14 else 1.0 - (hour - 14) / 10)

        reading = SensorReading(
            field_id=field.id,
            recorded_at=t.isoformat(),
            air_temp=round(base_temp + daily_var + random.gauss(0, 0.5), 1),
            humidity=round(max(40, min(100, 80 - daily_var * 2 + random.gauss(0, 3))), 1),
            pressure=round(1013.0 + random.gauss(0, 1.5), 1),
            water_temp=round(base_temp + daily_var * 0.7 - 2 + random.gauss(0, 0.3), 1),
            water_level=round(max(0, 5.0 + random.gauss(0, 1.0)), 1),
        )
        db.add(reading)
        count += 1

        # 30分間隔（深夜は60分）
        if 22 <= hour or hour < 5:
            t += timedelta(minutes=60)
        else:
            t += timedelta(minutes=30)

    db.flush()
    return count


def _seed_growth_stages(db, fields) -> int:
    """生育ステージ履歴（田植え日から日ごとに計算）"""
    from src.analyzers.growth_stage import estimate_growth_stage

    count = 0
    end = date(2026, 8, 31)

    for field in fields:
        d = field.transplant_date
        while d <= end:
            # その日までの有効積算温度を計算
            station = field.nearest_amedas
            daily_rows = db.query(DailyWeather).filter(
                DailyWeather.station_id == station,
                DailyWeather.date >= field.transplant_date,
                DailyWeather.date <= d,
            ).all()

            acc_temp = 0.0
            for row in daily_rows:
                if row.avg_temp and row.avg_temp > 10:
                    acc_temp += row.avg_temp - 10.0

            try:
                stage = estimate_growth_stage(field.variety, acc_temp)
            except ValueError:
                d += timedelta(days=1)
                continue

            days = (d - field.transplant_date).days

            gs = GrowthStage(
                field_id=field.id,
                date=d,
                accumulated_temp=round(acc_temp, 1),
                estimated_stage=stage["stage"],
                tiller_count_estimate=stage.get("progress_pct"),
                days_from_transplant=days,
            )
            db.add(gs)
            count += 1
            d += timedelta(days=1)

        if count % 100 == 0:
            db.flush()

    db.flush()
    return count


def _seed_blast_risk_and_notifications(db, fields) -> int:
    """いもち病リスクログ・予察情報・通知ログ"""
    # 予察情報
    advisories = [
        PestAdvisory(
            date=date(2026, 7, 10),
            pest_name="いもち病",
            advisory_level="技術情報",
            region="広島県全域",
            message="梅雨期の多湿により葉いもちの発生に注意",
            source_url="https://www.pref.hiroshima.lg.jp/soshiki/84/",
        ),
        PestAdvisory(
            date=date(2026, 7, 20),
            pest_name="いもち病",
            advisory_level="注意報",
            region="広島県全域",
            message="葉いもちの発生が平年より多い。防除徹底",
            source_url="https://www.pref.hiroshima.lg.jp/soshiki/84/",
        ),
    ]
    for a in advisories:
        db.add(a)

    # いもち病リスクログ（7月分サンプル）
    count = 0
    risk_dates = [
        (date(2026, 7, 5), "low", 3.0, 24.5, 88.0),
        (date(2026, 7, 10), "moderate", 7.5, 25.2, 93.0),
        (date(2026, 7, 15), "high", 12.0, 24.8, 95.0),
        (date(2026, 7, 20), "high", 14.5, 24.3, 96.0),
        (date(2026, 7, 25), "moderate", 8.0, 26.1, 91.0),
        (date(2026, 7, 30), "low", 4.0, 27.5, 82.0),
    ]

    for field in fields:
        for d, risk, wetness, temp, humid in risk_dates:
            bl = BlastRiskLog(
                field_id=field.id,
                assessed_at=datetime(d.year, d.month, d.day, 6, 15, 0, tzinfo=JST).isoformat(),
                risk_level=risk,
                avg_temp=temp,
                avg_humidity=humid,
                leaf_wetness_hours=wetness,
                notified=1 if risk == "high" else 0,
            )
            db.add(bl)
            count += 1

    # 通知ログ
    notifications = [
        Notification(
            field_id=fields[0].id,
            notification_type="daily_advice",
            message="おはようございます。\n家の前の田（コシヒカリ）\n田植えから30日目\n分げつ期です。",
            delivered=1,
        ),
        Notification(
            field_id=fields[0].id,
            notification_type="blast_alert",
            message="⚠️ いもち病に注意してください\n家の前の田（コシヒカリ）\n湿度90%以上が14時間連続",
            delivered=1,
        ),
        Notification(
            field_id=fields[0].id,
            notification_type="drain_reminder",
            message="📢 中干しを始める時期です\n家の前の田（コシヒカリ）",
            delivered=1,
        ),
    ]
    for n in notifications:
        db.add(n)

    db.flush()
    return count


if __name__ == "__main__":
    main()
