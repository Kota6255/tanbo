"""天気予報データ取得"""

import logging
from datetime import datetime, timedelta, timezone

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)
JST = timezone(timedelta(hours=9))


async def fetch_forecast() -> dict:
    """広島県の天気予報を取得"""
    url = f"{settings.forecast_url}/{settings.hiroshima_area_code}.json"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    result = _parse_forecast(data)
    logger.info("Fetched forecast: %s", result.get("today", {}).get("weather", ""))
    return result


def _parse_forecast(data: list) -> dict:
    """気象庁JSONレスポンスをパースして簡潔な天気情報を返す"""
    result = {"today": {}, "tomorrow": {}}

    try:
        # 最初の要素から天気情報を取得
        time_series = data[0]["timeSeries"]

        # 天気
        weather_ts = time_series[0]
        areas = weather_ts["areas"]
        if areas:
            area = areas[0]
            weathers = area.get("weathers", [])
            if len(weathers) >= 1:
                result["today"]["weather"] = weathers[0]
            if len(weathers) >= 2:
                result["tomorrow"]["weather"] = weathers[1]

        # 気温（2番目の要素）
        if len(data) > 1:
            temp_ts = data[1]["timeSeries"]
            if temp_ts:
                temp_areas = temp_ts[0]["areas"]
                if temp_areas:
                    temps = temp_areas[0].get("temps", [])
                    # temps は [今日最低, 今日最高, 明日最低, 明日最高] の順
                    if len(temps) >= 2:
                        result["today"]["max_temp"] = temps[1]
                    if len(temps) >= 4:
                        result["tomorrow"]["max_temp"] = temps[3]
    except (KeyError, IndexError) as e:
        logger.warning("Failed to parse forecast: %s", e)

    return result


def format_forecast_text(forecast: dict) -> str:
    """天気予報をLINE通知用テキストに整形"""
    lines = ["【天気】"]

    today = forecast.get("today", {})
    if today:
        weather = today.get("weather", "不明")
        # 長い天気文を短くする
        weather_short = weather[:20] + "…" if len(weather) > 20 else weather
        max_temp = today.get("max_temp", "?")
        lines.append(f"今日: {weather_short} 最高{max_temp}℃")

    tomorrow = forecast.get("tomorrow", {})
    if tomorrow:
        weather = tomorrow.get("weather", "不明")
        weather_short = weather[:20] + "…" if len(weather) > 20 else weather
        max_temp = tomorrow.get("max_temp", "?")
        lines.append(f"明日: {weather_short} 最高{max_temp}℃")

    return "\n".join(lines)
