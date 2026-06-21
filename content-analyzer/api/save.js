import { saveAnalysis } from '../lib/store.js';

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed. Use POST.' });
  try {
    const body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {});
    const id = await saveAnalysis({ meta: body.meta, embed: body.embed, report: body.report, comments: body.comments, video: body.video, transcript: body.transcript });
    res.status(200).json({ id });
  } catch (err) {
    console.error('Save failed:', err);
    res.status(502).json({ error: err.message || 'Save failed.' });
  }
}
