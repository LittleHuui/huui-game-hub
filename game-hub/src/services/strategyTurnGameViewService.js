import { createSnapshotReload } from './createSnapshotReload.js';
import { useStrategyTurnGameViewStore } from '../stores/strategyTurnGameViewStore.js';

/** @type {string} */
let activeRoomId = '';

/** 每次切房或重置都失效旧上下文，即使之后重新进入同一房间。 */
let roomContextGeneration = 0;

/** @type {number} */
let highestAcceptedVersion = 0;

/** @type {object|null} */
let displayedView = null;

/** @type {object[]} */
let displayFrameEvents = [];

/** @type {null|((roomId: string, options?: {signal?: AbortSignal}) => Promise<object>)} */
let authoritativeReloadHandler = null;

export const GAME_VIEW_SOURCES = Object.freeze({
  PUSH_INCREMENTAL: 'PUSH_INCREMENTAL',
  HTTP_AUTHORITATIVE: 'HTTP_AUTHORITATIVE',
  COMMIT_RESPONSE: 'COMMIT_RESPONSE'
});

export const GAME_VIEW_SYNC_STATUS = Object.freeze({
  IDLE: 'IDLE',
  RELOADING: 'RELOADING',
  READY: 'READY',
  FAILED: 'FAILED'
});

const RELOAD_BACKOFF_MS = [0, 250, 750];
let syncStatus = GAME_VIEW_SYNC_STATUS.IDLE;
let syncError = '';
let requiredReloadVersion = 0;
const handledProtocolErrors = new Set();

export const GAME_VIEW_ACCEPT_REASONS = Object.freeze({
  ACCEPTED: 'ACCEPTED',
  STALE: 'STALE',
  DUPLICATE: 'DUPLICATE',
  ROOM_MISMATCH: 'ROOM_MISMATCH',
  VERSION_GAP: 'VERSION_GAP',
  MAPPING_ERROR: 'MAPPING_ERROR'
});

/** @type {Set<(snapshot: object) => void>} */
const listeners = new Set();

/**
 * 构造 GameView 接收结果。
 * @param {boolean} accepted
 * @param {string} reason
 * @param {number} incomingVersion
 * @returns {{accepted: boolean; reason: string; incomingVersion: number; currentVersion: number}}
 */
function buildAcceptResult(
  accepted,
  reason,
  incomingVersion,
  acceptedVersion = highestAcceptedVersion
) {
  return {
    accepted,
    reason,
    incomingVersion,
    currentVersion: acceptedVersion
  };
}

/**
 * 注册版本断层时使用的权威快照加载器。
 * @param {((roomId: string, options?: {signal?: AbortSignal}) => Promise<object>)|null} handler
 */
export function setAuthoritativeReloadHandler(handler) {
  authoritativeReloadHandler = typeof handler === 'function' ? handler : null;
}

const authoritativeReload = createSnapshotReload({
  load: (roomId, options) => authoritativeReloadHandler(roomId, options),
  readVersion: () => highestAcceptedVersion,
  apply: (view) => {
    if (!view || view.roomId !== activeRoomId) throw new Error('权威视图房间不匹配');
    const result = acceptAuthoritativeGameView(view);
    if (result.reason === GAME_VIEW_ACCEPT_REASONS.MAPPING_ERROR) {
      throw new Error('权威视图格式错误');
    }
    return highestAcceptedVersion;
  },
  onStart: () => {
    syncStatus = GAME_VIEW_SYNC_STATUS.RELOADING;
    syncError = '';
    notifyListeners();
  },
  onReady: () => {
    requiredReloadVersion = 0;
    syncStatus = GAME_VIEW_SYNC_STATUS.READY;
    syncError = '';
    notifyListeners();
  },
  onFailure: (error) => {
    syncStatus = GAME_VIEW_SYNC_STATUS.FAILED;
    syncError = error?.message || '权威视图重拉失败';
    notifyListeners();
  },
  backoffMs: RELOAD_BACKOFF_MS
});

