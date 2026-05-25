import { REALTIME_MESSAGE_TYPES } from '../constants/realtimeMessageTypes.js';

const RECONNECT_INITIAL_DELAY_MS = 1000;
const RECONNECT_MAX_DELAY_MS = 30000;
const RECONNECT_MAX_ATTEMPTS = 6;
const HEARTBEAT_INTERVAL_MS = 60000;
const CLOSE_CODE_POLICY_VIOLATION = 1008;

let socket = null;
let socketUrl = '';
let reconnectTimer = null;
let heartbeatTimer = null;
let manualClose = false;
let authFailed = false;
let reconnectDelayMs = RECONNECT_INITIAL_DELAY_MS;
let reconnectAttempts = 0;
let shouldReconnect = null;
const handlers = new Map();

/**
 * 连接 WebSocket。
 * @param {string} url
 * @param {{ resetAuthFailed?: boolean; shouldReconnect?: () => boolean }} options
 */
export function connect(url, options = {}) {
  if (!url) {
    return;
  }
  if (options.resetAuthFailed) {
    authFailed = false;
    resetReconnectBackoff();
  }
  if (typeof options.shouldReconnect === 'function') {
    shouldReconnect = options.shouldReconnect;
  }
  if (authFailed) {
    return;
  }
  socketUrl = url;
  manualClose = false;
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }
  socket = new WebSocket(url);
  socket.onopen = () => {
    clearReconnectTimer();
    resetReconnectBackoff();
    startHeartbeat();
  };
  socket.onmessage = (event) => {
    dispatch(event.data);
  };
  socket.onclose = (event) => {
    stopHeartbeat();
    socket = null;
    if (event.code === CLOSE_CODE_POLICY_VIOLATION) {
      authFailed = true;
      clearReconnectTimer();
      return;
    }
    if (!manualClose && canAutoReconnect()) {
      scheduleReconnect();
    }
  };
  socket.onerror = () => {
    if (socket) {
      socket.close();
    }
  };
}

/**
 * 断开 WebSocket。
 */
export function disconnect() {
  manualClose = true;
  clearReconnectTimer();
  stopHeartbeat();
  if (socket) {
    socket.close();
    socket = null;
  }
}

/**
 * 清理身份失败状态，允许后续主动重连。
 */
export function clearAuthFailure() {
  authFailed = false;
  resetReconnectBackoff();
}

/**
 * 发送消息。
 * @param {object} message
 * @returns {boolean}
 */
export function send(message) {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    return false;
  }
  socket.send(JSON.stringify(message));
  return true;
}

/**
 * 监听指定消息类型。
 * @param {string} type
 * @param {(message: object) => void} handler
 */
export function on(type, handler) {
  if (!handlers.has(type)) {
    handlers.set(type, new Set());
  }
  handlers.get(type).add(handler);
}

/**
 * 移除指定消息类型监听。
 * @param {string} type
 * @param {(message: object) => void} handler
 */
export function off(type, handler) {
  const set = handlers.get(type);
  if (!set) {
    return;
  }
  set.delete(handler);
  if (set.size === 0) {
    handlers.delete(type);
  }
}

/**
 * 安排断线重连。
 */
export function scheduleReconnect() {
  if (reconnectTimer !== null || !socketUrl || !canAutoReconnect()) {
    return;
  }
  const delay = reconnectDelayMs;
  reconnectDelayMs = Math.min(reconnectDelayMs * 2, RECONNECT_MAX_DELAY_MS);
  reconnectAttempts += 1;
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null;
    connect(socketUrl);
  }, delay);
}

/**
 * @deprecated 使用 scheduleReconnect。
 */
export function reconnect() {
  scheduleReconnect();
}

function dispatch(raw) {
  let message = null;
  try {
    message = JSON.parse(raw);
  } catch {
    return;
  }
  const set = handlers.get(message.type);
  if (!set) {
    return;
  }
  for (const handler of set) {
    handler(message);
  }
}

function startHeartbeat() {
  stopHeartbeat();
  heartbeatTimer = window.setInterval(() => {
    send({
      type: REALTIME_MESSAGE_TYPES.ONLINE_PING,
      requestId: createRequestId(),
      payload: {},
      timestamp: Date.now()
    });
  }, HEARTBEAT_INTERVAL_MS);
}

function stopHeartbeat() {
  if (heartbeatTimer === null) {
    return;
  }
  window.clearInterval(heartbeatTimer);
  heartbeatTimer = null;
}

function clearReconnectTimer() {
  if (reconnectTimer === null) {
    return;
  }
  window.clearTimeout(reconnectTimer);
  reconnectTimer = null;
}

function canAutoReconnect() {
  if (manualClose || authFailed) {
    return false;
  }
  if (reconnectAttempts >= RECONNECT_MAX_ATTEMPTS) {
    return false;
  }
  if (typeof shouldReconnect === 'function' && !shouldReconnect()) {
    return false;
  }
  return true;
}

function resetReconnectBackoff() {
  reconnectDelayMs = RECONNECT_INITIAL_DELAY_MS;
  reconnectAttempts = 0;
}

function createRequestId() {
  if (window.crypto && typeof window.crypto.randomUUID === 'function') {
    return window.crypto.randomUUID();
  }
  return `req_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}
