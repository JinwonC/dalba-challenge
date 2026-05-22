"""광고소재성과 탭 → 소재별 주차 집계 → 광고소재_주차별 탭"""
import os
import json
from datetime import datetime, timedelta
from collections import defaultdict

from google.oauth2.service_account import Credentials
import gspread

SPREADSHEET_ID       = "1AhVPPUq6Npri72uhtFcOUVMBl1jA7nf2P0qDCDRRKfA"
SOURCE_SHEET         = "광고소재성과"
TARGET_SHEET         = "광고소재_주차별"
SERVICE_ACCOUNT_FILE = "service_account.json"

# SOURCE 컬럼 인덱스 (광고소재성과 헤더 순서)
# 날짜(0) 소재ID(1) 캠페인ID(2) 캠페인명(3) 아이템그룹ID(4)
# 게재상태(5) 지출금액(6) 주문수(7) 주문당비용(8) 총매출(9) ROI(10)
# 상품노출수(11) 상품클릭수(12) 상품클릭률(13)
# 광고클릭률(14) 광고전환율(15)
# 2초(16) 6초(17) 25%(18) 50%(19) 75%(20) 100%(21)

HEADERS = [
    "주차", "소재ID", "캠페인명",
    "지출금액", "주문수", "주문당비용", "총매출(GMV)", "ROI",
    "상품노출수", "상품클릭수", "상품클릭률",
    "광고클릭률", "광고전환율",
    "2초시청률", "6초시청률", "25%시청률", "50%시청률", "75%시청률", "100%시청률",
]


def to_float(v):
    try:
        return float(str(v).replace(",", "").strip())
    except Exception:
        return 0.0


def get_week(date_str: str) -> str:
    """날짜 → ISO 주차 (예: 2026-W20)"""
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"
    except Exception:
        return ""


def main():
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"]
    )
    spreadsheet = gspread.authorize(creds).open_by_key(SPREADSHEET_ID)

    # 소스 데이터 읽기
    print(f"  '{SOURCE_SHEET}' 탭 읽는 중...")
    src = spreadsheet.worksheet(SOURCE_SHEET)
    all_values = src.get_all_values()
    if len(all_values) < 2:
        print("  데이터 없음")
        return

    rows = all_values[1:]  # 헤더 제외
    print(f"  {len(rows)}행 읽음")

    # 소재ID × 주차별 집계
    # key: (week, item_id)
    agg = defaultdict(lambda: {
        "캠페인명": "",
        "cost": 0.0, "orders": 0.0, "gmv": 0.0,
        "impressions": 0.0, "clicks": 0.0,
        # 시청률은 노출수 가중평균을 위해 (값×노출수) 합산
        "ctr_sum": 0.0, "cvr_sum": 0.0,
        "v2s_sum": 0.0, "v6s_sum": 0.0,
        "vp25_sum": 0.0, "vp50_sum": 0.0,
        "vp75_sum": 0.0, "vp100_sum": 0.0,
    })

    for row in rows:
        if len(row) < 12:
            continue
        date_str = row[0]
        item_id  = row[1]
        week = get_week(date_str)
        if not week or not item_id:
            continue

        key = (week, item_id)
        d = agg[key]
        if not d["캠페인명"]:
            d["캠페인명"] = row[3] if len(row) > 3 else ""

        imp = to_float(row[11]) if len(row) > 11 else 0.0
        d["cost"]        += to_float(row[6])
        d["orders"]      += to_float(row[7])
        d["gmv"]         += to_float(row[9])
        d["impressions"] += imp
        d["clicks"]      += to_float(row[12]) if len(row) > 12 else 0.0

        # 비율 지표: 노출수 가중 합산
        d["ctr_sum"]   += to_float(row[14]) * imp if len(row) > 14 else 0.0
        d["cvr_sum"]   += to_float(row[15]) * imp if len(row) > 15 else 0.0
        d["v2s_sum"]   += to_float(row[16]) * imp if len(row) > 16 else 0.0
        d["v6s_sum"]   += to_float(row[17]) * imp if len(row) > 17 else 0.0
        d["vp25_sum"]  += to_float(row[18]) * imp if len(row) > 18 else 0.0
        d["vp50_sum"]  += to_float(row[19]) * imp if len(row) > 19 else 0.0
        d["vp75_sum"]  += to_float(row[20]) * imp if len(row) > 20 else 0.0
        d["vp100_sum"] += to_float(row[21]) * imp if len(row) > 21 else 0.0

    # 결과 행 생성 (주차 → 소재ID 정렬)
    output = []
    for (week, item_id) in sorted(agg.keys()):
        d = agg[(week, item_id)]
        cost    = d["cost"]
        orders  = d["orders"]
        gmv     = d["gmv"]
        imp     = d["impressions"]
        clicks  = d["clicks"]

        roi     = round(gmv / cost, 2) if cost else 0.0
        cpo     = round(cost / orders, 2) if orders else 0.0
        clk_r   = round(clicks / imp * 100, 2) if imp else 0.0

        def wavg(s): return round(s / imp, 4) if imp else 0.0

        output.append([
            week, item_id, d["캠페인명"],
            round(cost, 2), int(orders), cpo, round(gmv, 2), roi,
            int(imp), int(clicks), clk_r,
            wavg(d["ctr_sum"]), wavg(d["cvr_sum"]),
            wavg(d["v2s_sum"]), wavg(d["v6s_sum"]),
            wavg(d["vp25_sum"]), wavg(d["vp50_sum"]),
            wavg(d["vp75_sum"]), wavg(d["vp100_sum"]),
        ])

    # 타겟 시트 저장
    try:
        tgt = spreadsheet.worksheet(TARGET_SHEET)
        tgt.clear()
    except gspread.WorksheetNotFound:
        tgt = spreadsheet.add_worksheet(title=TARGET_SHEET, rows="10000", cols=str(len(HEADERS)))
        print(f"  시트 '{TARGET_SHEET}' 새로 생성됨")

    tgt.append_row(HEADERS)
    tgt.freeze(rows=1)
    tgt.append_rows(output, value_input_option="USER_ENTERED")
    print(f"  ✅ {len(output)}행 저장 완료 → '{TARGET_SHEET}'")


if __name__ == "__main__":
    print("=== 광고소재 주차별 집계 ===")
    main()
