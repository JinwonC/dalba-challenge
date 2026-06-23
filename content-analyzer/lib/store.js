import { put, get, list, del } from '@vercel/blob';
import { reportToPlainText } from './reportText.js';
import { pushToDrive, driveEnabled } from './drive.js';
import { deleteVideo } from './videos.js';

const ACCESS = 'private';
const token = () => process.env.BLOB_READ_WRITE_TOKEN;
export const storeEnabled = () => Boolean(process.env.BLOB_READ_WRITE_TOKEN);

const INDEX = 'index.json';
const validId = (id) => typeof id === 'string' && /^[\w-]{1,64}$/.test(id);

async function readJSON(pathname) {
  try {
    const g = await get(pathname, { token: token(), access: ACCESS });
    if (g.statusCode !== 200 || !g.stream) return null;
    const reader = g.stream.getReader();
    const chunks = [];
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(Buffer.from(value));
    }
    return JSON.parse(Buffer.concat(chunks).toString('utf8'));
  } catch {
    return null;
  }
}

async function writeJSON(pathname, obj) {
  await put(pathname, JSON.stringify(obj), {
    access: ACCESS,
    token: token(),
    contentType: 'application/json',
    allowOverwrite: true,
    cacheControlMaxAge: 0, // index/reports change; avoid stale CDN reads
  });
}

/**
 * Save (or overwrite) an analysis, keyed by videoId so re-analyzing the same
 * video updates the same entry. Also maintains a lightweight index for the
 * history list. Returns the id, or null if storage is not configured.
 */
export async function saveAnalysis(record) {
  if (!storeEnabled()) return null;
  const id = record?.embed?.videoId || record?.id;
  if (!validId(id)) throw new Error('Cannot save: missing/invalid video id.');

  const rec = { ...record, id, savedAt: Date.now() };
  await writeJSON(`reports/${id}.json`, rec);

  const idx = (await readJSON(INDEX)) || { items: [] };
  const summary = {
    id,
    creator: rec.meta?.author || '',
    title: rec.meta?.title || '',
    manager: rec.meta?.manager || '',
    product: rec.meta?.product || '',
    thumbnail: rec.meta?.thumbnail || '',
    url: rec.meta?.url || rec.embed?.url || '',
    savedAt: rec.savedAt,
  };
  idx.items = [summary, ...(idx.items || []).filter((x) => x.id !== id)].slice(0, 300);
  await writeJSON(INDEX, idx);

  // Best-effort: also export to Google Drive (as a Doc) if configured.
  if (driveEnabled()) {
    const title = `[분석] ${rec.meta?.author || ''} — ${(rec.meta?.title || id).slice(0, 60)}`;
    await pushToDrive({ title, text: reportToPlainText(rec) }).catch(() => {});
  }
  return id;
}

/** List saved analyses (newest first), summary fields only. */
export async function listAnalyses() {
  if (!storeEnabled()) return [];
  const idx = await readJSON(INDEX);
  return idx?.items || [];
}

/** Fetch one full saved analysis by id. */
export async function getAnalysis(id) {
  if (!storeEnabled() || !validId(id)) return null;
  return readJSON(`reports/${id}.json`);
}

/** Delete an analysis: report blob + index entry + stored video (best-effort). */
export async function deleteAnalysis(id) {
  if (!storeEnabled() || !validId(id)) return false;
  try {
    const { blobs } = await list({ prefix: `reports/${id}`, token: token() });
    for (const b of blobs) if (b.pathname === `reports/${id}.json`) await del(b.url, { token: token() });
    const idx = (await readJSON(INDEX)) || { items: [] };
    idx.items = (idx.items || []).filter((x) => x.id !== id);
    await writeJSON(INDEX, idx);
  } catch (e) {
    console.warn('Delete report failed:', e.message);
  }
  await deleteVideo(id).catch(() => {});
  return true;
}
