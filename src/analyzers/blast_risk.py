"""いもち病リスク判定モジュール（簡易 BLASTAM）

幼穂形成期〜出穂期はいもち病（穂いもち）の感受性が高いため、
湿度閾値を 90% → 85% に引き下げてリスク判定を行う。
"""

from datetime import date, datetime, timedelta

from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.models.database import SessionLocal, Field, AmedasObservation, PestAdvisory
from src.analyzers.accumulated_temp import calc_accumulated_temp
from src.analyzers.growth_stage import estimate_growth_stage, GROWTH_STAGES
from config.settings import settings

# 幼穂形成期〜出穂期（穂いもち危険期）のステージ
_PANICLE_SENSITIVE_STAGES = {"panicle_formation", "booting", "heading"}


# 品種別いもち病耐性（「弱」の品種はリスク 1 段階 UP）
_VARIETY_RESISTANCE = {
    "コシヒカリ": "弱",
    "ヒノヒカリ": "中",
    "あきろまん": "中",
}

_RISK_LEVELS = ["low", "moderate", "high"]
_RISK_LABELS = {
    "low": "低",
    "moderate": "中",
    "high": "高",
}


def _count_consecutive_wetness(
    observations: list,
    humidity_threshold: float | None = None,
) -> tuple[float, float]:
    """気温 20-28 ℃ かつ 湿度閾値以上の最大連続時間と
    その間の平均気温を返す。

    Parameters
    ----------
    observations : list[AmedasObservation]
        時系列順（古い→新しい）の観測データ。
    humidity_threshold : float or None
        湿度閾値。None の場合は settings のデフォルト値 (90%) を使用。
        幼穂形成期〜出穂期は 85% に引き下げる。

    Returns
    -------
    tuple[float, float]
        (最大連続湿潤時間, 湿潤時間中の平均気温)
    """
    temp_min = settings.blast_optimal_temp_min   # 20.0
    temp_max = settings.blast_optimal_temp_max   # 28.0
    if humidity_threshold is None:
        humidity_threshold = settings.blast_humidity_threshold  # 90.0

    max_consecutive = 0
    current_consecutive = 0
    wetness_temps = []
    current_temps = []

    for obs in observations:
        if obs.air_temp is None or obs.humidity is None:
            # データ欠損は連続途切れとみなす
            if current_consecutive > max_consecutive:
                max_consecutive = current_consecutive
                wetness_temps = list(current_temps)
            current_consecutive = 0
            current_temps = []
            continue

        is_wet = (
            temp_min <= obs.air_temp <= temp_max
            and obs.humidity >= humidity_threshold
        )

        if is_wet:
            current_consecutive += 1
            current_temps.append(obs.air_temp)
        else:
            if current_consecutive > max_consecutive:
                max_consecutive = current_consecutive
                wetness_temps = list(current_temps)
            current_consecutive = 0
            current_temps = []

    # 末尾チェック
    if current_consecutive > max_consecutive:
        max_consecutive = current_consecutive
        wetness_temps = list(current_temps)

    avg_temp = (
        sum(wetness_temps) / len(wetness_temps) if wetness_temps else 0.0
    )
    return float(max_consecutive), round(avg_temp, 1)


def _check_advisory_active(db: Session, days: int = 14) -> bool:
    """直近 N 日以内にいもち病の注意報が出ているか確認する。"""
    cutoff = date.today() - timedelta(days=days)
    advisory = (
        db.query(PestAdvisory)
        .filter(
            PestAdvisory.pest_name.like("%いもち%"),
            PestAdvisory.date >= cutoff,
        )
        .first()
    )
    return advisory is not None


def _escalate_risk(level: str, steps: int = 1) -> str:
    """リスクレベルを指定段階だけ引き上げる。"""
    idx = _RISK_LEVELS.index(level)
    new_idx = min(idx + steps, len(_RISK_LEVELS) - 1)
    return _RISK_LEVELS[new_idx]


