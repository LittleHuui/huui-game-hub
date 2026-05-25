import { apiBase } from '../api/request.js';
import { REALTIME_MESSAGE_TYPES } from '../constants/realtimeMessageTypes.js';
import * as userRepository from '../repositories/userRepository.js';
import { useSettingStore } from '../stores/settingStore.js';
import * as websocketClient from '../utils/websocketClient.js';

/**
 * 连接平台实时通道。
 * @param {{ resetAuthFailed?: boolean }} options
 */
export function connect(options = {}) {
  if (isLocalMode()) {
    websocketClient.disconnect();
    return;
  }
  const serviceId = userRepository.resolveServerUserId();
  if (!serviceId) {
    return;
  }
  websocketClient.connect(buildRealtimeUrl(serviceId), {
    resetAuthFailed: options.resetAuthFailed === true,
    shouldReconnect: canConnectRealtime
  });
}

/**
 * 断开平台实时通道。
 * @param {{ manual?: boolean }} [_options]
 */
export function disconnect(_options = {}) {
  websocketClient.disconnect();
}

/**
 * 发送平台实时消息。
 * @param {string} type
 * @param {object} [payload]
 * @returns {boolean}
 */
export function send(type, payload = {}) {
  return websocketClient.send({
    type,
    requestId: createRequestId(),
    payload,
    timestamp: Date.now()
  });
}

/**
 * 监听平台实时消息。
 * @param {string} type
 * @param {(message: object) => void} handler
 */
export function on(type, handler) {
  websocketClient.on(type, handler);
}

/**
 * 移除平台实时消息监听。
 * @param {string} type
 * @param {(message: object) => void} handler
 */
export function off(type, handler) {
  websocketClient.off(type, handler);
}

function buildRealtimeUrl(serviceId) {
  const base = apiBase();
  const origin = base || window.location.origin;
  const url = new URL('/ws/game-hub/realtime', origin);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  url.searchParams.set('serviceId', serviceId);
  return url.toString();
}

function canConnectRealtime() {
  return !isLocalMode() && Boolean(userRepository.resolveServerUserId());
}

function isLocalMode() {
  return useSettingStore().settings.repositoryMode === 'local';
}

function createRequestId() {
  if (window.crypto && typeof window.crypto.randomUUID === 'function') {
    return window.crypto.randomUUID();
  }
  return `req_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

export { REALTIME_MESSAGE_TYPES };
