"""
각 API 실제 응답 구조 확인 → _진단_결과.json 저장
실행: python _진단.py 2026-05-15
"""
import hashlib, hmac, time, json, sys, os
from urllib.parse import urlencode, quote
from datetime import datetime, timedelta
import requests

APP_KEY     = "6jd7l2nu36rd4"
APP_SECRET  = "9ab6f9c3467d53c72ca6e346c18b8071338f0ce4"
SHOP_CIPHER = "TTP_uE19hAAAAADx5Flb4Y_fjmWFiQfOEyTT"
BASE_URL    = "https://open-api.tiktokglobalshop.com"
TOKEN_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tokens.json")

def get_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            d = json.load(f)
            if d.get("access_token"):
                return d["access_token"]
    return ""

def make_sign(path, params):
    keys = sorted(params.keys())
    s = APP_SECRET + path
    for k in keys:
        s += k + str(params[k])
    s += APP_SECRET
    return hmac.new(APP_SECRET.encode(), s.encode(), hashlib.sha256).hexdigest()

def call_get(path, extra={}):
    ts = str(int(time.time()))
    params = {"app_key": APP_KEY, "shop_cipher": SHOP_CIPHER, "timestamp": ts, **extra}
    params["sign"] = make_sign(path, params)
    url = BASE_URL + path + "?" + urlencode(params, quote_via=quote)
    hdrs = {"x-tts-access-token": get_token(), "content-type": "application/json"}
    try:
        r = requests.get(url, headers=hdrs, timeout=30)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

date_str = sys.argv[1] if len(sys.argv) > 1 else input("날짜 입력 (예: 2026-05-15): ").strip()
next_day = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

print(f"\n진단 시작: {date_str}")
results = {}

# 1. 상품별 성과
print("  [1/8] 상품별_성과...")
results["상품별_성과"] = call_get("/analytics/202509/shop_products/performance", {
    "start_date_ge": date_str, "end_date_lt": next_day,
    "currency": "USD", "page_size": "3", "sort_field": "gmv", "sort_order": "DESC"
})

# 2. SKU별 성과
print("  [2/8] SKU별_성과...")
results["SKU별_성과"] = call_get("/analytics/202509/shop_skus/performance", {
    "start_date_ge": date_str, "end_date_lt": next_day,
    "currency": "USD", "page_size": "3", "sort_field": "gmv", "sort_order": "DESC"
})

# 3. 영상 전체 요약
print("  [3/8] 영상_전체_요약...")
results["영상_전체_요약"] = call_get("/analytics/202509/shop_videos/overview_performance", {
    "start_date_ge": date_str, "end_date_lt": next_day,
    "granularity": "ALL", "currency": "USD", "account_type": "ALL"
})

# 4. 라이브 성과 목록
print("  [4/8] 라이브_성과...")
results["라이브_성과"] = call_get("/analytics/202509/shop_lives/performance", {
    "start_date_ge": date_str, "end_date_lt": next_day,
    "currency": "USD", "account_type": "ALL", "page_size": "3"
})

# 5. 라이브 전체 요약
print("  [5/8] 라이브_전체_요약...")
results["라이브_전체_요약"] = call_get("/analytics/202509/shop_lives/overview_performance", {
    "start_date_ge": date_str, "end_date_lt": next_day,
    "granularity": "1D", "currency": "USD", "account_type": "ALL"
})

# live_id 추출 (분당/상품별 성과에 필요)
live_id = None
lives_data = (results["라이브_성과"].get("data") or {})
lives = lives_data.get("live_stream_sessions") or lives_data.get("lives") or lives_data.get("list") or []
if lives:
    live_id = lives[0].get("id") or lives[0].get("live_id")
    print(f"  → live_id: {live_id}")

# 상품 ID 추출 (상품별 성과 상세에 필요)
product_id = None
prods = (results["상품별_성과"].get("data") or {}).get("products") or []
if prods:
    product_id = prods[0].get("id")
    print(f"  → product_id: {product_id}")

# video_id 추출 (영상 상품별 성과에 필요)
video_id = None
print("  [영상 목록 조회...]")
vlist = call_get("/analytics/202409/shop_videos/performance", {
    "start_date_ge": date_str, "end_date_lt": next_day,
    "currency": "USD", "account_type": "ALL",
    "page_size": "3", "sort_field": "gmv", "sort_order": "DESC"
})
results["영상_목록"] = vlist
vids = (vlist.get("data") or {}).get("videos") or []
if vids:
    video_id = vids[0].get("id") or vids[0].get("video_id")
    print(f"  → video_id: {video_id}")

# 6. 라이브 분당 성과
if live_id:
    print(f"  [6/8] 라이브_분당_성과 ({live_id})...")
    path = f"/analytics/202510/shop_lives/{live_id}/performance_per_minutes"
    results["라이브_분당_성과"] = call_get(path, {"currency": "USD"})
else:
    results["라이브_분당_성과"] = {"skipped": "라이브 없음"}
    print("  [6/8] 라이브_분당_성과 - 스킵 (라이브 없음)")

# 7. 라이브 상품별 성과
if live_id:
    print(f"  [7/8] 라이브_상품별_성과 ({live_id})...")
    path = f"/analytics/202512/shop/{live_id}/products_performance"
    results["라이브_상품별_성과"] = call_get(path, {
        "currency": "USD", "sort_field": "direct_gmv", "sort_order": "DESC"
    })
else:
    results["라이브_상품별_성과"] = {"skipped": "라이브 없음"}
    print("  [7/8] 라이브_상품별_성과 - 스킵 (라이브 없음)")

# 8. 영상 상품별 성과
if video_id:
    print(f"  [8/8] 영상_상품별_성과 ({video_id})...")
    path = f"/analytics/202509/shop_videos/{video_id}/products/performance"
    results["영상_상품별_성과"] = call_get(path, {
        "start_date_ge": date_str, "end_date_lt": next_day,
        "currency": "USD", "page_size": "3", "sort_field": "gmv", "sort_order": "DESC"
    })
else:
    results["영상_상품별_성과"] = {"skipped": "영상 없음"}
    print("  [8/8] 영상_상품별_성과 - 스킵 (영상 없음)")

# 9. 상품별 성과 상세
if product_id:
    print(f"  [신규] 상품별_성과_상세 ({product_id})...")
    path = f"/analytics/202509/shop_products/{product_id}/performance"
    results["상품별_성과_상세"] = call_get(path, {
        "start_date_ge": date_str, "end_date_lt": next_day,
        "granularity": "ALL", "currency": "USD"
    })
else:
    results["상품별_성과_상세"] = {"skipped": "상품 없음"}
    print("  [신규] 상품별_성과_상세 - 스킵 (상품 없음)")

# 결과 저장
out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_진단_결과.json")
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n✅ 진단 완료! 결과 저장됨: _진단_결과.json")
print("이제 아래 명령어를 실행해주세요:")
print('  git add TEST/_진단_결과.json && git commit -m "진단 결과" && git push')
