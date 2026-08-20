import { runStylePass, HttpError } from '../lib/pipeline.js';

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed. Use POST.' });
  try {
    const b = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {});
    res.status(200).json(await runStylePass({ videoUrl: b.videoUrl }));
  } catch (err) {
    const status = err instanceof HttpError ? err.status : 502;
    if (status >= 500) console.error('Style pass failed:', err);
    res.status(status).json({ error: err.message || 'Style pass failed.' });
  }
}
