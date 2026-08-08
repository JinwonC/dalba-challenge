"""TikTok Shop Get Activity (상품 할인 / 플래시딜 프로모션)
→ 스프레드시트 1fVWfi... 'Get Activity' 탭

1) 프로모션 활동 목록 검색으로 activity_id 수집 (경로/메서드 자동 탐색)
2) 활동별 상세 조회 → 상품(및 SKU) 단위 행으로 저장
기본 기간: 2026-07-01 이후 생성된 활동
쿠폰은 별도 'Get Coupon' 탭 참조 (이 API는 쿠폰 미포함).
"""
import hashlib
import hmac
import json
import re
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlencode, quote

import requests
from google.oauth2.service_account import Credentials
import gspread
from token_manager import get_valid_token, handle_token_expired

APP_KEY = "6jd7l2nu36rd4"
APP_SECRET = "9ab6f9c3467d53c72ca6e346c18b8071338f0ce4"
ACCESS_TOKEN = "TTP_8qmwDAAAAAAKxe5s-tyxQjFx-BLmHCzEUHx_N8KtbJs8REguA-PlojAyV0wGbdEfcH65GTeVkz7R1pOu5g44xImqf4SrMwS1YxCDFaFiR71wCyyvCuiX9V4xVHdkwwVZjC2fEb9DckyVqVjeUiW-H2PBtsmHPpwLM6krtq-pI3-bR3oq5XS_LA"
REFRESH_TOKEN = "TTP_77fQXQAAAACRYHgjQ_4vEa-Xhe5ikMt0yvs0Zs2i5flXWHMzwGflyAsL_dJ53tHERRwYkVRh9AI"
SHOP_CIPHER = "TTP_uE19hAAAAADx5Flb4Y_fjmWFiQfOEyTT"

SPREADSHEET_ID = "1fVWfictZo6BiKyWO-eFfSo3fAVscOQMPVg1gqa5oMWI"
SHEET_NAME = "Get Activity"
SERVICE_ACCOUNT_FILE = "service_account.json"

BASE = "https://open-api.tiktokglobalshop.com"
LA_TZ = ZoneInfo("America/Los_Angeles")

SEARCH_PATHS = [
    "/promotion/202309/activities/search",
    "/promotion/202406/activities/search",
    "/promotion/202501/activities/search",
]
DETAIL_TEMPLATES = [
    "/promotion/202309/activities/{aid}",
    "/promotion/202406/activities/{aid}",
    "/promotion/202501/activities/{aid}",
]

HEADERS_ROW = [
    "활동ID", "제목", "활동유형", "상태", "기간유형",
    "시작일시(LA)", "종료일시(LA)", "생성일시(LA)", "수정일시(LA)",
    "상품레벨", "대상유저",
    "상품ID", "상품_할인율", "상품_활동가", "통화",
    "상품_수량한도", "1인당한도", "상품_사용수량",
    "SKU ID", "SKU_할인율", "SKU_활동가", "SKU_수량한도", "SKU_1인당한도", "SKU_사용수량",
    "참여제한(JSON)", "할인상세(JSON)", "혜택상품(JSON)",
]


def sign_str(path: str, params: dict, body: str = "") -> str:
    s = APP_SECRET + path
    for k in sorted(params.keys()):
        s += k + str(params[k])
    s += body
    return hmac.new(APP_SECRET.encode(), (s + APP_SECRET).encode(), hashlib.sha256).hexdigest()


def call(path: str, method: str = "GET", body_obj: dict | None = None, extra: dict | None = None):
    params = {"app_key": APP_KEY, "shop_cipher": SHOP_CIPHER,
              "timestamp": str(int(time.time())), **(extra or {})}
    body = json.dumps(body_obj, separators=(",", ":")) if body_obj is not None else ""
    params["sign"] = sign_str(path, dict(params), body)
    headers = {"content-type": "application/json",
               "x-tts-access-token": get_valid_token(ACCESS_TOKEN, REFRESH_TOKEN)}
    for attempt in range(1, 4):
        try:
            if method == "POST":
                r = requests.post(BASE + path, params=params, headers=headers, data=body, timeout=45)
            else:
                r = requests.get(BASE + path + "?" + urlencode(params, quote_via=quote),
                                 headers=headers, timeout=45)
            d = r.json()
            if d.get("code") == 105002:
                nt = handle_token_expired(REFRESH_TOKEN)
                if nt:
                    headers["x-tts-access-token"] = nt
                    continue
            return d
        except Exception as e:
            print(f"    [오류] {e} (시도 {attempt}/3)")
            time.sleep(1.5 * attempt)
    return None


def probe_search():
    for path in SEARCH_PATHS:
        for method, body in (("POST", {}), ("GET", None)):
            d = call(path, method, body, {"page_size": "20"})
            code = d.get("code") if d else None
            print(f"  probe {method} {path} → code={code} msg={str(d.get('message'))[:60] if d else '-'}")
            if code == 0:
                return path, method
            time.sleep(0.2)
    return None, None


