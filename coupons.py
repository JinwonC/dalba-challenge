"""TikTok Shop Get Coupon
→ 스프레드시트 1fVWfi... 'Get Coupon' 탭

1) 쿠폰 목록 검색 API로 coupon_id 수집 (경로/메서드 자동 탐색)
2) 쿠폰별 상세 조회 후 평탄화하여 저장 (생성일 오름차순)
기본 기간: 2026-07-01 이후 생성된 쿠폰
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
SHEET_NAME = "Get Coupon"
SERVICE_ACCOUNT_FILE = "service_account.json"

BASE = "https://open-api.tiktokglobalshop.com"
LA_TZ = ZoneInfo("America/Los_Angeles")

_VERS = ["202405", "202406", "202407", "202409", "202410", "202411",
         "202412", "202501", "202502", "202505", "202309"]
SEARCH_PATHS = [f"/promotion/{v}/coupons/search" for v in _VERS]
DETAIL_TEMPLATES = [f"/promotion/{v}/coupons/{{cid}}" for v in _VERS]

HEADERS_ROW = [
    "쿠폰ID", "제목", "상태", "표시유형", "생성일시(LA)", "수정일시(LA)",
    "수령시작", "수령종료", "사용시작", "사용종료", "사용기간유형",
    "프로모코드", "대상구매자", "표시채널",
    "1인수령한도", "총수령한도", "사용한도", "수령수", "사용수",
    "할인유형", "할인금액", "할인율", "최대할인",
    "조건유형", "최소구매액", "상품범위", "상품ID목록",
    "생성경로", "약관", "라이브태스크(JSON)",
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
    params["sign"] = sign_str(path, {k: v for k, v in params.items()}, body)
    headers = {"content-type": "application/json",
               "x-tts-access-token": get_valid_token(ACCESS_TOKEN, REFRESH_TOKEN)}
    for attempt in range(1, 4):
        try:
            if method == "POST":
                r = requests.post(BASE + path, params=params, headers=headers,
                                  data=body, timeout=45)
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


def search_page(path: str, page_size: int = 50, page_token: str | None = None):
    """page_size는 정수로 body에 담아야 함 (query string이면 타입 오류)."""
    body = {"page_size": page_size}
    if page_token:
        body["page_token"] = page_token
    return call(path, "POST", body)


def probe_search() -> tuple[str, str] | tuple[None, None]:
    for path in SEARCH_PATHS:
        d = search_page(path, 20)
        code = d.get("code") if d else None
        msg = str(d.get("message"))[:60] if d else "-"
        if code != 36009004 or "version" not in msg:
            print(f"  probe POST {path} → code={code} msg={msg}")
        if code == 0:
            return path, "POST"
        time.sleep(0.15)
    return None, None


def probe_detail(cid: str) -> str | None:
    for tpl in DETAIL_TEMPLATES:
        d = call(tpl.format(cid=cid), "GET")
        code = d.get("code") if d else None
        print(f"  probe {tpl} → code={code} msg={str(d.get('message'))[:60] if d else '-'}")
        if code == 0:
            return tpl
        time.sleep(0.2)
    return None


def ms_la(ts) -> str:
    try:
        v = int(ts)
        if v > 10_000_000_000:  # ms
            v //= 1000
        return datetime.fromtimestamp(v, LA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return ""


def row_of(c: dict) -> list:
    cd = c.get("claim_duration") or {}
    rd = c.get("redemption_duration") or {}
    ul = c.get("usage_limits") or {}
    us = c.get("usage_stats") or {}
    dc = c.get("discount") or {}
    th = c.get("threshold") or {}
    return [
        c.get("id", ""), c.get("title", ""), str(c.get("status", "")).strip(),
        str(c.get("display_type", "")).strip(),
        ms_la(c.get("create_time")), ms_la(c.get("update_time")),
        ms_la(cd.get("start_time")), ms_la(cd.get("end_time")),
        ms_la(rd.get("start_time")), ms_la(rd.get("end_time")), rd.get("type", ""),
        c.get("promo_code", ""), str(c.get("target_buyer_segment", "")).strip(),
        ", ".join(c.get("display_channels") or []),
        ul.get("single_buyer_claim_limit", ""), ul.get("total_claim_limit", ""),
        ul.get("redemption_limit", ""),
        us.get("claimed_count", ""), us.get("redeemed_count", ""),
        dc.get("type", ""), (dc.get("reduction_amount") or {}).get("amount", ""),
        dc.get("percentage", ""), (dc.get("max_discount") or {}).get("amount", ""),
        th.get("type", ""), (th.get("min_spend") or {}).get("amount", ""),
        c.get("product_scope", ""), ", ".join(c.get("product_ids") or []),
        c.get("creation_source", ""), str(c.get("seller_tnc", ""))[:500],
        json.dumps(c.get("live_tasks") or [], ensure_ascii=False)[:1000],
    ]


def main():
    raw = sys.argv[1] if len(sys.argv) > 1 else "2026-07-01 ~ 2026-08-07"
    nums = re.findall(r"\d{4}-\d{1,2}-\d{1,2}", raw)
    start = nums[0]
    end = nums[1] if len(nums) > 1 else nums[0]
    start_dt = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=LA_TZ)
    end_dt = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=LA_TZ) + timedelta(days=1)
    print(f"\n=== Get Coupon [{start} ~ {end}] ===")

    print("  [1/3] 쿠폰 목록 엔드포인트 탐색...")
    spath, smethod = probe_search()
    if not spath:
        print("  ❌ 쿠폰 목록 엔드포인트 확인 실패 — 문서 경로 필요")
        sys.exit(1)
    print(f"    ✅ {smethod} {spath}")

    print("  [2/3] 쿠폰 목록 수집...")
    coupons_raw: list[dict] = []
    page_token = None
    while True:
        d = search_page(spath, 50, page_token)
        if not d or d.get("code") != 0:
            print(f"    중단: code={d.get('code') if d else '-'} msg={str(d.get('message'))[:60] if d else '-'}")
            break
        data = d.get("data", {})
        items = data.get("coupons") or data.get("items") or []
        coupons_raw.extend(items)
        nt = data.get("next_page_token") or None
        if not nt or nt == page_token:
            break
        page_token = nt
        time.sleep(0.2)
    print(f"    쿠폰 {len(coupons_raw)}건 (전체)")

    def in_range(c) -> bool:
        try:
            v = int(c.get("create_time") or 0)
            if v > 10_000_000_000:
                v //= 1000
            return start_dt.timestamp() <= v < end_dt.timestamp()
        except (TypeError, ValueError):
            return False

    targets = [c for c in coupons_raw if in_range(c)] or coupons_raw
    targets.sort(key=lambda c: int(c.get("create_time") or 0))
    print(f"    대상 {len(targets)}건 (생성일 {start} 이후)")
    if not targets:
        print("  대상 없음 - 종료")
        return

    print("  [3/3] 쿠폰 상세 조회...")
    dtpl = probe_detail(str(targets[0].get("id", "")))
    rows = []
    for i, c in enumerate(targets, 1):
        cid = str(c.get("id", ""))
        detail = None
        if dtpl:
            d = call(dtpl.format(cid=cid), "GET")
            if d and d.get("code") == 0:
                detail = (d.get("data") or {}).get("coupon")
        rows.append(row_of(detail or c))
        if i % 50 == 0:
            print(f"    진행 {i}/{len(targets)}")
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
