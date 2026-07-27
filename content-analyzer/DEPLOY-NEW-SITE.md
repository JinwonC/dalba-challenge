# 두 번째 사이트 (다른 팀용) 세팅

같은 코드로 사이트를 하나 더 운영하고, **기존 사이트가 업데이트되면 자동으로 같이 업데이트**되게 하는 구성입니다.

**원리**: 같은 GitHub 레포·같은 브랜치를 바라보는 Vercel 프로젝트를 하나 더 둡니다.
코드는 100% 공유하고, **데이터·비밀번호만 환경변수로 분리**합니다.
브랜치에 푸시 한 번이면 두 사이트가 동시에 자동 배포됩니다. 코드 수정은 필요 없습니다.

```
git push  →  브랜치 갱신
              ├─→ dalba-content-analyzer        (기존 팀)
              └─→ dalba-content-analyzer-team2  (새 팀)
```

---

## 이미 만들어 둔 것

| 항목 | 값 |
|---|---|
| 프로젝트명 | `dalba-content-analyzer-team2` |
| 프로젝트 ID | `prj_QmO4WPlh1CtewKdBRf8JvswAZFHG` |
| 레포 | `JinwonC/dalba-challenge` (기존과 동일) |
| Root Directory | `content-analyzer` |
| `STORE_NAMESPACE` | `team2` — 히스토리 분리용 |
| `SITE_PASSWORD` | `dalbatts2` — 새 팀 전용 (원하는 값으로 변경 가능) |

### 히스토리 분리 방식

새 Upstash DB를 만들 필요가 없습니다. `STORE_NAMESPACE` 를 지정하면 **같은 Upstash DB 안에서
키 앞에 접두어가 붙어** 히스토리가 완전히 격리됩니다.

```
기존 팀:  report:<id>        summary:<id>        history_z
새 팀:    team2:report:<id>  team2:summary:<id>  team2:history_z
```

서로의 기록이 목록에 뜨지 않고, 한쪽에서 삭제해도 다른 쪽은 영향을 받지 않습니다.
팀을 더 늘리려면 `STORE_NAMESPACE` 값만 다르게(`team3` 등) 주면 됩니다.

> ⚠️ 기존 사이트에는 `STORE_NAMESPACE` 를 **넣지 마세요.** 넣는 순간 기존 220건이 목록에서 사라집니다
> (데이터가 지워지는 건 아니고, 다른 접두어를 보게 되는 것뿐 — 값을 지우면 즉시 복구됩니다).

---

## 담당자가 해야 하는 것

### 1. 프로덕션 브랜치 변경 ← **가장 중요**

Vercel 공개 API로는 바꿀 수 없어 대시보드에서만 가능합니다.
**이걸 하기 전에는 배포가 실패합니다** (기본값 `main` 에는 앱 코드가 없기 때문).

`dalba-content-analyzer-team2` → **Settings → Git → Production Branch**
→ `claude/determined-fermat-gnbdvg` 로 변경 → Save

### 2. 시크릿 환경변수 복사 (6개)

보안상 자동 복사가 차단되어 있어 직접 옮겨야 합니다.
`dalba-content-analyzer` → Settings → Environment Variables 에서 값을 확인해
`dalba-content-analyzer-team2` 의 같은 이름에 넣어주세요.
(모두 **Production / Preview / Development** 체크)

| 변수 | 설명 |
|---|---|
| `UPSTASH_REDIS_REST_URL` | 히스토리 저장소 (같은 DB 사용 — 네임스페이스로 분리됨) |
| `UPSTASH_REDIS_REST_TOKEN` | 〃 |
| `APIFY_TOKEN` | 스크래핑 |
| `GEMINI_API_KEY` | AI 영상분석 |
| `VIDEOS_READ_WRITE_TOKEN` | 영상 저장소 (공유해도 무방 — 영상 ID가 고유) |
| `DRIVE_WEBHOOK_URL` | Drive 저장 — 기존 폴더를 쓰려면 그대로 복사 |
| `DRIVE_WEBHOOK_SECRET` | 〃 |

**`BLOB_READ_WRITE_TOKEN` 은 복사하지 마세요.** 기존 팀의 옛날 기록(220건) 저장소라,
복사하면 새 팀이 그 기록에 접근할 수 있게 됩니다.

### 3. 재배포

환경변수를 넣은 뒤 **Deployments → 최신 배포 `···` → Redeploy**
(환경변수는 재배포해야 반영됩니다)

---

## 선택 사항

### 새 팀 전용 Drive로 바꾸기

기본은 기존 Drive 폴더를 함께 쓰는 구성입니다. 새 팀 드라이브에 따로 쌓으려면,
**그 팀 구글 계정으로** 아래를 만들고 `DRIVE_WEBHOOK_URL` / `DRIVE_WEBHOOK_SECRET` 만 교체하세요.

1. 저장할 Drive 폴더 생성 → 주소창에서 폴더 ID 복사
   `https://drive.google.com/drive/folders/<이 부분>`
2. https://script.google.com → 새 프로젝트 → 아래 코드 붙여넣고 맨 위 두 값 수정

```javascript
const SECRET = '여기에-비밀문자열';      // DRIVE_WEBHOOK_SECRET 과 동일하게
const FOLDER_ID = '여기에-폴더ID';       // 1번에서 복사한 값

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents || '{}');
    if (SECRET && body.secret !== SECRET) {
      return ContentService.createTextOutput(JSON.stringify({ error: 'unauthorized' }))
        .setMimeType(ContentService.MimeType.JSON);
    }
    const doc = DocumentApp.create(body.title || '제목 없음');
    doc.getBody().setText(body.text || '');
    doc.saveAndClose();

    if (FOLDER_ID) {
      const file = DriveApp.getFileById(doc.getId());
      DriveApp.getFolderById(FOLDER_ID).addFile(file);
      DriveApp.getRootFolder().removeFile(file);
    }
    return ContentService.createTextOutput(JSON.stringify({ id: doc.getId(), url: doc.getUrl() }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ error: String(err) }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
```

3. **배포 → 새 배포 → 유형: 웹 앱** / 실행 사용자: **나** / 액세스: **모든 사용자**
4. 나온 웹 앱 URL을 `DRIVE_WEBHOOK_URL` 에, 코드의 `SECRET` 을 `DRIVE_WEBHOOK_SECRET` 에

> Drive 저장이 필요 없으면 `DRIVE_WEBHOOK_URL` 을 빼면 됩니다. 나머지는 정상 작동합니다.

### 사용량(요금) 분리

`APIFY_TOKEN` 과 `GEMINI_API_KEY` 를 공유하면 **두 팀이 같은 월간 한도를 나눠 씁니다.**
한 팀이 많이 돌리면 다른 팀까지 멈춥니다. 팀별로 분리하려면 각자 계정/프로젝트에서
키를 따로 발급해 각 사이트에 다른 값을 넣으세요.

---

## 확인

1. Deployments 최신 배포가 **Ready + Production**
2. 사이트 접속 → 비밀번호(`dalbatts2`) → 화면이 뜨는지
3. 영상 하나 분석 → 히스토리에 쌓이는지 / 기존 팀 220건은 **안 보이는지**
