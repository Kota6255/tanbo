"""ESP32 CSVデータ取り込み"""

import csv
import logging
from pathlib import Path

from src.models.database import SessionLocal, SensorReading
from sqlalchemy import select

logger = logging.getLogger(__name__)


def import_sensor_csv(file_path: str, field_id: int) -> int:
    """
    ESP32が出力したCSVファイルをDBに取り込む。

    CSVフォーマット:
        timestamp,air_temp,humidity,pressure,water_temp,water_level

    Returns:
        imported_count: 取り込み件数
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    db = SessionLocal()
    imported = 0

    try:
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                recorded_at = row["timestamp"]

                # 重複チェック
                existing = db.execute(
                    select(SensorReading).where(
                        SensorReading.field_id == field_id,
                        SensorReading.recorded_at == recorded_at,
                    )
                ).scalar_one_or_none()

                if existing is not None:
                    continue

                reading = SensorReading(
                    field_id=field_id,
                    recorded_at=recorded_at,
                    air_temp=_float_or_none(row.get("air_temp")),
                    humidity=_float_or_none(row.get("humidity")),
                    pressure=_float_or_none(row.get("pressure")),
                    water_temp=_float_or_none(row.get("water_temp")),
                    water_level=_float_or_none(row.get("water_level")),
                )
                db.add(reading)
                imported += 1

        db.commit()
        logger.info("Imported %d sensor readings from %s for field %d", imported, file_path, field_id)
    finally:
        db.close()

    return imported


def _float_or_none(val: str | None) -> float | None:
    if val is None or val.strip() == "":
        return None
    try:
        return float(val)
    except ValueError:
        return None
