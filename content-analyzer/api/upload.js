import { handleUpload } from '@vercel/blob/client';

// Issues a short-lived client token so the browser can upload a video straight
// to the public videos Blob store (bypassing the 4.5MB serverless body limit).
export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed. Use POST.' });
  try {
    const body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {});
    const jsonResponse = await handleUpload({
      body,
      request: req,
      token: process.env.VIDEOS_READ_WRITE_TOKEN,
      onBeforeGenerateToken: async () => ({
        allowedContentTypes: [
          'video/mp4', 'video/quicktime', 'video/webm', 'video/x-m4v',
          'video/x-matroska', 'video/x-msvideo', 'application/octet-stream',
        ],
        addRandomSuffix: true,
        maximumSizeInBytes: 300 * 1024 * 1024,
      }),
      onUploadCompleted: async () => {},
    });
    return res.status(200).json(jsonResponse);
  } catch (err) {
    console.error('Upload token failed:', err);
    return res.status(400).json({ error: err.message || 'Upload failed.' });
  }
}
