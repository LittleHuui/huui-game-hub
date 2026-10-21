import { apiBase } from '../api/request.js';
import { REALTIME_MESSAGE_TYPES } from '../constants/realtimeMessageTypes.js';
import * as onlineAuthService from './onlineAuthService.js';
import { useSettingStore } from '../stores/settingStore.js';
import * as websocketClient from '../utils/websocketClient.js';
import { remoteRepository } from '../repositories/remoteRepository.js';

/**
 * 连接平台实时通道。
 * @param {{ resetAuthFailed?: boolean }} options
 */
export async function connect(options = {}) {
  if (isLocalMode()) {
    websocketClient.disconnect();
    return;
  }
  if (!onlineAuthService.hasCurrentAccessToken()) {
    return;
  }
  websocketClient.connect(createRealtimeUrl, {
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

function buildRealtimeUrl(ticket) {
  const base = apiBase();
  const origin = base || window.location.origin;
  const url = new URL('/ws/game-hub/realtime', origin);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  url.searchParams.set('ticket', ticket);
  return url.toString();
}

async function createRealtimeUrl() {
  const ticketData = await remoteRepository.issueRealtimeTicket();
  if (!ticketData?.ticket) {
    return '';
  }
  return buildRealtimeUrl(ticketData.ticket);
}

function canConnectRealtime() {
  return !isLocalMode() && onlineAuthService.hasCurrentAccessToken();
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

if (typeof window !== 'undefined') {
  window.addEventListener('game-hub-online-auth-failed', () => {
    disconnect({ manual: true });
  });
  window.addEventListener('game-hub-realtime-auth-failed', () => {
    onlineAuthService.handleAuthenticationFailure();
  });
}
