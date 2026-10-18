// Finishes the GitHub login and hands the token back to the /admin editor window.
export async function onRequest({ request, env }) {
  const url = new URL(request.url);
  const code = url.searchParams.get('code');
  const state = url.searchParams.get('state');
  const cookie = (request.headers.get('Cookie') || '').match(/(?:^|;\s*)oauth_state=([^;]+)/);
  const page = (status, payload) => new Response(
    `<!doctype html><html><body><script>
(function () {
  var msg = 'authorization:github:${status}:' + ${JSON.stringify(JSON.stringify(payload))};
  function receive(e) {
    if (e.origin !== ${JSON.stringify(url.origin)}) return;
    window.opener.postMessage(msg, e.origin);
    window.removeEventListener('message', receive, false);
    window.close();
  }
  window.addEventListener('message', receive, false);
  window.opener.postMessage('authorizing:github', ${JSON.stringify(url.origin)});
})();
</script></body></html>`,
    { headers: { 'Content-Type': 'text/html;charset=UTF-8', 'Set-Cookie': 'oauth_state=; Max-Age=0; Path=/; Secure; HttpOnly' } });

  if (!code || !state || !cookie || cookie[1] !== state) return page('error', { message: 'Login check failed. Please close this window and try again.' });
  const r = await fetch('https://github.com/login/oauth/access_token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ client_id: env.GITHUB_CLIENT_ID, client_secret: env.GITHUB_CLIENT_SECRET, code }),
  });
  const data = await r.json();
  if (!data.access_token) return page('error', { message: data.error_description || 'GitHub did not return a token.' });
  return page('success', { token: data.access_token, provider: 'github' });
}
