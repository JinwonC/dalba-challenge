"""모든 Analytics 스크립트 일괄 실행"""
import sys
import traceback

import 샵_일별_성과
import 샵_시간대별_성과
import 상품별_성과
import SKU별_성과
import 영상_전체_요약
import 라이브_성과
import 라이브_전체_요약
import 라이브_분당_성과
import 라이브_상품별_성과
import 영상_상품별_성과

from _공통 import get_date_input

SCRIPTS = [
    ("샵_일별_성과",       샵_일별_성과),
    ("샵_시간대별_성과",   샵_시간대별_성과),
    ("상품별_성과",        상품별_성과),
    ("SKU별_성과",         SKU별_성과),
    ("영상_전체_요약",     영상_전체_요약),
    ("라이브_성과",        라이브_성과),
    ("라이브_전체_요약",   라이브_전체_요약),
    ("라이브_분당_성과",   라이브_분당_성과),
    ("라이브_상품별_성과", 라이브_상품별_성과),
    ("영상_상품별_성과",   영상_상품별_성과),
]

def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else get_date_input()
    print(f"\n{'='*60}")
    print(f"전체 실행 시작: {date_str}")
    print('='*60)

    ok, fail = [], []
    for name, module in SCRIPTS:
        print(f"\n[{SCRIPTS.index((name, module))+1}/{len(SCRIPTS)}] {name} 실행 중...")
        try:
            module.run(date_str)
            ok.append(name)
        except Exception as e:
            print(f"  ❌ 오류 발생: {e}")
            traceback.print_exc()
            fail.append(name)

    print(f"\n{'='*60}")
    print(f"완료: {len(ok)}개 성공, {len(fail)}개 실패")
    if ok:
        print(f"  ✅ 성공: {', '.join(ok)}")
    if fail:
        print(f"  ❌ 실패: {', '.join(fail)}")
    print('='*60)

if __name__ == "__main__":
    main()
