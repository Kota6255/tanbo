"""LINE Webhook ハンドラ"""

import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Request, HTTPException
from linebot.v3.webhook import WebhookParser
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from src.models.database import SessionLocal, Field, GrowthStage
from src.analyzers.accumulated_temp import calc_accumulated_temp
from src.analyzers.growth_stage import estimate_growth_stage
from src.analyzers.blast_risk import assess_blast_risk
from src.analyzers.midseason_drain import assess_midseason_drain
from src.analyzers.heat_stress import assess_heat_stress
from src.notifiers.line_bot import send_reply_message
from config.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)
JST = timezone(timedelta(hours=9))

parser = WebhookParser(settings.line_channel_secret) if settings.line_channel_secret else None


@router.post("/webhook/line")
async def handle_line_webhook(request: Request):
    """LINE Webhookエンドポイント"""
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")

    if parser is None:
        raise HTTPException(status_code=500, detail="LINE credentials not configured")

    try:
        events = parser.parse(body, signature)
    except Exception as e:
        logger.error("Webhook parse error: %s", e)
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            await _handle_text_message(event)

    return {"status": "ok"}


async def _handle_text_message(event: MessageEvent):
    """テキストメッセージを処理"""
    text = event.message.text.strip()
    user_id = event.source.user_id
    reply_token = event.reply_token

    # ユーザーの圃場を取得
    db = SessionLocal()
    try:
        field = db.query(Field).filter(Field.line_user_id == user_id).first()
    finally:
        db.close()

    commands = {
        "今日": _cmd_today,
        "今週": _cmd_this_week,
        "いもち": _cmd_blast,
        "温度": _cmd_temperature,
        "ステージ": _cmd_stage,
        "ヘルプ": _cmd_help,
    }

    handler = commands.get(text)
    if handler:
        if field is None and text not in ("登録", "ヘルプ"):
            send_reply_message(reply_token, "圃場が登録されていません。\n「登録」と送信して、圃場情報を登録してください。")
            return
        response = handler(field)
    elif text == "登録":
        response = _cmd_register_start()
    else:
        response = "コマンドが認識できませんでした。\n「ヘルプ」と送信するとコマンド一覧を表示します。"

    send_reply_message(reply_token, response)


def _cmd_today(field: Field) -> str:
    """当日の行動提案+天気"""
    today = date.today()
    days = (today - field.transplant_date).days if field.transplant_date else 0

    acc_temp = calc_accumulated_temp(field.nearest_amedas, field.transplant_date, today)
    stage = estimate_growth_stage(field.variety, acc_temp)
    drain = assess_midseason_drain(field.id)
    blast = assess_blast_risk(field.id)

    lines = [
        f"🌾 {field.name}（{field.variety}）",
        f"📅 田植えから{days}日目",
        "",
        f"【生育ステージ】{stage['label']}",
        f"積算温度: {acc_temp:.0f}℃日",
        "",
    ]

    if drain.get("should_start"):
        lines.append("📢 中干しの時期です！")
        lines.append(drain.get("message", ""))
    elif blast.get("risk_level") in ("high", "moderate"):
        lines.append(f"⚠️ いもち病リスク: {blast['risk_level']}")
        lines.append(blast.get("message", ""))
    else:
        lines.append("🟢 特別な作業はありません。水管理を続けてください。")

    return "\n".join(lines)


def _cmd_this_week(field: Field) -> str:
    """今週の管理ポイント"""
    today = date.today()
    acc_temp = calc_accumulated_temp(field.nearest_amedas, field.transplant_date, today)
    stage = estimate_growth_stage(field.variety, acc_temp)

    lines = [
        f"🌾 {field.name} 今週の管理ポイント",
        f"現在: {stage['label']}",
        "",
    ]

    s = stage["stage"]
    if s in ("tillering", "max_tiller"):
        lines.append("・水深5cm程度を維持してください")
        lines.append("・分げつが進んでいます")
        if stage.get("days_to_next"):
            lines.append(f"・{stage['next_stage_label']}まであと約{stage['days_to_next']}日")
    elif s == "midseason_drain":
        lines.append("・中干しの時期です。水を抜いてください")
        lines.append("・田面にヒビが入るまで7-10日干します")
    elif s == "panicle_formation":
        lines.append("・幼穂が形成されています")
        lines.append("・穂肥のタイミングに注意してください")
    elif s in ("booting", "heading"):
        lines.append("・水を切らさないようにしてください")
        lines.append("・いもち病に注意（穂いもち防除）")
    elif s == "grain_filling":
        lines.append("・間断かんがいで根を活かしましょう")
        lines.append("・高温障害に注意して水管理を")
    elif s == "maturity":
        lines.append("・落水のタイミングを確認してください")
        lines.append("・籾の色づきを観察しましょう")

    return "\n".join(lines)


