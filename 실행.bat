@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [1/2] 최신 파일 업데이트 중...
git pull
echo.

echo [2/2] 실행할 스크립트를 선택하세요:
echo.
echo  1. 영상 성과 (tiktok_to_sheets.py)
echo  2. 상품별 일별 로그 (tiktok_daily_log.py)
echo  3. 주문 데이터 (tiktok_orders.py)
echo  4. [TEST] 샵 일별 성과
echo  5. [TEST] 샵 시간대별 성과
echo  6. [TEST] 상품별 성과
echo  7. [TEST] SKU별 성과
echo  8. [TEST] 영상 전체 요약
echo  9. [TEST] 라이브 성과
echo 10. [TEST] 라이브 전체 요약
echo 11. [TEST] 라이브 분당 성과
echo 12. [TEST] 라이브 상품별 성과
echo 13. [TEST] 영상 상품별 성과
echo 14. [진단] API 응답 구조 확인 (수정용)
echo.
set /p choice="번호 입력: "

if "%choice%"=="1"  python tiktok_to_sheets.py
if "%choice%"=="2"  python tiktok_daily_log.py
if "%choice%"=="3"  python tiktok_orders.py
if "%choice%"=="4"  cd TEST && python 샵_일별_성과.py
if "%choice%"=="5"  cd TEST && python 샵_시간대별_성과.py
if "%choice%"=="6"  cd TEST && python 상품별_성과.py
if "%choice%"=="7"  cd TEST && python SKU별_성과.py
if "%choice%"=="8"  cd TEST && python 영상_전체_요약.py
if "%choice%"=="9"  cd TEST && python 라이브_성과.py
if "%choice%"=="10" cd TEST && python 라이브_전체_요약.py
if "%choice%"=="11" cd TEST && python 라이브_분당_성과.py
if "%choice%"=="12" cd TEST && python 라이브_상품별_성과.py
if "%choice%"=="13" cd TEST && python 영상_상품별_성과.py
if "%choice%"=="14" cd TEST && python _진단.py && git config user.email "jinwon@dalba.com" && git config user.name "JinwonC" && git add _진단_결과.json && git commit -m "진단 결과" && git push

echo.
pause
