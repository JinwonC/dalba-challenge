"""남은 API들의 접근 권한(scope) 일괄 점검.
각 엔드포인트를 1회씩 호출해 code/message로 사용 가능 여부만 판정한다.
(105005 = 앱 권한 없음, 0 = 사용 가능, 36009004 = 경로/버전 문제)
"""
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode, quote

import requests
from token_manager import get_valid_token, handle_token_expired

APP_KEY = "6jd7l2nu36rd4"
APP_SECRET = "9ab6f9c3467d53c72ca6e346c18b8071338f0ce4"
ACCESS_TOKEN = "TTP_8qmwDAAAAAAKxe5s-tyxQjFx-BLmHCzEUHx_N8KtbJs8REguA-PlojAyV0wGbdEfcH65GTeVkz7R1pOu5g44xImqf4SrMwS1YxCDFaFiR71wCyyvCuiX9V4xVHdkwwVZjC2fEb9DckyVqVjeUiW-H2PBtsmHPpwLM6krtq-pI3-bR3oq5XS_LA"
REFRESH_TOKEN = "TTP_77fQXQAAAACRYHgjQ_4vEa-Xhe5ikMt0yvs0Zs2i5flXWHMzwGflyAsL_dJ53tHERRwYkVRh9AI"
SHOP_CIPHER = "TTP_uE19hAAAAADx5Flb4Y_fjmWFiQfOEyTT"
BASE = "https://open-api.tiktokglobalshop.com"
ORDER_SEARCH = "/order/202309/orders/search"


def sign_str(path, params, body=""):
    s = APP_SECRET + path
    for k in sorted(params.keys()):
        s += k + str(params[k])
    s += body
    return hmac.new(APP_SECRET.encode(), (s + APP_SECRET).encode(), hashlib.sha256).hexdigest()


def call(path, method="GET", body_obj=None):
    params = {"app_key": APP_KEY, "shop_cipher": SHOP_CIPHER, "timestamp": str(int(time.time()))}
    body = json.dumps(body_obj, separators=(",", ":")) if body_obj is not None else ""
    params["sign"] = sign_str(path, dict(params), body)
    headers = {"content-type": "application/json",
               "x-tts-access-token": get_valid_token(ACCESS_TOKEN, REFRESH_TOKEN)}
    try:
        if method == "POST":
            r = requests.post(BASE + path, params=params, headers=headers, data=body, timeout=30)
        else:
            r = requests.get(BASE + path + "?" + urlencode(params, quote_via=quote),
                             headers=headers, timeout=30)
        d = r.json()
        if d.get("code") == 105002:
            handle_token_expired(REFRESH_TOKEN)
        return d.get("code"), str(d.get("message"))[:80]
    except Exception as e:
        return "ERR", str(e)[:80]


def verdict(code, msg):
    if code == 0:
        return "✅ 사용가능"
    if code == 105005:
        return "🔒 권한없음(scope 필요)"
    if code == 36009004 and "version" in msg:
        return "❓ 경로/버전 불일치"
    return f"⚠️ code={code}"


def main():
    print("\n=== API 접근 권한 점검 ===\n")

    # 샘플 주문 1건 확보 (주문 관련 API 테스트용)
    body = json.dumps({"create_time_ge": 1754438400, "create_time_lt": 1754524800},
                      separators=(",", ":"))
    params = {"app_key": APP_KEY, "page_size": "10", "shop_cipher": SHOP_CIPHER,
              "sort_field": "create_time", "sort_order": "ASC",
              "timestamp": str(int(time.time()))}
    qp = dict(params)
    qp["sign"] = sign_str(ORDER_SEARCH, params, body)
    oid = ""
    try:
        r = requests.post(BASE + ORDER_SEARCH, params=qp,
                          headers={"content-type": "application/json",
                                   "x-tts-access-token": get_valid_token(ACCESS_TOKEN, REFRESH_TOKEN)},
                          data=body, timeout=30).json()
        orders = (r.get("data") or {}).get("orders") or []
        if orders:
            oid = str(orders[0].get("id", ""))
    except Exception as e:
        print(f"샘플 주문 조회 실패: {e}")
    print(f"샘플 주문ID: {oid or '(없음)'}\n")

    tests = [
        ("Get Order Detail (seller.order.info)", f"/order/202309/orders?ids={oid}", "GET", None),
        ("Get Price Detail (seller.order.info)", f"/order/202407/orders/{oid}/price_detail", "GET", None),
        ("Get Transactions by Order (seller.finance.info)",
         f"/finance/202309/orders/{oid}/statement_transactions", "GET", None),
        ("Get Coupon 목록 (seller.promotion.info)", "/promotion/202406/coupons/search", "POST", {"page_size": 10}),
        ("Get Activity 목록 (seller.promotion.info)", "/promotion/202309/activities/search", "POST", {"page_size": 10}),
        ("상품 목록 (seller.product.basic)", "/product/202312/products/search", "POST", {"page_size": 10}),
    ]
    for label, path, method, body_obj in tests:
        if "{}" in path or (oid == "" and "/orders/" in path):
            print(f"{label:52s} → (샘플 주문 없어 건너뜀)")
            continue
        code, msg = call(path, method, body_obj)
        print(f"{label:52s} → {verdict(code, msg)}  | {msg}")
        time.sleep(0.3)


if __name__ == "__main__":
    main()
