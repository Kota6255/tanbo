"""APScheduler ジョブ定義"""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.collectors.amedas import fetch_amedas_latest, calc_daily_summary
from src.collectors.forecast import fetch_forecast, format_forecast_text
from src.analyzers.accumulated_temp import calc_accumulated_temp
from src.analyzers.growth_stage import estimate_growth_stage
from src.analyzers.midseason_drain import assess_midseason_drain
from src.analyzers.blast_risk import assess_blast_risk
from src.analyzers.heat_stress import assess_heat_stress
from src.analyzers.drain_timing import assess_drain_timing
from src.analyzers.water_temp import assess_water_temp
from src.models.database import SessionLocal, Field, GrowthStage
from src.notifiers.line_bot import send_push_message
from src.notifiers.message_builder import (
    build_morning_message,
    build_blast_alert,
    build_drain_reminder,
    build_heat_stress_alert,
    build_water_temp_alert,
    build_drain_timing_alert,
)
from config.settings import settings

logger = logging.getLogger(__name__)
JST = timezone(timedelta(hours=9))

scheduler = AsyncIOScheduler(timezone="Asia/Tokyo")


def setup_jobs():
    """全ジョブを登録"""
    # 毎時00分: アメダスデータ取得
    scheduler.add_job(job_fetch_amedas, "cron", minute=0, id="fetch_amedas")

    # 毎日00:05: 前日の日別気象サマリ
    scheduler.add_job(job_calc_daily_summary, "cron", hour=0, minute=5, id="calc_daily_summary")

    # 毎日06:00: 生育ステージ更新
    scheduler.add_job(job_update_growth_stage, "cron", hour=6, minute=0, id="update_growth_stage")

    # 毎日06:15: いもち病リスク判定
    scheduler.add_job(job_assess_blast_risk, "cron", hour=6, minute=15, id="assess_blast_risk")

    # 毎日06:20: 高温障害リスク判定
    scheduler.add_job(job_assess_heat_stress, "cron", hour=6, minute=20, id="assess_heat_stress")

    # 毎日06:25: 活着期の水温チェック
    scheduler.add_job(job_check_water_temp, "cron", hour=6, minute=25, id="check_water_temp")

    # 毎日06:30: 落水タイミング判定
    scheduler.add_job(job_assess_drain_timing, "cron", hour=6, minute=30, id="assess_drain_timing")

    # 毎日07:00: 朝のLINE通知
    scheduler.add_job(job_send_morning_advice, "cron", hour=7, minute=0, id="send_morning_advice")

    logger.info("All scheduled jobs registered")


async def job_fetch_amedas():
    """アメダスデータ取得ジョブ"""
    try:
        results = await fetch_amedas_latest()
        logger.info("Amedas fetch complete: %d stations", len(results))
    except Exception as e:
        logger.error("Amedas fetch failed: %s", e)


async def job_calc_daily_summary():
    """日別気象サマリ計算ジョブ"""
    try:
        calc_daily_summary()
        logger.info("Daily summary calculation complete")
    except Exception as e:
        logger.error("Daily summary failed: %s", e)


async def job_update_growth_stage():
    """全圃場の生育ステージ更新ジョブ"""
    db = SessionLocal()
    try:
        fields = db.query(Field).filter(Field.transplant_date.isnot(None)).all()
        today = date.today()

        for field in fields:
            acc_temp = calc_accumulated_temp(
                field.nearest_amedas, field.transplant_date, today
            )
            stage = estimate_growth_stage(field.variety, acc_temp)
            days = (today - field.transplant_date).days

            from sqlalchemy import select
            existing = db.execute(
                select(GrowthStage).where(
                    GrowthStage.field_id == field.id,
                    GrowthStage.date == today,
                )
            ).scalar_one_or_none()

            if existing is None:
                gs = GrowthStage(
                    field_id=field.id,
                    date=today,
                    accumulated_temp=acc_temp,
                    estimated_stage=stage["stage"],
                    tiller_count_estimate=stage.get("progress_pct"),
                    days_from_transplant=days,
                )
                db.add(gs)
            else:
                existing.accumulated_temp = acc_temp
                existing.estimated_stage = stage["stage"]
                existing.days_from_transplant = days

        db.commit()
        logger.info("Updated growth stages for %d fields", len(fields))
    except Exception as e:
        logger.error("Growth stage update failed: %s", e)
    finally:
        db.close()


