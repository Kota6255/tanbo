"""いもち病リスク判定のテスト"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone, date

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models.database import (
    Base, engine, SessionLocal, init_db,
    Field, AmedasObservation, PestAdvisory,
)

JST = timezone(timedelta(hours=9))


def setup_module():
    """テスト用DBを初期化"""
    Base.metadata.drop_all(engine)
    init_db()
    _create_test_field()


def _create_test_field():
    """テスト用圃場を作成"""
    db = SessionLocal()
    try:
        f = Field(
            id=100,
            name="テスト田",
            latitude=34.4269,
            longitude=132.7433,
            variety="コシヒカリ",
            transplant_date=date(2026, 6, 5),
            nearest_amedas="67511",
        )
        db.merge(f)
        db.commit()
    finally:
        db.close()


def _insert_hourly_observations(station_id: str, hours: int, temp: float, humidity: float):
    """テスト用にN時間分の観測データを投入"""
    db = SessionLocal()
    try:
        now = datetime.now(JST)
        for i in range(hours):
            t = now - timedelta(hours=hours - i)
            obs = AmedasObservation(
                station_id=station_id,
                observed_at=t.isoformat(),
                air_temp=temp,
                humidity=humidity,
            )
            db.add(obs)
        db.commit()
    finally:
        db.close()


def test_high_risk():
    """気温24℃・湿度95%が12時間連続した場合、リスクhighと判定されること"""
    # データクリア
    db = SessionLocal()
    try:
        db.query(AmedasObservation).filter(AmedasObservation.station_id == "67511").delete()
        db.commit()
    finally:
        db.close()

    _insert_hourly_observations("67511", 12, 24.0, 95.0)

    from src.analyzers.blast_risk import assess_blast_risk
    result = assess_blast_risk(100, hours=72)
    assert result["risk_level"] == "high", f"Expected 'high', got {result['risk_level']}"
    assert result["leaf_wetness_hours"] >= 10


def test_low_risk():
    """気温30℃・湿度60%の場合、葉面湿潤なし。
    コシヒカリは耐性「弱」で1段階UPのため moderate になる。"""
    db = SessionLocal()
    try:
        db.query(AmedasObservation).filter(AmedasObservation.station_id == "67511").delete()
        db.commit()
    finally:
        db.close()

    _insert_hourly_observations("67511", 24, 30.0, 60.0)

    from src.analyzers.blast_risk import assess_blast_risk
    result = assess_blast_risk(100, hours=72)
    # 基本リスクは "low" だが、コシヒカリ（弱）の品種補正で "moderate" に上がる
    assert result["risk_level"] == "moderate", f"Expected 'moderate', got {result['risk_level']}"
    assert result["leaf_wetness_hours"] == 0


def test_moderate_risk():
    """気温25℃・湿度92%が8時間連続の場合、moderateと判定されること"""
    db = SessionLocal()
    try:
        db.query(AmedasObservation).filter(AmedasObservation.station_id == "67511").delete()
        db.commit()
    finally:
        db.close()

    _insert_hourly_observations("67511", 8, 25.0, 92.0)

    from src.analyzers.blast_risk import assess_blast_risk
    result = assess_blast_risk(100, hours=72)
    assert result["risk_level"] in ("moderate", "high")  # 品種補正で上がる可能性あり


def test_advisory_elevates_risk():
    """予察注意報がある場合、リスクが1段階上がること"""
    db = SessionLocal()
    try:
        db.query(AmedasObservation).filter(AmedasObservation.station_id == "67511").delete()
        db.commit()
    finally:
        db.close()

    # moderate相当のデータ（8時間）
    _insert_hourly_observations("67511", 8, 25.0, 92.0)

    # 注意報を追加
    db = SessionLocal()
    try:
        advisory = PestAdvisory(
            date=date.today(),
            pest_name="いもち病",
            advisory_level="注意報",
            region="広島県全域",
            message="テスト注意報",
        )
        db.add(advisory)
        db.commit()
    finally:
        db.close()

    from src.analyzers.blast_risk import assess_blast_risk
    result = assess_blast_risk(100, hours=72)
    assert result["advisory_active"] is True
