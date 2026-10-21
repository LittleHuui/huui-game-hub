import * as onlineApi from '../api/onlineApi.js';
import * as onlineAuthService from './onlineAuthService.js';
import * as toastService from './toastService.js';
import { canFetchRemote } from './remoteGate.js';

const ONLINE_REFRESH_INTERVAL_MS = 5 * 60 * 1000;

let refreshTimer = null;
let onlineUsers = [];

/**
 * 标记当前用户在线。
 * @returns {Promise<object|null>}
 */
export async function markOnline() {
  if (!canFetchRemote()) {
    return null;
  }
  if (!onlineAuthService.hasCurrentAccessToken()) {
    return null;
  }
  return onlineApi.updateOnlineStatus('online');
}

/**
 * 标记当前用户离线。
 * @returns {Promise<void>}
 */
export async function markOffline() {
  stopOnlineRefresh();
  if (!canFetchRemote()) {
    return;
  }
  if (!onlineAuthService.hasCurrentAccessToken()) {
    return;
  }
  try {
    await onlineApi.updateOnlineStatus('offline');
  } catch {
    // 离线标记失败时由 Redis TTL 兜底。
  }
}

/**
 * 启动在线状态定时刷新。
 */
export function startOnlineRefresh() {
  if (!canFetchRemote()) {
    return;
  }
  if (refreshTimer !== null) {
    return;
  }
  refreshTimer = window.setInterval(() => {
    markOnline().catch(() => {});
  }, ONLINE_REFRESH_INTERVAL_MS);
}

/**
 * 停止在线状态定时刷新。
 */
export function stopOnlineRefresh() {
  if (refreshTimer === null) {
    return;
  }
  window.clearInterval(refreshTimer);
  refreshTimer = null;
}

/**
 * 加载在线用户列表。
 * @param {{ silent?: boolean, throwOnError?: boolean }} options
 * @returns {Promise<object[]>}
 */
export async function loadOnlineUsers(options = {}) {
  const { silent = false, throwOnError = false } = options;
  if (!canFetchRemote()) {
    onlineUsers = [];
    return [];
  }
  try {
    const data = await onlineApi.getOnlineUsers();
    onlineUsers = Array.isArray(data?.users) ? data.users : [];
    return [...onlineUsers];
  } catch (e) {
    if (!silent) {
      toastService.push(e.message || '在线用户加载失败', 'warning');
    }
    if (throwOnError) {
      throw e;
    }
    return [...onlineUsers];
  }
}

if (typeof window !== 'undefined') {
  window.addEventListener('game-hub-online-auth-failed', () => {
    stopOnlineRefresh();
  });
}
