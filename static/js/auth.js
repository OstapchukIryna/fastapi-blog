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
