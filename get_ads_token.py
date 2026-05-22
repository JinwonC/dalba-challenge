"""TikTok Ads API Access Token 발급"""
import requests
import json
import os

APP_ID = "7641873128328101904"
SECRET = "4745bd7d6aad1b9a46dd05f1b20b006463e09962"
AUTH_CODE = "c001d5b0260c345897ba708a39f40b2ce1c74f9c"

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_tokens.json")

resp = requests.post(
    "https://business-api.tiktok.com/open_api/v1.3/oauth2/access_token/",
    json={"app_id": APP_ID, "secret": SECRET, "auth_code": AUTH_CODE},
    timeout=30
)

data = resp.json()
print(json.dumps(data, indent=2))

if data.get("code") == 0:
    token_data = {
        "access_token": data["data"]["access_token"],
        "advertiser_ids": data["data"].get("advertiser_ids", []),
        "scope": data["data"].get("scope", []),
    }
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)
    print(f"\n✅ 토큰 저장 완료: ads_tokens.json")
    print(f"   Advertiser IDs: {token_data['advertiser_ids']}")
else:
    print(f"\n❌ 실패: code={data.get('code')}, message={data.get('message')}")
