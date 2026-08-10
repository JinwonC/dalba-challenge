"""영상성과_신API테스트 탭 점검: 실제 '시간' 기준 정렬 상태 확인."""
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1_qkd6LZ1wFoihhJSuYdabQ4iRbx-jsFYVxeGIoEb-_g"
SHEET_NAME = "영상성과_신API테스트"


def parse(s: str):
    s = str(s).strip().replace("T", " ").replace("Z", "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                "%Y. %m. %d %H:%M:%S", "%m/%d/%Y %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def main():
    creds = Credentials.from_service_account_file(
        "service_account.json",
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"])
    ss = gspread.authorize(creds).open_by_key(SPREADSHEET_ID)
    sheet = ss.worksheet(SHEET_NAME)
    vals = sheet.get_all_values()
    header, rows = vals[0], vals[1:]
    i_post = header.index("video_post_time")
    print(f"총 {len(rows)}행 / video_post_time = S열")
    print(f"샘플 원본값: {[rows[i][i_post] for i in range(3)]}")

    parsed = []
    unparsed = 0
    for n, r in enumerate(rows, start=2):
        v = r[i_post] if len(r) > i_post else ""
        d = parse(v)
        if d is None:
            unparsed += 1
        parsed.append((n, d, v))
    print(f"파싱 실패: {unparsed}행")

    # 실제 시간 기준 역행 지점
    breaks = []
    prev = None
    for n, d, v in parsed:
        if d is None:
            continue
        if prev and d < prev[1]:
            breaks.append((n, prev[2], v))
        prev = (n, d, v)
    print(f"\n[시간 기준] 역행 지점: {len(breaks)}건")
    for n, a, b in breaks[:8]:
        print(f"  행 {n}: 이전 {a} → 현재 {b}")

    if breaks:
        first = breaks[0][0]
        print(f"\n  → 행 {first} 부터 시간순이 깨짐")
        tail = [d for n, d, v in parsed if n >= first and d]
        if tail:
            print(f"  → 이후 {len(tail)}행 범위: {min(tail)} ~ {max(tail)}")
    else:
        print("  ✅ 전체가 시간 오름차순으로 정렬되어 있음")

    # 마지막 30행 미리보기 (append된 구간 확인)
    print("\n[마지막 10행 포스팅일]")
    for n, d, v in parsed[-10:]:
        print(f"  행 {n}: {v}")


if __name__ == "__main__":
    main()
