import Anthropic from '@anthropic-ai/sdk';

const MODEL = process.env.ANTHROPIC_MODEL || 'claude-opus-4-8';

let _client = null;
function client() {
  if (!_client) {
    if (!process.env.ANTHROPIC_API_KEY) {
      throw new Error('ANTHROPIC_API_KEY is not set. Add it to your .env file.');
    }
    _client = new Anthropic();
  }
  return _client;
}

// Structured-output schema. Keep it within the supported subset:
// basic types, enums, arrays, additionalProperties:false, required on every object.
const ANALYSIS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    summary: { type: 'string', description: 'A 2-3 sentence overview of the video.' },
    hook: {
      type: 'object',
      additionalProperties: false,
      properties: {
        text: { type: 'string', description: 'The opening hook, as best inferred from caption/transcript.' },
        analysis: { type: 'string', description: 'Why the hook does or does not work.' },
      },
      required: ['text', 'analysis'],
    },
    content_breakdown: {
      type: 'object',
      additionalProperties: false,
      properties: {
        structure: { type: 'string', description: 'How the content is structured/paced from start to finish.' },
        themes: { type: 'array', items: { type: 'string' } },
        tone: { type: 'string' },
        target_audience: { type: 'string' },
        hashtags: { type: 'array', items: { type: 'string' } },
        on_screen_text_or_keywords: {
          type: 'array',
          items: { type: 'string' },
          description: 'Notable phrases, on-screen text, or keywords surfaced in the content.',
        },
      },
      required: ['structure', 'themes', 'tone', 'target_audience', 'hashtags', 'on_screen_text_or_keywords'],
    },
    creative_insights: {
      type: 'object',
      additionalProperties: false,
      properties: {
        whats_working: { type: 'array', items: { type: 'string' } },
        improvements: { type: 'array', items: { type: 'string' } },
        recommendations: {
          type: 'array',
          items: { type: 'string' },
          description: 'Concrete, actionable next steps for the creator/brand.',
        },
      },
      required: ['whats_working', 'improvements', 'recommendations'],
    },
  },
  required: ['summary', 'hook', 'content_breakdown', 'creative_insights'],
};

const SYSTEM_PROMPT = `You are a senior social-media content strategist for a beauty/skincare brand (d'Alba Piedmont).
You analyze short-form and long-form video content from YouTube and TikTok.
Be specific and grounded in the data you are given — do not invent metrics or claims.
When transcript or caption data is thin, reason from what is available and say so rather than fabricating detail.
Your analysis covers two things: (1) a content breakdown, and (2) creative insights with actionable recommendations.`;

function buildUserPrompt(content) {
  const stats = Object.entries(content.stats || {})
    .filter(([, v]) => v !== undefined && v !== null)
    .map(([k, v]) => `${k}: ${v}`)
    .join(', ');

  return `Analyze this ${content.platform.toUpperCase()} video.

URL: ${content.url}
Title: ${content.title || '(none)'}
Author/Channel: ${content.author || '(unknown)'}
Duration (seconds): ${content.durationSeconds ?? '(unknown)'}
Stats: ${stats || '(none available)'}
Hashtags: ${(content.hashtags || []).map((h) => '#' + h).join(' ') || '(none)'}

Caption / Description:
"""
${(content.description || '(none)').slice(0, 6000)}
"""

Transcript / Subtitles:
"""
${(content.transcript || '(none available)').slice(0, 20000)}
"""

Produce a structured content breakdown and creative insights for this video.`;
}

/** Run Claude analysis over a normalized content object. Returns parsed JSON. */
export async function analyzeContent(content) {
  const response = await client().messages.create({
    model: MODEL,
    max_tokens: 8000,
    output_config: {
      effort: 'medium',
      format: { type: 'json_schema', schema: ANALYSIS_SCHEMA },
    },
    system: SYSTEM_PROMPT,
    messages: [{ role: 'user', content: buildUserPrompt(content) }],
  });

  if (response.stop_reason === 'refusal') {
    throw new Error('The model declined to analyze this content.');
  }

  // output_config.format guarantees the first text block is valid JSON.
  const textBlock = response.content.find((b) => b.type === 'text');
  if (!textBlock) throw new Error('No analysis returned by the model.');
  return JSON.parse(textBlock.text);
}
