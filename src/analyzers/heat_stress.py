"""高温障害リスク判定モジュール"""

from datetime import date, datetime, timedelta

from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.models.database import SessionLocal, Field, DailyWeather, GrowthStage
from src.analyzers.accumulated_temp import calc_accumulated_temp
from src.analyzers.growth_stage import estimate_growth_stage, GROWTH_STAGES
from config.settings import settings


def _estimate_heading_date(
    db: Session, field: "Field", today: date
) -> date | None:
    """出穂日を推定する。

    1. GrowthStage テーブルに出穂期の記録があればその日付を使う。
    2. なければ積算温度から出穂期に入る日を予測する。

    Returns
    -------
    date or None
        推定出穂日。推定不能な場合は None。
    """
    # 1) DB に出穂期の記録があるか探す
    heading_record = (
        db.query(GrowthStage)
        .filter(
            GrowthStage.field_id == field.id,
            GrowthStage.estimated_stage == "heading",
        )
        .order_by(GrowthStage.date)
        .first()
    )
    if heading_record is not None:
        return heading_record.date

    # 2) 積算温度から予測
    if field.transplant_date is None or field.nearest_amedas is None:
        return None

    variety = field.variety
    if variety not in GROWTH_STAGES:
        return None

    acc_temp = calc_accumulated_temp(
        station_id=field.nearest_amedas,
        start_date=field.transplant_date,
        end_date=today,
        field_elevation=field.elevation_m,
    )

    heading_start_temp = GROWTH_STAGES[variety]["heading"]["temp_range"][0]

    if acc_temp >= heading_start_temp:
        # すでに出穂期に入っている → 今日を出穂日と仮定
        return today

    # 直近の日平均気温から出穂日を推定
    recent_rows = (
        db.query(DailyWeather.avg_temp)
        .filter(
            DailyWeather.station_id == field.nearest_amedas,
            DailyWeather.date >= today - timedelta(days=7),
            DailyWeather.date <= today,
            DailyWeather.avg_temp.isnot(None),
        )
        .all()
    )
    if recent_rows:
        recent_avg = sum(r[0] for r in recent_rows) / len(recent_rows)
    else:
        recent_avg = 20.0

    daily_effective = max(recent_avg - settings.base_temperature, 0.1)
    remaining = heading_start_temp - acc_temp
    days_to_heading = int(remaining / daily_effective)
    return today + timedelta(days=days_to_heading)


def assess_heat_stress(field_id: int) -> dict:
    """高温障害リスクを判定する。

    出穂後 20 日間の日平均気温を評価し、白未熟粒の発生リスクを判定する。

    Parameters
    ----------
    field_id : int
        圃場 ID。

    Returns
    -------
    dict
        risk_level : str             - "low" / "moderate" / "high"
        avg_temp_post_heading : float or None - 出穂後の平均気温
        days_post_heading : int      - 出穂後経過日数
        heading_date : date or None  - 推定出穂日
        message : str                - ユーザ向けメッセージ
    """
    db: Session = SessionLocal()
    try:
        field = db.query(Field).filter(Field.id == field_id).first()
        if field is None:
            raise ValueError(f"圃場が見つかりません: field_id={field_id}")

        station_id = field.nearest_amedas
        if station_id is None:
            raise ValueError("最寄りアメダス地点が設定されていません。")

        today = date.today()
        heading_date = _estimate_heading_date(db, field, today)

        if heading_date is None:
            return {
                "risk_level": "low",
                "avg_temp_post_heading": None,
                "days_post_heading": 0,
                "heading_date": None,
                "message": (
                    f"【{field.name}】出穂日を推定できません。"
                    "田植え日・品種情報を確認してください。"
                ),
            }

        days_post_heading = (today - heading_date).days
        eval_days = settings.heat_stress_eval_days  # 20

        if days_post_heading < 0:
            # まだ出穂していない
            return {
                "risk_level": "low",
                "avg_temp_post_heading": None,
                "days_post_heading": 0,
                "heading_date": heading_date,
                "message": (
                    f"【{field.name}】出穂予測日は "
                    f"{heading_date.strftime('%m/%d')} です。"
                    f"出穂後に高温障害リスクを評価します。"
                ),
            }

        # 出穂後の日平均気温・最低気温（夜温）を取得
        eval_end = min(heading_date + timedelta(days=eval_days), today)
        rows = (
            db.query(DailyWeather.avg_temp, DailyWeather.min_temp)
            .filter(
                DailyWeather.station_id == station_id,
                DailyWeather.date > heading_date,
                DailyWeather.date <= eval_end,
                DailyWeather.avg_temp.isnot(None),
            )
            .all()
        )

        if not rows:
            return {
                "risk_level": "low",
                "avg_temp_post_heading": None,
                "avg_night_temp": None,
                "days_post_heading": days_post_heading,
                "heading_date": heading_date,
                "message": (
                    f"【{field.name}】出穂後の気象データがまだありません。"
                ),
            }

        avg_temp = sum(r[0] for r in rows) / len(rows)
        avg_temp = round(avg_temp, 1)

        # 夜温（最低気温の平均）
        night_temps = [r[1] for r in rows if r[1] is not None]
        avg_night_temp = (
            round(sum(night_temps) / len(night_temps), 1)
            if night_temps
            else None
        )

        # リスク判定（日平均気温 + 夜温の二段階判定）
        high_temp = settings.heat_stress_high_temp         # 27.0
        moderate_temp = settings.heat_stress_moderate_temp  # 26.0
        night_high = settings.heat_stress_night_high_temp   # 23.0

        if avg_temp >= high_temp:
            risk_level = "high"
        elif avg_temp >= moderate_temp:
            risk_level = "moderate"
            # 夜温も高い場合はリスクを1段階引き上げ
            if avg_night_temp is not None and avg_night_temp >= night_high:
                risk_level = "high"
        else:
            risk_level = "low"

        # メッセージ生成
        risk_labels = {"low": "低", "moderate": "中", "high": "高"}
        messages = [
            f"【{field.name}】高温障害リスク: {risk_labels[risk_level]}"
        ]
        messages.append(
            f"出穂日: {heading_date.strftime('%m/%d')}　"
            f"出穂後 {days_post_heading} 日経過"
        )
        messages.append(
            f"出穂後 {len(rows)} 日間の平均気温: {avg_temp:.1f}℃"
        )
        if avg_night_temp is not None:
            messages.append(f"夜温（平均最低気温）: {avg_night_temp:.1f}℃")

        if risk_level == "high":
            messages.append(
                "白未熟粒の発生リスクが高い状態です。"
                "掛け流しかんがい・夜間入水を検討してください。"
            )
        elif risk_level == "moderate":
            messages.append(
                "やや高温傾向です。水管理に注意してください。"
            )
        else:
            messages.append(
                "現在のところ高温障害の心配は少ない状況です。"
            )

        return {
            "risk_level": risk_level,
            "avg_temp_post_heading": avg_temp,
            "avg_night_temp": avg_night_temp,
            "days_post_heading": days_post_heading,
            "heading_date": heading_date,
            "message": "\n".join(messages),
        }
    finally:
        db.close()
