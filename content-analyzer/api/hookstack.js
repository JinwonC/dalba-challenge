import { runHookStack, HttpError } from '../lib/pipeline.js';

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed. Use POST.' });
  try {
    const b = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {});
    res.status(200).json(await runHookStack({
      hookReports: b.hookReports,
      productInfo: b.productInfo,
      language: b.language,
      meta: b.meta,
    }));
  } catch (err) {
    const status = err instanceof HttpError ? err.status : 502;
    if (status >= 500) console.error('Hook stack failed:', err);
    res.status(status).json({ error: err.message || 'Hook stacking failed.' });
  }
}