def probe_detail(aid: str):
    for tpl in DETAIL_TEMPLATES:
        d = call(tpl.format(aid=aid), "GET")
        code = d.get("code") if d else None
        print(f"  probe {tpl} → code={code} msg={str(d.get('message'))[:60] if d else '-'}")
        if code == 0:
            return tpl
        time.sleep(0.2)
    return None


def la(ts) -> str:
    try:
        v = int(ts)
        if v > 10_000_000_000:
            v //= 1000
        return datetime.fromtimestamp(v, LA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return ""


def rows_of(a: dict) -> list[list]:
    base = [
        a.get("activity_id", "") or a.get("id", ""), a.get("title", ""),
        a.get("activity_type", ""), a.get("status", ""), a.get("duration_type", ""),
        la(a.get("begin_time")), la(a.get("end_time")),
        la(a.get("create_time")), la(a.get("update_time")),
        a.get("product_level", ""), (a.get("target_user_info") or {}).get("user_type", ""),
    ]
    tail = [
        json.dumps(a.get("participation_limit") or [], ensure_ascii=False)[:1000],
        json.dumps(a.get("discount") or {}, ensure_ascii=False)[:3000],
        json.dumps(a.get("benefit_products") or [], ensure_ascii=False)[:1000],
    ]
    prods = a.get("products") or []
    if not prods:
        return [base + [""] * (len(HEADERS_ROW) - len(base) - len(tail)) + tail]
    rows = []
    for p in prods:
        ap = p.get("activity_price") or {}
        pbase = base + [
            p.get("id", ""), p.get("discount", ""), ap.get("amount", ""), ap.get("currency", ""),
            p.get("quantity_limit", ""), p.get("quantity_per_user", ""), p.get("used_quantity", ""),
        ]
        skus = p.get("skus") or []
        if not skus:
            rows.append(pbase + ["", "", "", "", "", ""] + tail)
        for s in skus:
            sap = s.get("activity_price") or {}
            rows.append(pbase + [
                s.get("id", ""), s.get("discount", ""), sap.get("amount", ""),
                s.get("quantity_limit", ""), s.get("quantity_per_user", ""), s.get("used_quantity", ""),
            ] + tail)
    return rows


def main():
    raw = sys.argv[1] if len(sys.argv) > 1 else "2026-07-01 ~ 2026-08-07"
    nums = re.findall(r"\d{4}-\d{1,2}-\d{1,2}", raw)
    start = nums[0]
    end = nums[1] if len(nums) > 1 else nums[0]
    start_dt = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=LA_TZ)
    end_dt = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=LA_TZ) + timedelta(days=1)
    print(f"\n=== Get Activity [{start} ~ {end}] ===")

    print("  [1/3] 활동 목록 엔드포인트 탐색...")
    spath, smethod = probe_search()
    if not spath:
        print("  ❌ 활동 목록 엔드포인트 확인 실패 — 문서 경로 필요")
        sys.exit(1)
    print(f"    ✅ {smethod} {spath}")

    print("  [2/3] 활동 목록 수집...")
    items: list[dict] = []
    page_token = None
    while True:
        extra = {"page_size": "50"}
        if page_token:
            extra["page_token"] = page_token
        d = call(spath, smethod, {} if smethod == "POST" else None, extra)
        if not d or d.get("code") != 0:
            print(f"    중단: code={d.get('code') if d else '-'}")
            break
        data = d.get("data", {})
        items.extend(data.get("activities") or data.get("items") or [])
        nt = data.get("next_page_token") or None
        if not nt or nt == page_token:
            break
        page_token = nt
        time.sleep(0.2)
    print(f"    활동 {len(items)}건 (전체)")

    def in_range(a) -> bool:
        try:
            v = int(a.get("create_time") or 0)
            if v > 10_000_000_000:
                v //= 1000
            return start_dt.timestamp() <= v < end_dt.timestamp()
        except (TypeError, ValueError):
            return False

    targets = [a for a in items if in_range(a)] or items
    targets.sort(key=lambda a: int(a.get("create_time") or 0))
    print(f"    대상 {len(targets)}건 (생성일 {start} 이후)")
    if not targets:
        print("  대상 없음 - 종료")
        return

    print("  [3/3] 활동 상세 조회...")
    first_id = str(targets[0].get("activity_id") or targets[0].get("id") or "")
    dtpl = probe_detail(first_id)
    rows: list[list] = []
    for i, a in enumerate(targets, 1):
        aid = str(a.get("activity_id") or a.get("id") or "")
        detail = None
        if dtpl:
            d = call(dtpl.format(aid=aid), "GET")
            if d and d.get("code") == 0:
                detail = d.get("data") or {}
        rows.extend(rows_of(detail or a))
        if i % 25 == 0:
            print(f"    진행 {i}/{len(targets)} · 누적 {len(rows)}행")
        time.sleep(0.15)

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

    data_rows = [HEADERS_ROW] + rows
    for attempt in range(1, 9):
        try:
            sheet.update(data_rows, value_input_option="USER_ENTERED")
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
