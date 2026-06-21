import { put, get } from '@vercel/blob';

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
    thumbnail: rec.meta?.thumbnail || '',
    url: rec.meta?.url || rec.embed?.url || '',
    savedAt: rec.savedAt,
  };
  idx.items = [summary, ...(idx.items || []).filter((x) => x.id !== id)].slice(0, 300);
  await writeJSON(INDEX, idx);
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
