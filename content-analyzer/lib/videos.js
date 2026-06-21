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

const MAX_AGE_DAYS = Number(process.env.VIDEO_MAX_AGE_DAYS || 30);
const MAX_VIDEOS = Number(process.env.VIDEO_MAX_COUNT || 40);

/**
 * Prune stored videos so storage stays bounded: delete anything older than
 * MAX_AGE_DAYS, and keep at most MAX_VIDEOS newest. Best-effort; never throws.
 * History entries whose video was pruned fall back to the TikTok embed.
 */
export async function pruneOldVideos() {
  if (!videosEnabled()) return;
  try {
    const { blobs } = await list({ prefix: 'videos/', token: token() });
    const cutoff = Date.now() - MAX_AGE_DAYS * 86400000;
    const withTime = blobs.map((b) => ({ url: b.url, t: new Date(b.uploadedAt).getTime() }));
    const tooOld = withTime.filter((b) => b.t < cutoff);
    const fresh = withTime.filter((b) => b.t >= cutoff).sort((a, b) => b.t - a.t);
    const overflow = fresh.slice(MAX_VIDEOS); // keep newest MAX_VIDEOS
    const toDelete = [...tooOld, ...overflow].map((b) => b.url);
    if (toDelete.length) await del(toDelete, { token: token() });
  } catch (e) {
    console.warn('Video prune skipped:', e.message);
  }
}
