import { runAnalysis, HttpError } from '../lib/pipeline.js';

// maxDuration is configured in vercel.json (the whole pipeline — scrape +
// ~60MB download + Gemini upload/generate — is slow).

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed. Use POST.' });
  }
  try {
    // Vercel auto-parses JSON bodies, but guard against a string body too.
    const body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {});
    const result = await runAnalysis({ url: body.url, language: body.language });
    res.status(200).json(result);
  } catch (err) {
    const status = err instanceof HttpError ? err.status : 502;
    if (status >= 500) console.error('Analyze failed:', err);
    res.status(status).json({ error: err.message || 'Analysis failed.' });
  }
}
