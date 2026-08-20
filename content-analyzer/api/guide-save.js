import { pushToDrive, driveEnabled } from '../lib/drive.js';
import { guideToPlainText } from '../lib/guideText.js';

// Export a generated guide to Google Drive as a Doc. Returns { driveUrl }.
export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed. Use POST.' });
  try {
    const b = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {});
    const guide = b.guide || {};
    const meta = b.meta || {};
    if (!driveEnabled()) return res.status(200).json({ driveUrl: null, note: 'Drive not configured.' });
    const title = `[가이드] ${guide.creator ? '@' + guide.creator + ' 스타일' : ''} — ${meta.product || guide?.product?.name || 'Contents Brief'}`.slice(0, 90);
    const driveUrl = await pushToDrive({ title, text: guideToPlainText(guide, meta) }).catch(() => null);
    return res.status(200).json({ driveUrl });
  } catch (err) {
    console.error('Guide save failed:', err);
    return res.status(500).json({ error: err.message || 'Guide save failed.' });
  }
}
