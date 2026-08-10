"""영상성과_신API테스트 탭 점검: 포스팅일 정렬 상태 / 중복 / 분포."""
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
    i_post = header.index("video_post_time")
    i_id = header.index("id")
    col = chr(65 + i_post) if i_post < 26 else "?"
    print(f"총 데이터 행: {len(rows)} / video_post_time = {col}열 (index {i_post})")

    posts = [(r[i_post] if len(r) > i_post else "") for r in rows]

    # 정렬 붕괴 지점 탐색 (앞 행보다 과거인 행)
    breaks = []
    prev = ""
    for n, p in enumerate(posts, start=2):
        if p and prev and p < prev:
            breaks.append((n, prev, p))
        if p:
            prev = p
    print(f"\n[정렬] 오름차순 위배 지점: {len(breaks)}건")
    for n, a, b in breaks[:10]:
        print(f"  행 {n}: 이전 {a[:19]} → 현재 {b[:19]}")
    if len(breaks) > 10:
        print(f"  ... 외 {len(breaks)-10}건")

    # 정렬이 유지되는 마지막 행 = 최초 붕괴 지점 직전
    if breaks:
        first = breaks[0][0]
        print(f"\n  → 행 2~{first-1} 까지는 시간순 정상, 행 {first} 부터 섞임")
        tail = [p[:10] for p in posts[first-2:] if p]
        if tail:
            print(f"  → 섞인 구간 {len(tail)}행, 날짜 범위 {min(tail)} ~ {max(tail)}")

    ids = [str(r[i_id]).strip().lstrip("'") for r in rows if len(r) > i_id and r[i_id]]
    print(f"\n[중복] ID {len(ids):,}개 / 고유 {len(set(ids)):,}개 / 중복 {len(ids)-len(set(ids)):,}개")

    months = Counter(p[:7] for p in posts if p)
    print("\n[월별]")
    for m in sorted(months):
        print(f"  {m}: {months[m]:,}")


if __name__ == "__main__":
    main()
