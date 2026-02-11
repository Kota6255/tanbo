"""生育ステージ推定のテスト"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analyzers.growth_stage import estimate_growth_stage


def test_koshihikari_tillering():
    """コシヒカリで積算温度200℃日のとき、分げつ期と判定されること"""
    result = estimate_growth_stage("コシヒカリ", 200.0)
    assert result["stage"] == "tillering"
    assert result["label"] == "分げつ期"


def test_koshihikari_midseason_drain():
    """コシヒカリで積算温度550℃日のとき、中干し適期と判定されること"""
    result = estimate_growth_stage("コシヒカリ", 550.0)
    assert result["stage"] == "midseason_drain"
    assert result["label"] == "中干し適期"


def test_koshihikari_heading():
    """コシヒカリで積算温度1050℃日のとき、出穂期と判定されること"""
    result = estimate_growth_stage("コシヒカリ", 1050.0)
    assert result["stage"] == "heading"
    assert result["label"] == "出穂期"


def test_koshihikari_maturity():
    """コシヒカリで積算温度1700℃日のとき、成熟期と判定されること"""
    result = estimate_growth_stage("コシヒカリ", 1700.0)
    assert result["stage"] == "maturity"
    assert result["label"] == "成熟期"


def test_hinohikari_heading():
    """ヒノヒカリは出穂が遅い（積算温度1200必要）"""
    result = estimate_growth_stage("ヒノヒカリ", 1050.0)
    # 1050はヒノヒカリではまだ穂ばらみ期
    assert result["stage"] in ("booting", "heading")


def test_progress_percentage():
    """ステージ内の進行度が0-100%の範囲であること"""
    result = estimate_growth_stage("コシヒカリ", 575.0)
    assert 0 <= result["progress_pct"] <= 100


def test_days_to_next():
    """次ステージまでの日数が正の整数であること"""
    result = estimate_growth_stage("コシヒカリ", 400.0)
    assert result["days_to_next"] is not None
    assert result["days_to_next"] > 0


def test_unknown_variety():
    """未登録品種の場合はValueErrorが発生すること"""
    import pytest
    with pytest.raises(ValueError, match="未対応の品種"):
        estimate_growth_stage("未知の品種", 500.0)
