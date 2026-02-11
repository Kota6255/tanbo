"""積算温度計算のテスト"""

import sys
from pathlib import Path
from datetime import date

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models.database import Base, engine, SessionLocal, DailyWeather, init_db


def setup_module():
    """テスト用DBを初期化"""
    Base.metadata.drop_all(engine)
    init_db()


def _insert_daily_temps(station_id: str, start: date, temps: list[float]):
    """テスト用に日平均気温データを投入"""
    db = SessionLocal()
    try:
        from datetime import timedelta
        for i, temp in enumerate(temps):
            d = start + timedelta(days=i)
            dw = DailyWeather(station_id=station_id, date=d, avg_temp=temp)
            db.add(dw)
        db.commit()
    finally:
        db.close()


def test_accumulated_temp_basic():
    """日平均気温 [25, 22, 18, 28, 30] の有効積算温度は
    (25-10) + (22-10) + (18-10) + (28-10) + (30-10) = 73 であること"""
    station = "TEST01"
    start = date(2026, 6, 1)
    _insert_daily_temps(station, start, [25.0, 22.0, 18.0, 28.0, 30.0])

    from src.analyzers.accumulated_temp import calc_accumulated_temp
    end = date(2026, 6, 5)
    result = calc_accumulated_temp(station, start, end)
    assert result == 73.0, f"Expected 73.0, got {result}"


def test_accumulated_temp_below_base():
    """日平均気温が10℃未満の日はカウントしない"""
    station = "TEST02"
    start = date(2026, 4, 1)
    _insert_daily_temps(station, start, [8.0, 5.0, 12.0, 9.0, 15.0])

    from src.analyzers.accumulated_temp import calc_accumulated_temp
    end = date(2026, 4, 5)
    result = calc_accumulated_temp(station, start, end)
    # 有効なのは 12℃(+2) と 15℃(+5) のみ = 7.0
    assert result == 7.0, f"Expected 7.0, got {result}"


def test_accumulated_temp_with_elevation():
    """標高補正が正しく適用されること"""
    station = "TEST03"
    start = date(2026, 6, 10)
    _insert_daily_temps(station, start, [25.0, 25.0, 25.0])

    from src.analyzers.accumulated_temp import calc_accumulated_temp
    end = date(2026, 6, 12)

    # 圃場が観測所より100m高い場合: 25 - 0.6 = 24.4 → 有効 = 14.4 × 3 = 43.2
    result = calc_accumulated_temp(
        station, start, end,
        field_elevation=329.0,  # 観測所 + 100m
        station_elevation=229.0,
    )
    assert abs(result - 43.2) < 0.2, f"Expected ~43.2, got {result}"


def test_accumulated_temp_empty():
    """データがない期間の積算温度は0"""
    from src.analyzers.accumulated_temp import calc_accumulated_temp
    result = calc_accumulated_temp("NODATA", date(2026, 1, 1), date(2026, 1, 5))
    assert result == 0.0
