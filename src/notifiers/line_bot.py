"""LINE メッセージ送信"""

import logging
from datetime import datetime

from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage,
)

from src.models.database import SessionLocal, Notification
from config.settings import settings

logger = logging.getLogger(__name__)


def _get_messaging_api() -> MessagingApi:
    config = Configuration(access_token=settings.line_channel_access_token)
    client = ApiClient(config)
    return MessagingApi(client)


def send_push_message(
    line_user_id: str,
    message: str,
    field_id: int = None,
    notification_type: str = "daily_advice",
) -> bool:
    """LINEプッシュメッセージを送信"""
    try:
        api = _get_messaging_api()
        api.push_message(PushMessageRequest(
            to=line_user_id,
            messages=[TextMessage(text=message)],
        ))

        # 通知ログ保存
        _log_notification(field_id, notification_type, message)
        logger.info("Sent push message to %s (type: %s)", line_user_id, notification_type)
        return True
    except Exception as e:
        logger.error("Failed to send push message: %s", e)
        _log_notification(field_id, notification_type, message, delivered=0)
        return False


def send_reply_message(reply_token: str, message: str) -> bool:
    """LINE返信メッセージを送信"""
    try:
        api = _get_messaging_api()
        api.reply_message(ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=message)],
        ))
        return True
    except Exception as e:
        logger.error("Failed to send reply: %s", e)
        return False


def _log_notification(
    field_id: int | None,
    notification_type: str,
    message: str,
    delivered: int = 1,
):
    """通知ログをDBに保存"""
    db = SessionLocal()
    try:
        notif = Notification(
            field_id=field_id,
            notification_type=notification_type,
            message=message[:500],  # 長すぎるメッセージは切り詰め
            delivered=delivered,
        )
        db.add(notif)
        db.commit()
    finally:
        db.close()
