"""活着期の水温チェックモジュール"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from src.models.database import SessionLocal, Field, DailyWeather
from config.settings import settings


# 活着期の水温警戒閾値 (℃)
_WATER_TEMP_THRESHOLD = 15.0

# 田植え後何日間を活着期とみなすか
_ESTABLISHMENT_DAYS = 10


def _estimate_water_temp(min_temp: float, avg_temp: float) -> float:
    """水田の水温を推定する。

    水温は最低気温寄りになる（夜間冷却の影響が大きい）。
    水温 ≒ min_temp + (avg_temp - min_temp) * 0.3
    """
    return min_temp + (avg_temp - min_temp) * 0.3


def assess_water_temp(field_id: int) -> dict:
    """活着期の水温リスクを判定する。

    田植え後 1〜10 日間の水温を推定し、15℃以下であれば警告する。

    Parameters
    ----------
    field_id : int
        圃場 ID。

    Returns
    -------
    dict
        is_establishment : bool    - 活着期かどうか
        water_temp : float or None - 推定水温
        risk : bool                - 水温リスクがあるか
        days_from_transplant : int - 田植え後日数
        message : str              - ユーザ向けメッセージ
    """
    db: Session = SessionLocal()
    try:
        field = db.query(Field).filter(Field.id == field_id).first()
        if field is None:
            raise ValueError(f"圃場が見つかりません: field_id={field_id}")

        transplant_date = field.transplant_date
        station_id = field.nearest_amedas

        if transplant_date is None:
            raise ValueError("田植え日が登録されていません。")
        if station_id is None:
            raise ValueError("最寄りアメダス地点が設定されていません。")

        today = date.today()
        days_from_transplant = (today - transplant_date).days

        # 活着期外は即リターン
        if days_from_transplant < 1 or days_from_transplant > _ESTABLISHMENT_DAYS:
            return {
                "is_establishment": False,
                "water_temp": None,
                "risk": False,
                "days_from_transplant": days_from_transplant,
                "message": (
                    f"【{field.name}】活着期（田植え後1〜{_ESTABLISHMENT_DAYS}日）"
                    "の範囲外です。"
                ),
            }

        # 直近の気温データから水温を推定
        row = (
            db.query(DailyWeather)
            .filter(
                DailyWeather.station_id == station_id,
                DailyWeather.date == today,
            )
            .first()
        )

        # 当日データがなければ前日を使用
        if row is None or row.min_temp is None:
            row = (
                db.query(DailyWeather)
                .filter(
                    DailyWeather.station_id == station_id,
                    DailyWeather.date == today - timedelta(days=1),
                )
                .first()
            )

        if row is None or row.min_temp is None or row.avg_temp is None:
            return {
                "is_establishment": True,
                "water_temp": None,
                "risk": False,
                "days_from_transplant": days_from_transplant,
                "message": (
                    f"【{field.name}】活着期（{days_from_transplant}日目）ですが、"
                    "気温データを取得できません。"
                ),
            }

        water_temp = round(_estimate_water_temp(row.min_temp, row.avg_temp), 1)
        risk = water_temp < _WATER_TEMP_THRESHOLD

        messages = [
            f"【{field.name}】田植え後{days_from_transplant}日目（活着期）"
        ]
        messages.append(f"推定水温: {water_temp:.1f}℃")

        if risk:
            messages.append(
                f"水温が{_WATER_TEMP_THRESHOLD}℃を下回っています。"
                "活着遅延のおそれがあります。"
            )
            messages.append("深水管理（5〜7cm）で保温してください。")
        else:
            messages.append("水温は問題ありません。")

        return {
            "is_establishment": True,
            "water_temp": water_temp,
            "risk": risk,
            "days_from_transplant": days_from_transplant,
            "message": "\n".join(messages),
        }
    finally:
        db.close()
