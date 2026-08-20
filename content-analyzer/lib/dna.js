import { GoogleGenAI, createUserContent, createPartFromUri } from '@google/genai';

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

// ---- pacing: computed in plain JS from the reports (no model, no guessing) ----
function toSec(tok) {
  if (tok == null) return null;
  const s = String(tok).trim().replace(/초|s/gi, '').trim();
  if (/^\d{1,2}:\d{2}(:\d{2})?$/.test(s)) {
    const p = s.split(':').map(Number);
    return p.length === 3 ? p[0] * 3600 + p[1] * 60 + p[2] : p[0] * 60 + p[1];
  }
  const n = parseFloat(s);
  return Number.isFinite(n) ? n : null;
}
function sceneSpanSeconds(time) {
  const parts = String(time || '').split(/[~\-–—]/);
  const a = toSec(parts[0]);
  const b = parts[1] !== undefined ? toSec(parts[1]) : null;
  if (a == null || b == null || b <= a) return null;
  return b - a;
}

/** Aggregate pacing stats across creator videos: duration, scene counts, seconds per scene. */
export function computePacing(creatorReports = []) {
  const durs = [], counts = [], spans = [];
  for (const c of creatorReports) {
    const scenes = c.report?.scenes || [];
    if (scenes.length) counts.push(scenes.length);
    const d = Number(c.meta?.durationSeconds);
    if (Number.isFinite(d) && d > 0) durs.push(d);
    for (const s of scenes) {
      const sp = sceneSpanSeconds(s.time);
      if (sp != null && sp > 0 && sp < 300) spans.push(sp);
    }
  }
  const avg = (a) => (a.length ? Math.round((a.reduce((x, y) => x + y, 0) / a.length) * 10) / 10 : null);
  return {
    videos: creatorReports.length,
    avg_duration_s: avg(durs),
    min_duration_s: durs.length ? Math.min(...durs) : null,
    max_duration_s: durs.length ? Math.max(...durs) : null,
    avg_scene_count: avg(counts),
    avg_scene_seconds: avg(spans),
  };
}

const DNA_SCHEMA = {
  type: 'object',
  properties: {
    hook_formulas: {
      type: 'array',
      description: 'A가 반복해서 쓰는 훅 공식들(보통 2-3가지 유형).',
      items: {
        type: 'object',
        properties: {
          type: { type: 'string', description: '훅 유형 이름(한국어 짧게). 예: "도발/금기형", "질투 유발형", "궁금증 갭형".' },
          description: { type: 'string', description: '이 유형이 어떻게 작동하는지(한국어).' },
          example_original: { type: 'string', description: 'A의 영상에서 실제로 쓴 훅 문장 원문(영어 verbatim).' },
        },
        required: ['type', 'description', 'example_original'],
        propertyOrdering: ['type', 'description', 'example_original'],
      },
    },
    catchphrases: {
      type: 'array',
      items: { type: 'string' },
      description: 'A가 여러 영상에서 반복하는 말버릇·표현 원문(영어 verbatim). 문장 시작 패턴, 감탄사, 특유의 단어 포함. 5-12개.',
    },
    speech_style: { type: 'string', description: '말투 분석(한국어): 문장 길이, 속도감, 1인칭/2인칭 사용, 반말느낌/친구톤, 과장 강도 등.' },
    devices: {
      type: 'array',
      description: 'A가 반복 사용하는 연출 장치.',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string', description: '장치 이름. 예: "PIP 이미지 팝업", "마커로 얼굴에 그리기", "Before/After", "제품 클로즈업".' },
          how_used: { type: 'string', description: '어떻게/언제 쓰는지(한국어).' },
          frequency: { type: 'string', description: '몇 개 영상에서 나왔는지. 예: "4/5개 영상".' },
        },
        required: ['name', 'how_used', 'frequency'],
        propertyOrdering: ['name', 'how_used', 'frequency'],
      },
    },
    structure_pattern: { type: 'string', description: 'A의 전형적 비트 순서(한국어). 예: "도발 훅 → 문제 시연 → 성분 폭로 → 데모 → 소셜프루프 → 스카시티 CTA".' },
    cta_habits: { type: 'string', description: 'CTA 습관(한국어): 어떤 문구/타이밍/긴급성 장치를 쓰는지 + 실제 원문 예시(영어).' },
    tone: { type: 'string', description: '전반적 톤(한국어 한 줄). 예: "빠르고 확신에 찬 친구가 몰래 알려주는 꿀팁 톤".' },
  },
  required: ['hook_formulas', 'catchphrases', 'speech_style', 'devices', 'structure_pattern', 'cta_habits', 'tone'],
  propertyOrdering: ['hook_formulas', 'catchphrases', 'speech_style', 'devices', 'structure_pattern', 'cta_habits', 'tone'],
};

