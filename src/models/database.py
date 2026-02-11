"""SQLAlchemy モデル定義 - たんぼアドバイザー"""

from datetime import datetime, date

from sqlalchemy import (
    create_engine, Column, Integer, Text, Date, Float,
    ForeignKey, UniqueConstraint, CheckConstraint, Index,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from config.settings import settings

engine = create_engine(settings.database_url, echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Field(Base):
    """圃場マスタ"""
    __tablename__ = "fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    area_m2 = Column(Float)
    variety = Column(Text, nullable=False)
    transplant_date = Column(Date)
    nearest_amedas = Column(Text)
    elevation_m = Column(Float)
    line_user_id = Column(Text)
    created_at = Column(Text, default=lambda: datetime.now().isoformat())

    sensor_readings = relationship("SensorReading", back_populates="field")
    growth_stages = relationship("GrowthStage", back_populates="field")
    blast_risk_logs = relationship("BlastRiskLog", back_populates="field")
    notifications = relationship("Notification", back_populates="field")


class AmedasObservation(Base):
    """アメダス観測データ（1時間ごと蓄積）"""
    __tablename__ = "amedas_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(Text, nullable=False)
    observed_at = Column(Text, nullable=False)
    air_temp = Column(Float)
    humidity = Column(Float)
    precipitation_1h = Column(Float)
    wind_speed = Column(Float)
    sunshine_1h = Column(Float)
    pressure = Column(Float)

    __table_args__ = (
        UniqueConstraint("station_id", "observed_at"),
        Index("idx_amedas_station_time", "station_id", "observed_at"),
    )


class DailyWeather(Base):
    """日別気象サマリ（積算温度計算用）"""
    __tablename__ = "daily_weather"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(Text, nullable=False)
    date = Column(Date, nullable=False)
    avg_temp = Column(Float)
    max_temp = Column(Float)
    min_temp = Column(Float)
    total_precipitation = Column(Float)
    avg_humidity = Column(Float)
    total_sunshine = Column(Float)

    __table_args__ = (
        UniqueConstraint("station_id", "date"),
        Index("idx_daily_station_date", "station_id", "date"),
    )


class SensorReading(Base):
    """センサーデータ（ESP32から取り込み）"""
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field_id = Column(Integer, ForeignKey("fields.id"))
    recorded_at = Column(Text, nullable=False)
    air_temp = Column(Float)
    humidity = Column(Float)
    pressure = Column(Float)
    water_temp = Column(Float)
    water_level = Column(Float)

    field = relationship("Field", back_populates="sensor_readings")

    __table_args__ = (
        UniqueConstraint("field_id", "recorded_at"),
        Index("idx_sensor_field_time", "field_id", "recorded_at"),
    )


class GrowthStage(Base):
    """生育ステージ履歴"""
    __tablename__ = "growth_stages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field_id = Column(Integer, ForeignKey("fields.id"))
    date = Column(Date, nullable=False)
    accumulated_temp = Column(Float)
    estimated_stage = Column(Text)
    tiller_count_estimate = Column(Float)
    days_from_transplant = Column(Integer)

    field = relationship("Field", back_populates="growth_stages")

    __table_args__ = (
        UniqueConstraint("field_id", "date"),
        Index("idx_growth_field_date", "field_id", "date"),
    )


class BlastRiskLog(Base):
    """いもち病リスク判定ログ"""
    __tablename__ = "blast_risk_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field_id = Column(Integer, ForeignKey("fields.id"))
    assessed_at = Column(Text, nullable=False)
    risk_level = Column(Text)
    avg_temp = Column(Float)
    avg_humidity = Column(Float)
    leaf_wetness_hours = Column(Float)
    notified = Column(Integer, default=0)

    field = relationship("Field", back_populates="blast_risk_logs")

    __table_args__ = (
        CheckConstraint("risk_level IN ('low', 'moderate', 'high')"),
        Index("idx_blast_field_time", "field_id", "assessed_at"),
    )


class Notification(Base):
    """LINE通知ログ"""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field_id = Column(Integer, ForeignKey("fields.id"))
    sent_at = Column(Text, default=lambda: datetime.now().isoformat())
    notification_type = Column(Text)
    message = Column(Text)
    delivered = Column(Integer, default=1)

    field = relationship("Field", back_populates="notifications")


class PestAdvisory(Base):
    """予察情報"""
    __tablename__ = "pest_advisories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    pest_name = Column(Text, nullable=False)
    advisory_level = Column(Text)
    region = Column(Text)
    message = Column(Text)
    source_url = Column(Text)


def init_db():
    """テーブル作成"""
    Base.metadata.create_all(engine)


def get_db():
    """DBセッション取得（FastAPI Depends用）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
