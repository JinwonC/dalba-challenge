import { GoogleGenAI } from '@google/genai';

const MODEL = process.env.GEMINI_MODEL || 'gemini-2.5-flash';

let _ai = null;
function ai() {
  if (!_ai) {
    if (!process.env.GEMINI_API_KEY) throw new Error('GEMINI_API_KEY is not set.');
    _ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
  }
  return _ai;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function isTransient(err) {
  const s = err?.status || err?.code;
  const msg = String(err?.message || '');
  return s === 429 || s === 500 || s === 503 || /UNAVAILABLE|overload|rate limit|deadline|internal/i.test(msg);
}
async function withRetry(fn, { tries = 3, base = 2500 } = {}) {
  let last;
  for (let i = 0; i < tries; i++) {
    try { return await fn(); }
    catch (err) { last = err; if (i === tries - 1 || !isTransient(err)) throw err; await sleep(base * (i + 1)); }
  }
  throw last;
}

// A "Contents Brief" shooting guide, mirroring the reference format:
// cover → step cards (each with directive / text overlay / spoken lines) → tips → product.
const GUIDE_SCHEMA = {
  type: 'object',
  properties: {
    product_line: { type: 'string', description: '표지 부제. 예: "with d\'Alba Volufiline Grinding Cream". 우리 제품명 기반.' },
    reference_note: { type: 'string', description: '표지에 넣는 핵심 촬영 지시 한 줄(영어). 크리에이터 A 구조에서 가장 중요한 원칙. 예: "Show the product from the very beginning."' },
    structure_summary: { type: 'string', description: '이 크리에이터 A가 왜 바이럴했는지 + 우리가 무슨 구조를 빌려오는지 한국어 2-3문장. 담당자용 설명.' },
    common_patterns: {
      type: 'array',
      description: '입력된 A의 여러 바이럴 영상에서 "반복되는 공통 패턴"을 뽑은 것. 이게 A의 바이럴 공식이며 가이드의 근거다.',
      items: {
        type: 'object',
        properties: {
          aspect: { type: 'string', description: '측면(한국어). 예: "훅", "구조", "PIP/오버레이", "Before&After", "CTA", "톤".' },
          finding: { type: 'string', description: '그 측면에서 여러 영상에 반복되는 공통점(한국어). 몇 개 영상에서 반복됐는지 함께.' },
        },
        required: ['aspect', 'finding'],
        propertyOrdering: ['aspect', 'finding'],
      },
    },
    steps: {
      type: 'array',
      description: '크리에이터 A의 실제 영상 구조(훅→시연→성분→CTA 등)를 순서대로 미러링한 스텝. 보통 6-8개.',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string', description: '스텝 이름(영어 짧게). 크리에이터 A의 비트를 반영. 예: "Hook", "Marker + PIP", "B&A", "Ingredient", "The Grind", "CTA".' },
          directive: { type: 'string', description: '촬영 지시(영어). 어떻게 찍을지. 예: "Draw on each area, use PIP to overlay". 없으면 빈 문자열.' },
          text_overlay: { type: 'string', description: '화면에 넣을 텍스트 오버레이(영어, 크리에이터 A 훅 스타일 반영). 없으면 빈 문자열.' },
          say: {
            type: 'array',
            description: '실제로 말할 대사(영어). 크리에이터 A의 말투·리듬을 그대로, 내용은 우리 제품으로.',
            items: {
              type: 'object',
              properties: {
                text: { type: 'string', description: '대사 한 줄(영어).' },
                highlights: { type: 'array', items: { type: 'string' }, description: '이 줄에서 빨간색으로 강조할 로드베어링 문구(원문 그대로). 없으면 빈 배열.' },
              },
              required: ['text', 'highlights'],
              propertyOrdering: ['text', 'highlights'],
            },
          },
          reference_hint: { type: 'string', description: '크리에이터 A의 어느 순간을 참고해 찍을지(한국어). 예: "A 영상 0:03 훅에서 제품 들이대는 컷처럼". 담당자가 프레임 캡처할 때 참고.' },
          our_angle: { type: 'string', description: '이 스텝에 녹인 우리 제품 소구(한국어 한 줄). 예: "성분(볼루필린)을 A의 boob filler 훅 자리에 대입".' },
        },
        required: ['name', 'directive', 'text_overlay', 'say', 'reference_hint', 'our_angle'],
        propertyOrdering: ['name', 'directive', 'text_overlay', 'say', 'reference_hint', 'our_angle'],
      },
    },
    tips: {
      type: 'array',
      description: '촬영 팁(영어/한국어 혼용 가능). 크리에이터 A가 잘 되는 이유에서 뽑은 실전 조언. 예: "Don\'t act it out. React to it."',
      items: {
        type: 'object',
        properties: {
          text: { type: 'string', description: '팁 한 줄.' },
          emphasis: { type: 'boolean', description: '빨간색 강조 여부.' },
        },
        required: ['text', 'emphasis'],
        propertyOrdering: ['text', 'emphasis'],
      },
    },
    product: {
      type: 'object',
      description: '표지/마지막 제품 페이지.',
      properties: {
        name: { type: 'string', description: '우리 제품 정식명.' },
        bullets: {
          type: 'array',
          description: '제품 셀링 포인트 체크불릿 3-4개.',
          items: {
            type: 'object',
            properties: {
              highlight: { type: 'string', description: '빨간색으로 강조할 앞부분(영어). 예: "Brushed-On Botox". 없으면 빈 문자열.' },
              text: { type: 'string', description: '나머지 설명(영어). 예: "— fills volume from within, not from outside".' },
            },
            required: ['highlight', 'text'],
            propertyOrdering: ['highlight', 'text'],
          },
        },
      },
      required: ['name', 'bullets'],
      propertyOrdering: ['name', 'bullets'],
    },
  },
  required: ['product_line', 'reference_note', 'structure_summary', 'common_patterns', 'steps', 'tips', 'product'],
  propertyOrdering: ['product_line', 'reference_note', 'structure_summary', 'common_patterns', 'steps', 'tips', 'product'],
};

