"""TikTok Shop Video Performance Details (202509) → 'SHOP VIDEO PERFORMANCE' 탭

1) 202605 리스트 API(30일 청크)로 기간 내 영상 목록 수집
2) 포스팅일이 시작일 이후 & GMV > 0 인 영상만 선별 (영상별 호출이라 전량 불가)
3) 각 영상에 대해 /analytics/202509/shop_videos/{id}/performance 를
   30일 청크(granularity=ALL)로 조회, 가산 지표 합산 + ctr/gpm 재계산
4) 스프레드시트 15dP91bH...(US 매출/지표) 'SHOP VIDEO PERFORMANCE' 탭에
   포스팅일 오름차순으로 저장. viewer_profile 분포는 JSON 문자열로 저장.
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
SHEET_NAME = "SHOP VIDEO PERFORMANCE"
SERVICE_ACCOUNT_FILE = "service_account.json"

BASE = "https://open-api.tiktokglobalshop.com"
LIST_PATH = "/analytics/202605/shop_videos/performance"
MAX_VIDEOS = 30000  # 영상별 상세 호출 상한 (초과 시 GMV 상위 우선)

HEADERS_ROW = [
    "영상ID", "제목", "크리에이터", "포스팅일",
    "GMV($)", "GPM($)", "구매자수", "판매수량",
    "상품노출수", "상품클릭수", "CTR",
    "조회수", "신규팔로워", "공유수", "댓글수", "좋아요수",
    "성별분포", "연령분포", "국가분포",
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
            if d.get("code") == 28001022:  # 기간 오류는 재시도 무의미
                return {"__range_error__": True}
            print(f"  [경고] code={d.get('code')}, msg={d.get('message')} (시도 {attempt}/3)")
        except Exception as e:
            print(f"  [오류] {e} (시도 {attempt}/3)")
        time.sleep(2 * attempt)
    return None


def list_videos(start: str, end: str) -> list[dict]:
    """202605 리스트 API를 30일 청크로 전체 조회, id 기준 병합."""
    merged: dict[str, dict] = {}
    s_dt = datetime.strptime(start, "%Y-%m-%d")
    e_dt = datetime.strptime(end, "%Y-%m-%d")
    chunk_days = 30
    cur = s_dt
    while cur <= e_dt:
        c_end = min(cur + timedelta(days=chunk_days - 1), e_dt)
        cs, ce = cur.strftime("%Y-%m-%d"), c_end.strftime("%Y-%m-%d")
        print(f"  [목록] 청크 {cs} ~ {ce}")
        token = None
        ok = True
        while True:
            d = api_get(LIST_PATH, {
                "start_date_ge": cs, "end_date_lt": ce, "page_size": "100",
                "account_type": "ALL", "sort_field": "gmv", "sort_order": "DESC",
                **({"page_token": token} if token else {}),
            })
            if d and d.get("__range_error__") and chunk_days > 7:
                print("    → 기간 오류, 청크 7일로 축소")
                chunk_days = 7
                ok = False
                break
            if not d or d.get("__range_error__"):
                break
            for v in d.get("data", {}).get("videos") or []:
                vid = str(v.get("id", ""))
                if vid in merged:
                    try:
                        merged[vid]["_gmv"] += float((v.get("gmv") or {}).get("amount") or 0)
                    except (TypeError, ValueError):
                        pass
                else:
                    v["_gmv"] = float((v.get("gmv") or {}).get("amount") or 0)
                    merged[vid] = v
            nt = d.get("data", {}).get("next_page_token") or None
            if not nt or nt == token:
                break
            token = nt
            time.sleep(0.3)
        if ok:
            cur = c_end + timedelta(days=1)
    return list(merged.values())


def fetch_detail_sum(video_id: str, start: str, end: str, chunk_days: int) -> dict:
    """영상 상세를 조회해 가산 지표 합산, ctr/gpm 재계산, 분포는 대표값.
    호출 수를 줄이기 위해 전체 기간 1회 시도 → 기간 오류일 때만 청크 분할."""
    path = f"/analytics/202509/shop_videos/{video_id}/performance"
    agg = {"gmv": 0.0, "customers": 0, "items_sold": 0,
           "product_impressions": 0, "product_clicks": 0,
           "views": 0, "new_followers": 0, "shares": 0, "comments": 0, "likes": 0}
    profile = {"gender": "", "age": "", "country": ""}

    def absorb(d) -> bool:
        if not d or d.get("__range_error__"):
            return False
        perf = d.get("data", {}).get("performance") or {}
        for iv in perf.get("intervals") or []:
            o = (iv.get("sales") or {}).get("overall") or {}
            t = iv.get("traffic") or {}
            agg["gmv"] += float((o.get("gmv") or {}).get("amount") or 0)
            for k in ("customers", "items_sold", "product_impressions", "product_clicks"):
                agg[k] += int(o.get(k) or 0)
            for k in ("views", "new_followers", "shares", "comments", "likes"):
                agg[k] += int(t.get(k) or 0)
        for vp in perf.get("viewer_profile") or []:
            if vp.get("type") == "VIEWERS" or not profile["gender"]:
                profile["gender"] = json.dumps(vp.get("gender_distribution") or [], ensure_ascii=False)
                profile["age"] = json.dumps(vp.get("age_distribution") or [], ensure_ascii=False)
                profile["country"] = json.dumps(vp.get("country_distribution") or [], ensure_ascii=False)
        return True

    # 1회 전체 기간 시도
    whole = api_get(path, {"start_date_ge": start, "end_date_lt": end, "granularity": "ALL"})
    if not (whole and whole.get("__range_error__")):
        absorb(whole)
    else:
        s_dt = datetime.strptime(start, "%Y-%m-%d")
        e_dt = datetime.strptime(end, "%Y-%m-%d")
        cur = s_dt
        while cur <= e_dt:
            c_end = min(cur + timedelta(days=chunk_days - 1), e_dt)
            absorb(api_get(path, {
                "start_date_ge": cur.strftime("%Y-%m-%d"),
                "end_date_lt": c_end.strftime("%Y-%m-%d"),
                "granularity": "ALL",
            }))
            cur = c_end + timedelta(days=1)
            time.sleep(0.1)

    ctr = agg["product_clicks"] / agg["product_impressions"] if agg["product_impressions"] else 0
    gpm = agg["gmv"] / agg["views"] * 1000 if agg["views"] else 0
    return {**agg, "ctr": round(ctr, 4), "gpm": round(gpm, 2), **profile}


def main():
    raw = sys.argv[1] if len(sys.argv) > 1 else "2026-01-01 ~ 2026-08-07"
    nums = re.findall(r"\d{4}-\d{1,2}-\d{1,2}", raw)
    start = nums[0]
    end = nums[1] if len(nums) > 1 else nums[0]
    print(f"\n=== Shop Video Performance Details 202509 [{start} ~ {end}] ===")

    videos = list_videos(start, end)
    print(f"  목록 수집: 총 {len(videos)}개")

    # 포스팅일 필터만 적용 — 매출 없는 영상도 전부 포함
    targets = [v for v in videos
               if str(v.get("video_post_time", ""))[:10] >= start]
    print(f"  대상 (포스팅일 {start} 이후, 매출 무관 전체): {len(targets)}개")
    if len(targets) > MAX_VIDEOS:
        targets.sort(key=lambda v: -v.get("_gmv", 0))
        print(f"  ⚠️ 상한 {MAX_VIDEOS}개 초과 → GMV 상위 {MAX_VIDEOS}개만 (제외 {len(targets)-MAX_VIDEOS}개)")
        targets = targets[:MAX_VIDEOS]
    targets.sort(key=lambda v: str(v.get("video_post_time", "")))

    rows = []
    for i, v in enumerate(targets, 1):
        vid = str(v.get("id", ""))
        if i % 50 == 0 or i == 1:
            print(f"  [상세] {i}/{len(targets)} 조회 중...")
        det = fetch_detail_sum(vid, max(str(v.get("video_post_time", ""))[:10], start), end, 30)
        rows.append([
            "'" + vid, v.get("title", ""), v.get("username", ""),
            v.get("video_post_time", ""),
            round(det["gmv"], 2), det["gpm"], det["customers"], det["items_sold"],
            det["product_impressions"], det["product_clicks"], det["ctr"],
            det["views"], det["new_followers"], det["shares"], det["comments"], det["likes"],
            det["gender"], det["age"], det["country"],
        ])

    print(f"  상세 수집 완료: {len(rows)}행")
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
