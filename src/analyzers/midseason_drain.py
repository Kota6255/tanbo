"""中干しタイミング判定モジュール"""

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from src.models.database import SessionLocal, Field, DailyWeather
from src.analyzers.accumulated_temp import calc_accumulated_temp
from src.analyzers.growth_stage import estimate_growth_stage, GROWTH_STAGES
from config.settings import settings


def _get_recent_avg_temp(db: Session, station_id: str, days: int = 7) -> float:
    """直近 N 日間の日平均気温の平均を返す。取得できない場合は 20.0 を返す。"""
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


def assess_midseason_drain(field_id: int) -> dict:
    """中干しタイミングを判定する。

    Parameters
    ----------
    field_id : int
        圃場 ID。

    Returns
    -------
    dict
        should_start : bool        - 中干しを開始すべきか
        should_end : bool          - 中干しを終了すべきか
        remaining_days : int or None - 中干し開始までの日数
        current_stage : str        - 現在のステージキー
        current_stage_label : str  - 現在のステージ日本語名
        accumulated_temp : float   - 現在の積算温度
        estimated_heading_date : date or None - 出穂予測日
        drain_deadline : date or None         - 中干し完了期限
        message : str              - ユーザ向けメッセージ
    """
    db: Session = SessionLocal()
    try:
        field = db.query(Field).filter(Field.id == field_id).first()
        if field is None:
            raise ValueError(f"圃場が見つかりません: field_id={field_id}")

        variety = field.variety
        transplant_date = field.transplant_date
        station_id = field.nearest_amedas

        if transplant_date is None:
            raise ValueError("田植え日が登録されていません。")
        if station_id is None:
            raise ValueError("最寄りアメダス地点が設定されていません。")
        if variety not in GROWTH_STAGES:
            raise ValueError(f"未対応の品種です: {variety}")

        today = date.today()

        # 積算温度を計算
        acc_temp = calc_accumulated_temp(
            station_id=station_id,
            start_date=transplant_date,
            end_date=today,
            field_elevation=field.elevation_m,
        )

        # 直近の日平均気温
        recent_temp = _get_recent_avg_temp(db, station_id)

        # 生育ステージ推定
        stage_info = estimate_growth_stage(variety, acc_temp, recent_temp)

        # 中干し開始判定
        should_start = stage_info["stage"] == "midseason_drain"

        # ----- 出穂予測日 -----
        heading_range = GROWTH_STAGES[variety]["heading"]["temp_range"]
        heading_start_temp = heading_range[0]  # 出穂期に入る積算温度

        daily_effective = max(recent_temp - settings.base_temperature, 0.1)
        remaining_to_heading = max(heading_start_temp - acc_temp, 0.0)
        days_to_heading = int(remaining_to_heading / daily_effective)
        estimated_heading_date = today + timedelta(days=days_to_heading)

        # 中干し完了期限 = 出穂予測日 - 30 日
        drain_deadline = estimated_heading_date - timedelta(days=30)

        # ----- メッセージ生成 -----
        messages = []
        messages.append(
            f"【{field.name}】品種: {variety}　"
            f"積算温度: {acc_temp:.0f}℃日　"
            f"生育ステージ: {stage_info['label']}"
        )

        if should_start:
            messages.append(
                "中干し適期に入っています。速やかに中干しを開始してください。"
            )
            messages.append(
                f"出穂予測日: {estimated_heading_date.strftime('%m/%d')}　"
                f"中干し完了期限: {drain_deadline.strftime('%m/%d')}"
            )

        # ----- 中干し事前通知 -----
        remaining_days = None
        if stage_info["stage"] in ("tillering", "max_tiller"):
            midseason_start = GROWTH_STAGES[variety]["midseason_drain"]["temp_range"][0]
            remaining = max(midseason_start - acc_temp, 0.0)
            remaining_days = int(remaining / daily_effective)
            messages.append(
                f"中干し開始まであと約 {remaining_days} 日（積算温度あと {remaining:.0f}℃日）"
            )

        # ----- 中干し終了判定 -----
        # drain_start_date が Field に記録されている場合、
        # 開始から 7〜10日で終了を推奨。出穂25日前を超えると強制終了。
        should_end = False
        drain_end_reason = None
        if hasattr(field, "drain_start_date") and field.drain_start_date is not None:
            drain_days = (today - field.drain_start_date).days
            heading_deadline_end = estimated_heading_date - timedelta(days=25)

            if drain_days >= 10:
                should_end = True
                drain_end_reason = f"中干し開始から{drain_days}日経過。十分に干せました。"
            elif drain_days >= 7 and today >= heading_deadline_end:
                should_end = True
                drain_end_reason = (
                    f"中干し{drain_days}日目。出穂前に間に合わせるため終了。"
                )

            if should_end:
                messages.append(drain_end_reason)
                messages.append(
                    "水を入れて間断かんがいに切り替えてください。"
                )
        elif stage_info["stage"] not in (
            "tillering", "max_tiller", "midseason_drain"
        ) and not should_start:
            messages.append(
                f"現在は {stage_info['label']} です。中干し適期は過ぎています。"
            )

        return {
            "should_start": should_start,
            "should_end": should_end,
            "remaining_days": remaining_days,
            "current_stage": stage_info["stage"],
            "current_stage_label": stage_info["label"],
            "accumulated_temp": acc_temp,
            "estimated_heading_date": estimated_heading_date,
            "drain_deadline": drain_deadline,
            "message": "\n".join(messages),
        }
    finally:
        db.close()
