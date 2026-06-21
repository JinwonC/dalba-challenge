# 🔁 세션 인수인계 (HANDOFF)

> 새 세션이 시작되면 **이 파일을 먼저 읽고** 아래 "지금 할 일"부터 이어서 진행하세요.

## 목표
YouTube / TikTok 영상 **콘텐츠 분석기**. 링크를 주면:
1. **Apify** 로 영상 스크랩 (메타데이터·캡션·해시태그·자막·통계, TikTok은 mp4 다운로드 URL도)
2. **Gemini** 로 영상 화면 분석 (화면 속 텍스트·인물 행동·배경/세팅) — `GEMINI_API_KEY` 있을 때
3. **Claude** 가 자막 + 화면 합쳐서 **콘텐츠 브레이크다운 + 크리에이티브 인사이트** 생성
4. 웹 UI(d'Alba 골드 테마)로 렌더

## 빌드 상태 — 전부 완성·커밋·푸시됨 (브랜치: `claude/youtube-tiktok-analyzer-zj3msg`)
```
content-analyzer/
├── server.js            Express + POST /api/analyze
├── lib/apify.js         플랫폼 감지 + Apify 스크랩 (YouTube/TikTok)
├── lib/vision.js        Gemini 영상 분석 (mp4 다운로드 → Files API)
├── lib/analyze.js       Claude 구조화 분석 (setting/actions/on-screen text 포함)
├── public/index.html    프론트엔드
├── gemini-youtube.mjs   YouTube URL을 Gemini로 바로 분석하는 CLI 헬퍼
├── scrape-once.mjs      Apify 스크랩 1회 실행 CLI 헬퍼
└── .env.example         키 템플릿
```

## 분석 대상 (사용자 요청)
**TikTok:** `https://www.tiktok.com/@officialkatjames/video/7653227710688267534`

## 환경별 연결 상태 (이전 세션 기준)
| 서비스 | 이전(제한) 세션 | 비고 |
|---|---|---|
| Gemini (`generativelanguage.googleapis.com`) | ✅ 200 | 됨 |
| Google Drive MCP | ✅ | 됨 (영상 파일 다운로드 가능) |
| Apify (`api.apify.com`) | ❌ 403 | egress 차단 |
| TikTok / 일반 인터넷 | ❌ 403 | egress 차단 |

→ 사용자가 환경을 **"무제한 액세스"로 변경**함. **단, 네트워크 정책은 새 세션부터 적용**되므로 새 세션에서 다시 확인 필요.

## 🟢 지금 할 일 (새 세션 첫 작업)
1. **egress 확인** — `curl -s -o /dev/null -w "%{http_code}" https://api.apify.com/v2/users/me?token=$APIFY_TOKEN`
   - `200` 이면 → Apify 풀 파이프라인 가능:
     `cd content-analyzer && npm install && node scrape-once.mjs '<TikTok URL>'` 로 mp4 URL/캡션 확보 →
     mp4 다운로드 → `lib/vision.js` 로 Gemini 화면분석 → 최종 인사이트(직접 작성 가능, Anthropic 키 없이도 됨)
   - 아직 `403` 이면 → 아래 Drive 우회로 사용
2. **Drive 우회로 (네트워크 안 열려도 됨, Gemini+Drive만으로):**
   - 사용자가 TikTok 영상을 Google Drive에 업로드 → `search_files` 로 찾기 →
     `download_file_content` 로 mp4 base64 받기 → 디스크 저장 → Gemini Files API 로 화면분석.
   - 참고: Drive에 이미 d'Alba 팀 영상들 다수 공유돼 있음(`mimeType contains 'video/'` 로 검색됨).

## 키 (⚠️ 시크릿은 repo에 저장 안 함)
- `ANTHROPIC_API_KEY` — 앱의 Claude 호출용. **단, 최종 분석은 이 세션의 Claude가 직접 작성하면 키 불필요.**
- `APIFY_TOKEN` — TikTok mp4/스크랩용. 사용자에게 받기 (이전 채팅에 노출됐으니 **재발급** 권장).
- `GEMINI_API_KEY` — 화면 분석용 (Google AI Studio). 사용자에게 받기.
- 새 세션에서 사용자에게 키를 다시 받거나, 환경변수/`.env`로 주입.

## 메모
- 이 샌드박스에서 `npm install` 됨, 서버 부팅·health 체크 정상 확인됨.
- Gemini는 **YouTube URL은 다운로드 없이 바로** 분석 가능(`gemini-youtube.mjs`). **TikTok은 URL 직접 불가 → mp4 필요.**
