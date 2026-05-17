"""기간 입력 → 일별로 전체 Analytics 스크립트 순차 실행"""
import sys
import traceback
from datetime import datetime, timedelta

import 샵_일별_성과
import 샵_시간대별_성과
import 상품별_성과
import 상품별_성과_상세
import SKU별_성과
import 영상_전체_요약
import 라이브_성과
import 라이브_전체_요약
import 라이브_분당_성과
import 라이브_상품별_성과
import 영상_상품별_성과

SCRIPTS = [
    ("샵_일별_성과",       샵_일별_성과),
    ("샵_시간대별_성과",   샵_시간대별_성과),
    ("상품별_성과",        상품별_성과),
    ("상품별_성과_상세",   상품별_성과_상세),
    ("SKU별_성과",         SKU별_성과),
    ("영상_전체_요약",     영상_전체_요약),
    ("라이브_성과",        라이브_성과),
    ("라이브_전체_요약",   라이브_전체_요약),
    ("라이브_분당_성과",   라이브_분당_성과),
    ("라이브_상품별_성과", 라이브_상품별_성과),
    ("영상_상품별_성과",   영상_상품별_성과),
]

def get_date_range():
    if len(sys.argv) == 3:
        return sys.argv[1], sys.argv[2]
    raw = input("기간 입력 (예: 2026-05-15 ~ 2026-05-16): ").strip()
    parts = raw.replace("~", "-").replace(" ", "").split("-")
    # YYYY-MM-DD ~ YYYY-MM-DD 형식 파싱
    start = "-".join(parts[:3])
    end   = "-".join(parts[3:])
    return start, end

def date_range(start_str: str, end_str: str):
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end   = datetime.strptime(end_str,   "%Y-%m-%d")
    while start <= end:
        yield start.strftime("%Y-%m-%d")
        start += timedelta(days=1)

def main():
    start_str, end_str = get_date_range()
    dates = list(date_range(start_str, end_str))

    print(f"\n{'='*60}")
    print(f"기간 실행: {start_str} ~ {end_str}  ({len(dates)}일)")
    print('='*60)

    total_ok, total_fail = [], []

    for date_str in dates:
        print(f"\n{'━'*60}")
        print(f"📅 {date_str} 실행 시작")
        print('━'*60)
        for name, module in SCRIPTS:
            print(f"\n  [{name}] 실행 중...")
            try:
                module.run(date_str)
                total_ok.append(f"{date_str}/{name}")
            except Exception as e:
                print(f"  ❌ 오류: {e}")
                traceback.print_exc()
                total_fail.append(f"{date_str}/{name}")

    print(f"\n{'='*60}")
    print(f"전체 완료: {len(dates)}일 × {len(SCRIPTS)}개")
    print(f"  ✅ 성공: {len(total_ok)}건")
    if total_fail:
        print(f"  ❌ 실패: {len(total_fail)}건")
        for f in total_fail:
            print(f"     - {f}")
    print('='*60)

if __name__ == "__main__":
    main()