def assess_blast_risk(field_id: int, hours: int = 72) -> dict:
    """いもち病リスクを判定する。

    Parameters
    ----------
    field_id : int
        圃場 ID。
    hours : int
        過去何時間分の観測データを使用するか（デフォルト 72 時間）。

    Returns
    -------
    dict
        risk_level : str               - "low" / "moderate" / "high"
        leaf_wetness_hours : float      - 最大連続葉面湿潤時間
        avg_temp_during_wetness : float - 湿潤時間中の平均気温
        advisory_active : bool          - 注意報発令中か
        message : str                   - ユーザ向けメッセージ
    """
    db: Session = SessionLocal()
    try:
        field = db.query(Field).filter(Field.id == field_id).first()
        if field is None:
            raise ValueError(f"圃場が見つかりません: field_id={field_id}")

        station_id = field.nearest_amedas
        if station_id is None:
            raise ValueError("最寄りアメダス地点が設定されていません。")

        # 過去 N 時間の観測データを取得
        cutoff = datetime.now() - timedelta(hours=hours)
        cutoff_str = cutoff.isoformat()

        observations = (
            db.query(AmedasObservation)
            .filter(
                AmedasObservation.station_id == station_id,
                AmedasObservation.observed_at >= cutoff_str,
            )
            .order_by(AmedasObservation.observed_at)
            .all()
        )

        # ----- 生育ステージ判定 -----
        current_stage = None
        try:
            variety = field.variety
            if field.transplant_date and variety in GROWTH_STAGES:
                acc_temp = calc_accumulated_temp(
                    station_id=station_id,
                    start_date=field.transplant_date,
                    end_date=date.today(),
                    field_elevation=field.elevation_m,
                )
                stage_info = estimate_growth_stage(variety, acc_temp)
                current_stage = stage_info["stage"]
        except Exception:
            pass  # ステージ取得失敗時は通常閾値で判定

        # 幼穂形成期〜出穂期は湿度閾値を引き下げ
        is_panicle_sensitive = current_stage in _PANICLE_SENSITIVE_STAGES
        humidity_thresh = (
            settings.blast_humidity_threshold_panicle  # 85.0
            if is_panicle_sensitive
            else None  # デフォルト 90.0
        )

        # 葉面湿潤時間を計算
        leaf_wetness_hours, avg_temp = _count_consecutive_wetness(
            observations, humidity_threshold=humidity_thresh
        )

        # 基本リスク判定
        high_threshold = settings.blast_risk_threshold_hours       # 10.0
        moderate_threshold = settings.blast_moderate_threshold_hours  # 6.0

        if leaf_wetness_hours >= high_threshold:
            risk_level = "high"
        elif leaf_wetness_hours >= moderate_threshold:
            risk_level = "moderate"
        else:
            risk_level = "low"

        # 注意報チェック
        advisory_active = _check_advisory_active(db)
        if advisory_active:
            risk_level = _escalate_risk(risk_level)

        # 品種耐性チェック
        variety = field.variety
        resistance = _VARIETY_RESISTANCE.get(variety, "中")
        if resistance == "弱":
            risk_level = _escalate_risk(risk_level)

        # ----- メッセージ生成 -----
        risk_label = _RISK_LABELS[risk_level]
        messages = [
            f"【{field.name}】いもち病リスク: {risk_label}"
        ]

        messages.append(
            f"過去 {hours} 時間の最大連続葉面湿潤時間: {leaf_wetness_hours:.0f} 時間"
        )

        if avg_temp > 0:
            messages.append(f"湿潤時間中の平均気温: {avg_temp:.1f}℃")

        if advisory_active:
            messages.append("※ いもち病の注意報が発令中です。")

        if resistance == "弱":
            messages.append(f"※ {variety} はいもち病に弱い品種です。注意してください。")

        if is_panicle_sensitive:
            messages.append(
                f"※ 現在は穂いもち危険期（{current_stage}）のため、"
                "判定閾値を引き下げています。"
            )

        if risk_level == "high":
            messages.append(
                "感染リスクが高い状態です。予防的な薬剤散布を検討してください。"
            )
        elif risk_level == "moderate":
            messages.append(
                "やや感染リスクがあります。圃場の観察を強化してください。"
            )

        return {
            "risk_level": risk_level,
            "leaf_wetness_hours": leaf_wetness_hours,
            "avg_temp_during_wetness": avg_temp,
            "advisory_active": advisory_active,
            "is_panicle_sensitive": is_panicle_sensitive,
            "current_stage": current_stage,
            "message": "\n".join(messages),
        }
    finally:
        db.close()
