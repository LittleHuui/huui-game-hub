import * as onlineAuthService from './onlineAuthService.js';
import { canFetchRemote } from './remoteGate.js';
import { useSettingStore } from '../stores/settingStore.js';

/**
 * 标识当前成员查询所属的身份、服务地址与数据模式；离线时不存在有效查询上下文。
 * @returns {string} 仅用于隔离房间快照，不代表服务端成员资格或认证凭据。
 */
export function getRoomMembershipScope() {
  const playerId = getCurrentPlayerId();
  if (!canFetchRemote() || !playerId) return '';
  return JSON.stringify([playerId, import.meta.env.VITE_API_BASE || '', useSettingStore().settings.repositoryMode]);
}

export function requireServerUserId() {
  const serviceId = onlineAuthService.resolveCurrentServerUserId();
  if (!serviceId) {
    throw new Error('未登录，无法操作房间');
  }
  return serviceId;
}

export function getCurrentPlayerId() {
  return onlineAuthService.resolveCurrentServerUserId() || '';
}

export function assertRoomRemoteAvailable() {
  if (!canFetchRemote()) {
    throw new Error('当前无法访问房间服务');
  }
}
