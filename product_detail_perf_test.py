"""TikTok Shop Product Performance Detail (202509)
→ US매출/지표 시트 'Get Shop Product Performance Detail' 탭

1) 같은 스프레드시트의 '(중요, 자동) SKU Order' 탭에서 상품ID 목록 수집
2) 각 상품에 대해 /analytics/202509/shop_products/{id}/performance 를
   30일 청크(실패 시 7일, granularity=ALL)로 조회
3) 상품×기간(청크) 단위 행으로 저장, 기간 시작일 오름차순 정렬
   - 콘텐츠유형별 판매/트래픽 분해, 평점, 톱콘텐츠/톱크리에이터는 JSON 문자열
"""
import hashlib
import hmac
import json
import re
import sys
import time
from datetime import datetime, timedelta
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
SKU_SHEET_NAME = "(중요, 자동) SKU Order"
SHEET_NAME = "Get Shop Product Performance Detail"
SERVICE_ACCOUNT_FILE = "service_account.json"

BASE = "https://open-api.tiktokglobalshop.com"

HEADERS_ROW = [
    "상품ID", "기간시작", "기간종료",
    "GMV($)", "주문수", "판매수량",
    "반품", "취소", "환불", "교환",
    "판매_콘텐츠유형별(JSON)", "트래픽_콘텐츠유형별(JSON)",
    "평점분포(JSON)", "톱콘텐츠(JSON)", "톱크리에이터(JSON)",
]


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
    for attempt in range(1, 4):
        try:
            d = requests.get(url, headers=headers, timeout=30).json()
            if d.get("code") == 0:
                return d
            if d.get("code") == 105002:
                new_token = handle_token_expired(VIDEO_REFRESH_TOKEN)
                if new_token:
                    headers["x-tts-access-token"] = new_token
                    continue
            if d.get("code") == 28001022:
                return {"__range_error__": True}
            print(f"    [경고] code={d.get('code')}, msg={d.get('message')} (시도 {attempt}/3)")
        except Exception as e:
            print(f"    [오류] {e} (시도 {attempt}/3)")
        time.sleep(2 * attempt)
    return None


def get_gspread():
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds).open_by_key(SPREADSHEET_ID)


def collect_product_ids(ss) -> list[str]:
    """SKU Order 탭 B열(상품ID)에서 고유 상품ID 수집."""
    sheet = ss.worksheet(SKU_SHEET_NAME)
    vals = sheet.col_values(2)[1:]  # 헤더 제외
    ids: list[str] = []
    for v in vals:
        v = str(v).strip().lstrip("'")
        if v and v not in ids:
            ids.append(v)
    return ids


def main():
    raw = sys.argv[1] if len(sys.argv) > 1 else "2026-01-01 ~ 2026-08-07"
    nums = re.findall(r"\d{4}-\d{1,2}-\d{1,2}", raw)
    start = nums[0]
    end = nums[1] if len(nums) > 1 else nums[0]
    print(f"\n=== Shop Product Performance Detail 202509 [{start} ~ {end}] ===")

    ss = get_gspread()
    product_ids = collect_product_ids(ss)
    print(f"  SKU Order 탭에서 상품 {len(product_ids)}개 수집")

    s_dt = datetime.strptime(start, "%Y-%m-%d")
    e_dt = datetime.strptime(end, "%Y-%m-%d")
    chunk_days = 30
    rows = []

    for i, pid in enumerate(product_ids, 1):
        print(f"  [{i}/{len(product_ids)}] 상품 {pid} 조회 중...")
        path = f"/analytics/202509/shop_products/{pid}/performance"
        cur = s_dt
        while cur <= e_dt:
            c_end = min(cur + timedelta(days=chunk_days - 1), e_dt)
            d = api_get(path, {
                "start_date_ge": cur.strftime("%Y-%m-%d"),
                "end_date_lt": c_end.strftime("%Y-%m-%d"),
                "granularity": "ALL",
            })
            if d and d.get("__range_error__") and chunk_days > 7:
                print("    → 기간 오류, 청크 7일로 축소")
                chunk_days = 7
                continue
            cur = c_end + timedelta(days=1)
            if not d or d.get("__range_error__"):
                continue
            perf = d.get("data", {}).get("performance") or {}
            ratings = json.dumps(perf.get("ratings") or [], ensure_ascii=False)[:2000]
            top_contents = json.dumps(perf.get("top_contents") or [], ensure_ascii=False)[:2000]
            top_creators = json.dumps(perf.get("top_creators") or [], ensure_ascii=False)[:2000]
            for iv in perf.get("intervals") or []:
                sales = iv.get("sales") or {}
                gmv = float((sales.get("gmv") or {}).get("amount") or 0)
                traffic_bd = (iv.get("traffic") or {}).get("breakdowns") or []
                cnr = iv.get("cancel_and_refunds") or {}
                if gmv == 0 and not sales.get("orders") and not traffic_bd:
                    continue  # 활동 없는 구간 스킵
                rows.append([
                    "'" + pid,
                    iv.get("start_date", ""), iv.get("end_date", ""),
                    gmv, sales.get("orders", 0), sales.get("items_sold", 0),
                    cnr.get("returned", 0), cnr.get("canceled", 0),
                    cnr.get("refunded", 0), cnr.get("replacements", 0),
                    json.dumps(sales.get("breakdowns") or [], ensure_ascii=False)[:2000],
                    json.dumps(traffic_bd, ensure_ascii=False)[:2000],
                    ratings, top_contents, top_creators,
                ])
            time.sleep(0.15)

    rows.sort(key=lambda r: (r[1], r[0]))  # 기간시작 → 상품ID 순
    print(f"  총 {len(rows)}행 수집")
    if not rows:
        print("  데이터 없음 - 종료")
        return

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
