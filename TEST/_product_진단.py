"""Product API 권한 및 응답 구조 확인"""
import hashlib, hmac, time, json, os
from urllib.parse import urlencode, quote
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

def call_post(path, body_obj, extra_params={}):
    import json as _json
    ts = str(int(time.time()))
    body = _json.dumps(body_obj, separators=(",", ":"))
    params = {"app_key": APP_KEY, "shop_cipher": SHOP_CIPHER, "timestamp": ts, **extra_params}
    # POST는 body도 서명에 포함
    keys = sorted(params.keys())
    s = APP_SECRET + path
    for k in keys:
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

print("\n[Product API 테스트]")
print("  상품 목록 조회 중 (최대 10개)...")

resp = call_post("/product/202309/products/search", {}, {"page_size": "10"})

print(json.dumps(resp, ensure_ascii=False, indent=2)[:3000])

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_product_진단.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(resp, f, ensure_ascii=False, indent=2)

print(f"\n결과 저장: _product_진단.json")
print("이제 아래 명령어 실행:")
print('  git add TEST/_product_진단.json && git commit -m "product 진단" && git push')
