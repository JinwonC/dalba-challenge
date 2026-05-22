"""상품 성과 API 응답에 상품명 필드 있는지 확인"""
import hashlib, hmac, time, json, os
from urllib.parse import urlencode, quote
import requests

APP_KEY    = "6jd7l2nu36rd4"
APP_SECRET = "9ab6f9c3467d53c72ca6e346c18b8071338f0ce4"
SHOP_CIPHER = "TTP_uE19hAAAAADx5Flb4Y_fjmWFiQfOEyTT"
BASE_URL   = "https://open-api.tiktokglobalshop.com"
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tokens.json")

def get_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            d = json.load(f)
            if d.get("access_token"):
                return d["access_token"]
    return ""

def make_sign(path, params):
    s = APP_SECRET + path
    for k in sorted(params.keys()):
        s += k + str(params[k])
    s += APP_SECRET
    return hmac.new(APP_SECRET.encode(), s.encode(), hashlib.sha256).hexdigest()

def call_get(path, extra={}):
    ts = str(int(time.time()))
    params = {"app_key": APP_KEY, "shop_cipher": SHOP_CIPHER, "timestamp": ts, **extra}
    params["sign"] = make_sign(path, params)
    url = BASE_URL + path + "?" + urlencode(params, quote_via=quote)
    hdrs = {"x-tts-access-token": get_token(), "content-type": "application/json"}
    r = requests.get(url, headers=hdrs, timeout=30)
    return r.json()

from datetime import datetime, timedelta
today = datetime.now()
date_str = (today - timedelta(days=3)).strftime("%Y-%m-%d")
next_day = (today - timedelta(days=2)).strftime("%Y-%m-%d")

print(f"날짜: {date_str}")
print()

# 상품별 성과 응답 구조 확인
print("[1] /analytics/202509/shop_products/performance 응답 첫 항목 전체 key 확인")
d = call_get("/analytics/202509/shop_products/performance", {
    "start_date_ge": date_str, "end_date_lt": next_day,
    "currency": "USD", "page_size": "3", "sort_field": "gmv", "sort_order": "DESC"
})
print(f"code={d.get('code')}, msg={d.get('message')}")
products = (d.get("data") or {}).get("products") or []
if products:
    p = products[0]
    print(f"첫 상품 keys: {list(p.keys())}")
    print(f"첫 상품 전체: {json.dumps(p, ensure_ascii=False)[:500]}")
else:
    print("상품 없음")

# SKU 성과 응답 구조 확인
print()
print("[2] /analytics/202509/shop_skus/performance 응답 첫 항목 전체 key 확인")
d = call_get("/analytics/202509/shop_skus/performance", {
    "start_date_ge": date_str, "end_date_lt": next_day,
    "currency": "USD", "page_size": "3", "sort_field": "gmv", "sort_order": "DESC"
})
print(f"code={d.get('code')}, msg={d.get('message')}")
skus = (d.get("data") or {}).get("skus") or []
if skus:
    s = skus[0]
    print(f"첫 SKU keys: {list(s.keys())}")
    print(f"첫 SKU 전체: {json.dumps(s, ensure_ascii=False)[:500]}")
else:
    print("SKU 없음")

input("\n완료. 엔터 누르면 종료...")
