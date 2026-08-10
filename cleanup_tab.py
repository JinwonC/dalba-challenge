"""지정한 스프레드시트에서 탭 하나를 삭제한다 (사용자 요청 정리용).
사용: python cleanup_tab.py <spreadsheet_id> "<탭이름>"
"""
import sys

import gspread
from google.oauth2.service_account import Credentials

SERVICE_ACCOUNT_FILE = "service_account.json"


def main():
    sid = sys.argv[1]
    name = sys.argv[2]
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"])
    ss = gspread.authorize(creds).open_by_key(sid)
    print(f"스프레드시트: {ss.title}")
    print("현재 탭:", [w.title for w in ss.worksheets()])
    try:
        ws = ss.worksheet(name)
    except gspread.WorksheetNotFound:
        print(f"'{name}' 탭이 없습니다 — 이미 삭제됨")
        return
    rows, cols = ws.row_count, ws.col_count
    ss.del_worksheet(ws)
    print(f"✅ '{name}' 삭제 완료 (약 {rows * cols:,} 셀 확보)")
    print("남은 탭:", [w.title for w in ss.worksheets()])


if __name__ == "__main__":
    main()
