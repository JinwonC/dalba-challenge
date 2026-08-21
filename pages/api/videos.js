// GET /api/videos?from=YYYY-MM-DD&to=YYYY-MM-DD&minGmv=0
const { readAll } = require('../../lib/sheets');

function num(x) {
  const v = parseFloat(String(x == null ? '' : x).replace(/[$,%\s]/g, ''));
  return isNaN(v) ? 0 : v;
}

module.exports = async function handler(req, res) {
  if (process.env.APP_KEY && req.headers['x-app-key'] !== process.env.APP_KEY) {
    return res.status(401).json({ error: 'unauthorized' });
  }
  try {
    const rows = await readAll();
    const header = rows[0] || [];
    const H = {};
    header.forEach((h, i) => { H[h] = i; });
    const g = (row, name) => (H[name] != null ? row[H[name]] : '');

    const from = req.query.from || '2000-01-01';
    const to = req.query.to || '2999-12-31';
    const minGmv = num(req.query.minGmv || '0');

    const out = [];
    for (let r = 1; r < rows.length; r++) {
      const row = rows[r];
      const post = String(g(row, 'video_post_time') || '').slice(0, 10);
      if (!post || post < from || post > to) continue;
      const gmv = num(g(row, 'gmv.amount'));
      if (gmv < minGmv) continue;
      out.push({
        id: String(g(row, 'id') || '').replace(/^'/, ''),
        title: g(row, 'title') || '',
        handle: g(row, 'username') || '',
        product: g(row, 'products') || '',
        postDate: post,
        views: num(g(row, 'views')),
        gmv,
        gpm: num(g(row, 'gpm.amount')),
        units: num(g(row, 'items_sold')),
        orders: num(g(row, 'sku_orders')),
        ctr: g(row, 'click_through_rate') || '',
        rating: g(row, '평가') || '',
        note: g(row, '특이사항') || '',
      });
    }
    out.sort((a, b) => b.gmv - a.gmv);
    res.status(200).json({ count: out.length, videos: out.slice(0, 1500) });
  } catch (e) {
    res.status(500).json({ error: String((e && e.message) || e) });
  }
};
