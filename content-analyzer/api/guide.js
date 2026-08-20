import { runGuide, HttpError } from '../lib/pipeline.js';

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed. Use POST.' });
  try {
    const b = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {});
    res.status(200).json(await runGuide({
      creatorReports: b.creatorReports,
      ourReport: b.ourReport,
      productInfo: b.productInfo,
      meta: b.meta,
      dna: b.dna,
    }));
  } catch (err) {
    const status = err instanceof HttpError ? err.status : 502;
    if (status >= 500) console.error('Guide failed:', err);
    res.status(status).json({ error: err.message || 'Guide generation failed.' });
  }
}