function creatorDigest(label, meta, report) {
  const r = report || {};
  const scenes = (r.scenes || []).map((s) => `  [${s.scene} · ${s.time}] shot:${s.shot} | visual:${s.visual} | say(orig):"${s.audio_original}"`).join('\n');
  const hook = r.hook_breakdown ? JSON.stringify(r.hook_breakdown) : '(none)';
  const persu = r.persuasion ? JSON.stringify(r.persuasion) : '(none)';
  const kw = (r.keywords || []).map((k) => `${k.keyword} (${k.note})`).join('; ');
  const stats = Object.entries(meta?.stats || {}).filter(([, v]) => v != null).map(([k, v]) => `${k}:${v}`).join(' ');
  return `### ${label}
author: @${meta?.author || '?'} | title: ${meta?.title || ''} | 성과: ${stats || '(unknown)'} | 길이: ${meta?.durationSeconds ?? '?'}s
HOOK: ${hook}
SCENES:
${scenes || '  (none)'}
PERSUASION: ${persu}
KEYWORDS: ${kw}
`;
}

/**
 * Stage 1 — extract the creator's style DNA from their analyzed videos.
 * Text-only (fast). Pacing is computed in JS and attached, not model-guessed.
 */
export async function extractDna({ creatorReports = [] }) {
  if (!creatorReports.length) throw new Error('크리에이터 영상 분석이 최소 1개 필요합니다.');
  const client = ai();

  const block = creatorReports.map((c, i) => creatorDigest(`VIRAL #${i + 1}`, c.meta, c.report)).join('\n');
  const system = `너는 숏폼 크리에이터 스타일 분석 전문가다.
한 크리에이터의 바이럴 영상 분석 여러 개를 보고, 그 크리에이터의 "스타일 DNA"를 추출한다.
규칙:
- 여러 영상에 반복되는 것일수록 진짜 DNA다. 성과(조회수)가 높은 영상의 패턴에 더 가중치를 준다.
- catchphrases와 example_original은 반드시 영상 대사 원문(verbatim)에서 그대로 가져온다. 지어내지 말 것.
- 한 영상에만 나온 특이 요소는 devices/hook_formulas에 넣지 않는다(빈도 기준 미달).`;
  const prompt = `아래는 같은 크리에이터의 바이럴 영상 ${creatorReports.length}개 분석이다. 스타일 DNA를 추출하라.

${block}`;

  const response = await withRetry(() => client.models.generateContent({
    model: MODEL,
    contents: [system, prompt].join('\n\n'),
    config: { responseMimeType: 'application/json', responseSchema: DNA_SCHEMA, temperature: 0.3 },
  }));
  const text = response.text;
  if (!text) throw new Error('No DNA returned by Gemini.');
  const dna = JSON.parse(text);
  dna.pacing = computePacing(creatorReports);
  dna.creator = creatorReports[0]?.meta?.author || '';
  return dna;
}

const STYLE_SCHEMA = {
  type: 'object',
  properties: {
    setting: { type: 'string', description: '촬영 장소/배경(한국어). 예: "차 안 셀피, 자연광".' },
    framing: { type: 'string', description: '카메라 프레이밍/앵글(한국어). 예: "얼굴 위주 미디엄 클로즈업, 셀피 그립".' },
    lighting: { type: 'string', description: '조명 느낌(한국어).' },
    captions_style: { type: 'string', description: '화면 자막/텍스트 오버레이 스타일(한국어): 폰트 느낌, 위치, 색, 이모지 사용.' },
    editing_pace: { type: 'string', description: '컷 편집 속도/줌·트랜지션 습관(한국어).' },
    product_handling: { type: 'string', description: '제품을 어떻게 다루나(한국어): 들이대기, 클로즈업, 사용 순간 연출.' },
    wardrobe_look: { type: 'string', description: '의상/메이크업/전반적 룩(한국어).' },
    other: { type: 'string', description: '기타 눈에 띄는 시각적 습관(한국어). 없으면 빈 문자열.' },
  },
  required: ['setting', 'framing', 'lighting', 'captions_style', 'editing_pace', 'product_handling', 'wardrobe_look', 'other'],
  propertyOrdering: ['setting', 'framing', 'lighting', 'captions_style', 'editing_pace', 'product_handling', 'wardrobe_look', 'other'],
};

/**
 * Visual style pass — Gemini watches one of A's videos and extracts only the
 * VISUAL style (things text analysis cannot capture). One video per call.
 */
export async function analyzeVisualStyle({ videoBuffer, mimeType = 'video/mp4' }) {
  const client = ai();
  let file = await client.files.upload({
    file: new Blob([videoBuffer], { type: mimeType }),
    config: { mimeType },
  });
  for (let i = 0; i < 30 && file.state === 'PROCESSING'; i++) {
    await sleep(2000);
    file = await client.files.get({ name: file.name });
  }
  if (file.state !== 'ACTIVE') throw new Error(`Gemini could not process the video (state: ${file.state}).`);

  const prompt = `이 영상을 보고 "시각적 스타일"만 분석하라(내용/대사 분석 금지 — 이미 따로 했다).
촬영 장소, 프레이밍, 조명, 화면 자막 스타일(위치·색·이모지), 컷 편집 속도, 제품을 다루는 방식, 룩. 전부 한국어로.`;

  const response = await withRetry(() => client.models.generateContent({
    model: MODEL,
    contents: createUserContent([createPartFromUri(file.uri, file.mimeType), prompt]),
    config: { responseMimeType: 'application/json', responseSchema: STYLE_SCHEMA, temperature: 0.3 },
  }), { tries: 2 });
  const text = response.text;
  if (!text) throw new Error('No style analysis returned.');
  return JSON.parse(text);
}
