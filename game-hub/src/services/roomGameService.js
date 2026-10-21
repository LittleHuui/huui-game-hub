import * as roomRepository from '../repositories/roomRepository.js';
import { useRoomStore } from '../stores/roomStore.js';
import { requireServerUserId, assertRoomRemoteAvailable } from './roomAccessService.js';
import { loadRoomDetail, refreshRoomList } from './roomQueryService.js';
import * as strategyTurnGameViewService from './strategyTurnGameViewService.js';
import * as actionIntentService from './strategyTurnActionIntentService.js';
import { createClientId } from '../utils/idService.js';

strategyTurnGameViewService.setAuthoritativeReloadHandler(async (roomId, options = {}) => {
  requireServerUserId();
  return roomRepository.fetchRoomGameView(roomId, options);
});

export function createRoomActionRequestId() {
  return createClientId('room-action');
}

/**
 * 启动房间对局，并仅在原上下文仍有效时接纳视图和刷新房间。
 * @param {string} roomId
 * @param {{signal?: AbortSignal}} [options]
 * @returns {Promise<{room: object|null; gameView: object}>}
 */
export async function startRoomGame(roomId, options = {}) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  requireServerUserId();
  strategyTurnGameViewService.setActiveRoom(roomId);
  const isCurrent = strategyTurnGameViewService.captureGameViewContext(roomId, options.signal);
  const gameView = await roomRepository.startRoomGame(roomId);
  if (!isCurrent()) return { room: null, gameView };
  strategyTurnGameViewService.acceptAuthoritativeGameView(gameView);
  const room = await loadRoomDetail(roomId, options);
  if (!isCurrent()) return { room, gameView };
  const gameCode = room?.gameCode || useRoomStore().activeGameCode;
  if (gameCode) {
    try {
      await refreshRoomList(gameCode, options);
    } catch {
      // 列表刷新失败不阻断开局
    }
  }
  return { room, gameView };
}

/**
 * 查询完整视图；切房、重置和取消后的响应不再写入当前展示状态。
 * @param {string} roomId
 * @param {{signal?: AbortSignal}} [options]
 * @returns {Promise<object>}
 */
export async function loadRoomGameView(roomId, options = {}) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  strategyTurnGameViewService.setActiveRoom(roomId);
  const isCurrent = strategyTurnGameViewService.captureGameViewContext(roomId, options.signal);
  const gameView = await roomRepository.fetchRoomGameView(roomId, options);
  if (isCurrent()) strategyTurnGameViewService.acceptAuthoritativeGameView(gameView);
  return gameView;
}

/**
 * 通过幂等动作意图提交已声明的交互，并将响应限制在原房间上下文。
 * @param {string} roomId
 * @param {{submission: object; baseVersion: number; requestId?: string; signal?: AbortSignal}} body
 * @returns {Promise<object>}
 */
export async function applyRoomGameAction(roomId, body) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  const submission = body?.submission;
  if (!submission || typeof submission !== 'object') {
    throw new Error('缺少 submission');
  }
  const actionType = String(submission.actionType || '').trim();
  if (!actionType) {
    throw new Error('缺少 actionType');
  }
  const input = submission.input;
  if (!input || typeof input !== 'object' || !String(input.kind || '').trim()) {
    throw new Error('缺少 submission.input.kind');
  }
  requireServerUserId();
  const baseVersion = Number(body?.baseVersion);
  if (!Number.isFinite(baseVersion) || baseVersion < 0) {
    throw new Error('缺少 baseVersion');
  }
  const isCurrent = strategyTurnGameViewService.captureGameViewContext(roomId, body?.signal);
  const gameView = await actionIntentService.executeActionIntent({
    roomId,
    baseVersion,
    submission,
    requestId: body?.requestId,
    send: (intent) =>
      roomRepository.applyRoomGameAction(
        roomId,
        {
          baseVersion: intent.baseVersion,
          requestId: intent.requestId,
          submission: intent.submission
        },
        { signal: body?.signal }
      )
  });
  if (isCurrent()) strategyTurnGameViewService.acceptCommitGameView(gameView, baseVersion);
  return gameView;
}

export async function previewRoomGameAction(roomId, body) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  const submission = body?.submission;
  if (!submission || typeof submission !== 'object') {
    throw new Error('缺少 submission');
  }
  requireServerUserId();
  const baseVersion =
    body?.baseVersion != null
      ? Number(body.baseVersion)
      : strategyTurnGameViewService.getCurrentGameViewVersion();
  if (!Number.isFinite(baseVersion) || baseVersion < 0) {
    throw new Error('缺少 baseVersion');
  }
  return roomRepository.previewRoomGameAction(
    roomId,
    { baseVersion, submission },
    { signal: body?.signal }
  );
}

export async function fetchRoomActionSuggestions(roomId, body) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  const actionType = String(body?.actionType || '').trim();
  if (!actionType) {
    throw new Error('缺少 actionType');
  }
  requireServerUserId();
  const baseVersion =
    body?.baseVersion != null
      ? Number(body.baseVersion)
      : strategyTurnGameViewService.getCurrentGameViewVersion();
  if (!Number.isFinite(baseVersion) || baseVersion < 0) {
    throw new Error('缺少 baseVersion');
  }
  return roomRepository.fetchRoomActionSuggestions(
    roomId,
    {
      baseVersion,
      actionType,
      cursor: body?.cursor != null ? body.cursor : null,
      limit: body?.limit != null ? Number(body.limit) : 1
    },
    { signal: body?.signal }
  );
}

export function resetRoomGameView() {
  actionIntentService.clearActionIntents();
  strategyTurnGameViewService.resetGameViewState();
}
