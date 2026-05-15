"""
TikTok Shop Authorization Code → Access Token + Refresh Token 발급
"""

import hmac
import hashlib
import time
import requests
import json

APP_KEY = "6jd7l2nu36rd4"
APP_SECRET = "9ab6f9c3467d53c72ca6e346c18b8071338f0ce4"

def get_tokens(auth_code: str):
    path = "/authorization/202309/token"
    timestamp = str(int(time.time()))

    params = {
        "app_key": APP_KEY,
        "auth_code": auth_code,
        "grant_type": "authorized_code",
        "timestamp": timestamp
    }

    sorted_keys = sorted(params.keys())
    sign_str = APP_SECRET + path
    for key in sorted_keys:
        sign_str += key + str(params[key])
    sign_str += APP_SECRET

    sign = hmac.new(APP_SECRET.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    params["sign"] = sign

    url = "https://open-api.tiktokglobalshop.com" + path
    resp = requests.get(url, params=params, timeout=30)
    data = resp.json()

    if data.get("code") == 0:
        token_data = data.get("data", {})
        print("\n✅ 토큰 발급 성공!")
        print(f"ACCESS_TOKEN  = {token_data.get('access_token')}")
        print(f"REFRESH_TOKEN = {token_data.get('refresh_token')}")
        print(f"만료까지 남은 시간: {token_data.get('access_token_expire_in')}초")
        print(f"Refresh Token 만료: {token_data.get('refresh_token_expire_in')}초")
        return token_data
    else:
        print(f"\n❌ 실패: code={data.get('code')}, message={data.get('message')}")
        print("Auth Code가 만료됐을 수 있습니다. 새로 발급받아주세요.")
        return None


if __name__ == "__main__":
    print("TikTok Shop 인증 코드를 입력하세요.")
    print("(URL에서 code= 뒤의 값)")
    auth_code = input("> ").strip()
    get_tokens(auth_code)
