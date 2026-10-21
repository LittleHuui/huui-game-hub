import { REALTIME_MESSAGE_TYPES } from '../constants/realtimeMessageTypes.js';

const RECONNECT_INITIAL_DELAY_MS = 1000;
const RECONNECT_MAX_DELAY_MS = 30000;
const RECONNECT_MAX_ATTEMPTS = 6;
const HEARTBEAT_INTERVAL_MS = 60000;
const CLOSE_CODE_POLICY_VIOLATION = 1008;
const CLOSE_CODE_AUTH_EXPIRED = 4003;

let socket = null;
let createUrl = null;
let reconnectTimer = null;
let heartbeatTimer = null;
let manualClose = false;
let authFailed = false;
let reconnectDelayMs = RECONNECT_INITIAL_DELAY_MS;
let reconnectAttempts = 0;
let shouldReconnect = null;
let generation = 0;
const handlers = new Map();

/**
 * Connect WebSocket using an async URL factory.
 * @param {() => Promise<string>} urlFactory
 * @param {{ resetAuthFailed?: boolean; shouldReconnect?: () => boolean }} options
 */
export function connect(urlFactory, options = {}) {
  if (typeof urlFactory !== 'function') {
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
  createUrl = urlFactory;
  manualClose = false;
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }
  void openNextConnection();
}

export function disconnect() {
  manualClose = true;
  generation += 1;
  clearReconnectTimer();
  stopHeartbeat();
  if (socket) {
    socket.close();
    socket = null;
  }
}

export function clearAuthFailure() {
  authFailed = false;
  resetReconnectBackoff();
}

export function send(message) {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    return false;
  }
  socket.send(JSON.stringify(message));
  return true;
}

export function on(type, handler) {
  if (!handlers.has(type)) {
    handlers.set(type, new Set());
  }
  handlers.get(type).add(handler);
}

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

export function scheduleReconnect() {
  if (reconnectTimer !== null || !createUrl || !canAutoReconnect()) {
    return;
  }
  const delay = reconnectDelayMs;
  reconnectDelayMs = Math.min(reconnectDelayMs * 2, RECONNECT_MAX_DELAY_MS);
  reconnectAttempts += 1;
  const scheduledGeneration = generation;
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null;
    if (scheduledGeneration !== generation || !canAutoReconnect()) {
      return;
    }
    void openNextConnection();
  }, delay);
}

async function openNextConnection() {
  if (!createUrl || authFailed || manualClose) {
    return;
  }
  const myGeneration = generation + 1;
  generation = myGeneration;
  let url = '';
  try {
    url = await createUrl();
  } catch {
    if (myGeneration === generation && canAutoReconnect()) {
      scheduleReconnect();
    }
    return;
  }
  if (myGeneration !== generation || manualClose || authFailed || !url) {
    return;
  }
  const nextSocket = new WebSocket(url);
  socket = nextSocket;
  nextSocket.onopen = () => {
    if (myGeneration !== generation || socket !== nextSocket) {
      nextSocket.close();
      return;
    }
    clearReconnectTimer();
    resetReconnectBackoff();
    startHeartbeat();
  };
  nextSocket.onmessage = (event) => {
    if (myGeneration === generation && socket === nextSocket) {
      dispatch(event.data);
    }
  };
  nextSocket.onclose = (event) => {
    if (myGeneration !== generation || socket !== nextSocket) {
      return;
    }
    stopHeartbeat();
    socket = null;
    if (isAuthenticationCloseCode(event.code)) {
      authFailed = true;
      clearReconnectTimer();
      notifyRealtimeAuthenticationFailure();
      return;
    }
    if (!manualClose && canAutoReconnect()) {
      scheduleReconnect();
    }
  };
  nextSocket.onerror = () => {
    if (myGeneration === generation && socket === nextSocket) {
      nextSocket.close();
    }
  };
}

/**
 * @param {number} closeCode
 * @returns {boolean}
 */
function isAuthenticationCloseCode(closeCode) {
  return closeCode === CLOSE_CODE_POLICY_VIOLATION || closeCode === CLOSE_CODE_AUTH_EXPIRED;
}

/**
 * 由实时服务转接到与 HTTP 相同的认证失效流程。
 */
function notifyRealtimeAuthenticationFailure() {
  if (typeof window === 'undefined') {
    return;
  }
  window.dispatchEvent(new window.CustomEvent('game-hub-realtime-auth-failed'));
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