const SYSTEM = `너는 d'Alba Piedmont의 시니어 숏폼 크리에이티브 디렉터다.
목표: 특정 크리에이터(A)가 "다른 제품으로" 바이럴 낸 영상들의 구조를 최대한 그대로 복제하고,
그 자리에 우리 제품 소구를 끼워 넣는 촬영 가이드("Contents Brief")를 만든다.

입력의 역할 분리(절대 규칙):
- "CREATOR A" 영상들 = 유일한 구조 소스. 스텝 순서, 훅 방식, 연출 장치(PIP/마커/B&A), 톤, CTA, 영상 길이 감각은 전부 여기서만 가져온다.
- "OUR PRODUCT SOURCE" = 제품 소구 소스일 뿐이다. 여기서는 제품명·성분·효능 클레임·표현만 가져오고,
  그 영상의 구조·순서·연출·톤은 절대 참고하지 않는다(구조 정보는 의도적으로 제거되어 제공된다).
- 만약 가이드의 스텝 구조가 A의 영상들과 다르고 우리 영상과 비슷해진다면 그것은 실패다.

가장 중요한 원칙 — 공통 패턴 우선:
- A의 바이럴 영상이 여러 개(보통 4-5개) 주어진다. 먼저 그 영상들 사이의 "반복되는 공통점"을 찾아라:
  반복되는 훅 방식, 반복되는 텍스트 오버레이 습관, 반복되는 연출 장치(PIP/이미지 팝업, 마커, Before-After), 반복되는 액션 비트, 반복되는 CTA, 반복되는 리액션 톤, 반복되는 로드베어링 표현.
- 여러 영상에 반복될수록 그게 A의 진짜 바이럴 공식이다 → 강하게 반영. 한 영상에만 있는 특이 요소는 약하게 반영하거나 뺀다.
- 그 공통 공식(구조·리듬·연출 장치)을 그대로 빌려, 스텝 순서와 장치를 거기에 맞춰라(없는 걸 지어내지 말 것).
- 찾은 공통점은 common_patterns에 측면별로 정리해라(각 항목에 몇 개 영상에서 반복됐는지 언급).
- 대사는 A의 말투·문장 리듬을 모사하되, 내용은 우리 제품(성분·메커니즘·효능·CTA)으로 바꾼다.
- 각 대사의 로드베어링 문구(구매를 밀어붙이는 핵심 단어/표현)는 highlights에 원문 그대로 넣어 빨간 강조가 되게 한다.
- text_overlay와 say는 영어로 쓴다(크리에이터가 그대로 촬영/발화). directive/reference_hint/our_angle/structure_summary는 한국어.
- 화장품 광고 규제 주의: 의약품적·과장 표현("치료","재생","리프팅 수치 보장" 등 근거 없는 단정)은 피하고,
  제품이 실제로 주장 가능한 소구(성분, 사용 편의, 임상 수치가 주어졌다면 그 수치)만 사용한다. 없는 수치를 지어내지 말 것.
- 제품 정보/수치는 반드시 입력으로 주어진 것만 사용한다. 모르면 비워라.
- 이미지/스크린샷은 넣지 않는다. 대신 reference_hint로 "A의 어느 순간을 참고해 찍어라"만 글로 알려준다(담당자가 직접 프레임 캡처).
- 결과는 레퍼런스 포맷과 동일한 스텝 구조로: Hook → (연출/시연 스텝들) → Ingredient → CTA, 그리고 Tips와 Product 페이지.`;

