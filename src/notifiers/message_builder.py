"""LINE通知メッセージ組み立て"""

from datetime import date


def build_morning_message(
    field_name: str,
    variety: str,
    days_from_transplant: int,
    stage_info: dict,
    drain_info: dict,
    blast_info: dict,
    heat_info: dict,
    forecast_text: str,
) -> str:
    """毎朝7:00配信メッセージを組み立てる"""
    lines = [
        "おはようございます。",
        "━━━━━━━━━━",
        f"🌾 {field_name}（{variety}）",
        f"📅 田植えから{days_from_transplant}日目",
        "",
        "【今の状態】",
        f"{stage_info['label']}です。",
        f"積算温度 {stage_info.get('accumulated_temp', 0):.0f}℃日",
    ]

    # 茎数推定（分げつ期〜中干し期）
    if stage_info.get("stage") in ("tillering", "max_tiller", "midseason_drain"):
        progress = stage_info.get("progress_pct", 0)
        lines.append(f"推定茎数: 目標の約{progress}%")

    lines.append("")
    lines.append("【今週やること】")

    # 中干し判定
    if drain_info.get("should_start"):
        lines.append("🔴 中干しを始めてください")
        if drain_info.get("drain_deadline"):
            lines.append(f"　 {drain_info['drain_deadline']}までに完了")
    elif drain_info.get("remaining_days") and drain_info["remaining_days"] <= 7:
        days = drain_info["remaining_days"]
        lines.append(f"🔵 あと{days}日ほどで中干し開始の目安です")
        lines.append("　 田んぼの水を少しずつ減らす")
        lines.append("　 準備をしておいてください")

    # いもち病リスク
    if blast_info.get("risk_level") == "high":
        lines.append("🔴 いもち病リスク高 ― 葉の裏を確認してください")
    elif blast_info.get("risk_level") == "moderate":
        lines.append("🟡 いもち病やや注意 ― 葉の状態を観察しましょう")

    # 高温障害リスク
    if heat_info.get("risk_level") == "high":
        lines.append("🔴 高温注意 ― 掛け流しかんがいを検討してください")
    elif heat_info.get("risk_level") == "moderate":
        lines.append("🟡 気温が高めです ― 水管理に注意しましょう")

    # 特にアクションなし
    action_items = [l for l in lines if l.startswith(("🔴", "🔵", "🟡"))]
    if not action_items:
        next_label = stage_info.get("next_stage_label", "")
        days_to = stage_info.get("days_to_next")
        if days_to and next_label:
            lines.append(f"🟢 順調です。{next_label}まであと約{days_to}日の見込み")
        else:
            lines.append("🟢 順調です。引き続き水管理をお願いします")

    lines.append("")
    lines.append(forecast_text)
    lines.append("━━━━━━━━━━")

    return "\n".join(lines)


def build_blast_alert(
    field_name: str,
    variety: str,
    blast_info: dict,
) -> str:
    """いもち病緊急通知メッセージ"""
    wetness = blast_info.get("leaf_wetness_hours", 0)
    temp = blast_info.get("avg_temp_during_wetness", 0)
    advisory = blast_info.get("advisory_active", False)

    lines = [
        "⚠️ いもち病に注意してください",
        "",
        f"🌾 {field_name}（{variety}）",
        "",
        "湿度が高い状態が続いています。",
        f"（90%以上が{wetness:.0f}時間連続）",
        f"気温も{temp:.0f}℃前後で、いもち病が",
        "出やすい条件です。",
        "",
        "👉 葉の裏を確認してください",
        "👉 病斑を見つけたら早めに防除を",
    ]

    if advisory:
        lines.append("")
        lines.append("広島県からも注意報が出ています。")

    lines.append("━━━━━━━━━━")
    return "\n".join(lines)


def build_drain_reminder(
    field_name: str,
    variety: str,
    drain_info: dict,
) -> str:
    """中干し開始リマインダーメッセージ"""
    heading_date = drain_info.get("estimated_heading_date", "不明")
    deadline = drain_info.get("drain_deadline", "不明")

    lines = [
        "📢 中干しを始める時期です",
        "",
        f"🌾 {field_name}（{variety}）",
        "",
        "茎の数が目標に近づきました。",
        "水を抜いて中干しを始めてください。",
        "",
        "⏰ 目安: 7-10日間",
        f"📅 {deadline}までに終わらせましょう",
        f"　（出穂予測: {heading_date}）",
        "",
        "田面にヒビが入るまでしっかり干して、",
        "その後は間断かんがいに切り替えます。",
        "━━━━━━━━━━",
    ]
    return "\n".join(lines)


def build_water_temp_alert(
    field_name: str,
    variety: str,
    water_info: dict,
) -> str:
    """活着期の水温低下アラートメッセージ"""
    water_temp = water_info.get("water_temp", 0)
    days = water_info.get("days_from_transplant", 0)

    lines = [
        "⚠️ 水温低下にご注意ください",
        "",
        f"🌾 {field_name}（{variety}）",
        f"📅 田植え後{days}日目（活着期）",
        "",
        f"推定水温が{water_temp:.1f}℃で、",
        "15℃を下回っています。",
        "活着が遅れるおそれがあります。",
        "",
        "👉 深水管理（5〜7cm）で保温してください",
        "👉 田面の水温が低い場合は入水を検討",
        "━━━━━━━━━━",
    ]
    return "\n".join(lines)


def build_drain_timing_alert(
    field_name: str,
    variety: str,
    drain_info: dict,
) -> str:
    """落水タイミングアラートメッセージ"""
    harvest_date = drain_info.get("estimated_harvest_date")
    drain_date = drain_info.get("recommended_drain_date")
    drain_end = drain_info.get("recommended_drain_end")
    days_to = drain_info.get("days_to_drain", 0)

    harvest_str = harvest_date.strftime("%m/%d") if harvest_date else "不明"
    drain_str = drain_date.strftime("%m/%d") if drain_date else "不明"
    drain_end_str = drain_end.strftime("%m/%d") if drain_end else "不明"

    lines = [
        "📢 落水の準備をしてください",
        "",
        f"🌾 {field_name}（{variety}）",
        "",
        f"推定収穫日: {harvest_str}",
        f"落水推奨期間: {drain_str} 〜 {drain_end_str}",
    ]

    if days_to is not None and days_to <= 0:
        lines.append("")
        lines.append("落水推奨時期に入っています。")
        lines.append("👉 圃場の水を落としてください")
    else:
        lines.append("")
        lines.append(f"あと約{days_to}日で落水推奨時期です。")
        lines.append("👉 準備を始めてください")

    lines.append("━━━━━━━━━━")
    return "\n".join(lines)


def build_heat_stress_alert(
    field_name: str,
    variety: str,
    heat_info: dict,
) -> str:
    """高温障害アラートメッセージ"""
    temp = heat_info.get("avg_temp_post_heading", 0)
    night_temp = heat_info.get("avg_night_temp")
    days = heat_info.get("days_post_heading", 0)

    lines = [
        "🌡️ 高温障害に注意してください",
        "",
        f"🌾 {field_name}（{variety}）",
        "",
        f"出穂後{days}日間の平均気温が{temp:.1f}℃で",
    ]
    if night_temp is not None:
        lines.append(f"夜温（平均最低気温）が{night_temp:.1f}℃で、")
    lines.extend([
        "白未熟粒が増えるおそれがあります。",
        "",
        "👉 掛け流しかんがいで水温を下げましょう",
        "👉 夕方に新しい水を入れるのも効果的です",
        "━━━━━━━━━━",
    ])
    return "\n".join(lines)