async def job_assess_blast_risk():
    """全圃場のいもち病リスク判定ジョブ"""
    db = SessionLocal()
    try:
        fields = db.query(Field).all()
        for field in fields:
            result = assess_blast_risk(field.id)

            # リスク高の場合は即時通知
            if result["risk_level"] == "high" and field.line_user_id:
                msg = build_blast_alert(field.name, field.variety, result)
                send_push_message(
                    field.line_user_id, msg,
                    field_id=field.id,
                    notification_type="blast_alert",
                )
                logger.info("Sent blast alert for field %d", field.id)
    except Exception as e:
        logger.error("Blast risk assessment failed: %s", e)
    finally:
        db.close()


async def job_assess_heat_stress():
    """高温障害リスク判定ジョブ"""
    db = SessionLocal()
    try:
        fields = db.query(Field).all()
        for field in fields:
            result = assess_heat_stress(field.id)

            if result["risk_level"] == "high" and field.line_user_id:
                msg = build_heat_stress_alert(field.name, field.variety, result)
                send_push_message(
                    field.line_user_id, msg,
                    field_id=field.id,
                    notification_type="heat_stress_alert",
                )
    except Exception as e:
        logger.error("Heat stress assessment failed: %s", e)
    finally:
        db.close()


async def job_check_water_temp():
    """活着期の水温チェックジョブ"""
    db = SessionLocal()
    try:
        fields = db.query(Field).filter(
            Field.transplant_date.isnot(None),
            Field.line_user_id.isnot(None),
        ).all()
        for field in fields:
            result = assess_water_temp(field.id)

            if result.get("risk") and field.line_user_id:
                msg = build_water_temp_alert(field.name, field.variety, result)
                send_push_message(
                    field.line_user_id, msg,
                    field_id=field.id,
                    notification_type="water_temp_alert",
                )
                logger.info("Sent water temp alert for field %d", field.id)
    except Exception as e:
        logger.error("Water temp check failed: %s", e)
    finally:
        db.close()


async def job_assess_drain_timing():
    """落水タイミング判定ジョブ"""
    db = SessionLocal()
    try:
        fields = db.query(Field).filter(
            Field.transplant_date.isnot(None),
            Field.line_user_id.isnot(None),
        ).all()
        for field in fields:
            result = assess_drain_timing(field.id)

            # 落水推奨時期に入っている or あと7日以内
            days_to = result.get("days_to_drain")
            if days_to is not None and days_to <= 7 and field.line_user_id:
                msg = build_drain_timing_alert(field.name, field.variety, result)
                send_push_message(
                    field.line_user_id, msg,
                    field_id=field.id,
                    notification_type="drain_timing_alert",
                )
                logger.info("Sent drain timing alert for field %d", field.id)
    except Exception as e:
        logger.error("Drain timing assessment failed: %s", e)
    finally:
        db.close()


async def job_send_morning_advice():
    """朝の定期LINE通知送信ジョブ"""
    db = SessionLocal()
    try:
        fields = db.query(Field).filter(
            Field.line_user_id.isnot(None),
            Field.transplant_date.isnot(None),
        ).all()

        # 天気予報取得
        try:
            forecast = await fetch_forecast()
            forecast_text = format_forecast_text(forecast)
        except Exception:
            forecast_text = "【天気】\n天気情報を取得できませんでした"

        today = date.today()

        for field in fields:
            days = (today - field.transplant_date).days
            acc_temp = calc_accumulated_temp(field.nearest_amedas, field.transplant_date, today)
            stage = estimate_growth_stage(field.variety, acc_temp)
            stage["accumulated_temp"] = acc_temp

            drain = assess_midseason_drain(field.id)
            blast = assess_blast_risk(field.id)
            heat = assess_heat_stress(field.id)

            msg = build_morning_message(
                field_name=field.name,
                variety=field.variety,
                days_from_transplant=days,
                stage_info=stage,
                drain_info=drain,
                blast_info=blast,
                heat_info=heat,
                forecast_text=forecast_text,
            )

            send_push_message(
                field.line_user_id, msg,
                field_id=field.id,
                notification_type="daily_advice",
            )

            # 中干しリマインダー（別途送信）
            if drain.get("should_start"):
                reminder = build_drain_reminder(field.name, field.variety, drain)
                send_push_message(
                    field.line_user_id, reminder,
                    field_id=field.id,
                    notification_type="drain_reminder",
                )

        logger.info("Morning advice sent to %d fields", len(fields))
    except Exception as e:
        logger.error("Morning advice failed: %s", e)
    finally:
        db.close()
