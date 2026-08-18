"""주간보고용 데이터 소스 탐색: 후보 탭들의 헤더 + 샘플행 + 날짜범위 덤프."""
import gspread
from google.oauth2.service_account import Credentials

SA = "service_account.json"

# (스프레드시트ID, [탭명들])
SOURCES = {
    "15dP91bH_skc7ZzcJ3ehH9H4IKCzSxcfuOcREr3OaL0o": [
        "매출지표", "NEW 제품별 매출지표(raw)", "Get Shop Performance",
        "(중요,수동) 제품별 유입매출 RAW (520업데이트)",
        "(중요,수동) 제품별 AF 매출 RAW", "(수동) 브랜드 라이브 RAW",
        "(중요, 자동) SKU Order", "라이브성과",
    ],
    "1AhVPPUq6Npri72uhtFcOUVMBl1jA7nf2P0qDCDRRKfA": [
        "광고성과", "광고소재성과",
    ],
}


def main():
    creds = Credentials.from_service_account_file(
        SA, scopes=["https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive"])
    gc = gspread.authorize(creds)
    for sid, tabs in SOURCES.items():
        ss = gc.open_by_key(sid)
        print(f"\n########## {ss.title} ##########")
        existing = {w.title for w in ss.worksheets()}
        for tab in tabs:
            print(f"\n===== [{tab}] =====")
            if tab not in existing:
                # 부분일치 후보 안내
                cand = [t for t in existing if tab.split(" ")[0][:4] in t]
                print(f"  (없음) 유사탭: {cand[:5]}")
                continue
            ws = ss.worksheet(tab)
            try:
                head = ws.get("A1:AZ2")
            except Exception as e:
                print(f"  헤더 읽기 실패: {e}")
                continue
            if head:
                print(f"  헤더: {head[0]}")
                if len(head) > 1:
                    print(f"  1행:  {head[1]}")
            print(f"  크기: {ws.row_count}행 x {ws.col_count}열")


if __name__ == "__main__":
    main()
