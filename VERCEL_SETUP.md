# 영상 성과 · 크리에이터 평가 웹앱 (Vercel 배포 가이드)

`영상성과_신API테스트` 시트를 기반으로 한 대시보드입니다.
- 상단 **게시일 날짜 필터** + 최소 GMV
- `Usage Rights` 대신 **[상/중/하] 평가 버튼**
- **특이사항** 입력 → 시트에 저장/조회
- 평가·특이사항은 시트에 **`평가`·`특이사항` 열**로 저장되며, 매일 자동화가 이 열을 보존합니다.

## Vercel 설정 (한 번만)

1. Vercel에서 이 레포(dalba-check)에 연결된 프로젝트를 엽니다.
2. **Settings → Environment Variables** 에 아래 추가:

   | Name | Value |
   |------|-------|
   | `GOOGLE_SERVICE_ACCOUNT_JSON` | `service_account.json` 파일 **전체 내용**을 그대로 붙여넣기 (자동화에서 쓰는 그 서비스계정) |
   | `APP_KEY` | (선택) 접근 암호. 설정하면 웹앱 최초 접속 시 키를 물어봄. 안 넣으면 링크 아는 사람 누구나 접근 |

   - `SHEET_ID`, `SHEET_TAB` 은 코드에 기본값(영상 성과 시트/영상성과_신API테스트)이 있어 생략 가능. 다른 시트를 쓰려면 추가.

3. **Settings → General**
   - Framework Preset: **Next.js** (자동 감지)
   - Root Directory: **`./`** (레포 루트)
   - Production Branch: **`main`**

4. **Deployments** 에서 최신 커밋을 **Redeploy**.

## 동작 방식

- `GET /api/videos?from=&to=&minGmv=` : 시트를 읽어 기간/최소GMV로 필터, GMV 내림차순 상위 1,500건 반환
- `POST /api/review {id, rating, note}` : 영상ID로 행을 찾아 `평가`/`특이사항` 셀 저장
- 서비스계정 키는 서버(Vercel 서버리스)에만 있고 브라우저에 노출되지 않음

## 표시 항목 (우리 시트에 있는 것만)

영상제목(→틱톡 링크), 핸들, 상품ID, 게시일, 조회수, GMV, GPM, 판매수량, 주문수, CTR, 평가, 특이사항

> Ad Spend/ROI/CPA(광고)·Likes/Comments/Engagement(소셜)는 이 시트에 없어 미표시.
> 광고 지표가 필요하면 `광고소재성과`(소재ID=영상ID) 조인으로 추가 가능.
