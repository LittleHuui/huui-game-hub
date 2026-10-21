const ONLINE_AUTH_KEY = 'game_hub_online_auth';

function readJson(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    if (raw == null || raw === '') {
      return fallback;
    }
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

function writeJson(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

export function readOnlineAuth() {
  const value = readJson(ONLINE_AUTH_KEY, { tokensByServerUserId: {} });
  return value && typeof value === 'object' ? value : { tokensByServerUserId: {} };
}

export function saveToken(serverUserId, token) {
  const normalizedUserId = String(serverUserId || '').trim();
  const accessToken = String(token?.accessToken || '').trim();
  if (!normalizedUserId || !accessToken) {
    return;
  }
  const auth = readOnlineAuth();
  const tokensByServerUserId =
    auth.tokensByServerUserId && typeof auth.tokensByServerUserId === 'object'
      ? { ...auth.tokensByServerUserId }
      : {};
  tokensByServerUserId[normalizedUserId] = {
    accessToken,
    expiresAt: Number(token?.expiresAt || 0)
  };
  writeJson(ONLINE_AUTH_KEY, { ...auth, tokensByServerUserId });
}

export function getToken(serverUserId) {
  const normalizedUserId = String(serverUserId || '').trim();
  if (!normalizedUserId) {
    return null;
  }
  const auth = readOnlineAuth();
  const tokensByServerUserId =
    auth.tokensByServerUserId && typeof auth.tokensByServerUserId === 'object'
      ? auth.tokensByServerUserId
      : {};
  const token = tokensByServerUserId[normalizedUserId];
  return token && typeof token === 'object' ? token : null;
}

export function clearToken(serverUserId) {
  const normalizedUserId = String(serverUserId || '').trim();
  if (!normalizedUserId) {
    return;
  }
  const auth = readOnlineAuth();
  const tokensByServerUserId =
    auth.tokensByServerUserId && typeof auth.tokensByServerUserId === 'object'
      ? { ...auth.tokensByServerUserId }
      : {};
  delete tokensByServerUserId[normalizedUserId];
  writeJson(ONLINE_AUTH_KEY, { ...auth, tokensByServerUserId });
}
