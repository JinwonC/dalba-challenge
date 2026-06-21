// Edge middleware: simple shared-password gate (HTTP Basic Auth) over the whole site.
// Set SITE_PASSWORD in the project env to enable. If unset, the site stays open
// (so a missing env var can never lock you out). Username is ignored.

export const config = {
  // Protect everything except Vercel internals and the favicon.
  matcher: ['/((?!_vercel|favicon.ico).*)'],
};

export default function middleware(request) {
  const expected = process.env.SITE_PASSWORD;
  if (!expected) return; // gate disabled until a password is configured

  const header = request.headers.get('authorization') || '';
  const [scheme, encoded] = header.split(' ');
  if (scheme === 'Basic' && encoded) {
    let decoded = '';
    try { decoded = atob(encoded); } catch { decoded = ''; }
    const pass = decoded.slice(decoded.indexOf(':') + 1);
    if (pass === expected) return; // correct password -> allow through
  }

  return new Response('Authentication required.', {
    status: 401,
    headers: {
      'WWW-Authenticate': 'Basic realm="d\'Alba Content Analyzer", charset="UTF-8"',
      'Content-Type': 'text/plain; charset=utf-8',
    },
  });
}