/**
 * 同一房间的连续缺口共用一个恢复请求。
 * @param {string} [roomId]
 * @param {number} [minimumVersion]
 * @returns {Promise<object|null>}
 */
export function requestAuthoritativeReload(roomId = activeRoomId, minimumVersion = highestAcceptedVersion) {
  if (!roomId || roomId !== activeRoomId || !authoritativeReloadHandler) {
    return Promise.resolve(null);
  }
  requiredReloadVersion = Math.max(requiredReloadVersion, minimumVersion);
  return authoritativeReload.request(roomId, requiredReloadVersion);
}

/** 手动重试时结束旧请求及其等待者。 @returns {Promise<object|null>} */
export function retryAuthoritativeReload() {
  const minimumVersion = Math.max(highestAcceptedVersion, requiredReloadVersion);
  authoritativeReload.cancel();
  return requestAuthoritativeReload(activeRoomId, minimumVersion);
}

/**
 * 记录推送协议错误，并对同一坏消息仅触发一次恢复。
 * @param {string} roomId
 * @param {unknown} error
 * @param {string} [fingerprint]
 * @returns {Promise<object|null>}
 */
export function handlePushProtocolError(roomId, error, fingerprint = '') {
  const normalized = String(roomId || '').trim();
  if (!normalized || normalized !== activeRoomId) {
    return Promise.resolve(null);
  }
  const key = `${normalized}:${fingerprint || error?.message || 'unknown'}`;
  if (handledProtocolErrors.has(key)) {
    return Promise.resolve(null);
  }
  handledProtocolErrors.add(key);
  console.error('GameView push protocol error', error);
  syncError = error?.message || 'GameView 推送协议错误';
  notifyListeners();
  return requestAuthoritativeReload(normalized);
}

/**
 * 通知订阅方展示态已更新。
 */
function notifyListeners() {
  const snapshot = getDisplaySnapshot();
  useStrategyTurnGameViewStore().setDisplaySnapshot(snapshot);
  listeners.forEach((listener) => {
    listener(snapshot);
  });
}

/**
 * 将 GameView 转为展示用快照。
 * @param {object} view
 * @returns {object}
 */
function toDisplaySnapshot(view) {
  return {
    roomId: view.roomId,
    gameCode: view.gameCode,
    phase: view.phase,
    version: view.version,
    viewerPlayerId: view.viewerPlayerId,
    currentPlayerId: view.currentPlayerId,
    isGameOver: view.isGameOver,
    terminalMetadata: view.terminalMetadata || null,
    publicState: view.publicState,
    privateState: view.privateState,
    actionOffers: view.actionOffers,
    frameEvents: displayFrameEvents,
    playbackBusy: false,
    syncStatus,
    syncError
  };
}

/**
 * 构建空展示快照。
 * @returns {object}
 */
function buildEmptySnapshot() {
  return {
    roomId: activeRoomId,
    gameCode: '',
    phase: '',
    version: highestAcceptedVersion,
    viewerPlayerId: '',
    currentPlayerId: '',
    isGameOver: false,
    terminalMetadata: null,
    publicState: {},
    privateState: {},
    actionOffers: [],
    frameEvents: [],
    playbackBusy: false,
    syncStatus,
    syncError
  };
}

/**
 * 读取当前展示快照。
 * @returns {object}
 */
export function getDisplaySnapshot() {
  if (!displayedView) {
    return buildEmptySnapshot();
  }
  return toDisplaySnapshot(displayedView);
}

/**
 * 订阅展示态变更。
 * @param {(snapshot: object) => void} listener
 * @returns {() => void}
 */
export function subscribeDisplaySnapshot(listener) {
  if (typeof listener !== 'function') {
    return () => {};
  }
  listeners.add(listener);
  listener(getDisplaySnapshot());
  return () => {
    listeners.delete(listener);
  };
}

/**
 * 从入站 GameView 构建最终视图对象。
 * @param {object} incoming
 * @param {number} version
 * @returns {object}
 */
