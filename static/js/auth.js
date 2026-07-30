/**
 * Where the access token lives, and who is signed in.
 *
 * The token sits in localStorage because that is the only place a page
 * with no build step and no server-side session can reach it. The cost
 * is real and worth writing down: anything that manages to run script on
 * this origin can read it, which an httpOnly cookie would prevent. The
 * cookie is also what the server-rendered side actually needs — `Write`
 * and `Profile` are drawn by Jinja, and Jinja cannot see localStorage,
 * which is why `is_author` is still hardcoded in templating.py.
 *
 * So this is the client-side half of sign-in, honestly scoped: it proves
 * you have a token and lets the API accept you. It does not yet make the
 * server treat you as the author.
 */

const KEY = "accessToken";

// Kept in sync with the `data-signed-in` attribute the layout sets before
// the body is parsed, so the navigation never flashes the wrong link.
function publish(signedIn) {
  document.documentElement.dataset.signedIn = String(signedIn);
}

export function getToken() {
  return localStorage.getItem(KEY);
}

export function isSignedIn() {
  return Boolean(getToken());
}

export function saveToken(token) {
  localStorage.setItem(KEY, token);
  publish(true);
}

export function clearToken() {
  localStorage.removeItem(KEY);
  publish(false);
}

/**
 * Authorization header for a request, or nothing when signed out.
 *
 * Spread into a fetch's headers: `{...authHeaders(), ...}`. Returning an
 * empty object rather than undefined means the caller never has to check.
 */
export function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Who is signed in, from the token's own payload.
 *
 * The id is the `sub` claim, so reading it costs no request — which
 * matters, because every post page asks the question. The signature is
 * NOT checked here and cannot be: the secret is on the server. So this
 * answers "whose controls should this page show", never "may this
 * person do it". Anyone can put whatever they like in localStorage; the
 * answer to the second question has to come from the API refusing them.
 *
 * Returns null when signed out, when the token is not a readable JWT, or
 * when it has expired — an expired token should stop showing an Edit
 * link at the same moment it stops working.
 */
export function currentUserId() {
  const token = getToken();
  if (!token) return null;

  const [, payload] = token.split(".");
  if (!payload) return null;

  try {
    // JWT uses base64url and drops the padding; atob wants neither.
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
    const claims = JSON.parse(atob(padded));

    if (claims.exp && claims.exp * 1000 <= Date.now()) return null;

    const id = Number(claims.sub);
    return Number.isInteger(id) ? id : null;
  } catch {
    return null;
  }
}
