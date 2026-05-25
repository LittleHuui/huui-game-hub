import { apiUrl, requestJson } from './request.js';

const HUB = '/api/game-hub';

/**
 * 查询在线用户。
 * @returns {Promise<{ users: object[] }>}
 */
export function getOnlineUsers() {
  return requestJson('GET', apiUrl(`${HUB}/online/users`));
}

/**
 * 修改当前用户在线状态。
 * @param {'online'|'away'|'busy'|'offline'} status
 * @param {string} serviceId
 * @returns {Promise<object>}
 */
export function updateOnlineStatus(status, serviceId) {
  return requestJson('POST', apiUrl(`${HUB}/online/status`), { status }, 8000, {
    'X-Game-Hub-User-Id': serviceId
  });
}
