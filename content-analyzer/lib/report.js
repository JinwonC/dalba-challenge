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

/** Whether a Gemini error is transient and worth retrying. */
function isTransient(err) {
  const s = err?.status || err?.code;
  const msg = String(err?.message || '');
  return s === 429 || s === 500 || s === 503 ||
    /UNAVAILABLE|overload|high demand|rate limit|deadline|internal/i.test(msg);
}

/** Retry a transient call a few times with short backoff (keeps total under the serverless cap). */
async function withRetry(fn, { tries = 3, base = 2500 } = {}) {
  let last;
  for (let i = 0; i < tries; i++) {
    try {
      return await fn();
    } catch (err) {
      last = err;
      if (i === tries - 1 || !isTransient(err)) throw err;
      await sleep(base * (i + 1));
    }
  }
  throw last;
}

// Structured-output schema for the scene-by-scene report + d'Alba insights.
const REPORT_SCHEMA = {
  type: 'object',
  properties: {
    summary: { type: 'string', description: '2-3 sentence overview of the video.' },
    scenes: {
      type: 'array',
      description: 'The video segmented into sequential scenes, in order.',
      items: {
        type: 'object',
        properties: {
          scene: { type: 'string', description: 'Short scene label, e.g. "Opening Hook", "Product Information".' },
          time: { type: 'string', description: 'Time range, e.g. "0~16s" or "1:33~1:47".' },
          shot: { type: 'string', description: 'Camera framing, e.g. "Medium Close-Up", "Close-Up Shot".' },
          visual: { type: 'string', description: 'What is on screen: subject, actions, props, on-screen text, setting.' },
          audio: { type: 'string', description: 'The spoken words / audio script for this scene (cleaned transcript).' },
        },
        required: ['scene', 'time', 'shot', 'visual', 'audio'],
        propertyOrdering: ['scene', 'time', 'shot', 'visual', 'audio'],
      },
    },
    insights: {
      type: 'object',
      properties: {
        whats_working: { type: 'array', items: { type: 'string' } },
        improvements: { type: 'array', items: { type: 'string' } },
        recommendations: {
          type: 'array',
          items: { type: 'string' },
          description: "Concrete, actionable next steps for d'Alba (brand/creative team).",
        },
      },
      required: ['whats_working', 'improvements', 'recommendations'],
      propertyOrdering: ['whats_working', 'improvements', 'recommendations'],
    },
    dalba_relevance: {
      type: 'string',
      description: "How this content relates to d'Alba Piedmont (a beauty/skincare brand) and any product mentions or fit.",
    },
  },
  required: ['summary', 'scenes', 'insights', 'dalba_relevance'],
  propertyOrdering: ['summary', 'scenes', 'insights', 'dalba_relevance'],
};

const SYSTEM = `You are a senior short-form video strategist for d'Alba Piedmont, a premium vegan beauty/skincare brand.
You will WATCH the attached video and also read its time-coded transcript (WebVTT).
Produce a precise SCENE-BY-SCENE breakdown plus creative insights.

Rules:
- Segment the video into sequential, meaningful scenes (typically 6-10). Each scene = a coherent beat (hook, problem, product info, demo, social proof, CTA, etc.).
- "time" must be grounded in the actual timeline (use the transcript timestamps and what you see).
- "visual" describes what is actually on screen — people, actions, props, ON-SCREEN TEXT (quote it), setting/lighting. Do not invent.
- "audio" is the spoken script for that scene, lightly cleaned (fix obvious ASR errors). IMPORTANT: the ASR often mis-hears the brand "d'Alba" as "Diablo" — correct it to "d'Alba".
- Insights and dalba_relevance must be specific and grounded, framed for d'Alba's brand/creative team. No invented metrics.
- Write audio/visual/insights in the SAME LANGUAGE the user requests (default: match the video's spoken language).`;

/**
 * Generate the structured scene report with Gemini (watches the mp4 + reads the VTT).
 * @param {object} args
 * @param {Buffer} args.videoBuffer
 * @param {string} [args.mimeType]
 * @param {string} [args.transcriptVtt] time-coded subtitles (WebVTT)
 * @param {object} [args.meta] { url, title, author, durationSeconds, stats, hashtags }
 * @param {string} [args.language] e.g. 'Korean' | 'English'
 * @returns {Promise<object>} parsed report JSON
 */
export async function generateReport({ videoBuffer, mimeType = 'video/mp4', transcriptVtt = '', meta = {}, language = 'Korean' }) {
  const client = ai();

  let file = await client.files.upload({
    file: new Blob([videoBuffer], { type: mimeType }),
    config: { mimeType },
  });
  for (let i = 0; i < 30 && file.state === 'PROCESSING'; i++) {
    await sleep(2000);
    file = await client.files.get({ name: file.name });
  }
  if (file.state !== 'ACTIVE') {
    throw new Error(`Gemini could not process the video (state: ${file.state}).`);
  }

  const stats = Object.entries(meta.stats || {})
    .filter(([, v]) => v !== undefined && v !== null)
    .map(([k, v]) => `${k}: ${v}`)
    .join(', ');

  const prompt = `Analyze this ${(meta.platform || 'TikTok')} video and return the scene-by-scene report.

Write all free-text fields (scene labels, visual, audio, insights, dalba_relevance) in ${language}.

URL: ${meta.url || '(n/a)'}
Title/Caption: ${meta.title || '(none)'}
Author: ${meta.author || '(unknown)'}
Duration (s): ${meta.durationSeconds ?? '(unknown)'}
Stats: ${stats || '(none)'}
Hashtags: ${(meta.hashtags || []).map((h) => '#' + h).join(' ') || '(none)'}

Time-coded transcript (WebVTT):
"""
${(transcriptVtt || '(none available — rely on what you hear/see)').slice(0, 30000)}
"""`;

  const response = await withRetry(() => client.models.generateContent({
    model: MODEL,
    contents: createUserContent([
      createPartFromUri(file.uri, file.mimeType),
      SYSTEM,
      prompt,
    ]),
    config: {
      responseMimeType: 'application/json',
      responseSchema: REPORT_SCHEMA,
      temperature: 0.4,
    },
  }), { tries: 3, base: 2500 });

  const text = response.text;
  if (!text) throw new Error('No report returned by Gemini.');
  return JSON.parse(text);
}
