"""TikTok Ads API 진단 - GMV MAX 연결 상태 확인"""
import requests, json, os

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads_tokens.json")
with open(TOKEN_FILE) as f:
    token_data = json.load(f)

token = token_data["access_token"]
ADVERTISER_ID = "7573855166672355345"
BASE = "https://business-api.tiktok.com/open_api/v1.3"
headers = {"Access-Token": token}

def call(path, params={}):
    try:
        r = requests.get(f"{BASE}{path}", headers=headers,
                         params={"advertiser_id": ADVERTISER_ID, **params}, timeout=30)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def show(label, d):
    if d is None or "error" in d:
        print(f"  {label} → 응답 실패: {d}")
        return
    print(f"  {label} → code={d.get('code')}, msg={d.get('message')}")
    data = d.get("data") or {}
    if isinstance(data, dict):
        for k, v in data.items():
            print(f"    {k}: {v}")
    elif isinstance(data, list):
        for item in data[:5]:
            print(f"    {item}")

# 1. GMV MAX 스토어 연결 확인
print("=" * 50)
print("[1] GMV MAX 스토어 연결 확인")
d = call("/gmv_max/store/list/")
show("/gmv_max/store/list/", d)

# 2. GMV MAX 캠페인 정보
print()
print("=" * 50)
print("[2] GMV MAX 캠페인 정보")
d = call("/campaign/gmv_max/info/", {"page_size": 20})
show("/campaign/gmv_max/info/", d)

# 3. GMV MAX 세션 목록
print()
print("=" * 50)
print("[3] GMV MAX 세션 목록")
d = call("/campaign/gmv_max/session/list/", {"page_size": 20})
show("/campaign/gmv_max/session/list/", d)

# 4. GMV MAX 리포트 (campaign_id 기준, 필터 없이)
print()
print("=" * 50)
print("[4] GMV MAX 리포트 직접 시도 (2026-05-01, campaign_id 기준)")
try:
    r = requests.get(f"{BASE}/gmv_max/report/get/", headers=headers, params={
        "advertiser_id": ADVERTISER_ID,
        "store_ids": json.dumps(["7494221571082258140"]),
        "dimensions": json.dumps(["stat_time_day", "campaign_id"]),
        "metrics": json.dumps(["cost", "orders", "gross_revenue", "roi"]),
        "start_date": "2026-05-01",
        "end_date": "2026-05-01",
        "page": 1,
        "page_size": 10,
    }, timeout=30)
    d = r.json()
    print(f"  code={d.get('code')}, msg={d.get('message')}")
    print(f"  총={d.get('data', {}).get('page_info', {}).get('total_number', 0)}행")
    for item in (d.get("data", {}).get("list") or []):
        print(f"    {item}")
except Exception as e:
    print(f"  오류: {e}")
