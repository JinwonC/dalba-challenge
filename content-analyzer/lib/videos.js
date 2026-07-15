import { put, list, del } from '@vercel/blob';

// Public Blob store (separate from the private reports store) so the browser
// can stream the mp4 directly with range/seek support.
const token = () => process.env.VIDEOS_READ_WRITE_TOKEN;
export const videosEnabled = () => Boolean(process.env.VIDEOS_READ_WRITE_TOKEN);

/**
 * Save an mp4 to the public videos store and return its public URL.
 * Keyed by videoId so re-analysis overwrites. Returns null if not configured.
 */
export async function saveVideo(videoId, buffer, contentType = 'video/mp4') {
  if (!videosEnabled() || !videoId || !buffer) return null;
  const safe = String(videoId).replace(/[^\w-]/g, '');
  if (!safe) return null;
  const blob = await put(`videos/${safe}.mp4`, buffer, {
    access: 'public',
    token: token(),
    contentType,
    allowOverwrite: true,
    cacheControlMaxAge: 31536000, // videos are immutable per id
  });
  return blob.url;
}

/** Delete a stored video by id (best-effort). */
export async function deleteVideo(id) {
  if (!videosEnabled() || !id) return;
  const safe = String(id).replace(/[^\w-]/g, '');
  if (!safe) return;
  const { blobs } = await list({ prefix: `videos/${safe}`, token: token() });
  for (const b of blobs) if (b.pathname === `videos/${safe}.mp4`) await del(b.url, { token: token() });
}

const MAX_AGE_DAYS = Number(process.env.VIDEO_MAX_AGE_DAYS || 3);
const MAX_VIDEOS = Number(process.env.VIDEO_MAX_COUNT || 20);
const MAX_TOTAL_BYTES = Number(process.env.VIDEO_MAX_TOTAL_MB || 250) * 1e6; // keep well under the free-tier cap

/**
 * Prune stored videos so storage stays bounded. Deletes (oldest first):
 *  1) anything older than MAX_AGE_DAYS,
 *  2) beyond the newest MAX_VIDEOS,
 *  3) beyond a total-size budget (MAX_TOTAL_BYTES).
 * Best-effort; never throws. Pruned entries fall back to the TikTok embed.
 */
export async function pruneOldVideos() {
  if (!videosEnabled()) return;
  try {
    const { blobs } = await list({ prefix: 'videos/', token: token() });
    const cutoff = Date.now() - MAX_AGE_DAYS * 86400000;
    const items = blobs
      .map((b) => ({ url: b.url, size: Number(b.size) || 0, t: new Date(b.uploadedAt).getTime() }))
      .sort((a, b) => b.t - a.t); // newest first

    const toDelete = new Set();
    let kept = 0, bytes = 0;
    for (const it of items) {
      const expired = it.t < cutoff;
      kept += 1;
      bytes += it.size;
      if (expired || kept > MAX_VIDEOS || bytes > MAX_TOTAL_BYTES) {
        toDelete.add(it.url);
        bytes -= it.size; // it won't be kept
        kept -= 1;
      }
    }
    if (toDelete.size) await del([...toDelete], { token: token() });
  } catch (e) {
    console.warn('Video prune skipped:', e.message);
  }
}
