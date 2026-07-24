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

// Resolve at request time: the device token is constant, but the backend
// binds it to the authenticated officer's user_id before reading history.
export function getOwnerHeaders() {
  return { "X-Owner-Token": getOwnerToken() };
}
