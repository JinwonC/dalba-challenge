// Push a report to Google Drive via a user-deployed Apps Script web app.
// The script creates a Google Doc (owned by the user) in their folder.
// Configure DRIVE_WEBHOOK_URL (+ optional DRIVE_WEBHOOK_SECRET) to enable.

export const driveEnabled = () => Boolean(process.env.DRIVE_WEBHOOK_URL);

export async function pushToDrive({ title, text }) {
  if (!driveEnabled()) return null;
  try {
    // Apps Script responds via a 302 redirect; capture the Location then GET it
    // to read the JSON ({id, url}) so we can store a link to the created Doc.
    const res = await fetch(process.env.DRIVE_WEBHOOK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ secret: process.env.DRIVE_WEBHOOK_SECRET || '', title, text }),
      redirect: 'manual',
    });
    const loc = res.headers.get('location');
    if (!loc) return null;
    const j = await (await fetch(loc)).json().catch(() => null);
    if (j && j.id) return `https://docs.google.com/document/d/${j.id}/edit`;
    return (j && j.url) || null;
  } catch (e) {
    console.warn('Drive push error:', e.message);
    return null;
  }
}
