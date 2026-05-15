"""
TikTok Shop Access Token 자동 갱신 모듈
다른 스크립트에서 import해서 사용합니다.
"""

import hmac
import hashlib
import json
import os
import time
import requests

APP_KEY = "6jd7l2nu36rd4"
APP_SECRET = "9ab6f9c3467d53c72ca6e346c18b8071338f0ce4"

# 항상 스크립트 파일과 같은 폴더에 저장
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tokens.json")


def save_tokens(access_token: str, refresh_token: str):
    with open(TOKEN_FILE, "w") as f:
        json.dump({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "saved_at": int(time.time())
        }, f)


def load_tokens() -> dict:
    if not os.path.exists(TOKEN_FILE):
        return {}
    with open(TOKEN_FILE, "r") as f:
        return json.load(f)


def refresh_access_token(refresh_token: str) -> str | None:
    params = {
        "app_key": APP_KEY,
        "app_secret": APP_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    url = "https://auth.tiktok-shops.com/api/v2/token/refresh"
    resp = requests.get(url, params=params, timeout=30)
    data = resp.json()

    if data.get("code") == 0:
        token_data = data.get("data", {})
        new_access = token_data.get("access_token")
        new_refresh = token_data.get("refresh_token", refresh_token)
        save_tokens(new_access, new_refresh)
        print("  ✅ Access Token 자동 갱신 완료")
        return new_access
    else:
        print(f"  ❌ 토큰 갱신 실패: {data.get('message')}")
        return None


def get_valid_token(fallback_access_token: str, fallback_refresh_token: str) -> str:
    """
    저장된 토큰이 있으면 사용, 없으면 fallback 토큰 저장 후 사용
    API 호출 실패 시 자동으로 refresh 시도
    """
    tokens = load_tokens()
    if tokens.get("access_token"):
        return tokens["access_token"]

    # 처음 실행 시 현재 토큰 저장
    save_tokens(fallback_access_token, fallback_refresh_token)
    return fallback_access_token


def handle_token_expired(fallback_refresh_token: str) -> str | None:
    """토큰 만료 시 호출 - refresh token으로 갱신"""
    tokens = load_tokens()
    refresh_token = tokens.get("refresh_token", fallback_refresh_token)
    return refresh_access_token(refresh_token)
