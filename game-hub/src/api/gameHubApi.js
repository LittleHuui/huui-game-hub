import { apiUrl, requestJson, requestRawJson } from './request.js';

const HUB = '/api/game-hub';

/**
 * 健康检查（保留原始响应解析，避免 dev 下 index.html 误判）。
 * @returns {Promise<unknown>}
 */
export async function healthCheck() {
  const url = apiUrl(`${HUB}/health`);
  const controller = new AbortController();
  const tid = setTimeout(() => controller.abort(), 4000);
  try {
    const res = await fetch(url, {
      method: 'GET',
      signal: controller.signal,
      headers: { Accept: 'application/json' }
    });
    if (!res.ok) {
      throw new Error(`health HTTP ${res.status}`);
    }
    const ct = (res.headers.get('content-type') || '').toLowerCase();
    if (!ct.includes('application/json')) {
      throw new Error('health response is not application/json');
    }
    const raw = await res.json();
    if (raw && typeof raw === 'object' && 'code' in raw) {
      if (raw.code !== 0 || raw.success === false) {
        throw new Error(raw.message || 'health check failed');
      }
      return raw.data;
    }
    return raw;
  } catch (e) {
    if (e && e.name === 'AbortError') {
      throw new Error('health 请求超时');
    }
    throw e;
  } finally {
    clearTimeout(tid);
  }
}

/**
 * @param {object} payload
 * @returns {Promise<object>}
 */
export function getBootContext(payload) {
  return requestJson('POST', apiUrl(`${HUB}/boot/context`), payload);
}

/**
 * @param {object} payload
 * @returns {Promise<object>}
 */
export function syncCloudSave(payload) {
  return requestJson('POST', apiUrl(`${HUB}/sync/cloud-save`), payload, 12000);
}

export function getGames() {
  return requestJson('GET', apiUrl(`${HUB}/games`));
}

/**
 * @param {string} gameCode
 * @returns {Promise<object>}
 */
export function getGameConfig(gameCode) {
  return requestJson('GET', apiUrl(`${HUB}/games/${encodeURIComponent(gameCode)}/config`));
}

/**
 * @param {string} gameCode
 * @returns {Promise<object>}
 */
export function getGameProps(gameCode) {
  return requestJson('GET', apiUrl(`${HUB}/games/${encodeURIComponent(gameCode)}/props`));
}

/**
 * @param {{ enabled?: boolean }} [params]
 * @returns {Promise<object>}
 */
export function getProps(params = {}) {
  const q = new URLSearchParams();
  if (params.enabled != null) {
    q.set('enabled', String(params.enabled));
  }
  const qs = q.toString();
  return requestJson('GET', apiUrl(`${HUB}/props${qs ? `?${qs}` : ''}`));
}

/**
 * @param {{ gameCode: string; mode: string; difficultyCode?: string; limit?: number }} params
 * @returns {Promise<object>}
 */
export function getLeaderboard(params) {
  const q = new URLSearchParams();
  q.set('gameCode', params.gameCode);
  q.set('mode', params.mode);
  if (params.difficultyCode) {
    q.set('difficultyCode', params.difficultyCode);
  }
  if (params.limit != null) {
    q.set('limit', String(params.limit));
  }
  return requestJson('GET', apiUrl(`${HUB}/rankings?${q.toString()}`));
}

/**
 * @param {{ username: string; deviceId: string }} payload
 * @returns {Promise<{ user: object; systemSetting: object; wallet: object; inventory: object[] }>}
 */
export function login(payload) {
  return requestJson('POST', apiUrl(`${HUB}/auth/login`), payload);
}

/**
 * @param {object} payload
 * @returns {Promise<object>}
 */
export function createUser(payload) {
  return requestJson('POST', apiUrl(`${HUB}/users/`), payload);
}

/**
 * @param {string} userId
 * @returns {Promise<object>}
 */
export function getUser(userId) {
  return requestJson('GET', apiUrl(`${HUB}/users/${encodeURIComponent(userId)}`));
}

/**
 * @param {string} userId
 * @param {object} payload
 * @returns {Promise<object>}
 */
export function updateUserNickname(userId, payload) {
  return requestJson('PUT', apiUrl(`${HUB}/users/${encodeURIComponent(userId)}/nickname`), payload);
}

/**
 * @param {string} userId
 * @param {object} payload
 * @returns {Promise<object>}
 */
export function bindUserDevice(userId, payload) {
  return requestJson('POST', apiUrl(`${HUB}/users/${encodeURIComponent(userId)}/devices`), payload);
}

/**
 * @param {string} userId
 * @returns {Promise<object>}
 */
export function getUserSystemSetting(userId) {
  return requestJson('GET', apiUrl(`${HUB}/users/${encodeURIComponent(userId)}/system-setting`));
}

/**
 * @param {string} userId
 * @param {object} payload
 * @returns {Promise<object>}
 */
export function updateUserSystemSetting(userId, payload) {
  return requestJson('PUT', apiUrl(`${HUB}/users/${encodeURIComponent(userId)}/system-setting`), payload);
}

/**
 * @param {string} userId
 * @param {string} gameCode
 * @returns {Promise<object>}
 */