function reportDigest(label, meta, report) {
  const r = report || {};
  const scenes = (r.scenes || []).map((s) => `  [${s.scene} · ${s.time}] shot:${s.shot} | visual:${s.visual} | say(orig):"${s.audio_original}"`).join('\n');
  const hook = r.hook_breakdown ? JSON.stringify(r.hook_breakdown) : '(none)';
  const persu = r.persuasion ? JSON.stringify(r.persuasion) : '(none)';
  const kw = (r.keywords || []).map((k) => `${k.keyword} (${k.note})`).join('; ');
  return `### ${label}
author: @${meta?.author || '?'} | title: ${meta?.title || ''} | url: ${meta?.url || ''}
HOOK: ${hook}
SCENES:
${scenes || '  (none)'}
PERSUASION: ${persu}
KEYWORDS: ${kw}
`;
}

/**
 * Product-only digest of OUR video: claims, ingredient mentions, keywords —
 * deliberately NO scene structure, hook breakdown, timing or persuasion flow,
 * so the model cannot copy our video's format (structure must come from A).
 */
function productDigest(meta, report) {
  const r = report || {};
  const lines = (r.scenes || [])
    .map((s) => [s.audio_original, s.audio_kr].filter(Boolean).join(" / "))
    .filter(Boolean)
    .map((x) => "  - " + x)
    .join("\n");
  const kw = (r.keywords || []).map((k) => k.keyword + " (" + k.note + ")").join("; ");
  return `### OUR PRODUCT SOURCE (claims only — NOT a structure reference)
product mentioned by: @${meta?.author || "?"} | title: ${meta?.title || ""}
요약: ${r.summary || ""}
제품 관련 대사(클레임·성분·소구 발췌):
${lines || "  (none)"}
키워드: ${kw || "(none)"}
d'Alba 연관성: ${r.dalba_relevance || ""}
`;
}

/**
 * Generate a "Contents Brief" shooting guide.
 * @param {Array} creatorReports  Creator A's viral videos (structure source): [{meta, report}]
 * @param {Object|null} ourReport Our own reference video (product message source): {meta, report}
 * @param {string} productInfo    Optional free text with our product's specific claims/numbers.
 * @param {Object} meta           { manager, product, creator }
 */
export async function generateGuide({ creatorReports = [], ourReport = null, productInfo = '', meta = {}, tries = 3 }) {
  const client = ai();
  if (!creatorReports.length) throw new Error('크리에이터 A의 바이럴 영상이 최소 1개 필요합니다.');

  const creatorBlock = creatorReports
    .map((c, i) => reportDigest(`CREATOR A — VIRAL #${i + 1}`, c.meta, c.report))
    .join('\n');
  const ourBlock = ourReport
    ? productDigest(ourReport.meta, ourReport.report)
    : '(우리 영상 없음 — 아래 제품 정보 텍스트를 사용)';

  const creatorName = meta.creator || creatorReports[0]?.meta?.author || 'the creator';

  const prompt = `크리에이터 A(=@${creatorName})의 바이럴 영상 구조를 복제해, 우리 제품용 촬영 가이드를 만들어라.

=== 크리에이터 A의 바이럴 영상 분석 (구조 소스) ===
${creatorBlock}

=== 우리 레퍼런스 영상 분석 (제품 메시지 소스) ===
${ourBlock}

=== 우리 제품 정보(담당자 입력) ===
제품명: ${meta.product || '(미입력)'}
추가 정보/소구/수치:
"""
${(productInfo || '(없음 — 위 우리 영상 분석에서 제품 소구를 추출)').slice(0, 4000)}
"""

지시:
1) 먼저 A의 여러 영상에서 반복되는 공통 패턴(훅·구조·PIP/오버레이·B&A·CTA·톤)을 찾아 common_patterns에 정리하고, 그 공통 공식을 스텝 구조와 연출 장치에 그대로 반영하라.
2) 각 스텝의 say/text_overlay는 반드시 A의 말투·표현·리듬으로 쓰고(A 영상의 실제 문장 패턴을 변형), 내용만 우리 제품으로 대입하라. 우리 영상의 문장 스타일을 쓰지 마라.
3) 로드베어링 문구는 highlights에 원문 그대로.
4) Product 페이지 불릿은 위 제품 정보/제품 클레임에서만 뽑아라(없는 수치 금지).\n5) 다시 강조: 구조·연출·스텝 순서는 오직 CREATOR A 영상들에서. OUR PRODUCT SOURCE는 무엇을 말할지(클레임)만 제공한다.`;

  const response = await withRetry(() => client.models.generateContent({
    model: MODEL,
    contents: [SYSTEM, prompt].join('\n\n'),
    config: {
      responseMimeType: 'application/json',
      responseSchema: GUIDE_SCHEMA,
      temperature: 0.6,
    },
  }), { tries, base: 2500 });

  const text = response.text;
  if (!text) throw new Error('No guide returned by Gemini.');
  const guide = JSON.parse(text);
  // Attach the reference video links for the cover.
  guide.reference_videos = creatorReports
    .map((c, i) => ({ label: `LINK${i + 1}`, url: c.meta?.url || '' }))
    .filter((x) => x.url);
  guide.creator = creatorName;
  return guide;
}
