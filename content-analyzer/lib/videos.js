import { put } from '@vercel/blob';

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
