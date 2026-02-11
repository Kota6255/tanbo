"""通知メッセージ組み立てのテスト"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.notifiers.message_builder import (
    build_morning_message,
    build_blast_alert,
    build_drain_reminder,
    build_heat_stress_alert,
)


def _make_stage_info(**overrides):
    base = {
        "stage": "tillering",
        "label": "分げつ期",
        "progress_pct": 60,
        "days_to_next": 5,
        "next_stage_label": "最高分げつ期",
        "accumulated_temp": 280.0,
    }
    base.update(overrides)
    return base


def test_morning_message_contains_stage():
    """朝のメッセージに生育ステージが含まれること"""
    msg = build_morning_message(
        field_name="家の前の田",
        variety="コシヒカリ",
        days_from_transplant=30,
        stage_info=_make_stage_info(),
        drain_info={},
        blast_info={"risk_level": "low"},
        heat_info={"risk_level": "low"},
        forecast_text="【天気】\n今日: 晴れ 最高28℃",
    )
    assert "分げつ期" in msg
    assert "家の前の田" in msg
    assert "コシヒカリ" in msg
    assert "30日目" in msg


def test_morning_message_with_drain():
    """中干し推奨時のメッセージに中干し情報が含まれること"""
    msg = build_morning_message(
        field_name="家の前の田",
        variety="コシヒカリ",
        days_from_transplant=40,
        stage_info=_make_stage_info(stage="midseason_drain", label="中干し適期"),
        drain_info={"should_start": True, "drain_deadline": "7月10日"},
        blast_info={"risk_level": "low"},
        heat_info={"risk_level": "low"},
        forecast_text="【天気】\n今日: 曇り 最高25℃",
    )
    assert "中干し" in msg


def test_blast_alert_message():
    """いもち病アラートメッセージの文面が規定通りであること"""
    msg = build_blast_alert(
        field_name="家の前の田",
        variety="コシヒカリ",
        blast_info={
            "risk_level": "high",
            "leaf_wetness_hours": 14.5,
            "avg_temp_during_wetness": 24.3,
            "advisory_active": True,
        },
    )
    assert "いもち病" in msg
    assert "14時間" in msg
    assert "注意報" in msg
    assert "葉の裏を確認" in msg


def test_drain_reminder_message():
    """中干しリマインダーメッセージの内容確認"""
    msg = build_drain_reminder(
        field_name="家の前の田",
        variety="コシヒカリ",
        drain_info={
            "estimated_heading_date": "8月9日",
            "drain_deadline": "7月10日",
        },
    )
    assert "中干し" in msg
    assert "7月10日" in msg
    assert "8月9日" in msg


def test_heat_stress_alert():
    """高温障害アラートメッセージの内容確認"""
    msg = build_heat_stress_alert(
        field_name="家の前の田",
        variety="コシヒカリ",
        heat_info={
            "risk_level": "high",
            "avg_temp_post_heading": 27.5,
            "days_post_heading": 15,
        },
    )
    assert "高温障害" in msg
    assert "27.5" in msg
    assert "掛け流し" in msg


def test_morning_message_no_action():
    """特にアクションがない場合、順調メッセージが表示されること"""
    msg = build_morning_message(
        field_name="山の田",
        variety="ヒノヒカリ",
        days_from_transplant=20,
        stage_info=_make_stage_info(stage="tillering"),
        drain_info={},
        blast_info={"risk_level": "low"},
        heat_info={"risk_level": "low"},
        forecast_text="【天気】\n今日: 晴れ 最高30℃",
    )
    assert "順調" in msg
