"""積算温度計算モジュール"""

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from src.models.database import SessionLocal, DailyWeather
from config.settings import settings


def calc_accumulated_temp(
    station_id: str,
    start_date: date,
    end_date: date,
    field_elevation: float = None,
    station_elevation: float = None,
) -> float:
    """有効積算温度を計算する。

    DailyWeather テーブルから日平均気温を取得し、
    基準温度 (10 ℃) を超えた分だけ加算する。

    Parameters
    ----------
    station_id : str
        アメダス観測地点 ID。
    start_date : date
        積算開始日（田植え日など）。
    end_date : date
        積算終了日（通常は今日）。
    field_elevation : float, optional
        圃場の標高 (m)。station_elevation と合わせて指定すると標高補正する。
    station_elevation : float, optional
        アメダス観測地点の標高 (m)。

    Returns
    -------
    float
        有効積算温度 (℃日)。
    """
    db: Session = SessionLocal()
    try:
        rows = (
            db.query(DailyWeather)
            .filter(
                DailyWeather.station_id == station_id,
                DailyWeather.date >= start_date,
                DailyWeather.date <= end_date,
            )
            .order_by(DailyWeather.date)
            .all()
        )

        base_temp = settings.base_temperature  # 10.0
        lapse_rate = settings.elevation_lapse_rate  # 0.006 ℃/m

        # 標高補正を行うかどうか
        apply_correction = (
            field_elevation is not None and station_elevation is not None
        )

        accumulated = 0.0
        for row in rows:
            if row.avg_temp is None:
                continue

            temp = row.avg_temp

            # 標高補正: 圃場が観測地点より高い場合は気温が下がる
            if apply_correction:
                temp = temp - lapse_rate * (field_elevation - station_elevation)

            effective = max(temp - base_temp, 0.0)
            accumulated += effective

        return round(accumulated, 1)
    finally:
        db.close()