def _cmd_blast(field: Field) -> str:
    """いもち病リスク判定結果"""
    result = assess_blast_risk(field.id)
    risk_labels = {"low": "低い", "moderate": "やや高い", "high": "高い"}
    level = risk_labels.get(result["risk_level"], "不明")

    lines = [
        f"🌾 {field.name} いもち病リスク判定",
        "",
        f"リスクレベル: {level}",
        f"葉面湿潤推定時間: {result.get('leaf_wetness_hours', 0):.1f}時間",
        f"湿潤時平均気温: {result.get('avg_temp_during_wetness', 0):.1f}℃",
    ]

    if result.get("advisory_active"):
        lines.append("")
        lines.append("※ 広島県から注意報が出ています")

    lines.append("")
    lines.append(result.get("message", ""))

    return "\n".join(lines)


def _cmd_temperature(field: Field) -> str:
    """直近24時間の気温推移"""
    from src.models.database import AmedasObservation
    from sqlalchemy import select

    now = datetime.now(JST)
    since = (now - timedelta(hours=24)).isoformat()

    db = SessionLocal()
    try:
        rows = db.execute(
            select(AmedasObservation).where(
                AmedasObservation.station_id == field.nearest_amedas,
                AmedasObservation.observed_at >= since,
            ).order_by(AmedasObservation.observed_at)
        ).scalars().all()
    finally:
        db.close()

    if not rows:
        return "直近24時間の気温データがありません。"

    lines = [f"🌡️ {field.name} 最寄り観測所の気温（24時間）", ""]
    for r in rows:
        time_str = r.observed_at[11:16] if len(r.observed_at) > 16 else r.observed_at
        temp = r.air_temp if r.air_temp is not None else "?"
        lines.append(f"  {time_str}  {temp}℃")

    return "\n".join(lines)


def _cmd_stage(field: Field) -> str:
    """現在の推定生育ステージ詳細"""
    today = date.today()
    days = (today - field.transplant_date).days if field.transplant_date else 0
    acc_temp = calc_accumulated_temp(field.nearest_amedas, field.transplant_date, today)
    stage = estimate_growth_stage(field.variety, acc_temp)

    lines = [
        f"🌾 {field.name}（{field.variety}）生育ステージ",
        "",
        f"田植えから: {days}日",
        f"有効積算温度: {acc_temp:.1f}℃日",
        f"現在のステージ: {stage['label']}",
        f"ステージ内進行度: {stage['progress_pct']}%",
    ]

    if stage.get("next_stage_label"):
        lines.append(f"次のステージ: {stage['next_stage_label']}")
    if stage.get("days_to_next"):
        lines.append(f"次ステージまで: 約{stage['days_to_next']}日")

    return "\n".join(lines)


def _cmd_help() -> str:
    """コマンド一覧"""
    return (
        "【コマンド一覧】\n"
        "━━━━━━━━━━\n"
        "「今日」→ 当日の行動提案+天気\n"
        "「今週」→ 今週の管理ポイント\n"
        "「いもち」→ いもち病リスク判定\n"
        "「温度」→ 直近24時間の気温推移\n"
        "「ステージ」→ 生育ステージ詳細\n"
        "「登録」→ 圃場登録\n"
        "「ヘルプ」→ この一覧を表示\n"
        "━━━━━━━━━━"
    )


def _cmd_register_start() -> str:
    """圃場登録フロー開始"""
    return (
        "圃場を登録します。\n"
        "以下の情報を1行ずつ送信してください。\n\n"
        "1. 圃場の名前（例: 家の前の田）\n"
        "2. 品種（コシヒカリ / ヒノヒカリ / あきろまん）\n"
        "3. 田植え日（例: 6月5日）\n"
        "4. 最寄りの町（例: 東広島市西条）\n\n"
        "例:\n"
        "家の前の田\n"
        "コシヒカリ\n"
        "6月5日\n"
        "東広島市西条"
    )
