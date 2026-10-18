// Starts the GitHub login for the /admin editor (Cloudflare Pages Function).
// Needs two environment variables in Cloudflare: GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET.
export async function onRequest({ request, env }) {
  const url = new URL(request.url);
  if (!env.GITHUB_CLIENT_ID) return new Response('GITHUB_CLIENT_ID is not set in Cloudflare Pages settings.', { status: 500 });
  const state = crypto.randomUUID();
  const redirect = `${url.origin}/api/callback`;
  const target = 'https://github.com/login/oauth/authorize?client_id=' + encodeURIComponent(env.GITHUB_CLIENT_ID) +
    '&redirect_uri=' + encodeURIComponent(redirect) + '&scope=' + encodeURIComponent('repo,user') + '&state=' + state;
  return new Response(null, {
    status: 302,
    headers: { Location: target, 'Set-Cookie': `oauth_state=${state}; HttpOnly; Secure; Path=/; SameSite=Lax; Max-Age=600` },
  });
}
