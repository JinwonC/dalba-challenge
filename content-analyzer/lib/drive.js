// Push a report to Google Drive via a user-deployed Apps Script web app.
// The script creates a Google Doc (owned by the user) in their folder.
// Configure DRIVE_WEBHOOK_URL (+ optional DRIVE_WEBHOOK_SECRET) to enable.

export const driveEnabled = () => Boolean(process.env.DRIVE_WEBHOOK_URL);

export async function pushToDrive({ title, text }) {
  if (!driveEnabled()) return null;
  try {
    const res = await fetch(process.env.DRIVE_WEBHOOK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        secret: process.env.DRIVE_WEBHOOK_SECRET || '',
        title,
        text,
      }),
      redirect: 'follow',
    });
    if (!res.ok) { console.warn('Drive push failed:', res.status); return null; }
    const j = await res.json().catch(() => ({}));
    return j.url || null;
  } catch (e) {
    console.warn('Drive push error:', e.message);
    return null;
  }
}
