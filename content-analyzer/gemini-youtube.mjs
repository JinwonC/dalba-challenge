import { GoogleGenAI, createUserContent, createPartFromUri } from '@google/genai';

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
const url = process.argv[2];
const MODEL = process.env.GEMINI_MODEL || 'gemini-2.5-flash';

const PROMPT = `Watch this video and report ONLY what is actually on screen / spoken. Cover:
1. ON-SCREEN TEXT: every caption/title/graphic text, verbatim, in order.
2. SPOKEN CONTENT: a faithful summary of what is said (key lines quoted).
3. PEOPLE & ACTIONS: who is shown and what they do, as a short timeline.
4. SETTING & BACKGROUND: location, props, lighting, mood.
5. PRODUCTS/OBJECTS and VISUAL STYLE (shots, editing pace, color).
Be specific and factual.`;

const res = await ai.models.generateContent({
  model: MODEL,
  contents: createUserContent([createPartFromUri(url, 'video/*'), PROMPT]),
});
console.log(res.text);
