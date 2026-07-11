// Generates (once per browser) a random owner token and stores it,
// so this browser consistently "owns" the conversations it creates.
const KEY = "ksp_owner_token";

function getOwnerToken() {
  let token = localStorage.getItem(KEY);
  if (!token) {
    token = crypto.randomUUID();
    localStorage.setItem(KEY, token);
  }
  return token;
}

export const AUTH_HEADERS = { "X-Owner-Token": getOwnerToken() };