function buildFinalView(incoming, version) {
  const roomId = String(incoming.roomId || activeRoomId || '').trim();
  const events = Array.isArray(incoming.events) ? incoming.events : [];
  return {
    roomId,
    gameCode: String(incoming.gameCode || '').trim(),
    phase: String(incoming.phase || '').trim(),
    version,
    viewerPlayerId: incoming.viewerPlayerId,
    currentPlayerId: incoming.currentPlayerId,
    isGameOver: Boolean(incoming.isGameOver),
    terminalMetadata:
      incoming.terminalMetadata && typeof incoming.terminalMetadata === 'object'
        ? { ...incoming.terminalMetadata }
        : null,
    publicState: incoming.publicState,
    privateState: incoming.privateState,
    actionOffers: incoming.actionOffers,
    events
  };
}

/**
 * 清空当前帧事件，不干扰独立的权威请求生命周期。
 *
 * GameView 的帧事件是给页面派生展示信息的事实，不携带前端动画实现。
 * 不能用服务端的延时字段制造不可见的阻塞状态。
 */
function invalidateGameViewPresentation() {
  displayFrameEvents = [];
}

/**
 * 立即清除当前帧事件展示。
 * @returns {void}
 */
export function cancelGameViewPlayback() {
  invalidateGameViewPresentation();
  notifyListeners();
}

/**
 * 重置播放态与版本（保留 activeRoomId）。
 */
function resetGameViewPlayback() {
  invalidateGameViewPresentation();
  requiredReloadVersion = 0;
  highestAcceptedVersion = 0;
  displayedView = null;
  syncStatus = GAME_VIEW_SYNC_STATUS.IDLE;
  syncError = '';
  notifyListeners();
}

/**
 * 设置当前绑定的房间 ID；切换房间时重置本地 GameView 播放状态。
 * @param {string} roomId
 */
export function setActiveRoom(roomId) {
  const normalized = String(roomId || '').trim();
  if (normalized === activeRoomId) {
    return;
  }
  roomContextGeneration++;
  invalidateGameViewPresentation();
  authoritativeReload.cancel();
  requiredReloadVersion = 0;
  highestAcceptedVersion = 0;
  displayedView = null;
  activeRoomId = normalized;
  syncStatus = GAME_VIEW_SYNC_STATUS.IDLE;
  syncError = '';
  handledProtocolErrors.clear();
  notifyListeners();
}

/**
 * 接收服务端 GameView；立即写入权威展示状态，事件仅作为附加展示。
 * @param {object} incoming
 * @param {{source?: string; baseVersion?: number; authoritative?: boolean}} [options]
 * @returns {{accepted: boolean; reason: string; incomingVersion: number; currentVersion: number}}
 */
