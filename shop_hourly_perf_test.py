"""TikTok Shop Performance Per Hour (202509)
→ US매출/지표 시트 'Get Shop Performance Per Hour' 탭

주의: 이 API는 최근 30일(오늘 포함)만 조회 가능 — 1월 데이터는 제공되지 않음.
정확한 경로가 문서로 확인되지 않아 후보 경로를 자동 탐색(probe)한 뒤,
조회 가능한 각 날짜에 대해 시간대별(0~23시) 행 + 일별 OVERALL 행을 적재한다.
날짜↑, 시간↑ 정렬.
"""
import hashlib
import hmac
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, quote

import requests
from google.oauth2.service_account import Credentials
import gspread
from token_manager import get_valid_token, handle_token_expired

VIDEO_APP_KEY = "6jd7l2nu36rd4"
VIDEO_APP_SECRET = "9ab6f9c3467d53c72ca6e346c18b8071338f0ce4"
VIDEO_ACCESS_TOKEN = "TTP_8qmwDAAAAAAKxe5s-tyxQjFx-BLmHCzEUHx_N8KtbJs8REguA-PlojAyV0wGbdEfcH65GTeVkz7R1pOu5g44xImqf4SrMwS1YxCDFaFiR71wCyyvCuiX9V4xVHdkwwVZjC2fEb9DckyVqVjeUiW-H2PBtsmHPpwLM6krtq-pI3-bR3oq5XS_LA"
VIDEO_REFRESH_TOKEN = "TTP_77fQXQAAAACRYHgjQ_4vEa-Xhe5ikMt0yvs0Zs2i5flXWHMzwGflyAsL_dJ53tHERRwYkVRh9AI"
VIDEO_SHOP_CIPHER = "TTP_uE19hAAAAADx5Flb4Y_fjmWFiQfOEyTT"

SPREADSHEET_ID = "15dP91bH_skc7ZzcJ3ehH9H4IKCzSxcfuOcREr3OaL0o"  # US 매출/지표
SHEET_NAME = "Get Shop Performance Per Hour"
SERVICE_ACCOUNT_FILE = "service_account.json"

BASE = "https://open-api.tiktokglobalshop.com"

# 문서 미확인 → 후보 경로 자동 탐색
CANDIDATE_PATHS = [
    "/analytics/202509/shop/performance/hourly",
    "/analytics/202509/shop/hourly_performance",
    "/analytics/202509/shop/performance_per_hour",
    "/analytics/202509/shop/performance/per_hour",
    "/analytics/202509/shop_performance/hourly",
]

HEADERS_ROW = ["날짜", "시간", "GMV($)", "판매수량", "방문자수", "구매자수"]

LA_TZ = timezone(timedelta(hours=-8))


def make_sign(path: str, params: dict) -> str:
    s = VIDEO_APP_SECRET + path
    for k in sorted(params.keys()):
        s += k + str(params[k])
    s += VIDEO_APP_SECRET
    return hmac.new(VIDEO_APP_SECRET.encode(), s.encode(), hashlib.sha256).hexdigest()


def api_get(path: str, extra: dict):
    params = {
        "app_key": VIDEO_APP_KEY,
        "shop_cipher": VIDEO_SHOP_CIPHER,
        "currency": "USD",
        "timestamp": str(int(time.time())),
        **extra,
    }
    params["sign"] = make_sign(path, params)
    url = BASE + path + "?" + urlencode(params, quote_via=quote)
    headers = {"content-type": "application/json",
               "x-tts-access-token": get_valid_token(VIDEO_ACCESS_TOKEN, VIDEO_REFRESH_TOKEN)}
    try:
        return requests.get(url, headers=headers, timeout=30).json()
    except Exception as e:
        return {"code": -1, "message": str(e)}


def probe(date_str: str):
    """후보 경로 × 날짜 파라미터 방식을 시도해 맞는 조합을 찾는다."""
    param_styles = [
        {"date": date_str},
        {"start_date_ge": date_str,
         "end_date_lt": (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")},
    ]
    for path in CANDIDATE_PATHS:
        for style in param_styles:
            d = api_get(path, style)
            code = d.get("code")
            print(f"  probe {path} {list(style.keys())} → code={code} msg={str(d.get('message'))[:80]}")
            if code == 0:
                return path, style
            time.sleep(0.2)
    return None, None


def main():
    # 최근 30일 (API 제약) — 오늘(LA) 포함
    today_la = datetime.now(LA_TZ).date()
    dates = [(today_la - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(29, -1, -1)]
    print(f"\n=== Shop Performance Per Hour [{dates[0]} ~ {dates[-1]}] (API 제약: 최근 30일만) ===")

    # 토큰 워밍업 후 경로 탐색 (어제 날짜로)
    path, style_tpl = probe(dates[-2])
    if not path:
        print("  ❌ 유효한 엔드포인트를 찾지 못함 — 문서의 정확한 경로 확인 필요")
        sys.exit(1)
    print(f"  ✅ 엔드포인트 확정: {path} / 파라미터 {list(style_tpl.keys())}")

    rows = []
    for ds in dates:
        if "date" in style_tpl:
            extra = {"date": ds}
        else:
            extra = {"start_date_ge": ds,
                     "end_date_lt": (datetime.strptime(ds, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")}
        d = api_get(path, extra)
        if d.get("code") != 0:
            print(f"  [{ds}] code={d.get('code')} msg={str(d.get('message'))[:60]} — 건너뜀")
            continue
        perf = d.get("data", {}).get("performance") or {}
        o = perf.get("overall") or {}
        rows.append([ds, "OVERALL",
                     float((o.get("gmv") or {}).get("amount") or 0),
                     o.get("items_sold", 0), o.get("visitors", 0), o.get("customers", 0)])
        for iv in perf.get("intervals") or []:
            rows.append([ds, iv.get("index", ""),
                         float((iv.get("gmv") or {}).get("amount") or 0),
                         iv.get("items_sold", 0), iv.get("visitors", 0), iv.get("customers", 0)])
        time.sleep(0.2)

    print(f"  총 {len(rows)}행 수집")
    if not rows:
        print("  데이터 없음 - 종료")
        return

    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"])
    ss = gspread.authorize(creds).open_by_key(SPREADSHEET_ID)
    try:
        sheet = ss.worksheet(SHEET_NAME)
        sheet.clear()
    except gspread.WorksheetNotFound:
        sheet = ss.add_worksheet(title=SHEET_NAME, rows="1000", cols=str(len(HEADERS_ROW)))
    sheet.resize(rows=len(rows) + 10, cols=len(HEADERS_ROW))

    data = [HEADERS_ROW] + rows
    for attempt in range(1, 9):
        try:
            sheet.update(data, value_input_option="USER_ENTERED")
            sheet.freeze(rows=1)
            print(f"  ✅ '{SHEET_NAME}' 탭에 {len(rows)}행 저장 완료")
            return
        except Exception as e:
            if attempt == 8:
                raise
            wait = min(3 * attempt, 30)
            print(f"  시트 쓰기 실패 (시도 {attempt}/8), {wait}초 후 재시도... ({e})")
            time.sleep(wait)


if __name__ == "__main__":
    main()
