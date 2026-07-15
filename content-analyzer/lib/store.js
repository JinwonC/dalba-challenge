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

/** Build a history-list summary from a full stored record. */
function summaryOf(rec) {
  return {
    id: rec.id,
    creator: rec.meta?.author || '',
    title: rec.meta?.title || '',
    manager: rec.meta?.manager || '',
    product: rec.meta?.product || '',
    thumbnail: rec.meta?.thumbnail || '',
    url: rec.meta?.url || rec.embed?.url || '',
    driveUrl: rec.driveUrl || '',
    savedAt: rec.savedAt || 0,
  };
}

/** List the actual report blobs (source of truth) and their pathnames. */
async function listReportBlobs() {
  const { blobs } = await list({ prefix: 'reports/', token: token() });
  return blobs.filter((b) => /^reports\/[\w-]+\.json$/.test(b.pathname));
}

/**
 * Rebuild the history index from the report blobs themselves. The index is only
 * a derived cache; the reports/<id>.json blobs are the source of truth. Used to
 * self-heal when the cache is missing or out of sync (e.g. a transient index
 * read returned null, which previously clobbered the whole list).
 */
async function rebuildIndex() {
  const items = [];
  for (const b of await listReportBlobs()) {
    const rec = await readJSON(b.pathname);
    if (rec && rec.id) items.push(summaryOf(rec));
  }
  items.sort((a, b) => (b.savedAt || 0) - (a.savedAt || 0));
  return items.slice(0, 300);
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

  // Export to Google Drive first so we can store the Doc link with the record.
  let driveUrl = record.driveUrl || null;
  if (driveEnabled()) {
    const title = `[분석] ${rec.meta?.author || ''} — ${(rec.meta?.title || id).slice(0, 60)}`;
    driveUrl = (await pushToDrive({ title, text: reportToPlainText(rec) }).catch(() => null)) || driveUrl;
  }
  rec.driveUrl = driveUrl;

  await writeJSON(`reports/${id}.json`, rec);

  // If the index can't be read (transient/eventual-consistency), rebuild it from
  // the report blobs instead of starting from empty — otherwise this single save
  // would overwrite the index and wipe all prior history.
  let idx = await readJSON(INDEX);
  if (!idx || !Array.isArray(idx.items)) idx = { items: await rebuildIndex().catch(() => []) };
  idx.items = [summaryOf(rec), ...idx.items.filter((x) => x.id !== id)].slice(0, 300);
  await writeJSON(INDEX, idx);

  return { id, driveUrl };
}

/** List saved analyses (newest first), summary fields only. Self-heals a stale index. */
export async function listAnalyses() {
  if (!storeEnabled()) return [];
  const idx = await readJSON(INDEX);
  let items = idx && Array.isArray(idx.items) ? idx.items : null;
  try {
    const count = (await listReportBlobs()).length;
    // Cache missing, or out of sync with the real reports → rebuild and persist.
    if (items === null || count !== items.length) {
      items = await rebuildIndex();
      await writeJSON(INDEX, { items }).catch(() => {});
    }
  } catch { /* best-effort heal; fall back to whatever the index had */ }
  return items || [];
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