export function acceptGameView(incoming, options = {}) {
  const source = options.authoritative
    ? GAME_VIEW_SOURCES.HTTP_AUTHORITATIVE
    : options.source || GAME_VIEW_SOURCES.PUSH_INCREMENTAL;
  if (!incoming || typeof incoming !== 'object') {
    return buildAcceptResult(false, GAME_VIEW_ACCEPT_REASONS.MAPPING_ERROR, 0);
  }
  const roomId = String(incoming.roomId || '').trim();
  if (roomId) {
    if (activeRoomId && roomId !== activeRoomId) {
      return buildAcceptResult(
        false,
        GAME_VIEW_ACCEPT_REASONS.ROOM_MISMATCH,
        Number(incoming.version) || 0
      );
    }
    if (!activeRoomId) {
      activeRoomId = roomId;
    }
  }
  const version = Number(incoming.version);
  if (!Number.isFinite(version)) {
    return buildAcceptResult(false, GAME_VIEW_ACCEPT_REASONS.MAPPING_ERROR, 0);
  }
  if (version < highestAcceptedVersion) {
    return buildAcceptResult(false, GAME_VIEW_ACCEPT_REASONS.STALE, version);
  }
  if (version === highestAcceptedVersion) {
    return buildAcceptResult(false, GAME_VIEW_ACCEPT_REASONS.DUPLICATE, version);
  }

  if (source === GAME_VIEW_SOURCES.HTTP_AUTHORITATIVE) {
    invalidateGameViewPresentation();
    const authoritativeView = buildFinalView(incoming, version);
    highestAcceptedVersion = version;
    displayedView = authoritativeView;
    displayFrameEvents = Array.isArray(incoming.events) ? incoming.events : [];
    syncStatus = version < requiredReloadVersion ? GAME_VIEW_SYNC_STATUS.RELOADING : GAME_VIEW_SYNC_STATUS.READY;
    syncError = '';
    handledProtocolErrors.clear();
    notifyListeners();
    return buildAcceptResult(true, GAME_VIEW_ACCEPT_REASONS.ACCEPTED, version);
  }

  const expectedBase =
    source === GAME_VIEW_SOURCES.COMMIT_RESPONSE
      ? Number(options.baseVersion)
      : highestAcceptedVersion;
  if (expectedBase > 0 && version > expectedBase + 1) {
    if (source === GAME_VIEW_SOURCES.COMMIT_RESPONSE) {
      return acceptGameView(incoming, { source: GAME_VIEW_SOURCES.HTTP_AUTHORITATIVE });
    }
    const previousVersion = highestAcceptedVersion;
    cancelGameViewPlayback();
    void requestAuthoritativeReload(roomId || activeRoomId, version);
    return buildAcceptResult(
      false,
      GAME_VIEW_ACCEPT_REASONS.VERSION_GAP,
      version,
      previousVersion
    );
  }
  highestAcceptedVersion = version;
  const events = Array.isArray(incoming.events) ? incoming.events : [];
  const finalView = buildFinalView(incoming, version);
  displayedView = finalView;
  displayFrameEvents = events;
  syncStatus = version < requiredReloadVersion
    ? GAME_VIEW_SYNC_STATUS.RELOADING
    : GAME_VIEW_SYNC_STATUS.READY;
  syncError = '';
  notifyListeners();

  return buildAcceptResult(true, GAME_VIEW_ACCEPT_REASONS.ACCEPTED, version);
}

/**
 * 接收 WebSocket 增量推送。
 * @param {object} incoming
 * @returns {object}
 */
export function acceptPushGameView(incoming) {
  return acceptGameView(incoming, { source: GAME_VIEW_SOURCES.PUSH_INCREMENTAL });
}

/**
 * 接收 HTTP 权威完整快照。
 * @param {object} incoming
 * @returns {object}
 */
export function acceptAuthoritativeGameView(incoming) {
  return acceptGameView(incoming, { source: GAME_VIEW_SOURCES.HTTP_AUTHORITATIVE });
}

/**
 * 接收动作提交响应。
 * @param {object} incoming
 * @param {number} baseVersion
 * @returns {object}
 */
export function acceptCommitGameView(incoming, baseVersion) {
  return acceptGameView(incoming, {
    source: GAME_VIEW_SOURCES.COMMIT_RESPONSE,
    baseVersion
  });
}

/**
 * 重置本地 GameView 状态（离开房间等场景）。
 */
export function resetGameViewState() {
  roomContextGeneration++;
  authoritativeReload.cancel();
  handledProtocolErrors.clear();
  activeRoomId = '';
  resetGameViewPlayback();
}

/**
 * 当前已接收的权威 GameView 版本号。
 * @returns {number}
 */
export function getCurrentGameViewVersion() {
  return highestAcceptedVersion;
}

/**
 * 读取当前绑定的房间 ID。
 * @returns {string}
 */
export function getActiveRoomId() {
  return activeRoomId;
}

/**
 * 捕获命令所属的 GameView 上下文；清空后迟到的响应不得重新激活旧房间。
 * @param {string} roomId
 * @param {AbortSignal} [signal]
 * @returns {() => boolean}
 */
export function captureGameViewContext(roomId, signal) {
  const generation = roomContextGeneration;
  return () => !signal?.aborted && generation === roomContextGeneration && activeRoomId === roomId;
}
