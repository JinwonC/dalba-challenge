"""영상성과_신API테스트 탭의 실제 상태 점검 (포스팅일 분포 / 중복 여부)."""
import gspread
from google.oauth2.service_account import Credentials
from collections import Counter

SPREADSHEET_ID = "1_qkd6LZ1wFoihhJSuYdabQ4iRbx-jsFYVxeGIoEb-_g"
SHEET_NAME = "영상성과_신API테스트"


def main():
    creds = Credentials.from_service_account_file(
        "service_account.json",
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"])
    ss = gspread.authorize(creds).open_by_key(SPREADSHEET_ID)
    sheet = ss.worksheet(SHEET_NAME)
    vals = sheet.get_all_values()
    header, rows = vals[0], vals[1:]
    print(f"총 데이터 행: {len(rows)}")
    print(f"헤더: {header}")

    i_post = header.index("video_post_time")
    i_id = header.index("id")

    months = Counter()
    pre2026 = 0
    empty = 0
    for r in rows:
        p = str(r[i_post])[:10] if len(r) > i_post else ""
        if not p:
            empty += 1
            continue
        months[p[:7]] += 1
        if p < "2026-01-01":
            pre2026 += 1

    print("\n[포스팅 월별 분포]")
    for m in sorted(months):
        print(f"  {m}: {months[m]:,}행")
    print(f"\n2026-01-01 이전 포스팅: {pre2026:,}행")
    print(f"포스팅일 비어있음: {empty:,}행")

    ids = [str(r[i_id]).strip().lstrip("'") for r in rows if len(r) > i_id and r[i_id]]
    dup = len(ids) - len(set(ids))
    print(f"\n영상ID 총 {len(ids):,}개 / 고유 {len(set(ids)):,}개 / 중복 {dup:,}개")
    if dup:
        c = Counter(ids)
        print("  중복 예시:", [k for k, v in c.most_common(5) if v > 1])


if __name__ == "__main__":
    main()