export function getUserGameSetting(userId, gameCode) {
  return requestJson(
    'GET',
    apiUrl(`${HUB}/users/${encodeURIComponent(userId)}/games/${encodeURIComponent(gameCode)}/setting`)
  );
}

/**
 * @param {string} userId
 * @param {string} gameCode
 * @param {object} payload
 * @returns {Promise<object>}
 */
export function updateUserGameSetting(userId, gameCode, payload) {
  return requestJson(
    'PUT',
    apiUrl(`${HUB}/users/${encodeURIComponent(userId)}/games/${encodeURIComponent(gameCode)}/setting`),
    payload
  );
}

/**
 * @param {string} userId
 * @returns {Promise<object>}
 */
export function getWallet(userId) {
  return requestJson('GET', apiUrl(`${HUB}/users/${encodeURIComponent(userId)}/wallet`));
}

/**
 * @param {string} userId
 * @param {{ pageNum?: number; pageSize?: number }} [params]
 * @returns {Promise<object>}
 */
export function getWalletLedgers(userId, params = {}) {
  const q = new URLSearchParams();
  if (params.pageNum != null) {
    q.set('pageNum', String(params.pageNum));
  }
  if (params.pageSize != null) {
    q.set('pageSize', String(params.pageSize));
  }
  const qs = q.toString();
  return requestJson(
    'GET',
    apiUrl(`${HUB}/users/${encodeURIComponent(userId)}/wallet/ledgers${qs ? `?${qs}` : ''}`)
  );
}

/**
 * @param {string} userId
 * @param {{ gameCode?: string }} [params]
 * @returns {Promise<object>}
 */
export function getInventory(userId, params = {}) {
  const q = new URLSearchParams();
  if (params.gameCode) {
    q.set('gameCode', params.gameCode);
  }
  const qs = q.toString();
  return requestJson(
    'GET',
    apiUrl(`${HUB}/users/${encodeURIComponent(userId)}/inventory${qs ? `?${qs}` : ''}`)
  );
}

/**
 * @param {string} userId
 * @param {{ gameCode?: string; propCode?: string; pageNum?: number; pageSize?: number }} [params]
 * @returns {Promise<object>}
 */
export function getPropUsageRecords(userId, params = {}) {
  const q = new URLSearchParams();
  if (params.gameCode) {
    q.set('gameCode', params.gameCode);
  }
  if (params.propCode) {
    q.set('propCode', params.propCode);
  }
  if (params.pageNum != null) {
    q.set('pageNum', String(params.pageNum));
  }
  if (params.pageSize != null) {
    q.set('pageSize', String(params.pageSize));
  }
  const qs = q.toString();
  return requestJson(
    'GET',
    apiUrl(`${HUB}/users/${encodeURIComponent(userId)}/inventory/usage-records${qs ? `?${qs}` : ''}`)
  );
}

/**
 * @param {object} payload
 * @returns {Promise<object>}
 */
export function purchaseProp(payload) {
  return requestJson('POST', apiUrl(`${HUB}/purchases`), payload);
}

/**
 * @param {string} userId
 * @param {{ gameCode?: string; propCode?: string; pageNum?: number; pageSize?: number }} [params]
 * @returns {Promise<object>}
 */
export function getPurchases(userId, params = {}) {
  const q = new URLSearchParams();
  if (params.gameCode) {
    q.set('gameCode', params.gameCode);
  }
  if (params.propCode) {
    q.set('propCode', params.propCode);
  }
  if (params.pageNum != null) {
    q.set('pageNum', String(params.pageNum));
  }
  if (params.pageSize != null) {
    q.set('pageSize', String(params.pageSize));
  }
  const qs = q.toString();
  return requestJson(
    'GET',
    apiUrl(`${HUB}/users/${encodeURIComponent(userId)}/purchases${qs ? `?${qs}` : ''}`)
  );
}

/**
 * @param {string} userId
 * @param {{ gameCode?: string; mode?: string; result?: string; difficultyCode?: string; pageNum?: number; pageSize?: number }} [params]
 * @returns {Promise<object>}
 */
export function getMatches(userId, params = {}) {
  const q = new URLSearchParams();
  if (params.gameCode) {
    q.set('gameCode', params.gameCode);
  }
  if (params.mode) {
    q.set('mode', params.mode);
  }
  if (params.result) {
    q.set('result', params.result);
  }
  if (params.difficultyCode) {
    q.set('difficultyCode', params.difficultyCode);
  }
  if (params.pageNum != null) {
    q.set('pageNum', String(params.pageNum));
  }
  if (params.pageSize != null) {
    q.set('pageSize', String(params.pageSize));
  }
  const qs = q.toString();
  return requestJson(
    'GET',
    apiUrl(`${HUB}/users/${encodeURIComponent(userId)}/matches${qs ? `?${qs}` : ''}`)
  );
}

/**
 * @param {string} matchId
 * @returns {Promise<object>}
 */
export function getMatch(matchId) {
  return requestJson('GET', apiUrl(`${HUB}/matches/${encodeURIComponent(matchId)}`));
}

export { requestRawJson };
