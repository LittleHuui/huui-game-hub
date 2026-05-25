import { nowMs } from '../utils/timeService.js';

/**
 * @param {object} remote
 * @returns {import('../stores/userStore.js').GameUser}
 */
export function mapRemoteUserToLocal(remote) {
  const serverId = remote.serverId || remote.userId || '';
  return {
    clientId: remote.clientId || '',
    serverId,
    userId: serverId,
    username: remote.username || '',
    nickname: remote.nickname || remote.username || '',
    score: 0,
    totalScore: 0,
    autoRevive: false,
    prefs: {},
    createdAt: remote.createdAt ?? nowMs(),
    updatedAt: remote.updatedAt ?? nowMs(),
    serverCreatedAt: remote.createdAt ?? null,
    serverUpdatedAt: remote.updatedAt ?? null,
    syncedAt: nowMs()
  };
}

/**
 * 规范化用户列表字段（原 store.normalizeUsers）。
 * @param {import('../stores/userStore.js').GameUser[]} users
 */
export function normalizeUsersList(users) {
  const now = Date.now();
  for (const u of users) {
    if (u && 'props' in u) {
      delete u.props;
    }
    if (typeof u.autoRevive !== 'boolean') {
      u.autoRevive = false;
    }
    if (!u.prefs) {
      u.prefs = {};
    }
    if (!u.gameSettings || typeof u.gameSettings !== 'object') {
      u.gameSettings = {};
    }
    if (!u.clientId) {
      u.clientId = `u_${u.userId || now}`;
    }
    if (u.createdAt == null) {
      u.createdAt = now;
    }
    if (u.updatedAt == null) {
      u.updatedAt = now;
    }
  }
}
