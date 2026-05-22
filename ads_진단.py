"""상품 ID로 상품명 조회 가능한지 확인"""
import hashlib, hmac, time, json, os
from urllib.parse import urlencode, quote
import requests

APP_KEY    = "6jd7l2nu36rd4"
APP_SECRET = "9ab6f9c3467d53c72ca6e346c18b8071338f0ce4"
SHOP_CIPHER = "TTP_uE19hAAAAADx5Flb4Y_fjmWFiQfOEyTT"
BASE_URL   = "https://open-api.tiktokglobalshop.com"
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tokens.json")

def get_token():
    with open(TOKEN_FILE) as f:
        return json.load(f).get("access_token", "")

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

def call_post(path, body_obj, extra={}):
    ts = str(int(time.time()))
    body = json.dumps(body_obj, separators=(",", ":"))
    params = {"app_key": APP_KEY, "shop_cipher": SHOP_CIPHER, "timestamp": ts, **extra}
    s = APP_SECRET + path
    for k in sorted(params.keys()):
        s += k + str(params[k])
    s += body + APP_SECRET
    params["sign"] = hmac.new(APP_SECRET.encode(), s.encode(), hashlib.sha256).hexdigest()
    url = BASE_URL + path + "?" + urlencode(params, quote_via=quote)
    hdrs = {"x-tts-access-token": get_token(), "content-type": "application/json"}
    r = requests.post(url, headers=hdrs, data=body, timeout=30)
    return r.json()

# 알려진 상품 ID (진단에서 확인된 것)
PRODUCT_ID = "1732030444618027740"

print(f"테스트 상품 ID: {PRODUCT_ID}")
print()

# [1] 개별 상품 상세 조회
print("[1] GET /product/202309/products/{id}")
d = call_get(f"/product/202309/products/{PRODUCT_ID}")
print(f"  code={d.get('code')}, msg={d.get('message')}")
data = d.get("data") or {}
if data:
    print(f"  keys: {list(data.keys())}")
    print(f"  title/name: {data.get('title') or data.get('name') or '없음'}")

print()

# [2] 상품 목록 검색 (POST)
print("[2] POST /product/202309/products/search")
d = call_post("/product/202309/products/search",
              {"product_ids": [PRODUCT_ID]},
              {"page_size": "1"})
print(f"  code={d.get('code')}, msg={d.get('message')}")
products = (d.get("data") or {}).get("products") or []
if products:
    p = products[0]
    print(f"  keys: {list(p.keys())}")
    print(f"  title: {p.get('title') or p.get('name') or '없음'}")

print()

# [3] 다른 버전 시도
print("[3] GET /product/202312/products/{id}")
d = call_get(f"/product/202312/products/{PRODUCT_ID}")
print(f"  code={d.get('code')}, msg={d.get('message')}")
data = d.get("data") or {}
if data:
    print(f"  title: {data.get('title') or data.get('name') or list(data.keys())}")

input("\n완료. 엔터 누르면 종료...")
