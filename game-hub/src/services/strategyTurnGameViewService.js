import { useStrategyTurnGameViewStore } from '../stores/strategyTurnGameViewStore.js';
import * as strategyTurnEventQueueService from './strategyTurnEventQueueService.js';

/** @type {string} */
let activeRoomId = '';

/** @type {number} */
let currentVersion = 0;

/** @type {number} */
let pendingVersion = 0;

/** @type {number} */
let processingVersion = 0;

/** @type {object|null} */
let displayedView = null;

/** @type {object|null} */
let pendingFinalView = null;

/** @type {object|null} */
let confirmedView = null;

/** @type {string} */
let lastAnimationHint = '';

/** @type {object[]} */
let lastAcceptedFrameEvents = [];

/** @type {Set<(snapshot: object) => void>} */
const listeners = new Set();

/**
 * 清理待播放版本与最终视图，避免 busy 永久为 true。
 */
function clearPendingPlaybackState() {
  pendingVersion = 0;
  processingVersion = 0;
  pendingFinalView = null;
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
    publicState: view.publicState,
    privateState: view.privateState,
    legalActions: view.legalActions,
    frameEvents: lastAcceptedFrameEvents,
    animationHint: lastAnimationHint,
    playbackBusy: isGameViewPlaybackBusy()
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
    version: currentVersion,
    viewerPlayerId: '',
    currentPlayerId: '',
    isGameOver: false,
    publicState: {},
    privateState: {},
    legalActions: [],
    frameEvents: [],
    animationHint: lastAnimationHint,
    playbackBusy: isGameViewPlaybackBusy()
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
 * 重置播放态与版本（保留 activeRoomId）。
 */
function resetGameViewPlayback() {
  currentVersion = 0;
  clearPendingPlaybackState();
  displayedView = null;
  confirmedView = null;
  lastAnimationHint = '';
  lastAcceptedFrameEvents = [];
  strategyTurnEventQueueService.invalidateEventPlayback();
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
  strategyTurnEventQueueService.invalidateEventPlayback();
  currentVersion = 0;
  clearPendingPlaybackState();
  displayedView = null;
  confirmedView = null;
  lastAnimationHint = '';
  lastAcceptedFrameEvents = [];
  activeRoomId = normalized;
  notifyListeners();
}

/**
 * 接收服务端 GameView；若 version 未推进或已在播放则忽略。
 * @param {object} incoming
 * @returns {boolean} 是否已接受并进入播放/展示流程
 */
export function acceptGameView(incoming) {
  if (!incoming || typeof incoming !== 'object') {
    return false;
  }
  const roomId = String(incoming.roomId || '').trim();
  if (roomId) {
    if (activeRoomId && roomId !== activeRoomId) {
      return false;
    }
    if (!activeRoomId) {
      activeRoomId = roomId;
    }
  }
  const version = Number(incoming.version);
  if (!Number.isFinite(version) || version <= currentVersion) {
    return false;
  }
  if (version === pendingVersion || version === processingVersion) {
    return false;
  }

  const events = Array.isArray(incoming.events) ? incoming.events : [];
  lastAcceptedFrameEvents = events;
  const finalView = {
    roomId: roomId || activeRoomId,
    gameCode: String(incoming.gameCode || '').trim(),
    phase: String(incoming.phase || '').trim(),
    version,
    viewerPlayerId: incoming.viewerPlayerId,
    currentPlayerId: incoming.currentPlayerId,
    isGameOver: Boolean(incoming.isGameOver),
    publicState: incoming.publicState,
    privateState: incoming.privateState,
    legalActions: incoming.legalActions,
    events
  };

  const playbackEvents = strategyTurnEventQueueService.filterPlaybackEvents(events);
  if (playbackEvents.length === 0) {
    currentVersion = version;
    clearPendingPlaybackState();
    displayedView = finalView;
    confirmedView = finalView;
    lastAnimationHint = '';
    notifyListeners();
    return true;
  }

  pendingVersion = version;
  pendingFinalView = finalView;
  processingVersion = version;
  const playbackGeneration = strategyTurnEventQueueService.getPlaybackGeneration();
  strategyTurnEventQueueService.enqueueEventPlayback({
    generation: playbackGeneration,
    events,
    onEvent: (event) => {
      if (!strategyTurnEventQueueService.isPlaybackGenerationValid(playbackGeneration)) {
        return;
      }
      lastAnimationHint = String(event?.eventType || '').trim();
      notifyListeners();
    },
    onComplete: () => {
      if (!strategyTurnEventQueueService.isPlaybackGenerationValid(playbackGeneration)) {
        clearPendingPlaybackState();
        notifyListeners();
        return;
      }
      if (pendingVersion <= currentVersion) {
        clearPendingPlaybackState();
        notifyListeners();
        return;
      }
      currentVersion = pendingVersion;
      const finalView = pendingFinalView;
      clearPendingPlaybackState();
      displayedView = finalView;
      confirmedView = finalView;
      lastAnimationHint = '';
      notifyListeners();
    }
  });
  notifyListeners();
  return true;
}

/**
 * 重置本地 GameView 状态（离开房间等场景）。
 */
export function resetGameViewState() {
  activeRoomId = '';
  resetGameViewPlayback();
}

/**
 * 当前已确认的 GameView 版本号（事件播放完成前不推进）。
 * @returns {number}
 */
export function getCurrentGameViewVersion() {
  if (confirmedView && Number.isFinite(Number(confirmedView.version))) {
    return Number(confirmedView.version);
  }
  return currentVersion;
}

/**
 * 事件播放或待覆盖最终视图期间为忙碌态。
 * @returns {boolean}
 */
export function isGameViewPlaybackBusy() {
  return (
    strategyTurnEventQueueService.isEventPlaybackBusy() ||
    pendingVersion > currentVersion
  );
}

/**
 * 读取当前绑定的房间 ID。
 * @returns {string}
 */
export function getActiveRoomId() {
  return activeRoomId;
}
