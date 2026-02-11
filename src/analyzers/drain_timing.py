"""落水タイミング判定モジュール

出穂後の収穫判定は「日平均気温そのまま（基準温度を引かない）」の積算で行う。
農学標準では出穂後の日平均気温積算 ≒ 1000℃日 で成熟期（収穫適期）。
"""

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from src.models.database import SessionLocal, Field, DailyWeather, GrowthStage
from src.analyzers.accumulated_temp import calc_accumulated_temp
from src.analyzers.growth_stage import estimate_growth_stage, GROWTH_STAGES
from config.settings import settings


# 出穂後に成熟期到達とみなす積算温度（℃日）
# ※ 有効積算温度ではなく日平均気温そのまま積算
_MATURITY_ACCUMULATED_TEMP = 1000.0

# 落水推奨日は推定収穫日の何日前か
_DRAIN_LEAD_DAYS_MIN = 7
_DRAIN_LEAD_DAYS_MAX = 10


def _estimate_heading_date(
    db: Session, field: "Field", today: date
) -> date | None:
    """出穂日を推定する。

    GrowthStage テーブルに出穂期の記録があればその日付を返す。
    なければ積算温度から予測する。
    """
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

    # 積算温度から予測
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
        return today

    # 直近の日平均気温で推定
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
    recent_avg = (
        sum(r[0] for r in recent_rows) / len(recent_rows)
        if recent_rows
        else 20.0
    )

    daily_effective = max(recent_avg - settings.base_temperature, 0.1)
    remaining = heading_start_temp - acc_temp
    days_to_heading = int(remaining / daily_effective)
    return today + timedelta(days=days_to_heading)


def _get_recent_avg_temp(db: Session, station_id: str, days: int = 7) -> float:
    """直近 N 日間の日平均気温の平均を返す。"""
    end = date.today()
    start = end - timedelta(days=days)
    rows = (
        db.query(DailyWeather.avg_temp)
        .filter(
            DailyWeather.station_id == station_id,
            DailyWeather.date >= start,
            DailyWeather.date <= end,
            DailyWeather.avg_temp.isnot(None),
        )
        .all()
    )
    if not rows:
        return 20.0
    return sum(r[0] for r in rows) / len(rows)


def assess_drain_timing(field_id: int) -> dict:
    """落水タイミングを判定する。

    出穂後の積算温度が 1000 ℃日 に達した時点を成熟期（収穫適期）と
    推定し、その 7〜10 日前を落水推奨日とする。

    Parameters
    ----------
    field_id : int
        圃場 ID。

    Returns
    -------
    dict
        estimated_harvest_date : date or None  - 推定収穫日
        recommended_drain_date : date or None  - 落水推奨日（最早）
        recommended_drain_end  : date or None  - 落水推奨日（最遅）
        days_to_drain : int or None            - 落水までの日数
        heading_date : date or None            - 出穂日
        message : str                          - ユーザ向けメッセージ
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
                "estimated_harvest_date": None,
                "recommended_drain_date": None,
                "recommended_drain_end": None,
                "days_to_drain": None,
                "heading_date": None,
                "message": (
                    f"【{field.name}】出穂日を推定できません。"
                    "田植え日・品種情報を確認してください。"
                ),
            }

        # 出穂後の積算温度を計算（日平均気温そのまま積算、基準温度を引かない）
        if heading_date <= today:
            rows = (
                db.query(DailyWeather.avg_temp)
                .filter(
                    DailyWeather.station_id == station_id,
                    DailyWeather.date > heading_date,
                    DailyWeather.date <= today,
                    DailyWeather.avg_temp.isnot(None),
                )
                .all()
            )
            post_heading_acc = sum(r[0] for r in rows) if rows else 0.0
        else:
            post_heading_acc = 0.0

        # 直近の日平均気温（収穫日予測にも日平均気温そのまま使用）
        recent_avg = _get_recent_avg_temp(db, station_id)
        daily_avg_for_harvest = max(recent_avg, 1.0)

        # 成熟期（収穫適期）までの残り積算温度
        remaining = max(_MATURITY_ACCUMULATED_TEMP - post_heading_acc, 0.0)
        days_to_maturity = int(remaining / daily_avg_for_harvest)

        if heading_date > today:
            # まだ出穂前 → 出穂日からの日数を加算
            days_to_maturity += (heading_date - today).days

        estimated_harvest_date = today + timedelta(days=days_to_maturity)

        # 落水推奨日
        recommended_drain_date = estimated_harvest_date - timedelta(
            days=_DRAIN_LEAD_DAYS_MAX
        )
        recommended_drain_end = estimated_harvest_date - timedelta(
            days=_DRAIN_LEAD_DAYS_MIN
        )

        days_to_drain = (recommended_drain_date - today).days

        # ----- メッセージ生成 -----
        messages = [
            f"【{field.name}】落水タイミング判定"
        ]
        messages.append(
            f"出穂日: {heading_date.strftime('%m/%d')}　"
            f"出穂後積算温度: {post_heading_acc:.0f}℃日"
        )
        messages.append(
            f"推定収穫日: {estimated_harvest_date.strftime('%m/%d')}"
        )
        messages.append(
            f"落水推奨期間: "
            f"{recommended_drain_date.strftime('%m/%d')} 〜 "
            f"{recommended_drain_end.strftime('%m/%d')}"
        )

        if days_to_drain <= 0:
            messages.append(
                "落水推奨時期に入っています。圃場の水を落としてください。"
            )
        elif days_to_drain <= 7:
            messages.append(
                f"あと約 {days_to_drain} 日で落水推奨時期です。準備を始めてください。"
            )
        else:
            messages.append(
                f"落水まであと約 {days_to_drain} 日です。"
            )

        return {
            "estimated_harvest_date": estimated_harvest_date,
            "recommended_drain_date": recommended_drain_date,
            "recommended_drain_end": recommended_drain_end,
            "days_to_drain": days_to_drain,
            "heading_date": heading_date,
            "message": "\n".join(messages),
        }
    finally:
        db.close()
