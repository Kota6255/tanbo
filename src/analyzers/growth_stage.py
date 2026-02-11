"""生育ステージ推定モジュール"""

from datetime import date, datetime, timedelta
from typing import Optional

from config.settings import settings


# ---------------------------------------------------------------------------
# 品種別 生育ステージ定義
# temp_range: (下限積算温度, 上限積算温度)  ※ None は上限なし
# ---------------------------------------------------------------------------
GROWTH_STAGES = {
    "コシヒカリ": {
        "tillering":          {"temp_range": (0, 350),    "label": "分げつ期"},
        "max_tiller":         {"temp_range": (350, 500),  "label": "最高分げつ期"},
        "midseason_drain":    {"temp_range": (500, 650),  "label": "中干し適期"},
        "panicle_formation":  {"temp_range": (650, 800),  "label": "幼穂形成期"},
        "booting":            {"temp_range": (800, 950),  "label": "穂ばらみ期"},
        "heading":            {"temp_range": (950, 1100), "label": "出穂期"},
        "grain_filling":      {"temp_range": (1100, 1600), "label": "登熟期"},
        "maturity":           {"temp_range": (1600, None), "label": "成熟期"},
    },
    "ヒノヒカリ": {
        "tillering":          {"temp_range": (0, 400),    "label": "分げつ期"},
        "max_tiller":         {"temp_range": (400, 560),  "label": "最高分げつ期"},
        "midseason_drain":    {"temp_range": (560, 720),  "label": "中干し適期"},
        "panicle_formation":  {"temp_range": (720, 880),  "label": "幼穂形成期"},
        "booting":            {"temp_range": (880, 1040),  "label": "穂ばらみ期"},
        "heading":            {"temp_range": (1040, 1200), "label": "出穂期"},
        "grain_filling":      {"temp_range": (1200, 1750), "label": "登熟期"},
        "maturity":           {"temp_range": (1750, None), "label": "成熟期"},
    },
    "あきろまん": {
        "tillering":          {"temp_range": (0, 380),    "label": "分げつ期"},
        "max_tiller":         {"temp_range": (380, 540),  "label": "最高分げつ期"},
        "midseason_drain":    {"temp_range": (540, 700),  "label": "中干し適期"},
        "panicle_formation":  {"temp_range": (700, 860),  "label": "幼穂形成期"},
        "booting":            {"temp_range": (860, 1010),  "label": "穂ばらみ期"},
        "heading":            {"temp_range": (1010, 1150), "label": "出穂期"},
        "grain_filling":      {"temp_range": (1150, 1700), "label": "登熟期"},
        "maturity":           {"temp_range": (1700, None), "label": "成熟期"},
    },
}

# ステージの順序リスト（進行順）
_STAGE_ORDER = [
    "tillering",
    "max_tiller",
    "midseason_drain",
    "panicle_formation",
    "booting",
    "heading",
    "grain_filling",
    "maturity",
]


def estimate_growth_stage(
    variety: str,
    accumulated_temp: float,
    recent_daily_temp: float = 20.0,
) -> dict:
    """積算温度から現在の生育ステージを推定する。

    Parameters
    ----------
    variety : str
        品種名（例: "コシヒカリ"）。
    accumulated_temp : float
        現在の有効積算温度 (℃日)。
    recent_daily_temp : float
        直近の日平均気温 (℃)。次ステージまでの日数推定に使用。

    Returns
    -------
    dict
        stage : str          - ステージキー（例: "heading"）
        label : str          - 日本語ラベル（例: "出穂期"）
        progress_pct : float - 現ステージ内の進捗 (0-100%)
        days_to_next : int or None - 次ステージまでの推定日数
        next_stage_label : str or None - 次ステージの日本語ラベル
    """
    if variety not in GROWTH_STAGES:
        raise ValueError(f"未対応の品種です: {variety}")

    stages = GROWTH_STAGES[variety]
    base_temp = settings.base_temperature  # 10.0

    current_stage = None
    current_info = None

    for stage_key in _STAGE_ORDER:
        info = stages[stage_key]
        low, high = info["temp_range"]
        if high is None:
            # 最終ステージ（上限なし）
            if accumulated_temp >= low:
                current_stage = stage_key
                current_info = info
                break
        else:
            if low <= accumulated_temp < high:
                current_stage = stage_key
                current_info = info
                break

    # 積算温度が 0 未満のフォールバック
    if current_stage is None:
        current_stage = _STAGE_ORDER[0]
        current_info = stages[current_stage]

    low, high = current_info["temp_range"]

    # ----- 進捗率 -----
    if high is None:
        # 成熟期: 上限なしなので 100% とする
        progress_pct = 100.0
    else:
        span = high - low
        progress_pct = min(max((accumulated_temp - low) / span * 100, 0.0), 100.0)

    # ----- 次ステージ情報 -----
    idx = _STAGE_ORDER.index(current_stage)
    if idx + 1 < len(_STAGE_ORDER):
        next_stage_key = _STAGE_ORDER[idx + 1]
        next_info = stages[next_stage_key]
        next_stage_label = next_info["label"]

        # 次ステージ開始までの残り積算温度
        next_low = next_info["temp_range"][0]
        remaining_temp = max(next_low - accumulated_temp, 0.0)

        # 日あたりの有効積算温度
        daily_effective = max(recent_daily_temp - base_temp, 0.1)
        days_to_next = int(remaining_temp / daily_effective) + (
            1 if remaining_temp % daily_effective > 0 else 0
        )
    else:
        next_stage_label = None
        days_to_next = None

    return {
        "stage": current_stage,
        "label": current_info["label"],
        "progress_pct": round(progress_pct, 1),
        "days_to_next": days_to_next,
        "next_stage_label": next_stage_label,
    }
