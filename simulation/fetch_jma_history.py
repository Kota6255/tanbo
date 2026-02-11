"""気象庁の過去データページから東広島2025年の日別気温を取得する"""

import csv
import io
import re
from datetime import date
from pathlib import Path

import httpx

# 東広島 (アメダス) の地点番号
# 気象庁の過去データURLフォーマット
# prec_no=67 (広島県), block_no=1356 (東広島)
BASE_URL = "https://www.data.jma.go.jp/obd/stats/etrn/view/daily_a1.php"

OUTPUT = Path(__file__).parent / "higashihiroshima_2025.csv"


def fetch_month(year: int, month: int) -> list[dict]:
    """指定年月の日別気象データを取得"""
    params = {
        "prec_no": "67",
        "block_no": "1356",
        "year": str(year),
        "month": str(month),
        "day": "",
        "view": "a1",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (research purpose)",
        "Accept-Language": "ja",
    }

    resp = httpx.get(BASE_URL, params=params, headers=headers, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    html = resp.text

    rows = []
    # 日別データのテーブル行をパース
    # パターン: <tr ...> の中に <td> が並ぶ
    table_match = re.search(r'<table[^>]*id="tablefix1"[^>]*>(.*?)</table>', html, re.DOTALL)
    if not table_match:
        print(f"  {year}/{month:02d}: テーブルが見つかりません")
        return rows

    tbody = table_match.group(1)
    tr_pattern = re.findall(r'<tr[^>]*class="mtx"[^>]*>(.*?)</tr>', tbody, re.DOTALL)

    for tr_html in tr_pattern:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', tr_html, re.DOTALL)
        if len(tds) < 10:
            continue

        # td[0]=日, td[4]=日平均気温, td[5]=日最高気温, td[6]=日最低気温
        # td[7]=平均湿度  (レイアウトはアメダス日別で異なる場合あり)
        day_str = re.sub(r'<[^>]+>', '', tds[0]).strip()
        try:
            day_num = int(day_str)
        except ValueError:
            continue

        def extract_val(td_html):
            val = re.sub(r'<[^>]+>', '', td_html).strip()
            val = val.replace(')', '').replace(']', '').replace('*', '').strip()
            if val == '' or val == '///':
                return None
            try:
                return float(val)
            except ValueError:
                return None

        avg_temp = extract_val(tds[1]) if len(tds) > 1 else None
        max_temp = extract_val(tds[2]) if len(tds) > 2 else None
        min_temp = extract_val(tds[3]) if len(tds) > 3 else None

        d = date(year, month, day_num)
        rows.append({
            "date": d.isoformat(),
            "avg_temp": avg_temp,
            "max_temp": max_temp,
            "min_temp": min_temp,
        })

    print(f"  {year}/{month:02d}: {len(rows)}日分取得")
    return rows


def main():
    all_rows = []
    print("東広島 2025年 日別気温データ取得中...")
    for month in range(1, 13):
        try:
            rows = fetch_month(2025, month)
            all_rows.extend(rows)
        except Exception as e:
            print(f"  {month}月: エラー {e}")

    if all_rows:
        with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["date", "avg_temp", "max_temp", "min_temp"])
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"\n保存: {OUTPUT} ({len(all_rows)}行)")
    else:
        print("データ取得失敗。シミュレーションデータを使用します。")


if __name__ == "__main__":
    main()
