"""상품 리스팅 API 탐색"""
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
    try:
        r = requests.get(url, headers=hdrs, timeout=30)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

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
    try:
        r = requests.post(url, headers=hdrs, data=body, timeout=30)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

print("상품 리스팅 API 탐색\n" + "=" * 50)

# GET 엔드포인트들
get_paths = [
    "/product/202309/products",
    "/product/202312/products",
    "/product/202405/products",
    "/product/202309/seller/products",
]
for path in get_paths:
    d = call_get(path, {"page_size": "5"})
    code = d.get("code", "?")
    msg  = str(d.get("message", ""))[:60]
    total = (d.get("data") or {}).get("total_count", "?")
    print(f"GET {path}")
    print(f"  code={code}, msg={msg}, total={total}")
    if code == 0:
        products = (d.get("data") or {}).get("products") or []
        for p in products[:2]:
            print(f"  → id={p.get('id')}, title={p.get('title') or p.get('name') or list(p.keys())}")
    print()

# POST 엔드포인트들
post_paths = [
    ("/product/202309/products/search", {}),
    ("/product/202312/products/search", {}),
    ("/product/202405/products/search", {}),
]
for path, body in post_paths:
    d = call_post(path, body, {"page_size": "5"})
    code = d.get("code", "?")
    msg  = str(d.get("message", ""))[:60]
    total = (d.get("data") or {}).get("total_count", "?")
    print(f"POST {path}")
    print(f"  code={code}, msg={msg}, total={total}")
    if code == 0:
        products = (d.get("data") or {}).get("products") or []
        for p in products[:2]:
            print(f"  → id={p.get('id')}, title={p.get('title') or p.get('name') or list(p.keys())}")
    print()

input("완료. 엔터 누르면 종료...")
