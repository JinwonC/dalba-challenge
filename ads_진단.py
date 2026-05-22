"""TikTok Ads API 진단 - 캠페인 목록 + GMV MAX Store ID 확인"""
import requests, json, os, hashlib, hmac, time
from urllib.parse import urlencode, quote

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_tokens.json")
with open(TOKEN_FILE) as f:
    token = json.load(f)["access_token"]

ADVERTISER_ID = "7573855166672355345"
BASE = "https://business-api.tiktok.com/open_api/v1.3"
headers = {"Access-Token": token}

# 1. 전체 캠페인 목록
print("=" * 50)
print("전체 캠페인 목록 조회 중...")
r = requests.get(f"{BASE}/campaign/get/", headers=headers, params={
    "advertiser_id": ADVERTISER_ID,
    "page_size": 100,
    "filtering": json.dumps({"primary_status": "STATUS_ALL"}),
}, timeout=30)

data = r.json()
print(f"전체 캠페인 수: {data.get('data',{}).get('page_info',{}).get('total_number', 0)}")
for c in data.get("data", {}).get("list", []):
    print(f"  {c['campaign_name']}")
    print(f"    상태: {c['operation_status']} | 목표: {c.get('objective_type','')} | 생성: {c['create_time']}")

# 2. GMV MAX Store endpoint (raw)
print()
print("=" * 50)
print("GMV MAX Store 엔드포인트 테스트...")
for path in [
    "/gmv_max/advertiser/store/get/",
    "/gmv_max/store/get/",
]:
    r2 = requests.get(f"{BASE}{path}", headers=headers, params={"advertiser_id": ADVERTISER_ID}, timeout=30)
    print(f"  {path} → status={r2.status_code}, body={r2.text[:300]}")

# 3. 광고주 정보
print()
print("=" * 50)
print("광고주 정보 조회 중...")
r3 = requests.get(f"{BASE}/advertiser/info/", headers=headers, params={
    "advertiser_ids": json.dumps([ADVERTISER_ID]),
}, timeout=30)
d3 = r3.json()
for adv in d3.get("data", {}).get("list", []):
    print(f"  이름: {adv.get('name')}")
    print(f"  국가: {adv.get('country')}, 통화: {adv.get('currency')}")
    for k, v in adv.items():
        if any(x in k.lower() for x in ["store", "shop", "tts", "ecom"]):
            print(f"  [{k}]: {v}")

# 4. TikTok Shop API로 shop ID 조회
print()
print("=" * 50)
print("TikTok Shop API로 Shop ID 조회...")
SHOP_APP_KEY = "6jd7l2nu36rd4"
SHOP_APP_SECRET = "9ab6f9c3467d53c72ca6e346c18b8071338f0ce4"
SHOP_TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tokens.json")

def make_sign(path, params):
    keys = sorted(params.keys())
    s = SHOP_APP_SECRET + path
    for k in keys:
        s += k + str(params[k])
    s += SHOP_APP_SECRET
    return hmac.new(SHOP_APP_SECRET.encode(), s.encode(), hashlib.sha256).hexdigest()

if os.path.exists(SHOP_TOKEN_FILE):
    with open(SHOP_TOKEN_FILE) as f:
        shop_token = json.load(f).get("access_token", "")
    if shop_token:
        path = "/seller/202309/shops"
        ts = str(int(time.time()))
        params = {"app_key": SHOP_APP_KEY, "timestamp": ts}
        params["sign"] = make_sign(path, params)
        url = "https://open-api.tiktokglobalshop.com" + path + "?" + urlencode(params, quote_via=quote)
        r4 = requests.get(url, headers={"x-tts-access-token": shop_token}, timeout=30)
        print(f"  /seller/202309/shops → status={r4.status_code}")
        print(f"  응답: {r4.text[:500]}")
    else:
        print("  tokens.json에 access_token 없음")
else:
    print("  tokens.json 파일 없음")
