"""気象庁アメダスデータ取得"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from src.models.database import SessionLocal, AmedasObservation, DailyWeather
from config.settings import settings

logger = logging.getLogger(__name__)
JST = timezone(timedelta(hours=9))

# 広島県内の対象観測所
STATIONS_FILE = Path(__file__).resolve().parents[2] / "data" / "amedas_stations.json"


def load_target_stations() -> list[str]:
    """対象観測所IDリストを読み込む"""
    with open(STATIONS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return [s["id"] for s in data["stations"]]


async def fetch_amedas_latest() -> dict:
    """全国アメダス最新データを取得し、対象観測所のデータをDBに保存"""
    now = datetime.now(JST)
    # 10分単位に丸める
    minute = (now.minute // 10) * 10
    timestamp = now.replace(minute=minute, second=0, microsecond=0)
    url_time = timestamp.strftime("%Y%m%d%H%M%S")
    url = f"{settings.amedas_base_url}/data/map/{url_time}.json"

    target_ids = load_target_stations()
    results = {}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            # 数分前のデータを試す
            timestamp -= timedelta(minutes=10)
            url_time = timestamp.strftime("%Y%m%d%H%M%S")
            url = f"{settings.amedas_base_url}/data/map/{url_time}.json"
            resp = await client.get(url)
            resp.raise_for_status()

        all_data = resp.json()

    db = SessionLocal()
    try:
        for station_id in target_ids:
            if station_id not in all_data:
                continue

            raw = all_data[station_id]
            obs = AmedasObservation(
                station_id=station_id,
                observed_at=timestamp.isoformat(),
                air_temp=raw.get("temp", [None])[0],
                humidity=raw.get("humidity", [None])[0],
                precipitation_1h=raw.get("precipitation1h", [None])[0],
                wind_speed=raw.get("wind", [None])[0],
                sunshine_1h=raw.get("sun1h", [None])[0],
                pressure=raw.get("normalPressure", [None])[0],
            )

            # UPSERT: 既存なら更新、なければ挿入
            from sqlalchemy import select
            existing = db.execute(
                select(AmedasObservation).where(
                    AmedasObservation.station_id == station_id,
                    AmedasObservation.observed_at == timestamp.isoformat(),
                )
            ).scalar_one_or_none()

            if existing is None:
                db.add(obs)
                results[station_id] = {
                    "temp": obs.air_temp,
                    "humidity": obs.humidity,
                }

        db.commit()
        logger.info("Fetched amedas data for %d stations at %s", len(results), timestamp)
    finally:
        db.close()

    return results


def calc_daily_summary(target_date=None):
    """指定日（デフォルト前日）の日別気象サマリを計算してDBに保存"""
    if target_date is None:
        target_date = (datetime.now(JST) - timedelta(days=1)).date()

    target_ids = load_target_stations()
    db = SessionLocal()

    try:
        for station_id in target_ids:
            from sqlalchemy import select, func

            # 対象日のデータを集計
            day_start = datetime(
                target_date.year, target_date.month, target_date.day,
                0, 0, 0, tzinfo=JST
            ).isoformat()
            day_end = datetime(
                target_date.year, target_date.month, target_date.day,
                23, 59, 59, tzinfo=JST
            ).isoformat()

            rows = db.execute(
                select(AmedasObservation).where(
                    AmedasObservation.station_id == station_id,
                    AmedasObservation.observed_at >= day_start,
                    AmedasObservation.observed_at <= day_end,
                )
            ).scalars().all()

            if not rows:
                continue

            temps = [r.air_temp for r in rows if r.air_temp is not None]
            humidities = [r.humidity for r in rows if r.humidity is not None]
            precips = [r.precipitation_1h for r in rows if r.precipitation_1h is not None]
            sunshine = [r.sunshine_1h for r in rows if r.sunshine_1h is not None]

            if not temps:
                continue

            summary = DailyWeather(
                station_id=station_id,
                date=target_date,
                avg_temp=round(sum(temps) / len(temps), 1),
                max_temp=max(temps),
                min_temp=min(temps),
                total_precipitation=sum(precips) if precips else 0.0,
                avg_humidity=round(sum(humidities) / len(humidities), 1) if humidities else None,
                total_sunshine=sum(sunshine) if sunshine else None,
            )

            # UPSERT
            existing = db.execute(
                select(DailyWeather).where(
                    DailyWeather.station_id == station_id,
                    DailyWeather.date == target_date,
                )
            ).scalar_one_or_none()

            if existing is None:
                db.add(summary)
            else:
                existing.avg_temp = summary.avg_temp
                existing.max_temp = summary.max_temp
                existing.min_temp = summary.min_temp
                existing.total_precipitation = summary.total_precipitation
                existing.avg_humidity = summary.avg_humidity
                existing.total_sunshine = summary.total_sunshine

        db.commit()
        logger.info("Calculated daily summary for %s", target_date)
    finally:
        db.close()
